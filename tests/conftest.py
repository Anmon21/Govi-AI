from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from passlib.context import CryptContext

import app.config as config_module
from app.db import init_schema, get_connection
from app.main import app

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@pytest.fixture
def db_client(tmp_path, monkeypatch):
    """TestClient wired to a tmp-path SQLite DB with a seeded super-admin row."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(config_module.settings, "db_path", db_path)
    monkeypatch.setattr(config_module.settings, "jwt_secret", "test-secret-do-not-use-in-prod")
    monkeypatch.setattr(config_module.settings, "fernet_key", Fernet.generate_key().decode())
    monkeypatch.setattr(config_module.settings, "fb_app_id", "test-app-id")
    monkeypatch.setattr(config_module.settings, "fb_app_secret", "test-app-secret")
    monkeypatch.setattr(config_module.settings, "fb_redirect_uri", "http://localhost:8000/auth/facebook/callback")
    monkeypatch.setattr(config_module.settings, "internal_secret", "test-internal-secret")
    init_schema(db_path)
    conn = get_connection(db_path)
    try:
        super_admin_password = "admin-pass"
        conn.execute(
            "INSERT INTO tenants (email, password_hash, is_super_admin) VALUES (?, ?, 1)",
            ("admin@test.local", _pwd_context.hash(super_admin_password)),
        )
        conn.commit()
        row = conn.execute("SELECT id FROM tenants WHERE is_super_admin = 1").fetchone()
        super_admin_id = row["id"]
    finally:
        conn.close()
    with TestClient(app) as c:
        yield SimpleNamespace(
            client=c,
            super_admin_id=super_admin_id,
            super_admin_email="admin@test.local",
            super_admin_password=super_admin_password,
            db_path=db_path,
        )
