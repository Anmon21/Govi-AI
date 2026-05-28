# Phase 11: Auth & Tenant Management API - Pattern Map

**Mapped:** 2026-05-27
**Files analyzed:** 9 (3 new, 6 modified)
**Analogs found:** 9 / 9

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/auth.py` | utility/middleware | request-response | `app/crypto.py` | role-match (secret-guard + pure-function pattern) |
| `app/routers/auth.py` | router | request-response | `app/routers/ai.py` | exact (APIRouter + inline Pydantic + HTTPException) |
| `app/routers/tenants.py` | router | CRUD | `app/routers/ai.py` + `app/routers/health.py` | role-match |
| `app/config.py` | config | — | `app/config.py` itself | exact (add 3 fields to existing Settings) |
| `app/db.py` | model/schema | — | `app/db.py` itself | exact (extend CREATE TABLE tenants DDL) |
| `app/main.py` | config | — | `app/main.py` itself | exact (add two include_router calls) |
| `scripts/init_db.py` | utility | batch | `scripts/init_db.py` itself | exact (extend with idempotent seed logic) |
| `requirements.txt` | config | — | `requirements.txt` itself | exact (append two entries) |
| `tests/test_auth.py` | test | request-response | `tests/test_db_foundation.py` + `tests/test_health.py` | role-match |

---

## Pattern Assignments

### `app/auth.py` (utility, secret-guard + token operations)

**Analog:** `app/crypto.py`

**Imports pattern** (`app/crypto.py` lines 1-3):
```python
from cryptography.fernet import Fernet, InvalidToken

from app.config import settings
```
Copy the same import structure — `from app.config import settings` at module level, no `__init__` re-export.

**Secret-guard pattern** (`app/crypto.py` lines 7-10):
```python
def _fernet() -> Fernet:
    if not settings.fernet_key:
        raise RuntimeError("FERNET_KEY is not configured. Set it in .env.")
    return Fernet(settings.fernet_key.encode())
