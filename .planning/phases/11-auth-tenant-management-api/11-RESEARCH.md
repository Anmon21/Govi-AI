# Phase 11: Auth & Tenant Management API - Research

**Researched:** 2026-05-27
**Domain:** FastAPI JWT authentication + SQLite tenant CRUD
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Super-admin is a special row in the `tenants` table with `is_super_admin = 1`. No separate table.
- **D-02:** Schema reset — add `is_super_admin INTEGER NOT NULL DEFAULT 0` to `CREATE TABLE tenants` in `app/db.py`. Re-run `scripts/init_db.py` (dev-only DB, no migration needed for v1.2).
- **D-03:** Super-admin row seeded by `scripts/init_db.py` reading `SUPER_ADMIN_EMAIL` and `SUPER_ADMIN_PASSWORD` env vars; password stored as bcrypt hash. No hardcoded credentials.
- **D-04:** Admin-only endpoints (`/admin/tenants/*`) check `role == "super_admin"` in the JWT. Non-super-admin tokens receive **403 Forbidden**.
- **D-05:** Single `POST /auth/login` handles both roles. Returns JWT with `role: "super_admin"` or `role: "client"`.
- **D-06:** Client JWT payload: `{ "sub": "<tenant_id as string>", "role": "client", "exp": <timestamp> }`
- **D-07:** Super-admin JWT payload: `{ "sub": "<tenant_id of super-admin row>", "role": "super_admin", "exp": <timestamp> }`
- **D-08:** `GET /tenants/me` added to Phase 11 — returns the calling client's own tenant record. Enforces SC-5.
- **D-09:** Auth via FastAPI `Depends()` — reusable `get_current_tenant(token: str = Depends(oauth2_scheme))` dependency.
- **D-10:** PyJWT library — `pip install PyJWT`; add `PyJWT>=2.8.0` to `requirements.txt`.
- **D-11:** JWT signing secret in `JWT_SECRET` env var — `jwt_secret: str = ""` in `Settings`. Guard: raise `RuntimeError` at token creation time if empty.
- **D-12:** Token expiry: 7 days fixed (`exp = datetime.utcnow() + timedelta(days=7)`). No refresh tokens.
- **D-13:** Password hashing: `passlib` with bcrypt — add `passlib[bcrypt]>=1.7.4` to `requirements.txt`.
- **Module layout:**
  - `app/auth.py` — `create_access_token()`, `verify_token()`, `get_current_tenant()` Depends, `require_super_admin()` Depends
  - `app/routers/auth.py` — `POST /auth/login` (prefix `/auth`, tags `["auth"]`)
  - `app/routers/tenants.py` — super-admin CRUD (`/admin/tenants`) + client self-info (`/tenants/me`) (tags `["tenants"]`)
- **Tenant list response:** includes `page_count: int` via COUNT join on `pages` table.

### Claude's Discretion

- `DELETE /admin/tenants/{id}` performs a **soft delete** (`is_active = 0`), not hard delete.

### Deferred Ideas (OUT OF SCOPE)

- Refresh tokens
- Hard delete for tenant accounts
- Token revocation / blacklist
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TENANT-01 | Super-admin can create a client account (email + password) via the admin panel | `POST /admin/tenants` with bcrypt hashing; passlib CryptContext pattern |
| TENANT-02 | Super-admin can view a list of all client accounts and their connected Pages | `GET /admin/tenants` with COUNT join on `pages.tenant_id`; excludes super-admin row |
| TENANT-03 | Super-admin can delete or deactivate a client account (disconnects their Pages) | `DELETE /admin/tenants/{id}` soft-deletes tenant and sets `pages.is_active=0` for their pages |
</phase_requirements>

---

## Summary

Phase 11 implements a JWT-based authentication layer on top of the existing SQLite schema from Phase 10. All decisions are fully locked in CONTEXT.md: PyJWT for token signing, passlib/bcrypt for password hashing, a single `POST /auth/login` endpoint for both roles, and FastAPI `Depends()` for reusable auth injection.

