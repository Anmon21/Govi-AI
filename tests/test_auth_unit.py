"""Unit tests for app/auth.py — RED phase for Task 2."""
import pytest
import app.config as config_module
from fastapi import HTTPException


def test_create_access_token_returns_jwt_string(monkeypatch):
    """create_access_token returns a non-empty HS256 JWT string."""
    monkeypatch.setattr(config_module.settings, "jwt_secret", "test-secret")
    from app.auth import create_access_token
    token = create_access_token("42", "client")
    assert isinstance(token, str) and token.startswith("eyJ")


def test_create_access_token_no_secret_raises(monkeypatch):
    """create_access_token raises RuntimeError when jwt_secret is empty."""
    monkeypatch.setattr(config_module.settings, "jwt_secret", "")
    from app.auth import create_access_token
    with pytest.raises(RuntimeError, match="JWT_SECRET is not configured. Set it in .env."):
        create_access_token("42", "client")


def test_verify_token_roundtrip(monkeypatch):
    """verify_token decodes a token created by create_access_token."""
    monkeypatch.setattr(config_module.settings, "jwt_secret", "test-secret")
    from app.auth import create_access_token, verify_token
    token = create_access_token("42", "client")
    payload = verify_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "client"
    assert "exp" in payload


def test_verify_token_invalid_raises_401(monkeypatch):
    """verify_token raises HTTPException(401) for garbage tokens."""
    monkeypatch.setattr(config_module.settings, "jwt_secret", "test-secret")
    from app.auth import verify_token
    with pytest.raises(HTTPException) as exc_info:
        verify_token("garbage.token.value")
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"


def test_verify_token_expired_raises_401(monkeypatch):
    """verify_token raises HTTPException(401, detail='Token expired') for expired tokens."""
    monkeypatch.setattr(config_module.settings, "jwt_secret", "test-secret")
    import jwt
    from datetime import datetime, timedelta, timezone
    payload = {"sub": "1", "role": "client", "exp": datetime.now(tz=timezone.utc) - timedelta(seconds=1)}
    expired_token = jwt.encode(payload, "test-secret", algorithm="HS256")
    from app.auth import verify_token
    with pytest.raises(HTTPException) as exc_info:
        verify_token(expired_token)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Token expired"


def test_require_super_admin_rejects_client(monkeypatch):
    """require_super_admin raises HTTPException(403) for non-admin role."""
    import asyncio
    monkeypatch.setattr(config_module.settings, "jwt_secret", "test-secret")
    from app.auth import require_super_admin
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(require_super_admin({"sub": "1", "role": "client"}))
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Admin access required"


def test_require_super_admin_accepts_admin(monkeypatch):
    """require_super_admin returns the dict for super_admin role."""
    import asyncio
    monkeypatch.setattr(config_module.settings, "jwt_secret", "test-secret")
    from app.auth import require_super_admin
    payload = {"sub": "1", "role": "super_admin"}
    result = asyncio.run(require_super_admin(payload))
    assert result == payload
