---
phase: 11-auth-tenant-management-api
verified: 2026-05-28T12:00:00Z
status: human_needed
score: 9/10 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run `python3 main.py` to start the FastAPI server, then curl POST /auth/login with valid super-admin credentials, copy the access_token, open https://jwt.io, paste the token, and confirm: header alg=HS256, payload has sub (string), role='super_admin', exp is a Unix timestamp ~7 days out, and the token has exactly three dot-separated segments."
    expected: "jwt.io decodes without error; header alg=HS256; payload sub is a quoted-string tenant ID; role is 'super_admin'; exp resolves to approximately 2026-06-04 or later; Signature Verified badge appears when JWT_SECRET is pasted."
    why_human: "JWT structural correctness (header alg, claim names, exp timestamp value, three-segment format) cannot be confirmed by grepping source code or running unit tests — the token is issued at runtime against a production secret and must be inspected in an external tool to rule out malformed encoding or wrong algorithm header."
---

# Phase 11: Auth & Tenant Management API Verification Report

**Phase Goal:** A super-admin can log in and manage client accounts via FastAPI endpoints secured by JWT — clients see only their own data
**Verified:** 2026-05-28T12:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC-1 | POST /auth/login with valid super-admin credentials returns a signed JWT; invalid credentials return 401 | VERIFIED | `app/routers/auth.py`: bcrypt verify + is_active=1 filter in SQL; `test_login_success` and `test_login_invalid` pass (9/9 tests green) |
| SC-2 | Super-admin can create a new client account via POST /admin/tenants and it appears in the tenant list | VERIFIED | `app/routers/tenants.py` create_tenant handler; returns 201 + TenantResponse; `test_create_tenant` and `test_duplicate_email` pass |
| SC-3 | Super-admin can retrieve a list of all client accounts with Page count via GET /admin/tenants | VERIFIED | `app/routers/tenants.py` list_tenants with LEFT JOIN pages; WHERE t.is_super_admin=0; `test_list_tenants` passes including page_count assertion |
| SC-4 | Super-admin can delete/deactivate a client account via DELETE /admin/tenants/{id}; client Pages are disconnected | VERIFIED | `app/routers/tenants.py` delete_tenant: UPDATE tenants + UPDATE pages in one transaction; `test_soft_delete` passes including direct DB assertion of is_active=0 |
| SC-5 | Every tenant-scoped endpoint rejects requests whose JWT tenant_id does not match the resource | VERIFIED | `/tenants/me` parameterized by `int(current["sub"])`; require_super_admin returns 403 for client role; `test_tenant_isolation` and `test_forbidden` pass |
| SC-JWT | JWT is a well-formed HS256 token with correct sub/role/exp claims inspectable at jwt.io | UNCERTAIN | `app/auth.py` uses `jwt.encode(..., algorithm="HS256")` with a 7-day timedelta; automated test confirms roundtrip; human jwt.io inspection required to confirm structural correctness against a production token |

**Score:** 5/5 roadmap success criteria VERIFIED (plus 1 human checkpoint pending)

---

### Must-Haves from Plan Frontmatter (Plans 01, 02, 03 — merged, deduplicated)

| # | Must-Have | Status | Evidence |
|---|-----------|--------|----------|
| 1 | PyJWT and passlib[bcrypt] are installed and importable | VERIFIED | `requirements.txt` has `PyJWT>=2.8.0`, `passlib[bcrypt]>=1.7.4`, `bcrypt>=4.0.0,<5.0.0`; `from app.auth import ...` exits 0 |
| 2 | Settings exposes jwt_secret, super_admin_email, super_admin_password fields | VERIFIED | `app/config.py` lines 11-13: all three fields present with empty-string defaults |
| 3 | tenants table includes is_super_admin column with DEFAULT 0 | VERIFIED | `app/db.py` line 24: `is_super_admin INTEGER NOT NULL DEFAULT 0` |
| 4 | app.auth.create_access_token signs HS256 JWT with sub/role/exp claims (7-day expiry) | VERIFIED | `app/auth.py` lines 14-22: `timedelta(days=7)`, `algorithm="HS256"`; test roundtrip confirms claim presence |
| 5 | app.auth.verify_token raises HTTPException(401) on expired/invalid tokens | VERIFIED | `app/auth.py` lines 25-39: ExpiredSignatureError → 401 "Token expired"; InvalidTokenError → 401 "Invalid token"; `test_forbidden` confirms with "garbage.token.value" |
| 6 | app.auth.get_current_tenant and require_super_admin Depends are importable | VERIFIED | Import exits 0; both used in `app/routers/tenants.py` |
| 7 | scripts/init_db.py seeds a super-admin row idempotently from SUPER_ADMIN_EMAIL/PASSWORD env vars | VERIFIED | `scripts/init_db.py`: SELECT guard + INSERT SELECT WHERE NOT EXISTS pattern; RuntimeError guard present |
| 8 | tests/test_auth.py has 9 fully implemented tests, 0 skips, covering SC-1..SC-5 + TENANT-01..03 | VERIFIED | `grep -c "pytest.skip" tests/test_auth.py` returns 0; `python3 -m pytest tests/test_auth.py -v` shows 9 passed |
| 9 | tests/conftest.py provides db_client fixture wired to tmp-path SQLite with seeded super-admin | VERIFIED | `tests/conftest.py` lines 38-63: monkeypatches db_path + jwt_secret, calls init_schema, inserts super-admin row, yields SimpleNamespace |
| 10 | Human has decoded a real /auth/login JWT at jwt.io and confirmed sub, role, exp claims are correct | UNCERTAIN | Plan 03 Task 2 SUMMARY records "approved" but this is a human checkpoint whose evidence is outside the codebase — requires human re-confirmation at verification time |