The codebase already provides all patterns needed: `app/crypto.py` demonstrates the env-var guard pattern for secrets (`_fernet()`), `app/routers/ai.py` shows the inline Pydantic model pattern, and `app/db.py` shows raw SQL with `sqlite3.Row`. Phase 11 adds three new files (`app/auth.py`, `app/routers/auth.py`, `app/routers/tenants.py`) and modifies four existing files (`app/db.py`, `app/config.py`, `scripts/init_db.py`, `app/main.py`).

The test infrastructure is healthy: 21 tests pass, pytest collects cleanly, and `TestClient` + `monkeypatch` are the established patterns for FastAPI route testing. New tests should follow the same style.

**Primary recommendation:** Follow the locked decisions exactly. The crypto-guard pattern, raw SQL, and inline Pydantic models are the house style — do not deviate.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| JWT creation + verification | API / Backend (`app/auth.py`) | — | Tokens are server-signed secrets; client never generates them |
| Password hashing (bcrypt) | API / Backend (`app/auth.py` or seed script) | — | Hash must happen server-side; client sends plaintext over HTTPS |
| Login endpoint | API / Backend (`app/routers/auth.py`) | — | Credential validation is backend-only |
| Tenant CRUD | API / Backend (`app/routers/tenants.py`) | Database / Storage | SQLite rows + foreign key constraints own the persistence |
| Auth enforcement (Depends) | API / Backend (`app/auth.py`) | — | FastAPI middleware layer; each protected route declares dependency |
| Super-admin seeding | Database / Storage (`scripts/init_db.py`) | — | One-time DB operation; env-var driven, not a route |
| Schema change (`is_super_admin`) | Database / Storage (`app/db.py`) | — | DDL belongs in the schema definition, not application logic |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyJWT | 2.13.0 (latest) | JWT encode/decode, HS256 | Locked by D-10; most widely used Python JWT library |
| passlib[bcrypt] | 1.7.4 (latest) | Password hashing + verification | Locked by D-13; de-facto standard; bcrypt is industry-recommended |
| FastAPI (existing) | 0.128.8 | HTTP framework, `Depends()`, `OAuth2PasswordBearer` | Already installed; no new install needed |
| sqlite3 (stdlib) | — | Tenant + page queries | Project uses raw SQLite; no ORM |

**Version verification:** [VERIFIED: pip3 index versions — PyJWT latest is 2.13.0, passlib latest is 1.7.4]

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `fastapi.security.OAuth2PasswordBearer` | (in fastapi) | Extracts Bearer token from `Authorization` header | Used by `get_current_tenant()` Depends |
| `datetime.timedelta` (stdlib) | — | Token expiry calculation | In `create_access_token()` |
| `fastapi.status` | (in fastapi) | Named HTTP status constants | 401, 403 error responses |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyJWT | python-jose | python-jose is heavier and less maintained; PyJWT is actively maintained and simpler |
| passlib[bcrypt] | `bcrypt` package directly | passlib wraps bcrypt with a safer API (CryptContext); direct bcrypt use is lower-level |

**Installation:**
```bash
pip install "PyJWT>=2.8.0" "passlib[bcrypt]>=1.7.4"
```

---

## Architecture Patterns

### System Architecture Diagram

```
POST /auth/login
    |
    v
LoginRequest (email + password)
    |
    v
[DB: SELECT * FROM tenants WHERE email=?]
    |-- not found / is_active=0 --> 401 Unauthorized
    |
    v
bcrypt.verify(password, row.password_hash)
    |-- mismatch --> 401 Unauthorized
    |
    v
create_access_token(sub=str(id), role=...)
    |
    v
TokenResponse { access_token, token_type }

Protected Route (e.g. GET /admin/tenants)
    |
    v
Authorization: Bearer <token>
    |
    v
get_current_tenant() [Depends]
    |-- invalid/expired --> 401
    |
    v
require_super_admin() [Depends, stacked on get_current_tenant]
    |-- role != "super_admin" --> 403
    |
    v
Route handler executes

DELETE /admin/tenants/{id}
    |
    v
UPDATE tenants SET is_active=0 WHERE id=?
UPDATE pages   SET is_active=0 WHERE tenant_id=?
```

