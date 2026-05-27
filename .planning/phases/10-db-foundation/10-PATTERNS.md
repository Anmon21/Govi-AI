# Phase 10: DB Foundation - Pattern Map

**Mapped:** 2026-05-27
**Files analyzed:** 6
**Analogs found:** 5 / 6

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/db.py` | utility | CRUD (connection factory + DDL) | `app/routers/content.py` (load_vault pattern) | role-partial |
| `app/crypto.py` | utility | transform (encrypt/decrypt) | `app/routers/ai.py` (external client wrapper) | role-partial |
| `app/config.py` | config | — | `app/config.py` (self — surgical addition) | exact |
| `scripts/init_db.py` | utility (CLI script) | batch (one-shot DDL runner) | `main.py` (project root runner) | role-match |
| `requirements.txt` | config | — | `requirements.txt` (self — line addition) | exact |
| `tests/test_db_foundation.py` | test | — | `tests/test_health.py` + `tests/test_content.py` | role-match |

---

## Pattern Assignments

### `app/config.py` (config — surgical addition)

**Analog:** `app/config.py` (self — add two fields only, touch nothing else)

**Existing class** (lines 1–13, read entire file):
```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    app_env: str = "development"
    app_port: int = 8000
    vault_path: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
```

**Addition pattern — insert two new fields after `vault_path`:**
```python
    db_path: str = "govi.db"
    fernet_key: str = ""
```

**Rules:**
- Field names are snake_case (matches `anthropic_api_key`, `vault_path`).
- Default values are strings, not `None` — consistent with existing optional fields (`vault_path: str = ""`).
- Do NOT change `model_config`, `settings = Settings()`, or any existing field.
- No type imports needed — `str` is a builtin.

---

### `app/db.py` (utility, CRUD — connection factory + DDL)

**No exact analog exists.** The project has no existing DB module. Use the verified patterns from RESEARCH.md directly.

**Imports pattern** — follow `app/routers/ai.py` import style (stdlib first, then project):
```python
import sqlite3

