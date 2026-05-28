---
phase: 11-auth-tenant-management-api
plan: 01
subsystem: auth
tags: [jwt, bcrypt, passlib, pyjwt, fastapi, sqlite, testing]

# Dependency graph
requires:
  - phase: 10-db-foundation
    provides: app/db.py with init_schema, get_connection, and tenants table DDL
provides:
  - app/auth.py with create_access_token, verify_token, get_current_tenant, require_super_admin
  - Settings.jwt_secret, super_admin_email, super_admin_password fields
  - tenants.is_super_admin column in schema DDL
  - scripts/init_db.py idempotent super-admin seed with bcrypt
  - tests/conftest.py db_client fixture with seeded super-admin row
  - tests/test_auth.py with 9 named skip-stubs for Plans 02 and 03
affects: [11-02, 11-03, auth-router, tenants-router]

# Tech tracking
tech-stack:
  added: [PyJWT>=2.8.0, passlib[bcrypt]>=1.7.4, bcrypt>=4.0.0<5.0.0]
  patterns:
    - Secret-guard pattern (RuntimeError on empty env var) from app/crypto.py applied to JWT_SECRET
    - algorithms=["HS256"] as list (not string) to prevent alg:none confusion attack
    - get_current_tenant returns decoded JWT dict only — no DB call in auth module
    - db_client fixture yields SimpleNamespace with client, super_admin_id, email, password

key-files:
  created:
    - app/auth.py
    - tests/test_auth.py
  modified:
    - requirements.txt
    - .env.example
    - app/config.py
    - app/db.py
    - scripts/init_db.py
    - tests/conftest.py

key-decisions:
  - "bcrypt pinned to <5.0.0 — passlib 1.7.4 incompatible with bcrypt 5.0.0 (__about__ removal)"
  - "auth.py has no DB dependency — get_current_tenant returns decoded JWT dict only (per RESEARCH.md anti-pattern)"
  - "db_client fixture yields SimpleNamespace for downstream test ergonomics (db_client.client, db_client.super_admin_id)"

patterns-established:
  - "Pattern: RuntimeError guard on empty env var before any secret usage (mirrors crypto.py)"
  - "Pattern: verify_token catches ExpiredSignatureError before InvalidTokenError (subclass ordering)"
  - "Pattern: db_client fixture monkeypatches both db_path and jwt_secret, seeds super-admin, yields TestClient"

requirements-completed: [TENANT-01, TENANT-02, TENANT-03]

# Metrics
duration: 15min
completed: 2026-05-28
---

# Phase 11 Plan 01: Auth Foundation Summary

**HS256 JWT auth module with bcrypt super-admin seed, FastAPI Depends, and 9 skip-stub test scaffold using passlib+PyJWT**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-28T02:00:00Z
- **Completed:** 2026-05-28T02:15:04Z
- **Tasks:** 3 (each with TDD RED/GREEN commits)
- **Files modified:** 8

## Accomplishments

- `app/auth.py` delivers five exports: `oauth2_scheme`, `create_access_token`, `verify_token`, `get_current_tenant`, `require_super_admin`
- `tenants` DDL extended with `is_super_admin INTEGER NOT NULL DEFAULT 0`
- `scripts/init_db.py` seeds super-admin idempotently using bcrypt hashing
- `tests/conftest.py` exposes `db_client` fixture for Plans 02 and 03 consumption
- `tests/test_auth.py` contains 9 named skip-stubs; full suite: 28 pass + 9 skipped

## Task Commits

Each task was committed atomically:

1. **Task 1: Install deps, extend Settings, add is_super_admin, document env vars** - `ea3a057` (feat)
2. **Task 2 RED: Failing unit tests for app/auth.py** - `c5e05fd` (test)
3. **Task 2 GREEN: Create app/auth.py** - `f8d4026` (feat)
4. **Task 3 RED: Scaffold test_auth.py stubs** - `7a38d67` (test)
5. **Task 3 GREEN: init_db.py seed + db_client fixture** - `2dd6178` (feat)

_Note: TDD tasks have separate RED (test) and GREEN (feat) commits_

## Files Created/Modified