```
Apply the identical guard to `create_access_token()`: check `if not settings.jwt_secret` and raise `RuntimeError("JWT_SECRET is not configured. Set it in .env.")`.

**Error-wrapping pattern** (`app/crypto.py` lines 17-21):
```python
def decrypt_token(enc: str) -> str:
    try:
        return _fernet().decrypt(enc.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Token decryption failed: invalid ciphertext or wrong key") from exc
```
Mirror this in `verify_token()`: catch `jwt.ExpiredSignatureError` and `jwt.InvalidTokenError`, re-raise as `HTTPException` (not `ValueError` — auth context requires HTTP semantics).

**No analog in codebase for:** `OAuth2PasswordBearer`, `Depends` FastAPI patterns — use the RESEARCH.md skeleton verbatim for those sections.

---

### `app/routers/auth.py` (router, request-response)

**Analog:** `app/routers/ai.py`

**Imports pattern** (`app/routers/ai.py` lines 1-6):
```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import anthropic

from app.config import settings
```
Copy structure. Replace `import anthropic` with:
```python
from passlib.context import CryptContext
from app.auth import create_access_token
from app.db import get_connection
```

**Router declaration pattern** (`app/routers/ai.py` line 7):
```python
router = APIRouter(prefix="/ai", tags=["ai"])
```
New file uses: `router = APIRouter(prefix="/auth", tags=["auth"])`

**Inline Pydantic model pattern** (`app/routers/ai.py` lines 10-21):
```python
class ChatRequest(BaseModel):
    message: str
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 1024


class ChatResponse(BaseModel):
    reply: str
    model: str
    input_tokens: int
    output_tokens: int
```
Define `LoginRequest` and `TokenResponse` inline in the same file, same style. No imports from a separate models file.

**Guard-before-external-call pattern** (`app/routers/ai.py` lines 25-27):
```python
if not settings.anthropic_api_key:
    raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")
```
The auth router does NOT apply this guard inline — the guard lives in `app/auth.py:create_access_token()` as a `RuntimeError`. The router raises `HTTPException(status_code=401, detail="Invalid credentials")` only for bad login.

**Async route with response_model pattern** (`app/routers/ai.py` lines 23-42):
```python
@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    ...
    return ChatResponse(...)
```
New route: `@router.post("/login", response_model=TokenResponse)` — same decorator + async + return model instance pattern.

**DB connection: use try/finally to close** (established pattern from `app/db.py` lines 14-15, `init_schema` uses try/finally):
```python
conn = get_connection(settings.db_path)
try:
    row = conn.execute("SELECT ...", (...,)).fetchone()
finally:
    conn.close()
```
Password verification happens AFTER `conn.close()` — no DB handle needed for bcrypt step.

---

### `app/routers/tenants.py` (router, CRUD)

**Analog:** `app/routers/ai.py` (router structure) + `app/routers/health.py` (simple inline models)

**Router declaration pattern** (`app/routers/health.py` line 9):
```python
router = APIRouter(prefix="/health", tags=["health"])
```
This file uses two logical prefixes: `/admin/tenants` for super-admin CRUD and `/tenants` for client self-info. Declare routes with full paths rather than a single prefix:
```python
router = APIRouter(tags=["tenants"])
```

**Inline Pydantic model pattern** (`app/routers/health.py` lines 12-16):
```python
class HealthResponse(BaseModel):
    status: str
    vault_loaded: bool
    content_count: int


@router.get("", response_model=HealthResponse)
```
Define all tenant request/response models inline: `CreateTenantRequest`, `TenantResponse`, `TenantListItem`. Never include `password_hash` in any response model.

**Depends injection pattern** (no existing analog in codebase — use RESEARCH.md):
```python
from app.auth import get_current_tenant, require_super_admin
from fastapi import Depends

@router.get("/admin/tenants")
async def list_tenants(current: dict = Depends(require_super_admin)):
    ...

@router.get("/tenants/me")
async def get_my_tenant(current: dict = Depends(get_current_tenant)):
    ...
```

**Raw SQL + `?` placeholder pattern** (`app/db.py` lines 17-62):
All queries use `conn.execute("... WHERE id = ?", (value,))` — never f-strings. Follow exact same style for all tenant queries.

**HTTPException error pattern** (`app/routers/ai.py` line 26):
```python
raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")
```
Tenant router uses same raise style: 404 for not-found, 409 for duplicate email, 403 for self-delete guard.

---

### `app/config.py` (config, add 3 fields)

**Analog:** `app/config.py` itself

**Existing field pattern** (`app/config.py` lines 4-12):
```python
class Settings(BaseSettings):
    anthropic_api_key: str = ""
    app_env: str = "development"
    app_port: int = 8000
    vault_path: str = ""
    db_path: str = "govi.db"
    fernet_key: str = ""

    model_config = {"env_file": ".env"}
```
Add three fields using the exact same `fieldname: str = ""` convention (no `Field(...)`, no `Optional`, empty string default — matching `fernet_key` style):
```python
    jwt_secret: str = ""
    super_admin_email: str = ""
    super_admin_password: str = ""
```

---

### `app/db.py` (schema, add `is_super_admin` column)

**Analog:** `app/db.py` itself

**Existing DDL column pattern** (`app/db.py` lines 19-24):
```python
CREATE TABLE IF NOT EXISTS tenants (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
```
Add `is_super_admin` column following the existing `INTEGER NOT NULL DEFAULT N` style, positioned before `created_at`:
```sql
    is_super_admin INTEGER NOT NULL DEFAULT 0,
```
Schema uses `CREATE TABLE IF NOT EXISTS` — this is a full reset path (dev DB), not a migration. Adding the column to the DDL and re-running `init_db.py` is the correct approach per D-02.

---

### `app/main.py` (config, add 2 routers)

**Analog:** `app/main.py` itself

**Existing router registration pattern** (`app/main.py` lines 6, 25-27):
```python
from app.routers import health, ai, content

app.include_router(health.router)
app.include_router(ai.router)
app.include_router(content.router)
```
Add to the import line and append two `include_router` calls in the same style:
```python
from app.routers import health, ai, content, auth, tenants

app.include_router(auth.router)
app.include_router(tenants.router)
```
No prefix overrides needed at registration — prefixes are declared in each router file.

---

### `scripts/init_db.py` (utility, batch seed)

**Analog:** `scripts/init_db.py` itself

**Existing pattern** (`scripts/init_db.py` lines 1-11):
```python
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import init_schema
from app.config import settings

if __name__ == "__main__":
    init_schema(settings.db_path)
    print(f"Schema initialized at {settings.db_path}")
```
Extend the `if __name__ == "__main__"` block: after `init_schema(settings.db_path)`, open a connection, run the idempotent seed, close it. Add two env-var guards before the seed (same `RuntimeError` raise style as `app/crypto.py`):
```python
if not settings.super_admin_email or not settings.super_admin_password:
    raise RuntimeError("SUPER_ADMIN_EMAIL and SUPER_ADMIN_PASSWORD must be set in .env.")
```
Then the idempotent insert (from RESEARCH.md Pattern 6).

---

### `tests/test_auth.py` (test, new file)

**Analog:** `tests/test_db_foundation.py` + `tests/conftest.py`

**Import pattern** (`tests/test_db_foundation.py` lines 1-8):
```python
import sqlite3

import pytest
import app.config as config_module
from cryptography.fernet import Fernet

from app.db import get_connection, init_schema
from app.crypto import encrypt_token, decrypt_token
```
New test file imports:
```python
import pytest
import app.config as config_module
from fastapi.testclient import TestClient
from app.main import app
from app.db import init_schema, get_connection
from app.auth import create_access_token
```

**monkeypatch settings pattern** (`tests/test_db_foundation.py` lines 44-47):
```python
def test_fernet_round_trip(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(config_module.settings, "fernet_key", key)
    assert decrypt_token(encrypt_token("test_page_access_token")) == "test_page_access_token"
```
Tests that exercise `create_access_token()` or protected routes must `monkeypatch.setattr(config_module.settings, "jwt_secret", "test-secret")` before any call — same pattern.

**TestClient fixture pattern** (`tests/conftest.py` lines 14-22):
```python
@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
    content_module._vault.clear()
    content_module._vault.update(content_module.load_vault())
    with TestClient(app) as c:
        yield c
    content_module._vault.clear()
```
New `db_client` fixture for auth tests:
```python
@pytest.fixture
def db_client(tmp_path, monkeypatch):
    db = str(tmp_path / "test.db")
    monkeypatch.setattr(config_module.settings, "db_path", db)
    monkeypatch.setattr(config_module.settings, "jwt_secret", "test-secret")
    init_schema(db)
    # seed super-admin row here
    with TestClient(app) as c:
        yield c
```

**TestClient explicit headers pattern** (no existing analog — from RESEARCH.md Pitfall 7):
Protected route tests must pass explicit headers; `TestClient` carries no session state:
```python
headers = {"Authorization": f"Bearer {token}"}
resp = client.get("/admin/tenants", headers=headers)
```

**Docstring pattern** (`tests/test_db_foundation.py` line 12):
```python
def test_schema_creates_all_tables(tmp_path):
    """DB-01: init_schema creates all four tables."""
```
Each test function includes a one-line docstring with the requirement ID (SC-1 through SC-5, TENANT-01 through TENANT-03).

---

## Shared Patterns

### Secret-Guard (RuntimeError on empty env var)
**Source:** `app/crypto.py` lines 7-10
**Apply to:** `app/auth.py:create_access_token()`, `scripts/init_db.py` (seed block)
```python
if not settings.fernet_key:
    raise RuntimeError("FERNET_KEY is not configured. Set it in .env.")
```
Copy the exact raise message format: `"<VAR_NAME> is not configured. Set it in .env."`

### APIRouter Declaration
**Source:** `app/routers/ai.py` line 7 and `app/routers/health.py` line 9
**Apply to:** `app/routers/auth.py`, `app/routers/tenants.py`
```python
router = APIRouter(prefix="/prefix", tags=["tag"])
```
One `router` object per file. No sub-routers.

### Inline Pydantic Models
**Source:** `app/routers/ai.py` lines 10-21, `app/routers/health.py` lines 12-16
**Apply to:** `app/routers/auth.py`, `app/routers/tenants.py`
All request/response models are defined in the same file as the routes that use them. No separate `schemas.py` or `models.py`.

### Raw SQL with `?` Placeholders
**Source:** `app/db.py` lines 17-62
**Apply to:** `app/routers/auth.py`, `app/routers/tenants.py`, `scripts/init_db.py`
```python
conn.execute("SELECT id FROM tenants WHERE email = ?", (email,))
```
Never use f-strings or `.format()` for SQL parameters.

### DB Connection try/finally
**Source:** `app/db.py` lines 14-15 (`init_schema` try/finally block)
**Apply to:** `app/routers/auth.py`, `app/routers/tenants.py`
```python
conn = get_connection(settings.db_path)
try:
    row = conn.execute(...).fetchone()
finally:
    conn.close()
```
Every function that opens a connection must close it in a `finally` block.

### HTTPException Error Responses
**Source:** `app/routers/ai.py` line 26
**Apply to:** `app/routers/auth.py`, `app/routers/tenants.py`, `app/auth.py`
```python
raise HTTPException(status_code=N, detail="descriptive message")
```
401 responses on protected routes must include `headers={"WWW-Authenticate": "Bearer"}`.

### Settings Import
**Source:** `app/routers/ai.py` line 6, `app/crypto.py` line 3
**Apply to:** All new `app/` files
```python
from app.config import settings
```
Always imported as the module-level singleton. Never instantiated locally.

### monkeypatch Settings in Tests
**Source:** `tests/test_db_foundation.py` lines 44-47, `tests/conftest.py` lines 17-18
**Apply to:** `tests/test_auth.py`, `tests/conftest.py` (new `db_client` fixture)
```python
monkeypatch.setattr(config_module.settings, "fieldname", "value")
```
Required for any test touching `jwt_secret`, `super_admin_email`, `super_admin_password`, or `db_path`.

---

## No Analog Found

All files have analogs. No entries.

---

## Metadata

**Analog search scope:** `app/`, `app/routers/`, `scripts/`, `tests/`
**Files scanned:** 10 (`app/crypto.py`, `app/config.py`, `app/db.py`, `app/main.py`, `app/routers/ai.py`, `app/routers/health.py`, `scripts/init_db.py`, `tests/conftest.py`, `tests/test_db_foundation.py`, `tests/test_health.py`)
**Pattern extraction date:** 2026-05-27
