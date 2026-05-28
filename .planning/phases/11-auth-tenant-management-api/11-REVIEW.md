---
phase: 11-auth-tenant-management-api
reviewed: 2026-05-28T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - app/auth.py
  - app/config.py
  - app/db.py
  - app/main.py
  - app/routers/auth.py
  - app/routers/tenants.py
  - scripts/init_db.py
  - tests/conftest.py
  - tests/test_auth.py
findings:
  critical: 2
  warning: 4
  info: 3
  total: 9
status: issues_found
---

# Phase 11: Code Review Report

**Reviewed:** 2026-05-28T00:00:00Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Reviewed the auth and tenant management API implementation: JWT creation/verification (`app/auth.py`), login (`app/routers/auth.py`), tenant CRUD (`app/routers/tenants.py`), DB setup (`app/db.py`), app wiring (`app/main.py`), seeding script (`scripts/init_db.py`), and the test suite.

The core bcrypt password hashing, SQL parameterization, soft-delete logic, JWT role enforcement, and self-delete guard are all correctly implemented. Two blockers stand out: an uncaught `InvalidKeyError` in `verify_token` that returns 500 instead of 401 when `jwt_secret` is empty, and a race condition in `create_tenant` where a concurrent duplicate-email insertion reaches the SQLite `UNIQUE` constraint and surfaces as an unhandled 500 instead of the expected 409. Four warnings cover: no input validation on password/email fields, a deactivated tenant's JWT remaining valid for authenticated endpoints, a non-atomic check-then-act pattern in `delete_tenant`, and an implied requirement to manually run `init_db.py` before the app will function (no startup guard).

---

## Critical Issues

### CR-01: `verify_token` does not catch `jwt.InvalidKeyError` — returns 500 when `jwt_secret` is empty

**File:** `app/auth.py:25-39`

**Issue:** `jwt.decode()` raises `jwt.exceptions.InvalidKeyError` (inherits from `PyJWTError`, not from `InvalidTokenError`) when `settings.jwt_secret` is an empty string. The `except` clauses on lines 28 and 34 only catch `ExpiredSignatureError` and `InvalidTokenError`. `InvalidKeyError` therefore propagates uncaught through `verify_token` and `get_current_tenant`, causing every authenticated request to return 500 rather than 401 when `JWT_SECRET` is missing from `.env`. This is a runtime crash that silently disables all authentication enforcement.

`create_access_token` does guard against an empty secret (line 15), but `verify_token` has no such guard. If the secret is present when tokens are issued and later cleared (e.g., an ops mistake or environment variable misconfiguration), all subsequent token verification calls crash.

**Fix:**
```python
def verify_token(token: str) -> dict:
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (jwt.InvalidTokenError, jwt.exceptions.InvalidKeyError):
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
```

---

### CR-02: Race condition in `create_tenant` — duplicate-email INSERT raises unhandled `sqlite3.IntegrityError` (500)

**File:** `app/routers/tenants.py:47-64`

**Issue:** The duplicate-email guard is a two-step check-then-act: a `SELECT` on lines 48-50 followed by an `INSERT` on lines 53-55. Under concurrent requests, two threads can both pass the `SELECT` check (both see no existing row), then both attempt the `INSERT`. One succeeds; the other hits the SQLite `UNIQUE` constraint on `email` and raises `sqlite3.IntegrityError`. The `try/finally` block only closes the connection — it does not catch `IntegrityError`. The exception propagates to FastAPI as an unhandled 500 instead of the expected 409.

**Fix:**
```python
import sqlite3

@router.post("/admin/tenants", response_model=TenantResponse, status_code=201)
async def create_tenant(
    request: CreateTenantRequest,
    current: dict = Depends(require_super_admin),
) -> TenantResponse:
    conn = get_connection(settings.db_path)
    try:
        existing = conn.execute(
            "SELECT id FROM tenants WHERE email = ?", (request.email,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Email already exists")
        try:
            cur = conn.execute(
                "INSERT INTO tenants (email, password_hash, is_super_admin) VALUES (?, ?, 0)",
                (request.email, pwd_context.hash(request.password)),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Email already exists")
        conn.commit()
        new_id = cur.lastrowid
        row = conn.execute(
            "SELECT id, email, is_active, is_super_admin, created_at FROM tenants WHERE id = ?",
            (new_id,),
        ).fetchone()
    finally:
        conn.close()
    return TenantResponse(...)
```

---

## Warnings

### WR-01: No minimum-length validation on `password` and `email` fields — empty strings accepted

**File:** `app/routers/auth.py:14-16`, `app/routers/tenants.py:15-17`

**Issue:** Both `LoginRequest` and `CreateTenantRequest` accept `password: str` and `email: str` with no constraints. An empty string `""` passes Pydantic validation, is successfully hashed by bcrypt, and gets stored in the database. A tenant can be created with `password=""`. On login, `pwd_context.verify("", hash_of_empty)` returns `True`, granting access. Additionally, bcrypt silently truncates passwords longer than 72 bytes — two passwords that differ only past the 72nd byte will collide. No maximum length is enforced, and a very long password string will cause a bcrypt computation proportional to only 72 chars but an HTTP request parsing cost proportional to the full length.

**Fix:**
```python
from pydantic import BaseModel, field_validator, EmailStr

class CreateTenantRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v) > 72:
            raise ValueError("Password must not exceed 72 characters")
        return v
```

Apply the same validators to `LoginRequest.password` (length check only — do not reject on login to avoid enumeration).

---

