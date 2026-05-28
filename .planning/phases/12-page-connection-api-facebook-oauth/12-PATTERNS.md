# Phase 12: Page Connection API + Facebook OAuth - Pattern Map

**Mapped:** 2026-05-28
**Files analyzed:** 6 (3 new, 2 modified, 1 env file)
**Analogs found:** 5 / 6

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/routers/pages.py` | router | request-response + CRUD | `app/routers/tenants.py` | exact |
| `app/fb_client.py` | utility/service | request-response (outbound HTTP) | `app/crypto.py` (thin helper module pattern) | role-match |
| `tests/test_pages.py` | test | — | `tests/test_auth.py` | exact |
| `app/main.py` | config (mount) | — | self (1-line addition) | exact |
| `app/config.py` | config | — | self (3-field addition) | exact |
| `.env.example` | config | — | `.env.example` (root) | exact |

---

## Pattern Assignments

### `app/routers/pages.py` (router, request-response + CRUD)

**Analog:** `app/routers/tenants.py`

**Imports pattern** (`app/routers/tenants.py` lines 1-7):
```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import get_current_tenant
from app.config import settings
from app.db import get_connection
```

Additional imports needed for pages.py (not in tenants.py):
```python
import secrets
import jwt
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from fastapi.responses import RedirectResponse
from typing import Literal
from app.crypto import encrypt_token, decrypt_token
from app import fb_client  # new module
```

**Router declaration pattern** (`app/routers/auth.py` line 9):
```python
router = APIRouter(prefix="/auth", tags=["auth"])
```
Pages router should use no prefix (like tenants.py line 10) since it mixes `/auth/facebook/*` and `/pages/*` paths:
```python
router = APIRouter(tags=["pages"])
```

**Inline Pydantic response model pattern** (`app/routers/tenants.py` lines 15-38):
```python
class TenantResponse(BaseModel):
    id: int
    email: str
    is_active: bool
    is_super_admin: bool
    created_at: str

class DeleteResponse(BaseModel):
    detail: str
    pages_deactivated: int
```
Pages analog — define inline in the same file:
```python
class PageResponse(BaseModel):
    id: int
    page_fb_id: str
    page_name: str
    status: Literal["active", "revoked"]
    created_at: str

class HealthResponse(BaseModel):
    is_valid: bool
    expires_at: int | None
```

**Auth dependency pattern** (`app/routers/tenants.py` lines 41-45):
```python
@router.post("/admin/tenants", response_model=TenantResponse, status_code=201)
async def create_tenant(
    request: CreateTenantRequest,
    current: dict = Depends(require_super_admin),
) -> TenantResponse:
```
Pages equivalent — all page endpoints use `get_current_tenant` (not `require_super_admin`):
```python
@router.get("/auth/facebook/start")
async def facebook_oauth_start(
    current: dict = Depends(get_current_tenant),
) -> RedirectResponse:
```

**DB connection pattern — try/finally** (`app/routers/tenants.py` lines 46-71):
```python
conn = get_connection(settings.db_path)
try:
    existing = conn.execute(
        "SELECT id FROM tenants WHERE email = ?", (request.email,)
    ).fetchone()
    if existing:
        raise HTTPException(status_code=409, detail="Email already exists")
    cur = conn.execute(
        "INSERT INTO tenants (email, password_hash, is_super_admin) VALUES (?, ?, 0)",
        (request.email, pwd_context.hash(request.password)),
    )
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute(
        "SELECT id, email, is_active, is_super_admin, created_at FROM tenants WHERE id = ?",
        (new_id,),
    ).fetchone()
finally:
    conn.close()
```
Copy this exact try/finally structure for all DB operations in pages.py. Use `?` placeholders, never f-strings.

**Cross-tenant isolation pattern** (`app/routers/tenants.py` lines 104-119):
```python
@router.delete("/admin/tenants/{tenant_id}", response_model=DeleteResponse)
async def delete_tenant(
    tenant_id: int,
    current: dict = Depends(require_super_admin),
) -> DeleteResponse:
    if tenant_id == int(current["sub"]):
        raise HTTPException(status_code=403, detail="Cannot delete your own account")
    conn = get_connection(settings.db_path)
    try:
        existing = conn.execute(
            "SELECT id FROM tenants WHERE id = ? AND is_active = 1 AND is_super_admin = 0",
            (tenant_id,),
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Tenant not found or already inactive")
```
Pages equivalent — every page query must include `tenant_id = ?` bound to `int(current["sub"])`:
```python
row = conn.execute(
    "SELECT id, page_fb_id, access_token_enc FROM pages WHERE id = ? AND tenant_id = ? AND is_active = 1",
    (page_id, int(current["sub"])),
).fetchone()
if not row:
    raise HTTPException(status_code=404, detail="Page not found")
```

**Soft-delete pattern** (`app/routers/tenants.py` lines 120-126):
```python
conn.execute("UPDATE tenants SET is_active = 0 WHERE id = ?", (tenant_id,))
pages_cur = conn.execute(
    "UPDATE pages SET is_active = 0 WHERE tenant_id = ?", (tenant_id,)
)
pages_deactivated = pages_cur.rowcount
conn.commit()
```
Pages disconnect equivalent:
```python
conn.execute("UPDATE pages SET is_active = 0 WHERE id = ? AND tenant_id = ?", (page_id, tenant_id))
conn.commit()
```

---

### `app/fb_client.py` (utility, outbound request-response)

**Analog:** `app/crypto.py` — thin helper module, pure functions, no FastAPI types.

**Module structure pattern** (`app/crypto.py` lines 1-21):
```python
from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _fernet() -> Fernet:
    if not settings.fernet_key:
        raise RuntimeError("FERNET_KEY is not configured. Set it in .env.")
    return Fernet(settings.fernet_key.encode())


def encrypt_token(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_token(enc: str) -> str:
    try:
        return _fernet().decrypt(enc.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Token decryption failed: invalid ciphertext or wrong key") from exc
```
fb_client.py follows the same shape: module-level constant + pure functions, imports `settings`:
```python
import httpx
from fastapi import HTTPException
from app.config import settings

GRAPH_BASE = "https://graph.facebook.com/v25.0"

def exchange_code_for_short_token(code: str) -> str: ...
def exchange_for_long_lived_token(short_token: str) -> str: ...
def get_user_pages(long_lived_token: str) -> list[dict]: ...
def subscribe_page_webhook(page_fb_id: str, page_access_token: str) -> None: ...
def unsubscribe_page_webhook(page_fb_id: str, page_access_token: str) -> None: ...
def check_token_health(page_access_token: str) -> bool: ...
```

**Error-check pattern after httpx** (from RESEARCH.md Pitfall 2 — no existing codebase analog):
```python
resp = httpx.get(...)
resp.raise_for_status()
data = resp.json()
if "error" in data:
    raise HTTPException(status_code=400, detail=data["error"]["message"])
```
Apply this to every `exchange_*` and `get_user_pages` call. `check_token_health` swallows errors (returns `False`), `unsubscribe_page_webhook` swallows errors (best-effort).

**Settings guard pattern** (`app/crypto.py` lines 7-10 / `app/auth.py` lines 15-17):
```python
# crypto.py pattern:
if not settings.fernet_key:
    raise RuntimeError("FERNET_KEY is not configured. Set it in .env.")

# auth.py pattern:
if not settings.jwt_secret:
    raise RuntimeError("JWT_SECRET is not configured. Set it in .env.")
```
Apply the same guard to the new settings fields used by fb_client.py:
```python
# In fb_client functions that need them:
if not settings.fb_app_id or not settings.fb_app_secret:
    raise RuntimeError("FACEBOOK_APP_ID / FACEBOOK_APP_SECRET not configured.")
```

---

### `tests/test_pages.py` (test)

**Analog:** `tests/test_auth.py` — closest match by fixture use, helper pattern, assertion style.

**Fixture use pattern** (`tests/test_auth.py` lines 42-59):
```python
def test_login_success(db_client):
    client = db_client.client
    email = db_client.super_admin_email
    password = db_client.super_admin_password
    sa_id = db_client.super_admin_id

    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
```
test_pages.py uses the same `db_client` fixture. The fixture must be extended (in `conftest.py`) to monkeypatch the three new settings fields and the `fernet_key`.

**Shared test helper pattern** (`tests/test_auth.py` lines 15-35):
```python
def _login(client, email, password) -> str:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"login failed: {resp.status_code} {resp.text}"
    return resp.json()["access_token"]

def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}

def _create_client(client, admin_token, email, password) -> dict:
    resp = client.post(
        "/admin/tenants",
        json={"email": email, "password": password},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 201, f"create_tenant failed: {resp.status_code} {resp.text}"
    return resp.json()
```
test_pages.py adds one analogous helper:
```python
def _connect_page(client, token, monkeypatch) -> dict:
    """Simulate the callback path with mocked httpx; returns page row dict."""
    ...
```

**Direct SQL seed pattern** (`tests/test_auth.py` lines 170-179):
```python
conn = get_connection(db_client.db_path)
try:
    conn.execute(
        "INSERT INTO pages (tenant_id, page_fb_id, page_name, is_active) VALUES (?, 'fb-123', 'Test Page', 1)",
        (c1_id,),
    )
    conn.commit()
finally:
    conn.close()
```
test_pages.py uses the same pattern to pre-seed `pages` rows with an encrypted token for LIST and HEALTH tests:
```python
conn = get_connection(db_client.db_path)
try:
    conn.execute(
        "INSERT INTO pages (tenant_id, page_fb_id, page_name, access_token_enc, is_active) "
        "VALUES (?, ?, ?, ?, 1)",
        (tenant_id, "fb-111", "Test Page", encrypt_token("fake-page-token")),
    )
    conn.commit()
finally:
    conn.close()
```

**Isolation assertion pattern** (`tests/test_auth.py` lines 256-289):
```python
token_a = _login(client, "a@test.local", "pass-a")
token_b = _login(client, "b@test.local", "pass-b")
resp_a = client.get("/tenants/me", headers=_auth_headers(token_a))
assert resp_a.json()["id"] == a_id
resp_b = client.get("/tenants/me", headers=_auth_headers(token_b))
assert resp_b.json()["id"] == b_id
assert body_a["id"] != body_b["id"]
```
test_pages.py replicates this pattern for `test_pages_isolation`: page seeded under tenant A must not appear in tenant B's `GET /pages` response.

**httpx mock pattern** (project uses `monkeypatch`; see `conftest.py` lines 22-27):
```python
monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
```
For tests that exercise fb_client calls, use `monkeypatch.setattr` on the `httpx` functions imported inside `app.fb_client`:
```python
monkeypatch.setattr("app.fb_client.httpx.get", lambda url, **kw: MockResponse(...))
monkeypatch.setattr("app.fb_client.httpx.post", lambda url, **kw: MockResponse(...))
monkeypatch.setattr("app.fb_client.httpx.delete", lambda url, **kw: MockResponse(...))
```
Define a `MockResponse` class in test_pages.py:
```python
class MockResponse:
    def __init__(self, json_data: dict, status_code: int = 200):
        self._json = json_data
        self.status_code = status_code
    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)
    def json(self):
        return self._json
```

---

### `app/main.py` (modify — 1-line router mount)

**Analog:** `app/main.py` line 9 and lines 30-34.

**Import line pattern** (`app/main.py` line 9):
```python
from app.routers import health, ai, content, auth, tenants
```
Change to:
```python
from app.routers import health, ai, content, auth, tenants, pages
```

**Router mount pattern** (`app/main.py` lines 30-34):
```python
app.include_router(health.router)
app.include_router(ai.router)
app.include_router(content.router)
app.include_router(auth.router)
app.include_router(tenants.router)
```
Append:
```python
app.include_router(pages.router)
```
No prefix argument — pages.py router has no APIRouter prefix (same as tenants.py).

---

### `app/config.py` (modify — 3 new fields)

**Analog:** `app/config.py` lines 1-18 (self).

**Field addition pattern** (`app/config.py` lines 4-16):
```python
class Settings(BaseSettings):
    anthropic_api_key: str = ""
    app_env: str = "development"
    app_port: int = 8000
    vault_path: str = ""
    db_path: str = "govi.db"
    fernet_key: str = ""
    jwt_secret: str = ""
    super_admin_email: str = ""
    super_admin_password: str = ""

    model_config = {"env_file": ".env"}
```
Add three fields before `model_config`, matching the existing snake_case naming and `str = ""` default pattern:
```python
    fb_app_id: str = ""
    fb_app_secret: str = ""
    fb_redirect_uri: str = ""
```
Pydantic-settings maps `FB_APP_ID` → `fb_app_id` automatically via its env var name convention.

---

## Shared Patterns

### Authentication — Dependency Injection
**Source:** `app/auth.py` lines 42-43 + `app/routers/tenants.py` lines 41-45
**Apply to:** All five route handlers in `app/routers/pages.py`
```python
from app.auth import get_current_tenant
...
current: dict = Depends(get_current_tenant)
# Extract tenant_id as:
tenant_id = int(current["sub"])
```
The `/auth/facebook/callback` endpoint does NOT use `get_current_tenant` — it receives the state JWT from Facebook's redirect instead. All other endpoints (`GET /pages`, `DELETE /pages/{id}`, `GET /pages/{id}/health`, `GET /auth/facebook/start`) require the Bearer dependency.

### DB Connection — try/finally Close
**Source:** `app/routers/tenants.py` lines 46, 64 / lines 78, 81 / lines 112, 125
**Apply to:** Every route handler in `app/routers/pages.py` that opens a DB connection
```python
conn = get_connection(settings.db_path)
try:
    # ... SQL operations ...
    conn.commit()
finally:
    conn.close()
```
The callback handler's `_store_pages_and_subscribe` function also needs `conn.rollback()` in the `except` branch before `raise`.

### JWT Encode/Decode Pattern
**Source:** `app/auth.py` lines 14-38
```python
# Encode (from create_access_token):
payload = {
    "sub": sub,
    "role": role,
    "exp": datetime.now(tz=timezone.utc) + timedelta(days=7),
}
return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

# Decode (from verify_token):
try:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
except jwt.ExpiredSignatureError:
    raise HTTPException(status_code=401, detail="Token expired", ...)
except jwt.InvalidTokenError:
    raise HTTPException(status_code=401, detail="Invalid token", ...)
```
`create_oauth_state` / `verify_oauth_state` in `app/routers/pages.py` follow this same pattern verbatim, replacing `status_code=401` with `status_code=400` (OAuth state errors are bad requests, not auth failures) and using `timedelta(minutes=10)`.

### Fernet Encryption Pattern
**Source:** `app/crypto.py` lines 13-21
```python
def encrypt_token(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()

def decrypt_token(enc: str) -> str:
    try:
        return _fernet().decrypt(enc.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Token decryption failed: invalid ciphertext or wrong key") from exc
```
Always call `encrypt_token()` before writing to `pages.access_token_enc`. Always call `decrypt_token()` before passing to any `fb_client.*` function.

### Error Handling — HTTPException
**Source:** `app/routers/tenants.py` lines 51-52, 118-119
```python
raise HTTPException(status_code=409, detail="Email already exists")
raise HTTPException(status_code=404, detail="Tenant not found or already inactive")
```
Pattern: raise FastAPI `HTTPException` directly; no custom exception classes. Status codes:
- 400 — invalid OAuth state / no pages returned / FB API error JSON
- 404 — page not found or belongs to another tenant
- 403 — not used in pages.py (no admin-only routes)

### SQL Parameterization
**Source:** `app/routers/tenants.py` lines 48-51, `app/db.py` line 4 comment
```python
# get_connection — callers MUST use ? placeholders, never f-strings, for SQL parameters
conn.execute("SELECT id FROM tenants WHERE email = ?", (request.email,))
```
All SQL in `app/routers/pages.py` must use `?` placeholders. The `page_fb_id` from Facebook's API response is external data — it must be parameterized.

### Test Fixture — db_client Extension
**Source:** `tests/conftest.py` lines 38-63
```python
@pytest.fixture
def db_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(config_module.settings, "db_path", db_path)
    monkeypatch.setattr(config_module.settings, "jwt_secret", "test-secret-do-not-use-in-prod")
    init_schema(db_path)
    ...
```
`tests/test_pages.py` must monkeypatch the three new settings fields plus `fernet_key` using the same `monkeypatch.setattr` pattern. This can be done either in a `pages_db_client` fixture local to test_pages.py, or by extending `conftest.py`'s `db_client` fixture. Recommended: add to `conftest.py` so all future test files inherit them.

Fields to add to `db_client` fixture:
```python
monkeypatch.setattr(config_module.settings, "fernet_key", Fernet.generate_key().decode())
monkeypatch.setattr(config_module.settings, "fb_app_id", "test-app-id")
monkeypatch.setattr(config_module.settings, "fb_app_secret", "test-app-secret")
monkeypatch.setattr(config_module.settings, "fb_redirect_uri", "http://localhost:8000/auth/facebook/callback")
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `app/fb_client.py` (outbound HTTP logic) | utility | outbound request-response | No existing file makes outbound HTTP calls in the Python backend; `httpx` is installed but unused in `app/`. The Messenger bot (`messenger-bot/src/index.ts`) makes outbound calls but is TypeScript. Use RESEARCH.md Pattern 2, 3, 4 as the reference. |

---

## Metadata

**Analog search scope:** `app/routers/`, `app/`, `tests/`
**Files scanned:** 9 (`tenants.py`, `auth.py`, `auth.py` router, `config.py`, `db.py`, `crypto.py`, `main.py`, `conftest.py`, `test_auth.py`)
**Pattern extraction date:** 2026-05-28
