import pytest
import app.config as config_module
from fastapi.testclient import TestClient
from app.main import app
from app.db import init_schema, get_connection
from app.auth import create_access_token, verify_token


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
    """SC-1: login with invalid credentials returns 401."""
    pytest.skip("Wave 0 stub — implemented in plan 03")


def test_inactive_tenant(db_client):
    """SC-4: deactivated tenant login attempt returns 401."""
    pytest.skip("Wave 0 stub — implemented in plan 03")


def test_create_tenant(db_client):
    """TENANT-01: POST /admin/tenants creates a new tenant with bcrypt hash."""
    pytest.skip("Wave 0 stub — implemented in plan 03")


def test_duplicate_email(db_client):
    """TENANT-01: duplicate email returns 409."""
    pytest.skip("Wave 0 stub — implemented in plan 03")


def test_list_tenants(db_client):
    """TENANT-02: GET /admin/tenants lists non-super-admin tenants with page_count."""
    pytest.skip("Wave 0 stub — implemented in plan 03")


def test_soft_delete(db_client):
    """TENANT-03: DELETE /admin/tenants/{id} soft-deletes tenant and pages."""
    pytest.skip("Wave 0 stub — implemented in plan 03")


def test_tenant_isolation(db_client):
    """SC-5: GET /tenants/me returns only own tenant record."""
    pytest.skip("Wave 0 stub — implemented in plan 03")


def test_forbidden(db_client):
    """SC-5: non-super-admin token returns 403 on /admin/tenants."""
    pytest.skip("Wave 0 stub — implemented in plan 03")
