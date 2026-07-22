from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest

from app.config import settings
from app.crypto import decrypt_token, encrypt_token
from app.db import get_connection

from tests.test_auth import _auth_headers, _create_client, _login


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

class MockResponse:
    def __init__(self, json_data: dict, status_code: int = 200):
        self._json = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._json


def _make_client_token(db_client) -> tuple[int, str]:
    """Create a client tenant via super-admin and return (client_id, client_token)."""
    client = db_client.client
    admin_token = _login(client, db_client.super_admin_email, db_client.super_admin_password)
    created = _create_client(client, admin_token, "page-client@test.local", "page-pass")
    client_id = created["id"]
    client_token = _login(client, "page-client@test.local", "page-pass")
    return client_id, client_token


def _seed_page(db_path, tenant_id, page_fb_id, page_name, page_token) -> int:
    """Insert an active page row for tenant_id with an encrypted token; return lastrowid."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO pages (tenant_id, page_fb_id, page_name, access_token_enc, is_active) "
            "VALUES (?, ?, ?, ?, 1)",
            (tenant_id, page_fb_id, page_name, encrypt_token(page_token)),
        )
        page_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return page_id


def _dispatch_httpx_get(url: str, **kwargs) -> MockResponse:
    """Success-path dispatcher for the 3 Graph API GET calls."""
    params = kwargs.get("params", {}) or {}
    if "/oauth/access_token" in url and "fb_exchange_token" in params:
        return MockResponse({"access_token": "long-tok"})
    if "/oauth/access_token" in url:
        return MockResponse({"access_token": "short-tok"})
    if "/me/accounts" in url:
        return MockResponse({
            "data": [
                {"id": "fb-page-1", "name": "Test Page", "access_token": "page-tok"}
            ]
        })
    raise AssertionError(f"unexpected httpx.get URL: {url}")


# ---------------------------------------------------------------------------
# PAGE-01 tests
# ---------------------------------------------------------------------------

def test_oauth_start(db_client):
    """PAGE-01: GET /auth/facebook/start returns 302 redirect to FB dialog with state."""
    client = db_client.client
    _, token = _make_client_token(db_client)

    resp = client.get("/auth/facebook/start", headers=_auth_headers(token), follow_redirects=False)
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith("https://www.facebook.com/v25.0/dialog/oauth?")
    assert "client_id=test-app-id" in location
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fauth%2Ffacebook%2Fcallback" in location
    assert "scope=pages_show_list%2Cpages_manage_metadata%2Cpages_messaging" in location
    assert "response_type=code" in location
    assert "state=" in location

    # Without Bearer header: 401
    resp_no_auth = client.get("/auth/facebook/start", follow_redirects=False)
    assert resp_no_auth.status_code == 401


def test_state_jwt(db_client):
    """PAGE-01: state JWT is verifiable and contains tenant_id, nonce, exp."""
    client = db_client.client
    client_id, token = _make_client_token(db_client)

    resp = client.get("/auth/facebook/start", headers=_auth_headers(token), follow_redirects=False)
    assert resp.status_code == 302
    location = resp.headers["location"]

    qs = parse_qs(urlparse(location).query)
    state = qs["state"][0]

    decoded = jwt.decode(state, settings.jwt_secret, algorithms=["HS256"])
    assert decoded["tenant_id"] == str(client_id)
    assert "nonce" in decoded
    assert len(decoded["nonce"]) >= 16
    assert "exp" in decoded

    now_ts = int(datetime.now(tz=timezone.utc).timestamp())
    upper_ts = int((datetime.now(tz=timezone.utc) + timedelta(minutes=11)).timestamp())
    assert decoded["exp"] > now_ts
    assert decoded["exp"] <= upper_ts


def test_callback_invalid_state(db_client):
    """PAGE-01: callback with malformed state returns 400."""
    client = db_client.client

    resp = client.get("/auth/facebook/callback?code=anycode&state=not.a.valid.jwt")
    assert resp.status_code == 400
    assert resp.json()["detail"] in ("Invalid OAuth state", "OAuth state expired — please try again")


def test_callback_expired_state(db_client):
    """PAGE-01: callback with expired state JWT returns 400 with expired message."""
    client = db_client.client

    expired_state = jwt.encode(
        {
            "tenant_id": "1",
            "nonce": "abc",
            "exp": datetime.now(tz=timezone.utc) - timedelta(minutes=1),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )

    resp = client.get(f"/auth/facebook/callback?code=anycode&state={expired_state}")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "OAuth state expired — please try again"


def test_callback_webhook_failure_rollback(db_client, monkeypatch):
    """PAGE-01: subscription failure rolls back DB insert — no rows committed."""
    client = db_client.client
    client_id, _ = _make_client_token(db_client)

    valid_state = jwt.encode(
        {
            "tenant_id": str(client_id),
            "nonce": "abc123def456",
            "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=10),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )

    monkeypatch.setattr("app.fb_client.httpx.get", _dispatch_httpx_get)

    def _fail_subscribe(page_fb_id, page_access_token):
        raise RuntimeError("subscription failed")

    monkeypatch.setattr("app.routers.pages.fb_client.subscribe_page_webhook", _fail_subscribe)

    # Starlette TestClient re-raises unhandled server exceptions by default.
    # The RuntimeError propagating is itself evidence the callback failed;
    # what matters for T-12-06 is that no row committed after rollback.
    with pytest.raises(RuntimeError, match="subscription failed"):
        client.get(f"/auth/facebook/callback?code=test&state={valid_state}")

    # Direct SQL: no row committed — proves conn.rollback() executed
    conn = get_connection(db_client.db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) as c FROM pages WHERE tenant_id = ?", (client_id,)
        ).fetchone()
    finally:
        conn.close()
    assert row["c"] == 0


def test_callback_success(db_client, monkeypatch):
    """PAGE-01: successful callback stores encrypted token + subscribes webhook; UPSERT is idempotent."""
    client = db_client.client
    client_id, _ = _make_client_token(db_client)

    valid_state = jwt.encode(
        {
            "tenant_id": str(client_id),
            "nonce": "abc123def456",
            "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=10),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )

    monkeypatch.setattr("app.fb_client.httpx.get", _dispatch_httpx_get)
    monkeypatch.setattr(
        "app.fb_client.httpx.post",
        lambda url, **kw: MockResponse({"success": True}),
    )

    resp = client.get(f"/auth/facebook/callback?code=test&state={valid_state}")
    assert resp.status_code == 200
    assert resp.json() == {"pages_connected": 1}

    conn = get_connection(db_client.db_path)
    try:
        rows = conn.execute(
            "SELECT page_fb_id, page_name, access_token_enc, is_active "
            "FROM pages WHERE tenant_id = ?",
            (client_id,),
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1
    row = rows[0]
    assert row["page_fb_id"] == "fb-page-1"
    assert row["page_name"] == "Test Page"
    assert row["is_active"] == 1
    assert row["access_token_enc"] is not None
    assert row["access_token_enc"] != "page-tok"
    assert decrypt_token(row["access_token_enc"]) == "page-tok"

    # UPSERT idempotency — re-run same callback
    resp2 = client.get(f"/auth/facebook/callback?code=test&state={valid_state}")
    assert resp2.status_code == 200
    assert resp2.json() == {"pages_connected": 1}

    conn = get_connection(db_client.db_path)
    try:
        count = conn.execute(
            "SELECT COUNT(*) as c FROM pages WHERE tenant_id = ?", (client_id,)
        ).fetchone()["c"]
    finally:
        conn.close()
    assert count == 1


# ---------------------------------------------------------------------------
# PAGE-02 tests
# ---------------------------------------------------------------------------

def test_list_pages(db_client, monkeypatch):
    """PAGE-02: GET /pages returns tenant's active pages with status derived from debug_token."""
    client = db_client.client
    client_id, token = _make_client_token(db_client)

    _seed_page(db_client.db_path, client_id, "fb-A", "Page A", "tok-A")
    _seed_page(db_client.db_path, client_id, "fb-B", "Page B", "tok-B")

    monkeypatch.setattr(
        "app.fb_client.httpx.get",
        lambda url, **kw: MockResponse({"data": {"is_valid": True, "expires_at": 0}}),
    )

    resp = client.get("/pages", headers=_auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 2
    for entry in body:
        assert set(entry.keys()) == {"id", "page_fb_id", "page_name", "status", "created_at"}
        assert entry["status"] == "active"
    fb_ids = {entry["page_fb_id"] for entry in body}
    assert fb_ids == {"fb-A", "fb-B"}


def test_list_pages_revoked(db_client, monkeypatch):
    """PAGE-02: revoked debug_token response maps to status='revoked'."""
    client = db_client.client
    client_id, token = _make_client_token(db_client)

    _seed_page(db_client.db_path, client_id, "fb-X", "Page X", "tok-X")

    monkeypatch.setattr(
        "app.fb_client.httpx.get",
        lambda url, **kw: MockResponse(
            {"data": {"is_valid": False, "error": {"code": 190, "message": "revoked"}}}
        ),
    )

    resp = client.get("/pages", headers=_auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["status"] == "revoked"


def test_pages_isolation(db_client, monkeypatch):
    """PAGE-02 / T-12-09: tenant A cannot see tenant B's pages via GET /pages."""
    client = db_client.client
    admin_token = _login(client, db_client.super_admin_email, db_client.super_admin_password)
    a = _create_client(client, admin_token, "tenant-a@test.local", "pw-a")
    b = _create_client(client, admin_token, "tenant-b@test.local", "pw-b")
    token_a = _login(client, "tenant-a@test.local", "pw-a")
    token_b = _login(client, "tenant-b@test.local", "pw-b")

    _seed_page(db_client.db_path, a["id"], "fb-A-only", "A Page", "tok-A")
    _seed_page(db_client.db_path, b["id"], "fb-B-only", "B Page", "tok-B")

    monkeypatch.setattr(
        "app.fb_client.httpx.get",
        lambda url, **kw: MockResponse({"data": {"is_valid": True, "expires_at": 0}}),
    )

    resp_a = client.get("/pages", headers=_auth_headers(token_a))
    assert resp_a.status_code == 200
    body_a = resp_a.json()
    assert len(body_a) == 1
    assert body_a[0]["page_fb_id"] == "fb-A-only"
    assert all(entry["page_fb_id"] != "fb-B-only" for entry in body_a)

    resp_b = client.get("/pages", headers=_auth_headers(token_b))
    assert resp_b.status_code == 200
    body_b = resp_b.json()
    assert len(body_b) == 1
    assert body_b[0]["page_fb_id"] == "fb-B-only"
    assert all(entry["page_fb_id"] != "fb-A-only" for entry in body_b)


# ---------------------------------------------------------------------------
# PAGE-03 tests
# ---------------------------------------------------------------------------

def test_disconnect_page(db_client, monkeypatch):
    """PAGE-03: DELETE /pages/{id} unsubscribes webhook + soft-deletes row."""
    client = db_client.client
    client_id, token = _make_client_token(db_client)

    page_id = _seed_page(db_client.db_path, client_id, "fb-D", "Delete Me", "tok-D")

    delete_calls: list[dict] = []

    def _fake_delete(url, **kw):
        delete_calls.append(kw.get("params", {}) or {})
        return MockResponse({"success": True})

    monkeypatch.setattr("app.fb_client.httpx.delete", _fake_delete)
    monkeypatch.setattr(
        "app.fb_client.httpx.get",
        lambda url, **kw: MockResponse({"data": {"is_valid": True, "expires_at": 0}}),
    )

    resp = client.delete(f"/pages/{page_id}", headers=_auth_headers(token))
    assert resp.status_code == 200
    assert "disconnected" in resp.json()["detail"]

    assert len(delete_calls) == 1
    assert delete_calls[0]["access_token"] == "tok-D"

    conn = get_connection(db_client.db_path)
    try:
        row = conn.execute(
            "SELECT is_active FROM pages WHERE id = ?", (page_id,)
        ).fetchone()
    finally:
        conn.close()
    assert row["is_active"] == 0

    resp_list = client.get("/pages", headers=_auth_headers(token))
    assert resp_list.status_code == 200
    assert resp_list.json() == []


def test_disconnect_not_found(db_client, monkeypatch):
    """PAGE-03 / T-12-10: DELETE returns 404 for other tenant's pages and unknown ids."""
    client = db_client.client
    admin_token = _login(client, db_client.super_admin_email, db_client.super_admin_password)
    a = _create_client(client, admin_token, "tenant-a@test.local", "pw-a")
    b = _create_client(client, admin_token, "tenant-b@test.local", "pw-b")
    token_a = _login(client, "tenant-a@test.local", "pw-a")
    token_b = _login(client, "tenant-b@test.local", "pw-b")

    page_id_a = _seed_page(db_client.db_path, a["id"], "fb-A", "A Page", "tok-A")

    monkeypatch.setattr(
        "app.fb_client.httpx.delete",
        lambda url, **kw: MockResponse({"success": True}),
    )
    monkeypatch.setattr(
        "app.fb_client.httpx.get",
        lambda url, **kw: MockResponse({"data": {"is_valid": True, "expires_at": 0}}),
    )

    # B tries to delete A's page
    resp_cross = client.delete(f"/pages/{page_id_a}", headers=_auth_headers(token_b))
    assert resp_cross.status_code == 404
    assert resp_cross.json()["detail"] == "Page not found"

    # A tries to delete a nonexistent id
    resp_missing = client.delete("/pages/99999", headers=_auth_headers(token_a))
    assert resp_missing.status_code == 404

    # Verify A's row was NOT mutated by B's failed attempt
    conn = get_connection(db_client.db_path)
    try:
        row = conn.execute(
            "SELECT is_active FROM pages WHERE id = ?", (page_id_a,)
        ).fetchone()
    finally:
        conn.close()
    assert row["is_active"] == 1

    # A deletes their own page successfully
    resp_ok = client.delete(f"/pages/{page_id_a}", headers=_auth_headers(token_a))
    assert resp_ok.status_code == 200

    # Second delete returns 404 (already inactive)
    resp_again = client.delete(f"/pages/{page_id_a}", headers=_auth_headers(token_a))
    assert resp_again.status_code == 404


# ---------------------------------------------------------------------------
# PAGE-04 tests
# ---------------------------------------------------------------------------

def test_token_health(db_client, monkeypatch):
    """PAGE-04: GET /pages/{id}/health reports is_valid + expires_at from debug_token."""
    client = db_client.client
    admin_token = _login(client, db_client.super_admin_email, db_client.super_admin_password)
    a = _create_client(client, admin_token, "tenant-a@test.local", "pw-a")
    b = _create_client(client, admin_token, "tenant-b@test.local", "pw-b")
    token_a = _login(client, "tenant-a@test.local", "pw-a")
    token_b = _login(client, "tenant-b@test.local", "pw-b")

    page_id = _seed_page(db_client.db_path, a["id"], "fb-H", "Health Page", "tok-H")

    current_response: list[MockResponse] = [
        MockResponse({"data": {"app_id": "test-app-id", "is_valid": True, "expires_at": 0}})
    ]

    def _fake_get(url, **kw):
        return current_response[0]

    monkeypatch.setattr("app.fb_client.httpx.get", _fake_get)

    # Phase 1 — valid, non-expiring (expires_at=0 → None)
    resp1 = client.get(f"/pages/{page_id}/health", headers=_auth_headers(token_a))
    assert resp1.status_code == 200
    assert resp1.json() == {"is_valid": True, "expires_at": None}

    # Phase 2 — revoked
    current_response[0] = MockResponse(
        {"data": {"is_valid": False, "error": {"code": 190, "message": "expired"}}}
    )
    resp2 = client.get(f"/pages/{page_id}/health", headers=_auth_headers(token_a))
    assert resp2.status_code == 200
    assert resp2.json() == {"is_valid": False, "expires_at": None}

    # Phase 3 — valid with a real expiry
    current_response[0] = MockResponse({"data": {"is_valid": True, "expires_at": 1900000000}})
    resp3 = client.get(f"/pages/{page_id}/health", headers=_auth_headers(token_a))
    assert resp3.status_code == 200
    assert resp3.json() == {"is_valid": True, "expires_at": 1900000000}

    # Cross-tenant (T-12-09): tenant B cannot health-check A's page
    resp_cross = client.get(f"/pages/{page_id}/health", headers=_auth_headers(token_b))
    assert resp_cross.status_code == 404


# ---------------------------------------------------------------------------
# Internal endpoint — GET /internal/pages/{page_fb_id}/access-token
# Used by the messenger-bot Node service. Guarded by X-Internal-Key.
# ---------------------------------------------------------------------------

def test_internal_token_success(db_client):
    client = db_client.client
    client_id, _ = _make_client_token(db_client)
    _seed_page(db_client.db_path, client_id, "fb-page-777", "Internal Page", "the-page-token")

    resp = client.get(
        "/internal/pages/fb-page-777/access-token",
        headers={"X-Internal-Key": "test-internal-secret"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"access_token": "the-page-token"}


def test_internal_token_forbidden_without_key(db_client):
    client = db_client.client
    client_id, _ = _make_client_token(db_client)
    _seed_page(db_client.db_path, client_id, "fb-page-777", "Internal Page", "the-page-token")

    # Missing header
    r_missing = client.get("/internal/pages/fb-page-777/access-token")
    assert r_missing.status_code == 403

    # Wrong secret
    r_wrong = client.get(
        "/internal/pages/fb-page-777/access-token",
        headers={"X-Internal-Key": "wrong-secret"},
    )
    assert r_wrong.status_code == 403


def test_internal_token_404_for_unknown_page(db_client):
    client = db_client.client
    resp = client.get(
        "/internal/pages/nonexistent-page/access-token",
        headers={"X-Internal-Key": "test-internal-secret"},
    )
    assert resp.status_code == 404


def test_internal_token_404_after_disconnect(db_client, monkeypatch):
    client = db_client.client
    client_id, client_token = _make_client_token(db_client)
    page_id = _seed_page(db_client.db_path, client_id, "fb-page-888", "Soon-Disconnected", "tok")

    # Stub the unsubscribe call so we don't hit Facebook
    monkeypatch.setattr("app.fb_client.unsubscribe_page_webhook", lambda *a, **kw: None)
    del_resp = client.delete(f"/pages/{page_id}", headers=_auth_headers(client_token))
    assert del_resp.status_code == 200

    r = client.get(
        "/internal/pages/fb-page-888/access-token",
        headers={"X-Internal-Key": "test-internal-secret"},
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# CONTENT-01/02/04 — PUT /pages/{page_id}/config
# ---------------------------------------------------------------------------

def test_put_config_creates_then_updates(db_client):
    """CONTENT-01/02/04: first PUT creates the config row; second PUT overwrites it."""
    client = db_client.client
    client_id, token = _make_client_token(db_client)
    page_id = _seed_page(db_client.db_path, client_id, "fb-cfg-1", "Config Page", "tok-cfg-1")

    payload1 = {
        "welcome_text": "Welcome!",
        "menu_json": [{"title": "Products", "payload": "MENU_PRODUCTS"}],
        "escalation_psid": "psid-1",
        "escalation_message": "Talk to a human",
    }
    resp1 = client.put(
        f"/pages/{page_id}/config", json=payload1, headers=_auth_headers(token)
    )
    assert resp1.status_code == 200
    body1 = resp1.json()
    assert body1["page_id"] == page_id
    assert body1["welcome_text"] == "Welcome!"
    assert body1["menu_json"] == [{"title": "Products", "payload": "MENU_PRODUCTS"}]
    assert body1["escalation_psid"] == "psid-1"
    assert body1["escalation_message"] == "Talk to a human"

    payload2 = {
        "welcome_text": "New welcome",
        "menu_json": [{"title": "Support", "payload": "MENU_SUPPORT"}],
        "escalation_psid": "psid-2",
        "escalation_message": "Different message",
    }
    resp2 = client.put(
        f"/pages/{page_id}/config", json=payload2, headers=_auth_headers(token)
    )
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["welcome_text"] == "New welcome"
    assert body2["menu_json"] == [{"title": "Support", "payload": "MENU_SUPPORT"}]
    assert body2["escalation_psid"] == "psid-2"
    assert body2["escalation_message"] == "Different message"

    conn = get_connection(db_client.db_path)
    try:
        count = conn.execute(
            "SELECT COUNT(*) as c FROM page_configs WHERE page_id = ?", (page_id,)
        ).fetchone()["c"]
    finally:
        conn.close()
    assert count == 1


def test_put_config_menu_roundtrip(db_client):
    """CONTENT-02: a two-item flat menu_json roundtrips in order."""
    client = db_client.client
    client_id, token = _make_client_token(db_client)
    page_id = _seed_page(db_client.db_path, client_id, "fb-cfg-2", "Menu Page", "tok-cfg-2")

    payload = {
        "welcome_text": "Hi",
        "menu_json": [
            {"title": "First", "payload": "PAYLOAD_FIRST"},
            {"title": "Second", "payload": "PAYLOAD_SECOND"},
        ],
    }
    resp = client.put(
        f"/pages/{page_id}/config", json=payload, headers=_auth_headers(token)
    )
    assert resp.status_code == 200
    assert resp.json()["menu_json"] == [
        {"title": "First", "payload": "PAYLOAD_FIRST"},
        {"title": "Second", "payload": "PAYLOAD_SECOND"},
    ]


def test_put_config_rejects_nested_menu(db_client):
    """CONTENT-02/D-04: an extra key or nested object in a menu item returns 422."""
    client = db_client.client
    client_id, token = _make_client_token(db_client)
    page_id = _seed_page(db_client.db_path, client_id, "fb-cfg-3", "Bad Menu Page", "tok-cfg-3")

    payload_extra_key = {
        "welcome_text": "Hi",
        "menu_json": [{"title": "First", "payload": "P1", "children": []}],
    }
    resp1 = client.put(
        f"/pages/{page_id}/config", json=payload_extra_key, headers=_auth_headers(token)
    )
    assert resp1.status_code == 422

    payload_nested = {
        "welcome_text": "Hi",
        "menu_json": [{"title": "First", "payload": {"nested": "object"}}],
    }
    resp2 = client.put(
        f"/pages/{page_id}/config", json=payload_nested, headers=_auth_headers(token)
    )
    assert resp2.status_code == 422


def test_put_config_cross_tenant_404(db_client):
    """T-13-04: tenant B PUTs to tenant A's page_id -> 404, no page_configs row created."""
    client = db_client.client
    admin_token = _login(client, db_client.super_admin_email, db_client.super_admin_password)
    a = _create_client(client, admin_token, "cfg-tenant-a@test.local", "pw-a")
    b = _create_client(client, admin_token, "cfg-tenant-b@test.local", "pw-b")
    token_b = _login(client, "cfg-tenant-b@test.local", "pw-b")

    page_id_a = _seed_page(db_client.db_path, a["id"], "fb-cfg-cross", "A's Page", "tok-a")

    payload = {"welcome_text": "Hijack attempt", "menu_json": []}
    resp = client.put(
        f"/pages/{page_id_a}/config", json=payload, headers=_auth_headers(token_b)
    )
    assert resp.status_code == 404

    conn = get_connection(db_client.db_path)
    try:
        row = conn.execute(
            "SELECT id FROM page_configs WHERE page_id = ?", (page_id_a,)
        ).fetchone()
    finally:
        conn.close()
    assert row is None


def test_put_config_unauthenticated_401(db_client):
    """T-13-06: PUT with no Authorization header is rejected."""
    client = db_client.client
    client_id, _ = _make_client_token(db_client)
    page_id = _seed_page(db_client.db_path, client_id, "fb-cfg-unauth", "Unauth Page", "tok-u")

    payload = {"welcome_text": "Hi", "menu_json": []}
    resp = client.put(f"/pages/{page_id}/config", json=payload)
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Internal endpoint — GET /internal/pages/{page_fb_id}/config
# ---------------------------------------------------------------------------

def test_internal_config_forbidden_without_key(db_client):
    """T-13-07: missing or wrong X-Internal-Key returns 403."""
    client = db_client.client
    client_id, _ = _make_client_token(db_client)
    _seed_page(db_client.db_path, client_id, "fb-icfg-1", "Internal Config Page", "tok-i1")

    r_missing = client.get("/internal/pages/fb-icfg-1/config")
    assert r_missing.status_code == 403

    r_wrong = client.get(
        "/internal/pages/fb-icfg-1/config",
        headers={"X-Internal-Key": "wrong-secret"},
    )
    assert r_wrong.status_code == 403


def test_internal_config_returns_config(db_client):
    """CONTENT-01/02/04: internal read returns the persisted config with parsed menu_json."""
    client = db_client.client
    client_id, token = _make_client_token(db_client)
    page_id = _seed_page(db_client.db_path, client_id, "fb-icfg-2", "Internal Config Page 2", "tok-i2")

    payload = {
        "welcome_text": "Bot welcome",
        "menu_json": [
            {"title": "Cat A", "payload": "PAYLOAD_A"},
            {"title": "Cat B", "payload": "PAYLOAD_B"},
        ],
        "escalation_psid": "psid-bot",
        "escalation_message": "Escalating now",
    }
    put_resp = client.put(
        f"/pages/{page_id}/config", json=payload, headers=_auth_headers(token)
    )
    assert put_resp.status_code == 200

    resp = client.get(
        "/internal/pages/fb-icfg-2/config",
        headers={"X-Internal-Key": "test-internal-secret"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["welcome_text"] == "Bot welcome"
    assert body["menu_json"] == [
        {"title": "Cat A", "payload": "PAYLOAD_A"},
        {"title": "Cat B", "payload": "PAYLOAD_B"},
    ]
    assert body["escalation_psid"] == "psid-bot"
    assert body["escalation_message"] == "Escalating now"


def test_internal_config_unknown_page_404(db_client):
    """T-13-07: valid key but unknown page_fb_id returns 404."""
    client = db_client.client
    resp = client.get(
        "/internal/pages/nonexistent-config-page/config",
        headers={"X-Internal-Key": "test-internal-secret"},
    )
    assert resp.status_code == 404


def test_internal_config_defaults_when_no_row(db_client):
    """CONTENT-01/02/04: active page with no config row yet returns schema defaults."""
    client = db_client.client
    client_id, _ = _make_client_token(db_client)
    _seed_page(db_client.db_path, client_id, "fb-icfg-nodefault", "No Config Yet", "tok-nd")

    resp = client.get(
        "/internal/pages/fb-icfg-nodefault/config",
        headers={"X-Internal-Key": "test-internal-secret"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["welcome_text"] == ""
    assert body["menu_json"] == []
    assert body["escalation_psid"] is None
    assert body["escalation_message"] is None