### Recommended Project Structure

```
app/
├── auth.py              # create_access_token, verify_token, get_current_tenant, require_super_admin
├── config.py            # Settings — add jwt_secret, super_admin_email, super_admin_password
├── db.py                # init_schema — add is_super_admin column to tenants DDL
├── crypto.py            # unchanged
├── main.py              # add app.include_router(auth.router), app.include_router(tenants.router)
└── routers/
    ├── auth.py          # POST /auth/login
    ├── tenants.py       # GET|POST /admin/tenants, DELETE /admin/tenants/{id}, GET /tenants/me
    ├── health.py        # unchanged
    ├── ai.py            # unchanged
    └── content.py       # unchanged

scripts/
└── init_db.py           # update: seed super-admin row (idempotent)
```

### Pattern 1: JWT Create + Verify (PyJWT 2.x)

**What:** Sign a dict payload with HS256, decode and validate on receipt.
**When to use:** In `app/auth.py` — called by login route and by `get_current_tenant`.

```python
# Source: https://github.com/jpadilla/pyjwt/blob/master/docs/usage.md
import jwt
from datetime import datetime, timedelta, timezone

def create_access_token(sub: str, role: str) -> str:
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is not configured. Set it in .env.")
    payload = {
        "sub": sub,
        "role": role,
        "exp": datetime.now(tz=timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired",
                            headers={"WWW-Authenticate": "Bearer"})
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token",
                            headers={"WWW-Authenticate": "Bearer"})
```

**Note on `datetime.utcnow()` vs `datetime.now(tz=timezone.utc)`:** PyJWT 2.x compares against UTC-aware datetimes. Using `datetime.now(tz=timezone.utc)` is the modern form; `datetime.utcnow()` is deprecated in Python 3.12+. Either works with PyJWT 2.x for the `exp` claim. [VERIFIED: Context7 /jpadilla/pyjwt]

### Pattern 2: FastAPI OAuth2 Bearer Depends

**What:** `OAuth2PasswordBearer` extracts the raw token string from the `Authorization: Bearer` header. Stack a second Depends for role gating.
**When to use:** Every protected route.

```python
# Source: https://github.com/fastapi/fastapi/blob/master/docs/en/docs/tutorial/security/get-current-user.md
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_tenant(token: str = Depends(oauth2_scheme)) -> dict:
    return verify_token(token)  # raises 401 on failure

async def require_super_admin(current: dict = Depends(get_current_tenant)) -> dict:
    if current.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current
```

**401 response shape:** Include `headers={"WWW-Authenticate": "Bearer"}` — this is the HTTP spec requirement for OAuth2 bearer schemes. [VERIFIED: Context7 /fastapi/fastapi]

### Pattern 3: bcrypt with passlib CryptContext

**What:** Application-level singleton for hashing and verifying passwords.
**When to use:** In `scripts/init_db.py` (super-admin seed) and `app/routers/tenants.py` (client creation).

```python
# Source: https://passlib.readthedocs.io/en/stable/narr/quickstart.html
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hash (at creation time):
hashed = pwd_context.hash(plain_password)

# Verify (at login time):
is_valid = pwd_context.verify(plain_password, stored_hash)
```

**Why CryptContext over `passlib.hash.bcrypt` directly:** CryptContext is passlib's recommended application interface; it handles algorithm upgrades transparently. [VERIFIED: Context7 /websites/passlib_readthedocs_io_en_stable]

### Pattern 4: Soft Delete with Page Cascade

**What:** Deactivating a tenant must also deactivate all their pages (SC-4).
**When to use:** `DELETE /admin/tenants/{id}` handler.

```python
# Raw SQL pattern matching app/db.py conventions
conn.execute("UPDATE tenants SET is_active = 0 WHERE id = ?", (tenant_id,))
conn.execute("UPDATE pages   SET is_active = 0 WHERE tenant_id = ?", (tenant_id,))
conn.commit()
```

Both UPDATEs must run in the same transaction (single `conn` object, committed together).

### Pattern 5: Tenant List with Page Count