**Score:** 9/10 must-haves verified (1 uncertain — human checkpoint)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `requirements.txt` | PyJWT and passlib pinned | VERIFIED | Lines contain `PyJWT>=2.8.0`, `passlib[bcrypt]>=1.7.4`, `bcrypt>=4.0.0,<5.0.0` |
| `.env.example` | JWT_SECRET, SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD documented | VERIFIED | All three present with `=` suffix |
| `app/config.py` | Settings with jwt_secret, super_admin_email, super_admin_password | VERIFIED | Lines 11-13 add all three fields; existing fields preserved |
| `app/db.py` | tenants DDL with is_super_admin column | VERIFIED | Line 24: `is_super_admin INTEGER NOT NULL DEFAULT 0` before created_at |
| `app/auth.py` | create_access_token, verify_token, get_current_tenant, require_super_admin, oauth2_scheme | VERIFIED | 49-line file; all five exports present; no DB import |
| `app/routers/auth.py` | POST /auth/login with LoginRequest + TokenResponse | VERIFIED | 41-line file; prefix="/auth"; is_active=1 filter in SQL; bcrypt verify; password_hash never in response |
| `app/routers/tenants.py` | GET/POST /admin/tenants, DELETE /admin/tenants/{id}, GET /tenants/me | VERIFIED | 155-line file; four routes; three with require_super_admin, one with get_current_tenant |
| `app/main.py` | Registers auth.router and tenants.router | VERIFIED | Lines 6, 28-29: import and include_router for both |
| `scripts/init_db.py` | Idempotent super-admin seed with bcrypt | VERIFIED | 37-line file; RuntimeError guard; SELECT + INSERT SELECT WHERE NOT EXISTS pattern |
| `tests/conftest.py` | db_client fixture with monkeypatched db_path + jwt_secret + seeded admin | VERIFIED | Lines 38-63; both monkeypatches present; existing `client` and `vault_dir` fixtures preserved |
| `tests/test_auth.py` | 9 implemented tests, 0 skips | VERIFIED | 327-line file; 9 tests, 0 pytest.skip calls |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/auth.py` | `app.config.settings.jwt_secret` | module-level import + direct access | VERIFIED | Line 7: `from app.config import settings`; lines 15, 22, 27: all use `settings.jwt_secret` |
| `scripts/init_db.py` | `app.config.settings.super_admin_email/password` | module-level import | VERIFIED | Lines 8-9; lines 17, 30 reference both fields |
| `tests/conftest.py` | `app.db.init_schema + app.main.app` via TestClient | fixture wires tmp-path DB | VERIFIED | Lines 43, 56: `init_schema(db_path)` and `TestClient(app)` |
| `app/routers/auth.py` | `app.auth.create_access_token` | import + call inside login() | VERIFIED | Line 5: `from app.auth import create_access_token`; line 39: `create_access_token(sub=..., role=...)` |
| `app/routers/tenants.py` | `app.auth.get_current_tenant + require_super_admin` | Depends() on every route | VERIFIED | Line 5: import; `grep -c "Depends(require_super_admin)"` returns 3; `Depends(get_current_tenant)` returns 1 |
| `app/routers/tenants.py` | SQLite pages table | LEFT JOIN COUNT + UPDATE pages on delete | VERIFIED | Line 85: LEFT JOIN; line 122: UPDATE pages SET is_active=0 WHERE tenant_id=? |
| `app/main.py` | `app.routers.auth + app.routers.tenants` | include_router calls | VERIFIED | Lines 6, 28-29: import and both include_router calls present |
| `tests/test_auth.py` | `tests/conftest.py db_client` fixture | fixture parameter on every test | VERIFIED | All 9 test functions take `db_client` as parameter |
| `tests/test_auth.py` | POST /auth/login + /admin/tenants/* routes | TestClient HTTP calls with Bearer headers | VERIFIED | `_auth_headers` helper used throughout; protected-route calls pass Authorization header |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `app/routers/auth.py::login` | `row` (tenant row) | `conn.execute("SELECT ... WHERE email = ? AND is_active = 1")` | Yes — SQLite query with parameterized WHERE | FLOWING |
| `app/routers/tenants.py::list_tenants` | `rows` (tenant list) | LEFT JOIN query with `WHERE t.is_super_admin = 0` | Yes — real DB query; page_count from COUNT | FLOWING |
| `app/routers/tenants.py::create_tenant` | `row` (new tenant) | INSERT then SELECT WHERE id=? | Yes — INSERT + fresh row fetch | FLOWING |
| `app/routers/tenants.py::delete_tenant` | `pages_deactivated` | UPDATE pages; rowcount | Yes — real UPDATE rowcount | FLOWING |
| `app/routers/tenants.py::get_my_tenant` | `row` | SELECT WHERE id=int(current["sub"]) | Yes — tenant-isolated query from JWT sub | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 9 auth tests pass | `python3 -m pytest tests/test_auth.py -v -q` | 9 passed, 0 skipped, 0 failed (5.45s) | PASS |
| Full suite passes (37 tests) | `python3 -m pytest tests/ -q` | 37 passed, 0 failed | PASS |
| auth.py imports cleanly | `from app.auth import create_access_token, verify_token, get_current_tenant, require_super_admin, oauth2_scheme` | exits 0 | PASS |
| Routes registered in OpenAPI | `{r.path for r in app.routes if r.path.startswith(('/auth', '/admin', '/tenants'))}` | `['/admin/tenants', '/admin/tenants/{tenant_id}', '/auth/login', '/tenants/me']` | PASS |
| algorithms list form used | `grep -c 'algorithms=\["HS256"\]' app/auth.py` | 1 | PASS |
| No pytest.skip remaining | `grep -c "pytest.skip" tests/test_auth.py` | 0 | PASS |

---

### Probe Execution

Step 7c: SKIPPED — no `scripts/*/tests/probe-*.sh` files found. Phase does not declare conventional probes.

---

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| TENANT-01 | 11-01, 11-02, 11-03 | Super-admin can create a client account (email + password) | SATISFIED | `app/routers/tenants.py` POST /admin/tenants; `test_create_tenant` + `test_duplicate_email` pass |
| TENANT-02 | 11-01, 11-02, 11-03 | Super-admin can view list of all client accounts and Pages | SATISFIED | `app/routers/tenants.py` GET /admin/tenants with page_count LEFT JOIN; `test_list_tenants` passes |
| TENANT-03 | 11-01, 11-02, 11-03 | Super-admin can delete/deactivate a client account (disconnects Pages) | SATISFIED | `app/routers/tenants.py` DELETE /admin/tenants/{id} soft-delete cascade; `test_soft_delete` passes including direct DB assertion |

All three requirement IDs declared across all three plan frontmatters are accounted for. No orphaned requirements for Phase 11 were found in REQUIREMENTS.md (traceability table maps TENANT-01/02/03 to Phase 11 only).

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_auth.py` (all 8 non-login-success tests) | 16 warnings | InsecureKeyLengthWarning: test jwt_secret is 30 bytes, below 32-byte minimum for SHA256 | INFO | Test-only — production secret will be generated by `secrets.token_urlsafe(48)` per .env.example instruction. No security impact on production code. |

No TBD, FIXME, XXX, TODO, HACK, or PLACEHOLDER markers found in any phase-modified file. No stub patterns (empty returns, hardcoded arrays, console.log-only handlers) found.

---

### Human Verification Required

#### 1. JWT Structural Inspection at jwt.io

**Test:** Ensure `JWT_SECRET`, `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD` are set in `.env`. Run `python3 scripts/init_db.py` to seed the super-admin. Start the server: `python3 main.py`. In a second terminal: `curl -s -X POST http://localhost:8000/auth/login -H 'Content-Type: application/json' -d '{"email":"<SUPER_ADMIN_EMAIL>","password":"<SUPER_ADMIN_PASSWORD>"}'`. Copy the `access_token` value. Open https://jwt.io, paste the token into the Encoded panel. Inspect the decoded payload.

**Expected:**
- Token starts with `eyJ` (confirmed by automated test, but inspect structure manually)
- Header: `{"alg":"HS256","typ":"JWT"}`
- Payload has exactly three keys: `sub` (quoted string, e.g. `"1"`), `role` (`"super_admin"`), `exp` (integer Unix timestamp)
- `exp` resolves to approximately 7 days from the time the token was issued
- Three dot-separated segments only (no extras)
- Optional: paste JWT_SECRET into jwt.io Verify Signature field — "Signature Verified" green badge appears

**Why human:** The JWT roundtrip is verified by automated tests, but structural correctness (header alg field, claim name spelling, exp value, segment count) against a real production-signed token requires external tool inspection. Tests use a short test secret and verify only that claims survive encode/decode; they do not inspect raw token format or header bytes.

---

### Gaps Summary

No gaps were found that block the automated phase goal. All 5 roadmap success criteria have passing tests. The only pending item is the human jwt.io inspection checkpoint defined in 11-03-PLAN.md Task 2 as a blocking gate.

Note: The `db_client` SimpleNamespace in `tests/conftest.py` does NOT expose a `jwt_secret` attribute (the 11-03-PLAN interface spec listed it, and one test in the 11-03-PLAN mentioned `monkeypatch.setattr(config_module.settings, "jwt_secret", db_client.jwt_secret)`). In practice, no test references `db_client.jwt_secret` — the fixture already monkeypatches the secret internally during setup, making the attribute unnecessary. Tests pass. This is a documentation discrepancy, not a functional gap.

---

_Verified: 2026-05-28T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
