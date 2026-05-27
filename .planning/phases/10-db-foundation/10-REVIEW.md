---
phase: 10-db-foundation
reviewed: 2026-05-27T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - .env.example
  - .gitignore
  - app/config.py
  - app/crypto.py
  - app/db.py
  - requirements.txt
  - scripts/init_db.py
  - tests/test_db_foundation.py
findings:
  critical: 2
  warning: 5
  info: 2
  total: 9
status: fixed
---

# Phase 10: Code Review Report

**Reviewed:** 2026-05-27T00:00:00Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

This phase introduces SQLite persistence (`app/db.py`), Fernet-based token encryption (`app/crypto.py`), updated configuration (`app/config.py`), an init script, and a test suite. The schema design and WAL/PRAGMA setup are structurally sound. The `CREATE TABLE IF NOT EXISTS` pattern is correctly idempotent, WAL mode is set on the connection before `executescript`, and `busy_timeout`/`foreign_keys` are correctly applied per-connection in `get_connection`.

Two blockers require fixes before this code ships: `decrypt_token` will crash with an unhandled exception on bad ciphertext, and the empty-string default for `fernet_key` means misconfigured deployments fail with an obscure `ValueError` from deep inside the cryptography library rather than a clear startup error. Five warnings cover a connection leak in `init_schema`, a schema integrity gap in `qa_items`, and three missing test cases that leave the crypto error paths entirely untested.

---

## Critical Issues

### CR-01: `decrypt_token` does not catch `InvalidToken` — crashes caller on bad ciphertext

**File:** `app/crypto.py:16`

**Issue:** `decrypt_token` calls `_fernet().decrypt(enc.encode())` with no exception handling. If the stored ciphertext is corrupted, was encrypted with a different key, or the `FERNET_KEY` is rotated without re-encrypting existing rows, `cryptography.fernet.InvalidToken` is raised and propagates uncaught. The import on line 1 imports `InvalidToken` but never uses it, confirming this was the intended guard that was never wired in. Any caller — including a future route handler — will receive an unhandled 500 with no actionable message.

**Fix:**
```python
from cryptography.fernet import Fernet, InvalidToken

def decrypt_token(enc: str) -> str:
    try:
        return _fernet().decrypt(enc.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Token decryption failed: invalid ciphertext or wrong key") from exc
```

The caller is then responsible for catching `ValueError` and surfacing an appropriate HTTP error or fallback. The key point is that `InvalidToken` must not propagate as an unhandled exception past the module boundary.

---

### CR-02: Empty `fernet_key` default is silently accepted — `ValueError` raised at first use with no context

**File:** `app/config.py:10`, `app/crypto.py:8`

**Issue:** `fernet_key: str = ""` in `Settings` means a deployment that forgets `FERNET_KEY` in `.env` will start successfully but crash the first time any code calls `encrypt_token` or `decrypt_token`. The error is `ValueError: Fernet key must be 32 url-safe base64-encoded bytes` thrown from inside `_fernet()` with no indication that the root cause is a missing config variable. This is a misconfiguration-causes-runtime-crash pattern that should be caught at startup.

**Fix — option A (preferred): validate at config load time using a Pydantic validator:**
```python
from pydantic import field_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str = ""
    app_env: str = "development"
    app_port: int = 8000
    vault_path: str = ""
    db_path: str = "govi.db"
    fernet_key: str = ""

    @field_validator("fernet_key")
    @classmethod
    def fernet_key_must_be_set(cls, v: str) -> str:
        if not v:
            raise ValueError("FERNET_KEY must be set in .env")
        return v

    model_config = {"env_file": ".env"}
```

**Fix — option B (minimal): guard in `_fernet()`:**
```python
def _fernet() -> Fernet:
    if not settings.fernet_key:
        raise RuntimeError("FERNET_KEY is not configured. Set it in .env.")
    return Fernet(settings.fernet_key.encode())
```

Option A is preferred because it fails at import/startup rather than at the first encrypt/decrypt call.

---

## Warnings

### WR-01: `init_schema` leaks connection on exception

**File:** `app/db.py:13-62`

**Issue:** `init_schema` calls `get_connection`, then `conn.execute`, `conn.executescript`, `conn.commit`, and `conn.close`. If `executescript` or `commit` raises (e.g., disk full, permissions error), `conn.close()` is never reached. Python's garbage collector will eventually close it, but in long-running processes or test runners, this can exhaust file descriptors.