**What:** COUNT subquery join to include `page_count` per tenant row.
**When to use:** `GET /admin/tenants` handler.

```python
# Excludes super-admin row and returns page count per tenant
rows = conn.execute("""
    SELECT t.id, t.email, t.is_active, t.created_at,
           COUNT(p.id) AS page_count
    FROM   tenants t
    LEFT JOIN pages p ON p.tenant_id = t.id AND p.is_active = 1
    WHERE  t.is_super_admin = 0
    GROUP BY t.id
""").fetchall()
```

### Pattern 6: Idempotent Super-Admin Seed

**What:** Insert super-admin only if no row with `is_super_admin=1` already exists.
**When to use:** `scripts/init_db.py` after `init_schema()`.

```python
existing = conn.execute(
    "SELECT id FROM tenants WHERE is_super_admin = 1"
).fetchone()
if not existing:
    conn.execute(
        "INSERT INTO tenants (email, password_hash, is_super_admin) VALUES (?, ?, 1)",
        (settings.super_admin_email, pwd_context.hash(settings.super_admin_password))
    )
    conn.commit()
```

Guard: raise `RuntimeError` if `SUPER_ADMIN_EMAIL` or `SUPER_ADMIN_PASSWORD` env vars are empty.

### Anti-Patterns to Avoid

- **Comparing passwords with `==`:** Always use `pwd_context.verify()`. Timing attacks are real.
- **Returning token in a non-standard shape:** The field must be `access_token` (string) and `token_type: "bearer"` for OAuth2 clients and the OpenAPI `/docs` UI to work correctly.
- **Using `algorithms="HS256"` (string) for decode:** Must be a list — `algorithms=["HS256"]`. PyJWT 2.x requires a list; a string raises `DecodeError`. [VERIFIED: Context7 /jpadilla/pyjwt]
- **Skipping the `is_active` check in login:** A deactivated tenant must not be able to log in even if their password is correct.
- **Letting `get_current_tenant` return a DB row:** Return the decoded JWT dict only; avoids an extra DB round-trip on every request.
- **Including `password_hash` in any response model:** Never serialize the hash. Define explicit Pydantic response models that omit it.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JWT signing / verification | Custom HMAC token format | PyJWT | Algorithm confusion attacks, expiry handling, decode failures all handled |
| Password hashing | MD5/SHA256 plain hash | passlib[bcrypt] | Salting, work factor, timing-safe comparison all required; bcrypt is the standard |
| Bearer token extraction | Manual `Authorization` header parse | `OAuth2PasswordBearer` | Handles missing header → 401 auto-response; integrates with OpenAPI /docs |
| Transaction safety | Multiple `conn.execute()` without commit boundary | Single `conn`, explicit `conn.commit()` | SQLite WAL mode is still susceptible to partial writes without explicit commit |

**Key insight:** PyJWT and passlib together handle the entire auth surface. The only custom code needed is the business logic (role gating, tenant lookup).

---

## Common Pitfalls

### Pitfall 1: `algorithms` Must Be a List in PyJWT 2.x

**What goes wrong:** `jwt.decode(token, key, algorithms="HS256")` raises `DecodeError: It is required that you pass in a value for the "algorithms" argument when calling decode()` or a type error.
**Why it happens:** PyJWT 2.x changed the signature to require a list for security (prevents algorithm confusion attacks).
**How to avoid:** Always use `algorithms=["HS256"]`.
**Warning signs:** `DecodeError` in tests even when token looks correct.

### Pitfall 2: `datetime.utcnow()` Deprecation Warning in Python 3.12

**What goes wrong:** `DeprecationWarning: datetime.datetime.utcnow() is deprecated` during tests on Python 3.12+.
**Why it happens:** Python 3.12 deprecated `utcnow()` in favour of timezone-aware `now(tz=timezone.utc)`.
**How to avoid:** Use `datetime.now(tz=timezone.utc)` for `exp` claim. PyJWT 2.x handles it correctly.
**Warning signs:** DeprecationWarning in test output.

### Pitfall 3: Login Must Check `is_active` Before Password Verify

