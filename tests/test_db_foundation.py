import sqlite3

import pytest
import app.config as config_module
from cryptography.fernet import Fernet

from app.db import get_connection, init_schema
from app.crypto import encrypt_token, decrypt_token


def test_schema_creates_all_tables(tmp_path):
    """DB-01: init_schema creates all four tables."""
    db = str(tmp_path / "test.db")
    init_schema(db)
    conn = sqlite3.connect(db)
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert {"tenants", "pages", "page_configs", "qa_items"} <= tables
    conn.close()


def test_wal_mode_enabled(tmp_path):
    """DB-01: WAL mode is set on a file-based DB."""
    db = str(tmp_path / "test.db")
    init_schema(db)
    conn = sqlite3.connect(db)
    result = conn.execute("PRAGMA journal_mode").fetchone()
    assert result == ("wal",)
    conn.close()


def test_busy_timeout(tmp_path):
    """DB-01: busy_timeout=5000 is set on connections from get_connection()."""
    db = str(tmp_path / "test.db")
    init_schema(db)
    conn = get_connection(db)
    result = conn.execute("PRAGMA busy_timeout").fetchone()
    assert result[0] == 5000
    conn.close()


def test_fernet_round_trip(monkeypatch):
    """DB-01: encrypt_token/decrypt_token round-trip returns original value."""
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(config_module.settings, "fernet_key", key)
    assert decrypt_token(encrypt_token("test_page_access_token")) == "test_page_access_token"


def test_schema_idempotent(tmp_path):
    """DB-01: calling init_schema twice does not raise."""
    db = str(tmp_path / "test.db")
    init_schema(db)
    init_schema(db)  # must not raise


def test_decrypt_token_invalid_ciphertext(monkeypatch):
    """Decrypting a corrupted ciphertext raises ValueError, not InvalidToken."""
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(config_module.settings, "fernet_key", key)
    with pytest.raises(ValueError, match="decryption failed"):
        decrypt_token("this-is-not-valid-ciphertext")


def test_decrypt_token_wrong_key(monkeypatch):
    """Decrypting with the wrong key raises ValueError."""
    key1 = Fernet.generate_key().decode()
    key2 = Fernet.generate_key().decode()
    monkeypatch.setattr(config_module.settings, "fernet_key", key1)
    ciphertext = encrypt_token("secret")
    monkeypatch.setattr(config_module.settings, "fernet_key", key2)
    with pytest.raises(ValueError, match="decryption failed"):
        decrypt_token(ciphertext)