**Fix:** Use a `try/finally` block:
```python
def init_schema(db_path: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tenants ( ... );
            ...
        """)
        conn.commit()
    finally:
        conn.close()
```

---

### WR-02: `qa_items.category_id` has no type constraint — a `question` row can reference another `question` as its parent

**File:** `app/db.py:51`

**Issue:** The schema enforces `type IN ('category', 'question')` on `qa_items.type`, but there is no constraint preventing a `question` row from setting `category_id` to another `question` row's `id`. This means the tree structure can silently become malformed at the data layer. Any code that renders the menu tree will need to defensively handle this case.

**Fix:** Add a CHECK constraint that enforces the parent must be a category. SQLite does not support subquery CHECK constraints natively, but the business rule can be enforced at the application layer with a trigger or by convention. At minimum, document this limitation in a comment:
```sql
-- category_id must reference a row where type='category'; enforced at application layer
category_id INTEGER REFERENCES qa_items(id),
```
If strict enforcement is required, add an `AFTER INSERT OR UPDATE` trigger that validates `category_id` points to a `type='category'` row.

---

### WR-03: `InvalidToken` is imported but never used

**File:** `app/crypto.py:1`

**Issue:** `from cryptography.fernet import Fernet, InvalidToken` — `InvalidToken` is imported but not referenced anywhere in the file. This is a dead import that signals the error-handling code was intended but not written (confirmed by CR-01). Until CR-01 is fixed, this import is misleading because it implies the error is handled.

**Fix:** Either remove the import (if the guard is not added), or wire it into `decrypt_token` as described in CR-01. Do not leave it as an orphaned import.

---

### WR-04: No test for `decrypt_token` with invalid/corrupted ciphertext

**File:** `tests/test_db_foundation.py`

**Issue:** `test_fernet_round_trip` only tests the happy path. There is no test that calls `decrypt_token` with a corrupted ciphertext or a ciphertext encrypted with a different key. After CR-01 is fixed, the new error-handling path has zero test coverage.

**Fix:**
```python
import pytest
from cryptography.fernet import Fernet

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
```

---

### WR-05: No test for `init_schema` idempotency (called twice on the same DB)

**File:** `tests/test_db_foundation.py`

**Issue:** `CREATE TABLE IF NOT EXISTS` should make `init_schema` idempotent, but this is not tested. If a future migration accidentally changes the DDL to a plain `CREATE TABLE`, a second call would raise `sqlite3.OperationalError: table already exists`. The idempotency guarantee is a contract worth testing explicitly.

**Fix:**
```python
def test_schema_idempotent(tmp_path):
    """DB-01: calling init_schema twice does not raise."""
    db = str(tmp_path / "test.db")
    init_schema(db)
    init_schema(db)  # must not raise
```

---

## Info

### IN-01: Parameterized query enforcement is comment-only

**File:** `app/db.py:4`

**Issue:** The comment `# get_connection — callers MUST use ? placeholders, never f-strings, for SQL parameters` is the only guard against SQL injection. `get_connection` returns a raw `sqlite3.Connection` with no wrapper that enforces this. A future caller who misses the comment can construct an injectable query. This is acceptable for the current scope (all callers are internal), but the risk grows as the codebase expands.

**Fix:** No immediate code change required. When query helper functions are introduced (e.g., in a DAO layer), wrap `execute` to reject string interpolation patterns, or adopt a typed query builder. Document this constraint in `CONCERNS.md` if that file is created.

---

### IN-02: `_fernet()` re-instantiates `Fernet` on every call

**File:** `app/crypto.py:7-8`

**Issue:** `_fernet()` calls `Fernet(settings.fernet_key.encode())` on every `encrypt_token` and `decrypt_token` invocation. `Fernet.__init__` decodes and validates the key on each call. For the current call volume this is negligible, but the pattern is inconsistent with how the Anthropic client is documented as a known anti-pattern in `CLAUDE.md`. The key never changes at runtime, so re-instantiation has no benefit.

**Fix:** Cache the instance at module level, similar to the `settings` singleton pattern:
```python
from functools import lru_cache

@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    return Fernet(settings.fernet_key.encode())
```
Note: apply this only after CR-02 is fixed so that the guard runs before caching.

---

_Reviewed: 2026-05-27T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
