from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest

from app.config import settings
from app.crypto import decrypt_token
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