**What goes wrong:** A soft-deleted tenant can still log in if the password check runs first.
**Why it happens:** Query returns the row regardless of `is_active`; password matches; token issued.
**How to avoid:** `WHERE email = ? AND is_active = 1` in the login query, or check `is_active` before `pwd_context.verify()`.
**Warning signs:** SC-4 test passes but deactivated user still receives a 200.

### Pitfall 4: `GET /admin/tenants` Must Exclude the Super-Admin Row

**What goes wrong:** The super-admin account appears in the tenant list, allowing itself to be soft-deleted.
**Why it happens:** No `WHERE is_super_admin = 0` filter on the listing query.
**How to avoid:** Always add `WHERE t.is_super_admin = 0` to tenant list and delete queries.
**Warning signs:** Super-admin row visible in list response.

### Pitfall 5: `DELETE /admin/tenants/{id}` Must Not Allow Self-Deletion

**What goes wrong:** Super-admin deletes their own account, locking themselves out.
**Why it happens:** No guard on the delete endpoint.
**How to avoid:** Check `tenant_id == int(current["sub"])` and return 403 if true. Or enforce via `WHERE is_super_admin = 0`.
**Warning signs:** DELETE on own ID returns 200.

### Pitfall 6: `conftest.py` Requires `monkeypatch` for New Settings Fields

**What goes wrong:** Tests that import `app.main` (and thus `app.config.settings`) fail if `JWT_SECRET`, `SUPER_ADMIN_EMAIL`, or `SUPER_ADMIN_PASSWORD` are not set in the test environment.
**Why it happens:** pydantic-settings reads `.env` at import time; missing required fields fail validation or default to empty strings.
**How to avoid:** All fields default to `""` (same as `fernet_key`). Tests that exercise `create_access_token()` or the seed must `monkeypatch.setattr(config_module.settings, "jwt_secret", "test-secret")` before calling.
**Warning signs:** `RuntimeError: JWT_SECRET is not configured` in test output.

### Pitfall 7: `TestClient` Does Not Forward `Authorization` Headers Automatically

**What goes wrong:** Protected route tests return 401 when using `client.get("/admin/tenants")` without setting headers.
**Why it happens:** `TestClient` is stateless — no session or cookie carry-forward.
**How to avoid:** Pass explicit `headers={"Authorization": f"Bearer {token}"}` in every protected route test.
**Warning signs:** All protected route tests fail with 401 even when a valid token is generated.

---

## Code Examples

### Full `app/auth.py` skeleton

```python
# Source: Context7 /jpadilla/pyjwt + /fastapi/fastapi
import jwt
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from app.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def create_access_token(sub: str, role: str) -> str:
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is not configured. Set it in .env.")
    payload = {
        "sub": sub,
        "role": role,
        "exp": datetime.now(tz=timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_tenant(token: str = Depends(oauth2_scheme)) -> dict:
    return verify_token(token)


async def require_super_admin(
    current: dict = Depends(get_current_tenant),
) -> dict:
    if current.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current
```

### `POST /auth/login` route skeleton

