---
phase: 11-auth-tenant-management-api
plan: 02
subsystem: auth-routers
tags: [fastapi, jwt, bcrypt, passlib, sqlite, tenants, auth, testing]

# Dependency graph
requires:
  - phase: 11-auth-tenant-management-api
    plan: 01
    provides: app/auth.py with get_current_tenant, require_super_admin, create_access_token; db_client fixture; is_super_admin column
provides:
  - app/routers/auth.py with POST /auth/login (LoginRequest + TokenResponse)
  - app/routers/tenants.py with POST/GET /admin/tenants, DELETE /admin/tenants/{id}, GET /tenants/me
  - app/main.py with auth+tenants routers registered
  - tests/test_auth.py test_login_success smoke test passing
affects: [11-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - conn try/finally per route handler (connection close discipline)
    - pwd_context = CryptContext(schemes=["bcrypt"]) singleton per router file (passlib singletons are cheap)
    - bool(row["is_active"]) coercion for SQLite integer to Python bool in TenantResponse
    - No global prefix on tenants router — serves /admin/tenants/* and /tenants/me from same APIRouter

key-files:
  created:
    - app/routers/auth.py
    - app/routers/tenants.py
  modified:
    - app/main.py
    - tests/test_auth.py

key-decisions:
  - "tenants router has no global prefix — both /admin/tenants and /tenants/me are full path decorators"
  - "password_hash appears twice in auth.py (SELECT + row[\"password_hash\"] for verify) — both are server-side only, never serialized in response"
  - "verify_token imported in test_auth.py for JWT claim assertions in smoke test"

# Metrics
duration: 20min
completed: 2026-05-28
---

# Phase 11 Plan 02: Auth Routers and Tenant CRUD Summary

**POST /auth/login + /admin/tenants CRUD + /tenants/me FastAPI routers wired to SQLite; smoke test confirms JWT pipeline end-to-end**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-28T02:20:00Z
- **Completed:** 2026-05-28T02:40:00Z
- **Tasks:** 3 (each with TDD atomic commits)
- **Files modified:** 4

## Accomplishments

- `app/routers/auth.py` delivers POST /auth/login with bcrypt verify, is_active filter, no user enumeration (T-11-09, T-11-10)
- `app/routers/tenants.py` delivers POST/GET /admin/tenants behind require_super_admin, DELETE with soft-delete cascade, GET /tenants/me with JWT isolation (T-11-11 through T-11-17)
- `app/main.py` extended to register both routers — all 5 routes now visible in OpenAPI
- `tests/test_auth.py` test_login_success unskipped and passing; other 8 stubs remain for Plan 03

## Route Table

| Path | Methods | Depends |
|------|---------|---------|
| /auth/login | POST | none |
| /admin/tenants | POST | require_super_admin |
| /admin/tenants | GET | require_super_admin |
| /admin/tenants/{tenant_id} | DELETE | require_super_admin |
| /tenants/me | GET | get_current_tenant |

## Task Commits

1. **Task 1: POST /auth/login in app/routers/auth.py** - `e0d5009` (feat)
2. **Task 2: /admin/tenants CRUD + /tenants/me in app/routers/tenants.py** - `c2cfd88` (feat)
3. **Task 3: Register routers in app/main.py + unskip smoke test** - `13283ba` (feat)

## OpenAPI Confirmation

Running `python3 -c "from app.main import app; paths = sorted({r.path for r in app.routes}); print(paths)"` after all commits lists `/admin/tenants`, `/admin/tenants/{tenant_id}`, `/auth/login`, `/tenants/me` alongside all previously registered routes. All 5 new operations are visible.

## Smoke Test Result

`python3 -m pytest tests/test_auth.py::test_login_success -x -q` exits 0:
- POST /auth/login with seeded super-admin credentials returns 200
- body["token_type"] == "bearer" and body["access_token"] starts with "eyJ"
- verify_token(token) returns decoded["sub"] == str(sa_id) and decoded["role"] == "super_admin"

## Pytest Summary

`python3 -m pytest tests/ -q`: **29 passed, 8 skipped, 0 failures**

- 21 Phase 10 db_foundation tests: pass (no regression)
- 7 Phase 11 Plan 01 auth unit tests: pass (no regression)
- 1 new smoke test (test_login_success): pass
- 8 skip stubs in test_auth.py: skipped (awaiting Plan 03)

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Notes

The acceptance criterion `grep -c 'password_hash' app/routers/auth.py` returns 2 (not 1 as stated in the plan). The second occurrence is `row["password_hash"]` in the bcrypt verify call — also server-side only. The security property holds: password_hash is never serialized in any response model. Both usages are necessary for correct operation, and neither leaks to clients.

## Known Stubs

`tests/test_auth.py` — 8 remaining test functions call `pytest.skip("Wave 0 stub — implemented in plan 03")`. This is intentional: Plan 03 fills in the full behavioral matrix.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes beyond those defined in the plan's threat model. All T-11-09 through T-11-17 mitigations are implemented as specified.

---
*Phase: 11-auth-tenant-management-api*
*Completed: 2026-05-28*