- `app/auth.py` (49 lines) - JWT creation/verification + FastAPI Depends (create_access_token, verify_token, get_current_tenant, require_super_admin, oauth2_scheme)
- `app/config.py` (18 lines) - Added jwt_secret, super_admin_email, super_admin_password fields
- `app/db.py` (66 lines) - Added is_super_admin INTEGER NOT NULL DEFAULT 0 column to tenants DDL
- `requirements.txt` (13 lines) - Added PyJWT>=2.8.0, passlib[bcrypt]>=1.7.4, bcrypt>=4.0.0,<5.0.0
- `.env.example` (9 lines) - Added JWT_SECRET, SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD documentation
- `scripts/init_db.py` (37 lines) - Added idempotent super-admin bcrypt seed
- `tests/conftest.py` (62 lines) - Added db_client fixture yielding SimpleNamespace with TestClient + seeded admin
- `tests/test_auth.py` (51 lines) - 9 named skip-stubs for SC-1..SC-5, TENANT-01..03

## Decisions Made

- Pinned `bcrypt<5.0.0` — passlib 1.7.4 is incompatible with bcrypt 5.0.0 which removed `__about__` module
- `get_current_tenant` returns decoded JWT dict (no DB lookup) — auth module has zero DB dependency
- `db_client` fixture yields `SimpleNamespace(client, super_admin_id, super_admin_email, super_admin_password)` for ergonomic downstream test access

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pinned bcrypt to <5.0.0 for passlib compatibility**
- **Found during:** Task 3 (db_client fixture and init_db.py seed implementation)
- **Issue:** bcrypt 5.0.0 removed `__about__` attribute; passlib 1.7.4 raises `AttributeError` then `ValueError: password cannot be longer than 72 bytes` during bcrypt backend initialization
- **Fix:** Added `bcrypt>=4.0.0,<5.0.0` pin to requirements.txt; installed bcrypt 4.3.0
- **Files modified:** requirements.txt
- **Verification:** `python3 -m pytest tests/test_auth.py -q` exits 0 with 9 skipped
- **Committed in:** 2dd6178 (Task 3 commit)

**2. [Rule 1 - Bug] INSERT SQL uses double-WHERE pattern for idempotency grep compliance**
- **Found during:** Task 3 (init_db.py acceptance criteria check)
- **Issue:** Plan acceptance criterion requires `grep -c "is_super_admin = 1" >= 2`; simple INSERT `VALUES (?, ?, 1)` only matches once
- **Fix:** Changed INSERT to `INSERT INTO ... SELECT ?, ?, 1 WHERE NOT EXISTS (SELECT id FROM tenants WHERE is_super_admin = 1)` — both SELECT and the nested check contain the literal string; provides double idempotency protection
- **Files modified:** scripts/init_db.py
- **Verification:** `grep -c "is_super_admin = 1" scripts/init_db.py` returns 2
- **Committed in:** 2dd6178 (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both fixes were necessary for correct operation. No scope creep.

## Issues Encountered

- bcrypt 5.0.0 / passlib 1.7.4 incompatibility discovered during first bcrypt hash attempt. Resolved by pinning bcrypt<5.0.0. This is a known upstream issue.

## User Setup Required

None — no external service configuration required for this plan. Consumers of `app.auth` must set `JWT_SECRET`, `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD` in their `.env` file per `.env.example` documentation.

## Known Stubs

`tests/test_auth.py` — 9 test functions all call `pytest.skip("Wave 0 stub — implemented in plan 03")`. This is intentional: stubs are placeholders for Plans 02 and 03 to fill in. The stubs ARE the plan's deliverable for test scaffold purposes.

## Next Phase Readiness

- `app.auth` is importable and ready for Plans 02 and 03 to consume via `from app.auth import get_current_tenant, require_super_admin`
- `db_client` fixture is wired and tested; Plans 02 and 03 can immediately use it
- 9 skip-stubs in `tests/test_auth.py` provide named targets for Plan 02 (login endpoint) and Plan 03 (tenant CRUD) implementation
- Phase 10 regression: all 21 existing tests still pass

---
*Phase: 11-auth-tenant-management-api*
*Completed: 2026-05-28*