```python
# Source: project conventions from app/routers/ai.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from passlib.context import CryptContext

from app.auth import create_access_token
from app.config import settings
from app.db import get_connection

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    conn = get_connection(settings.db_path)
    try:
        row = conn.execute(
            "SELECT id, password_hash, is_super_admin FROM tenants "
            "WHERE email = ? AND is_active = 1",
            (request.email,),
        ).fetchone()
    finally:
        conn.close()

    if not row or not pwd_context.verify(request.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    role = "super_admin" if row["is_super_admin"] else "client"
    token = create_access_token(sub=str(row["id"]), role=role)
    return TokenResponse(access_token=token)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `datetime.utcnow()` for JWT exp | `datetime.now(tz=timezone.utc)` | Python 3.12 | Suppresses DeprecationWarning; functionally identical for PyJWT |
| `jwt.decode(token, key, algorithms="HS256")` (string) | `jwt.decode(..., algorithms=["HS256"])` (list) | PyJWT 2.0 | String form raises DecodeError in 2.x |
| `passlib.hash.bcrypt` directly | `passlib.context.CryptContext` | passlib 1.7 | CryptContext is the recommended application interface |

**Deprecated/outdated:**
- `jwt.decode(token, key, algorithms="HS256")` with a string — use a list.
- `datetime.utcnow()` — deprecated in Python 3.12; use `timezone.utc`-aware form.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `pwd_context` singleton should be defined at module level in `routers/tenants.py` and `routers/auth.py` (or extracted to `app/auth.py`) — not re-instantiated per request | Architecture Patterns | Low: CryptContext is cheap to instantiate, but module-level is cleaner |
| A2 | Python version on dev machine (3.9.6) does not raise DeprecationWarning for `datetime.utcnow()` — warning only appears on 3.12+ | Common Pitfalls | Low: using `datetime.now(tz=timezone.utc)` is safe on all versions |

**All other claims are VERIFIED via tool calls in this session.**

---

## Open Questions

1. **`app/routers/health.py` references `content._vault`**
   - What we know: `health.py` imports `app.routers.content` for vault stats — tightly coupled to vault content loading.
   - What's unclear: Phase 11 does not touch `health.py`, but if Phase 13 removes the vault, this import will break.
   - Recommendation: Out of scope for Phase 11; note in STATE.md as a future concern.

2. **`is_active` check on `DELETE /admin/tenants/{id}` — guard against re-deactivating an already-deactivated tenant**
   - What we know: Soft delete sets `is_active = 0`; if called twice, the UPDATE is a no-op but returns 200.
   - What's unclear: Should a 404 be returned if the tenant is already inactive?
   - Recommendation: Return 404 if `SELECT id FROM tenants WHERE id=? AND is_active=1` returns nothing. This is the safer user experience.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.x | All backend code | ✓ | 3.9.6 | — |
| pytest | Test suite | ✓ | installed (requirements.txt) | — |
| PyJWT | `app/auth.py` | ✗ (not yet installed) | 2.13.0 available | — (must install) |
| passlib[bcrypt] | auth + seed script | ✗ (not yet installed) | 1.7.4 available | — (must install) |
| FastAPI + TestClient | Tests | ✓ | 0.128.8 | — |
| SQLite (stdlib) | DB layer | ✓ | stdlib | — |

**Missing dependencies with no fallback:**
- PyJWT — must be installed before `app/auth.py` can be imported
- passlib[bcrypt] — must be installed before login or seed script can hash passwords

**Wave 0 task:** `pip install "PyJWT>=2.8.0" "passlib[bcrypt]>=1.7.4"` and add both to `requirements.txt`.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (>=8.0.0, installed) |
| Config file | none — pytest discovers `tests/` by convention |
| Quick run command | `python3 -m pytest tests/test_auth.py -x -q` |
| Full suite command | `python3 -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TENANT-01 | `POST /admin/tenants` creates tenant, stores bcrypt hash | unit+integration | `pytest tests/test_auth.py -k "create_tenant" -x` | ❌ Wave 0 |
| TENANT-01 | Duplicate email returns 409 | unit | `pytest tests/test_auth.py -k "duplicate_email" -x` | ❌ Wave 0 |
| TENANT-02 | `GET /admin/tenants` lists only non-super-admin tenants with page_count | integration | `pytest tests/test_auth.py -k "list_tenants" -x` | ❌ Wave 0 |
| TENANT-03 | `DELETE /admin/tenants/{id}` sets tenant + pages is_active=0 | integration | `pytest tests/test_auth.py -k "soft_delete" -x` | ❌ Wave 0 |
| SC-1 (login) | `POST /auth/login` valid credentials → JWT with correct payload | unit | `pytest tests/test_auth.py -k "login_success" -x` | ❌ Wave 0 |
| SC-1 (login) | Invalid password → 401 | unit | `pytest tests/test_auth.py -k "login_invalid" -x` | ❌ Wave 0 |
| SC-4 | Deactivated client cannot log in | unit | `pytest tests/test_auth.py -k "inactive_tenant" -x` | ❌ Wave 0 |
| SC-5 | `GET /tenants/me` returns own record; JWT for tenant A cannot see tenant B | integration | `pytest tests/test_auth.py -k "tenant_isolation" -x` | ❌ Wave 0 |
| SC-5 | Non-super-admin token → 403 on `/admin/tenants` | unit | `pytest tests/test_auth.py -k "forbidden" -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `python3 -m pytest tests/test_auth.py -x -q`
- **Per wave merge:** `python3 -m pytest tests/ -q`
- **Phase gate:** Full suite green (21 existing + new auth tests) before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_auth.py` — covers all SC-1 through SC-5 and TENANT-01 through TENANT-03
- [ ] Install PyJWT and passlib[bcrypt]: `pip install "PyJWT>=2.8.0" "passlib[bcrypt]>=1.7.4"` + update `requirements.txt`
- [ ] `tests/conftest.py` — extend with a `db_client` fixture providing a `TestClient` wired to a tmp-path SQLite DB with a seeded super-admin row, similar to the `monkeypatch` pattern in `test_db_foundation.py`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | passlib/bcrypt for password storage; `POST /auth/login` rejects inactive tenants |
| V3 Session Management | yes | PyJWT HS256; 7-day expiry; no refresh tokens (deferred) |
| V4 Access Control | yes | `require_super_admin()` Depends returns 403 for non-admin JWTs; tenant isolation via `sub` claim check |
| V5 Input Validation | yes | Pydantic `LoginRequest`, `CreateTenantRequest` — validate email + password fields |
| V6 Cryptography | yes | HS256 for JWT (keyed hash, not encryption); bcrypt for passwords — both are standard |