from app.config import settings
```

**Core pattern — connection factory:**
```python
def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
```

**Key points (from RESEARCH.md verified patterns):**
- `check_same_thread=False` — required for FastAPI async context.
- `row_factory = sqlite3.Row` — enables `dict(row)` access in callers.
- WAL mode persists at the file level; still set it in `get_connection()` so the first connection after `init_schema()` is consistent — OR set WAL only in `init_schema()` (per RESEARCH.md Pitfall 4 guidance). Planner should choose: set WAL only in `init_schema()` and omit it from `get_connection()`.
- `foreign_keys=ON` must be set on every connection (resets to OFF per new connection).
- `busy_timeout=5000` must be set on every connection.

**Core pattern — idempotent schema init:**
```python
def init_schema(db_path: str) -> None:
    conn = get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tenants (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            email         TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            is_active     INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        );

        CREATE TABLE IF NOT EXISTS pages (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id        INTEGER NOT NULL REFERENCES tenants(id),
            page_fb_id       TEXT    NOT NULL UNIQUE,
            page_name        TEXT    NOT NULL,
            access_token_enc TEXT,
            is_active        INTEGER NOT NULL DEFAULT 1,
            created_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        );

        CREATE TABLE IF NOT EXISTS page_configs (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            page_id            INTEGER NOT NULL UNIQUE REFERENCES pages(id),
            welcome_text       TEXT    NOT NULL DEFAULT '',
            menu_json          TEXT    NOT NULL DEFAULT '[]',
            escalation_psid    TEXT,
            escalation_message TEXT,
            updated_at         TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        );

        CREATE TABLE IF NOT EXISTS qa_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            page_id     INTEGER NOT NULL REFERENCES pages(id),
            type        TEXT    NOT NULL CHECK(type IN ('category', 'question')),
            title       TEXT    NOT NULL,
            body        TEXT    NOT NULL DEFAULT '',
            category_id INTEGER REFERENCES qa_items(id),
            enabled     INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        );

        CREATE INDEX IF NOT EXISTS idx_pages_tenant_id      ON pages(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_page_configs_page_id ON page_configs(page_id);
        CREATE INDEX IF NOT EXISTS idx_qa_items_page_id     ON qa_items(page_id);
        CREATE INDEX IF NOT EXISTS idx_qa_items_category_id ON qa_items(category_id);
    """)
    conn.commit()
    conn.close()
```

**Style rules:**
- 4-space indent (matches all existing Python files).
- Short inline comments using em-dash style if needed: `# Connection factory — applies all per-connection PRAGMAs`.
- Module exposes two plain functions: `get_connection` and `init_schema`. No class wrapper.
- No `__all__` needed — consistent with `app/routers/health.py` and `app/config.py` which export via plain assignment.

---

### `app/crypto.py` (utility, transform — Fernet encrypt/decrypt)

**Closest analog:** `app/routers/ai.py` — thin wrapper around an external SDK client, loads key from `settings`, one function per operation.

**Analog pattern from `app/routers/ai.py` (lines 1–6, 25–28):**
```python
# External client loaded from settings, used inside a function (not at module level)
from app.config import settings

if not settings.anthropic_api_key:
    raise HTTPException(...)
client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
```

**Imports pattern** — follow `app/routers/ai.py` style:
```python
from cryptography.fernet import Fernet, InvalidToken

from app.config import settings
```

**Core pattern:**
```python
def _fernet() -> Fernet:
    return Fernet(settings.fernet_key.encode())


def encrypt_token(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_token(enc: str) -> str:
    return _fernet().decrypt(enc.encode()).decode()
```

**Key points:**
- `_fernet()` is a private helper — underscore prefix matches Python convention; no need to expose it.
- `InvalidToken` is re-exported implicitly by importing it — callers (Phase 12+) can catch it.
- Lazy key loading (not validated at startup) — consistent with RESEARCH.md Open Question 2 recommendation and with how `ai.py` guards the API key only at call time.
- No try/except in this file — consistent with existing Python router error handling pattern (`app/routers/ai.py` has no try/except; errors propagate).

---

### `scripts/init_db.py` (utility CLI script, batch)

**Closest analog:** `main.py` (project root) — a standalone Python script that imports from `app/` and runs a single action.

**Analog pattern from `main.py` (lines 1–5):**
```python
import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.app_port, reload=True)
```

**Pattern to copy:**
```python
from app.db import init_schema
from app.config import settings

if __name__ == "__main__":
    init_schema(settings.db_path)
    print(f"Schema initialized at {settings.db_path}")
```

**Style rules:**
- `if __name__ == "__main__"` guard — matches `main.py`.
- Absolute imports from `app/` — consistent with all Python files in the project.
- Single `print()` for confirmation output — no logging framework (Python side has no logging calls per CLAUDE.md conventions).
- No argparse — RESEARCH.md does not require CLI arguments; `DB_PATH` comes from `Settings`.

---

### `requirements.txt` (config — line addition)

**Analog:** `requirements.txt` (self — append one line only).

**Existing file** (lines 1–9):
```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
pydantic>=2.7.0
pydantic-settings>=2.3.0
python-dotenv>=1.0.0
httpx>=0.27.0
anthropic>=0.30.0
python-frontmatter>=1.1.0
pytest>=8.0.0
```

**Addition — append after `pytest>=8.0.0`:**
```
cryptography>=41.0.0
```

**Rules:**
- No version cap — consistent with all existing lines (all use `>=` lower bounds only).
- No blank line between entries — matches existing file format.
- `cryptography` not `pycryptodome` — per RESEARCH.md Standard Stack.

---

### `tests/test_db_foundation.py` (test)

**Closest analogs:**
- `tests/test_health.py` — simple pytest functions, no class, uses `monkeypatch` and `tmp_path`.
- `tests/test_content.py` — uses `tmp_path` for file-based state, helper function at top of file.

**Imports pattern from `tests/test_health.py` (lines 1–4):**
```python
import app.routers.content as content_module
import app.config as config_module
from fastapi.testclient import TestClient
from app.main import app
```

**Adapted imports for DB tests:**
```python
import sqlite3

import pytest

from app.db import get_connection, init_schema
from app.crypto import encrypt_token, decrypt_token
```

**Test structure pattern from `tests/test_health.py` (lines 7–19):**
```python
def test_health_includes_vault_stats(monkeypatch):
    """VAULT-01: GET /health response includes status, vault_loaded, and content_count."""
    monkeypatch.setattr(config_module.settings, "vault_path", "")
    ...
    assert resp.status_code == 200
```

**Pattern to copy for DB tests:**
```python
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
    from cryptography.fernet import Fernet
    import app.config as config_module
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(config_module.settings, "fernet_key", key)
    plain = "test_page_access_token"
    assert decrypt_token(encrypt_token(plain)) == plain
```

**Style rules (from test analogs):**
- Docstring per test using the requirement ID format: `"""DB-01: description."""`.
- `tmp_path` fixture for file-based DB tests — never use `:memory:` for WAL mode tests (RESEARCH.md Pitfall 2).
- `monkeypatch` for settings overrides — matches `test_health.py` and `test_content.py`.
- No test class — all tests are plain functions (consistent with entire existing test suite).
- No `conftest.py` additions needed — `tmp_path` and `monkeypatch` are pytest builtins.

---

## Shared Patterns

### Settings Singleton Import
**Source:** `app/config.py` line 13; used in `app/routers/ai.py` line 5 and `app/routers/health.py` line 5.
**Apply to:** `app/db.py`, `app/crypto.py`, `scripts/init_db.py`
```python
from app.config import settings
```

### Absolute Imports from `app/`
**Source:** Every existing Python file in the project.
**Apply to:** All new files.
```python
# Correct
from app.config import settings
from app.db import init_schema

# Wrong — never use relative imports
from .config import settings
```

### 4-Space Indentation, No Formatter Config
**Source:** All existing Python files — verified by reading `app/config.py`, `app/routers/ai.py`, `app/routers/health.py`.
**Apply to:** All new Python files.

### snake_case Module Files
**Source:** `app/config.py`, `app/routers/ai.py`, `app/routers/health.py`, `app/routers/content.py`.
**Apply to:** `app/db.py`, `app/crypto.py`, `scripts/init_db.py`, `tests/test_db_foundation.py` — all already snake_case.

### No Logging on Python Side
**Source:** CLAUDE.md Logging section — "Python side: no logging calls present."
**Apply to:** `app/db.py`, `app/crypto.py`.
Use `print()` only in `scripts/init_db.py` (CLI output), not in library modules.

### Error Handling — No try/except in Library Modules
**Source:** `app/routers/ai.py` — no try/except; errors propagate.
**Apply to:** `app/db.py`, `app/crypto.py`.
- `app/db.py`: Let `sqlite3.OperationalError` and `sqlite3.IntegrityError` propagate to callers.
- `app/crypto.py`: Let `cryptography.fernet.InvalidToken` and `ValueError` propagate to callers (Phase 12 will handle them).

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `app/db.py` | utility | CRUD | No DB module exists; closest analog is content.py (vault loader) but data flow is different enough that RESEARCH.md patterns are the primary reference |

---

## Metadata

**Analog search scope:** `/Users/anmon/Desktop/Govi-AI/app/`, `/Users/anmon/Desktop/Govi-AI/tests/`, `/Users/anmon/Desktop/Govi-AI/main.py`
**Files scanned:** 9 Python files (config.py, main.py, routers/ai.py, routers/health.py, routers/content.py, main.py root, tests/conftest.py, tests/test_health.py, tests/test_content.py)
**Pattern extraction date:** 2026-05-27
