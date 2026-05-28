import sqlite3

import pytest
import app.config as config_module
from fastapi.testclient import TestClient
from app.main import app
from app.db import init_schema, get_connection
from app.auth import create_access_token, verify_token


# ---------------------------------------------------------------------------
# Shared test helpers — stateless, no side effects
# ---------------------------------------------------------------------------

def _login(client, email, password) -> str:
    """POST /auth/login; return access_token string. Raises on non-200."""
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"login failed: {resp.status_code} {resp.text}"
    return resp.json()["access_token"]


def _auth_headers(token: str) -> dict:
    """Return Authorization Bearer header dict."""
    return {"Authorization": f"Bearer {token}"}


def _create_client(client, admin_token, email, password) -> dict:
    """POST /admin/tenants with super-admin token; return response JSON."""
    resp = client.post(
        "/admin/tenants",
        json={"email": email, "password": password},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 201, f"create_tenant failed: {resp.status_code} {resp.text}"
    return resp.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_login_success(db_client):
    """SC-1: login with valid credentials returns a JWT."""
    client = db_client.client
    email = db_client.super_admin_email
    password = db_client.super_admin_password
    sa_id = db_client.super_admin_id

    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200

    body = resp.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert body["access_token"].startswith("eyJ")

    decoded = verify_token(body["access_token"])
    assert decoded["sub"] == str(sa_id)
    assert decoded["role"] == "super_admin"


def test_login_invalid(db_client):
    """SC-1: login with invalid credentials returns 401 with identical detail (no user enumeration)."""
    client = db_client.client
    email = db_client.super_admin_email

    # Wrong password
    resp1 = client.post("/auth/login", json={"email": email, "password": "wrong-password"})
    assert resp1.status_code == 401
    assert resp1.json()["detail"] == "Invalid credentials"

    # Unknown email
    resp2 = client.post("/auth/login", json={"email": "nonexistent@example.com", "password": "any-pass"})
    assert resp2.status_code == 401
    assert resp2.json()["detail"] == "Invalid credentials"

    # Empty password
    resp3 = client.post("/auth/login", json={"email": email, "password": ""})
    assert resp3.status_code == 401
    assert resp3.json()["detail"] == "Invalid credentials"


def test_inactive_tenant(db_client):
    """SC-4: deactivated tenant login attempt returns 401."""
    client = db_client.client
    admin_token = _login(client, db_client.super_admin_email, db_client.super_admin_password)

    # Create a client tenant via super-admin
    _create_client(client, admin_token, "client@test.local", "client-pass")

    # Deactivate via direct SQL
    conn = get_connection(db_client.db_path)
    try:
        conn.execute("UPDATE tenants SET is_active = 0 WHERE email = 'client@test.local'")
        conn.commit()
    finally:
        conn.close()

    # Deactivated tenant cannot log in even with correct password
    resp = client.post("/auth/login", json={"email": "client@test.local", "password": "client-pass"})
    assert resp.status_code == 401


def test_create_tenant(db_client):
    """TENANT-01: POST /admin/tenants creates a new tenant with bcrypt hash."""
    client = db_client.client
    admin_token = _login(client, db_client.super_admin_email, db_client.super_admin_password)

    resp = client.post(
        "/admin/tenants",
        json={"email": "new@test.local", "password": "new-pass"},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 201

    body = resp.json()
    # Response shape: {id, email, is_active, is_super_admin, created_at} — NO password_hash
    assert "id" in body
    assert "email" in body
    assert "is_active" in body
    assert "is_super_admin" in body
    assert "created_at" in body
    assert "password_hash" not in body

    assert body["email"] == "new@test.local"
    assert body["is_active"] is True
    assert body["is_super_admin"] is False

    # Confirm bcrypt prefix in DB
    conn = get_connection(db_client.db_path)
    try:
        row = conn.execute(
            "SELECT password_hash FROM tenants WHERE email = 'new@test.local'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row["password_hash"][:4] in ("$2b$", "$2a$")
    assert row["password_hash"] != "new-pass"


def test_duplicate_email(db_client):
    """TENANT-01: duplicate email returns 409."""
    client = db_client.client
    admin_token = _login(client, db_client.super_admin_email, db_client.super_admin_password)

    # First creation succeeds
    _create_client(client, admin_token, "dup@test.local", "pass1")

    # Second creation with same email returns 409
    resp = client.post(
        "/admin/tenants",
        json={"email": "dup@test.local", "password": "pass2"},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Email already exists"


def test_list_tenants(db_client):
    """TENANT-02: GET /admin/tenants lists non-super-admin tenants with page_count."""
    client = db_client.client
    admin_token = _login(client, db_client.super_admin_email, db_client.super_admin_password)

    # Create two client tenants
    c1 = _create_client(client, admin_token, "c1@test.local", "pass-c1")
    c2 = _create_client(client, admin_token, "c2@test.local", "pass-c2")
    c1_id = c1["id"]

    # Seed a page for c1 via direct SQL
    conn = get_connection(db_client.db_path)
    try:
        conn.execute(
            "INSERT INTO pages (tenant_id, page_fb_id, page_name, is_active) VALUES (?, 'fb-123', 'Test Page', 1)",
            (c1_id,),
        )
        conn.commit()
    finally:
        conn.close()

    resp = client.get("/admin/tenants", headers=_auth_headers(admin_token))
    assert resp.status_code == 200

    items = resp.json()
    # Exactly 2 items — super-admin excluded
    assert len(items) == 2

    # Each item has the required keys
    for item in items:
        assert "id" in item
        assert "email" in item
        assert "is_active" in item
        assert "created_at" in item
        assert "page_count" in item

    # Super-admin row not in list
    emails_in_list = {item["email"] for item in items}
    assert db_client.super_admin_email not in emails_in_list

    # c1 has page_count >= 1; c2 has page_count == 0
    c1_item = next(item for item in items if item["id"] == c1_id)
    c2_item = next(item for item in items if item["id"] == c2["id"])
    assert c1_item["page_count"] >= 1
    assert c2_item["page_count"] == 0


def test_soft_delete(db_client):
    """TENANT-03 + SC-4: DELETE /admin/tenants/{id} soft-deletes tenant and their pages."""
    client = db_client.client
    admin_token = _login(client, db_client.super_admin_email, db_client.super_admin_password)

    # Create a client to delete
    created = _create_client(client, admin_token, "delete-me@test.local", "del-pass")
    client_id = created["id"]

    # Seed a page for the client via direct SQL
    conn = get_connection(db_client.db_path)
    try:
        conn.execute(
            "INSERT INTO pages (tenant_id, page_fb_id, page_name, is_active) VALUES (?, 'fb-123', 'Test Page', 1)",
            (client_id,),
        )
        conn.commit()
    finally:
        conn.close()

    # Delete returns 200 with pages_deactivated=1
    resp = client.delete(f"/admin/tenants/{client_id}", headers=_auth_headers(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["pages_deactivated"] == 1
    assert body["detail"].startswith("Tenant ")
    assert "deactivated" in body["detail"]

    # Direct SQL: tenant and page are both inactive
    conn = get_connection(db_client.db_path)
    try:
        tenant_row = conn.execute("SELECT is_active FROM tenants WHERE id = ?", (client_id,)).fetchone()
        page_row = conn.execute("SELECT is_active FROM pages WHERE tenant_id = ?", (client_id,)).fetchone()
    finally:
        conn.close()
    assert tenant_row["is_active"] == 0
    assert page_row["is_active"] == 0

    # Second DELETE on same id returns 404 (already inactive)
    resp2 = client.delete(f"/admin/tenants/{client_id}", headers=_auth_headers(admin_token))
    assert resp2.status_code == 404

    # Self-delete returns 403
    super_admin_id = db_client.super_admin_id
    resp3 = client.delete(f"/admin/tenants/{super_admin_id}", headers=_auth_headers(admin_token))
    assert resp3.status_code == 403
    assert resp3.json()["detail"] == "Cannot delete your own account"


def test_tenant_isolation(db_client):
    """SC-5: GET /tenants/me returns only own tenant record (JWT sub-claim isolation)."""
    client = db_client.client
    admin_token = _login(client, db_client.super_admin_email, db_client.super_admin_password)

    # Create two client tenants
    a = _create_client(client, admin_token, "a@test.local", "pass-a")
    b = _create_client(client, admin_token, "b@test.local", "pass-b")
    a_id = a["id"]
    b_id = b["id"]

    # Login as A and B
    token_a = _login(client, "a@test.local", "pass-a")
    token_b = _login(client, "b@test.local", "pass-b")

    # A's token returns A's row
    resp_a = client.get("/tenants/me", headers=_auth_headers(token_a))
    assert resp_a.status_code == 200
    body_a = resp_a.json()
    assert body_a["id"] == a_id
    assert body_a["email"] == "a@test.local"
    assert "password_hash" not in body_a

    # B's token returns B's row
    resp_b = client.get("/tenants/me", headers=_auth_headers(token_b))
    assert resp_b.status_code == 200
    body_b = resp_b.json()
    assert body_b["id"] == b_id
    assert body_b["email"] == "b@test.local"
    assert "password_hash" not in body_b

    # Confirm responses are distinct — A's token never returns B's row
    assert body_a["id"] != body_b["id"]
    assert body_a["email"] != body_b["email"]


def test_forbidden(db_client):
    """SC-5: client JWT receives 403 on /admin/tenants; missing/garbage tokens return 401."""
    client = db_client.client
    admin_token = _login(client, db_client.super_admin_email, db_client.super_admin_password)

    # Create a client tenant
    _create_client(client, admin_token, "client@test.local", "client-pass")
    client_token = _login(client, "client@test.local", "client-pass")

    # Client token rejected with 403 on every /admin/tenants endpoint
    resp_get = client.get("/admin/tenants", headers=_auth_headers(client_token))
    assert resp_get.status_code == 403
    assert resp_get.json()["detail"] == "Admin access required"

    resp_post = client.post(
        "/admin/tenants",
        json={"email": "new@test.local", "password": "np"},
        headers=_auth_headers(client_token),
    )
    assert resp_post.status_code == 403

    resp_del = client.delete("/admin/tenants/999", headers=_auth_headers(client_token))
    assert resp_del.status_code == 403

    # Missing Authorization header returns 401
    resp_no_auth = client.get("/admin/tenants")
    assert resp_no_auth.status_code == 401

    # Garbage token returns 401 with "Invalid token"
    resp_garbage = client.get(
        "/admin/tenants",
        headers={"Authorization": "Bearer garbage.token.value"},
    )
    assert resp_garbage.status_code == 401
    assert resp_garbage.json()["detail"] == "Invalid token"