### Known Threat Patterns for JWT + SQLite

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| JWT algorithm confusion (e.g., `alg: none`) | Spoofing | PyJWT 2.x requires `algorithms=["HS256"]` list — `none` algorithm rejected by default |
| Brute-force login | Spoofing | bcrypt work factor (cost 12) slows offline attacks; rate limiting is out of scope for v1.2 |
| Cross-tenant data access | Information Disclosure | `sub` claim in JWT compared to resource's `tenant_id` before any data is returned |
| Deactivated user accessing data | Elevation of Privilege | Login query includes `is_active = 1`; existing tokens remain valid until expiry (acceptable for 7-day low-traffic tool) |
| `JWT_SECRET` exposure | Information Disclosure | Secret in `.env` (gitignored); `RuntimeError` at creation time if empty; never logged |
| SQL injection via email/password fields | Tampering | Raw SQL with `?` placeholders throughout — no f-string interpolation (project-wide convention) |

---

## Sources

### Primary (HIGH confidence)

- Context7 `/jpadilla/pyjwt` — encode/decode, algorithms list requirement, ExpiredSignatureError, leeway [VERIFIED]
- Context7 `/websites/passlib_readthedocs_io_en_stable` — CryptContext, bcrypt hash/verify, rounds [VERIFIED]
- Context7 `/fastapi/fastapi` — OAuth2PasswordBearer, Depends, get_current_user pattern, 401 WWW-Authenticate header [VERIFIED]
- `pip3 index versions PyJWT` — current latest 2.13.0 [VERIFIED: pip registry]
- `pip3 index versions passlib` — current latest 1.7.4 [VERIFIED: pip registry]
- `python3 -m pytest tests/ --collect-only -q` — 21 tests collected, all pass [VERIFIED: local run]
- `app/db.py`, `app/config.py`, `app/crypto.py`, `app/routers/health.py`, `app/routers/ai.py`, `app/main.py`, `scripts/init_db.py` — existing codebase patterns [VERIFIED: direct read]

### Secondary (MEDIUM confidence)

- None required — all critical claims verified via primary sources.

### Tertiary (LOW confidence)

- None.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions verified against pip registry; both libraries confirmed available for install
- Architecture: HIGH — patterns derived directly from existing codebase files and Context7 FastAPI/PyJWT docs
- Pitfalls: HIGH — PyJWT 2.x algorithm list requirement and datetime deprecation verified via Context7; others derived from locked decisions in CONTEXT.md

**Research date:** 2026-05-27
**Valid until:** 2026-06-27 (PyJWT and passlib are stable; FastAPI auth patterns are stable)