### WR-02: Deactivated tenant's existing JWT remains valid — no is_active check on authenticated routes

**File:** `app/routers/tenants.py:134-154`, `app/auth.py:42-43`

**Issue:** After `DELETE /admin/tenants/{id}` soft-deletes a tenant (sets `is_active=0`), the tenant's existing JWT tokens are not invalidated. The `get_current_tenant` dependency only verifies the JWT signature and expiration — it never queries the database for the tenant's current `is_active` status. A deactivated tenant holding a valid (non-expired) token can still call `GET /tenants/me` and any other route protected only by `get_current_tenant` or `require_super_admin`. With a 7-day token lifetime (`timedelta(days=7)` in `app/auth.py:20`), this window is substantial.

**Fix:** Add an `is_active` check in `get_my_tenant` (and any future routes that use `get_current_tenant`), or add a DB lookup in `get_current_tenant` itself:
```python
async def get_current_tenant(token: str = Depends(oauth2_scheme)) -> dict:
    payload = verify_token(token)
    conn = get_connection(settings.db_path)
    try:
        row = conn.execute(
            "SELECT is_active FROM tenants WHERE id = ?", (int(payload["sub"]),)
        ).fetchone()
    finally:
        conn.close()
    if not row or not row["is_active"]:
        raise HTTPException(status_code=401, detail="Account deactivated",
                            headers={"WWW-Authenticate": "Bearer"})
    return payload
```

Note: this adds a DB query per authenticated request. An alternative is a short token lifetime (e.g., 15 minutes) with a refresh token mechanism.

---

### WR-03: `delete_tenant` has a TOCTOU between existence check and soft-delete UPDATE

**File:** `app/routers/tenants.py:113-127`

**Issue:** `delete_tenant` performs a `SELECT` to check `is_active = 1` (line 114), then issues `UPDATE SET is_active = 0` (line 120) in a separate statement. Two concurrent admin requests to `DELETE /admin/tenants/{id}` can both pass the `SELECT` check before either commits, resulting in the deactivation logic running twice. The second execution silently succeeds (SQLite UPDATE with 0 matching rows is not an error), and the `pages_deactivated` count in the second response would be 0 (pages already deactivated). This is misleading to the caller rather than returning the expected 404.

**Fix:** Use a single atomic `UPDATE ... WHERE is_active = 1` and check `rowcount` to determine if the row was found:
```python
cur = conn.execute(
    "UPDATE tenants SET is_active = 0 WHERE id = ? AND is_active = 1 AND is_super_admin = 0",
    (tenant_id,),
)
if cur.rowcount == 0:
    raise HTTPException(status_code=404, detail="Tenant not found or already inactive")
pages_cur = conn.execute(
    "UPDATE pages SET is_active = 0 WHERE tenant_id = ?", (tenant_id,)
)
```

---

### WR-04: App starts successfully with no database file — all DB-backed routes silently fail with 500

**File:** `app/main.py:9-13`

**Issue:** The `lifespan` function only initializes the content vault. There is no call to `init_schema` and no check that `settings.db_path` exists or is reachable. If the database has not been initialized via `scripts/init_db.py`, every request to `/auth/login`, `/admin/tenants`, and `/tenants/me` raises an `sqlite3.OperationalError` (no such table) which surfaces as an unhandled 500. The app gives no startup warning, so the operator has no indication the system is broken until the first request.

**Fix:** Add a startup guard in the lifespan function:
```python
from app.db import init_schema

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_schema(settings.db_path)   # idempotent — safe to call on every start
    content._vault.clear()
    content._vault.update(content.load_vault())
    yield
```

`init_schema` uses `CREATE TABLE IF NOT EXISTS` throughout, so calling it on startup is idempotent and removes the dependency on the manual seeding script for schema creation (though seeding the super-admin still requires the script).

---

## Info

### IN-01: `CryptContext` instantiated separately in two router modules — duplication

**File:** `app/routers/auth.py:11`, `app/routers/tenants.py:12`

**Issue:** `pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")` is copy-pasted as a module-level singleton in both `auth.py` and `tenants.py`. If the hashing configuration ever changes (e.g., adding argon2), it must be updated in two places.

**Fix:** Move the `CryptContext` definition to `app/auth.py` (or a new `app/crypto.py`) and import it in both routers.

---

### IN-02: 7-day JWT lifetime is long for an admin-capable system

**File:** `app/auth.py:20`

**Issue:** `timedelta(days=7)` means a compromised or deactivated-tenant token remains valid for up to 7 days. This amplifies the impact of WR-02. For a system with super-admin access that can create/delete tenant accounts, a shorter-lived token is more appropriate.

**Fix:** Reduce the lifetime to 1 hour or 24 hours and implement a refresh token endpoint, or at minimum make the expiry configurable via `settings`:
```python
"exp": datetime.now(tz=timezone.utc) + timedelta(hours=int(settings.jwt_expiry_hours or 24)),
```

---

### IN-03: `db_path` default is a relative path — resolved relative to process CWD

**File:** `app/config.py:9`

**Issue:** `db_path: str = "govi.db"` resolves relative to whatever the current working directory is when the process starts. If the process is started from a directory other than the project root (e.g., a systemd unit with `WorkingDirectory=/`), SQLite will create or look for the file in that directory, silently creating a separate empty database instead of the intended one.

**Fix:** Document the expected CWD in deployment instructions, or default to an absolute path derived from the project root:
```python
import os
db_path: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "govi.db")
```

---

_Reviewed: 2026-05-28T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
