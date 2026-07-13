---
phase: 12-page-connection-api-facebook-oauth
plan: 01
subsystem: auth-oauth
tags: [facebook, oauth, page-connection, jwt-state, graph-api, fernet, upsert]
requires:
  - Phase 10: pages table schema, Fernet encrypt_token/decrypt_token, get_connection
  - Phase 11: get_current_tenant Depends, JWT_SECRET setting, /admin/tenants API, test conftest
provides:
  - GET /auth/facebook/start (302 redirect to FB v25.0 OAuth dialog, Bearer required)
  - GET /auth/facebook/callback (validates state JWT, runs 3-step token exchange, encrypts + UPSERTs pages, subscribes webhooks)
  - app/fb_client.py Graph API helper module (v25.0)
  - Settings.fb_app_id, Settings.fb_app_secret, Settings.fb_redirect_uri
  - create_oauth_state / verify_oauth_state helpers (HS256, 10-min exp)
affects:
  - app/config.py
  - app/main.py (mounts pages.router)
  - .env.example
  - tests/conftest.py (db_client fixture)
tech-stack:
  added: []
  patterns:
    - Stateless CSRF via HS256-signed state JWT carrying tenant_id + nonce + 10-min exp
    - 3-step Graph API token exchange (code -> short -> long -> page tokens) via synchronous httpx
    - Atomic UPSERT + webhook subscription in single try/except with conn.rollback on failure
    - Fernet encryption of Page access tokens before persistence
    - Every Graph API URL built from module-level GRAPH_BASE = "https://graph.facebook.com/v25.0"
key-files:
  created:
    - app/fb_client.py
    - app/routers/pages.py
    - tests/test_pages.py
    - .planning/phases/12-page-connection-api-facebook-oauth/12-01-SUMMARY.md
  modified:
    - app/config.py
    - .env.example
    - app/main.py
    - tests/conftest.py
decisions:
  - "Stateless state JWT (no server-side session store) — reuses existing JWT_SECRET; 10-min exp bounds replay window"
  - "Synchronous httpx.get/post/delete in fb_client — matches existing project pattern (Pitfall 8 accepts for MVP admin traffic)"
  - "check_token_health and unsubscribe_page_webhook swallow errors (best-effort); token-exchange helpers surface errors as HTTPException 400"
  - "test_callback_webhook_failure_rollback uses pytest.raises(RuntimeError) — Starlette TestClient re-raises server exceptions by default; DB assertion (0 rows) is the primary rollback proof"
metrics:
  duration_minutes: 4
  tasks_completed: 3
  files_touched: 7
  tests_added: 6
  tests_passing: 43
  completed: "2026-07-13T20:35:15Z"
---

# Phase 12 Plan 01: Facebook OAuth Page-Connection API Summary

Facebook OAuth start + callback endpoints, stateless CSRF-protected state JWTs, 3-step Graph API token exchange, Fernet-encrypted Page-token UPSERT, atomic webhook subscription with rollback, and a full PAGE-01 test suite — 43 tests green (37 pre-existing + 6 new).

## Tasks Completed

| # | Task | Files | Commit |
|---|------|-------|--------|
| 1 | Config + env + conftest + fb_client helper module | `app/config.py`, `.env.example`, `tests/conftest.py`, `app/fb_client.py` | `539d986` |
| 2 | `app/routers/pages.py` with start + callback endpoints + main.py mount | `app/routers/pages.py`, `app/main.py` | `c43e706` |
| 3 | PAGE-01 test suite (6 tests) with mocked Graph API | `tests/test_pages.py` | `35bc218` |

## What Was Built

**`app/fb_client.py` — Graph API helper module (v25.0)**
- `GRAPH_BASE = "https://graph.facebook.com/v25.0"` — every URL derives from this constant.
- `exchange_code_for_short_token`, `exchange_for_long_lived_token`, `get_user_pages` — token-exchange helpers with `resp.raise_for_status()` **and** JSON `error`-key check (Pitfall 2: Graph API returns HTTP 200 with `error` in body for auth failures).
- `subscribe_page_webhook` — POST `/{page-id}/subscribed_apps` with `messages,messaging_postbacks,messaging_referrals` fields.
- `unsubscribe_page_webhook` — best-effort DELETE (swallows errors, per disconnect UX contract).
- `check_token_health` — inline app-token `f"{app_id}|{app_secret}"`, returns `False` on any exception.
- `_require_fb_settings` guard raises `RuntimeError` when any of the three env vars are unset (mirrors `app/crypto.py::_fernet()` pattern).

**`app/routers/pages.py` — OAuth wiring**
- `router = APIRouter(tags=["pages"])` — no prefix (paths served: `/auth/facebook/start`, `/auth/facebook/callback`).
- `create_oauth_state(tenant_id)` — HS256 JWT carrying `tenant_id`, `nonce` (secrets.token_hex(16)), `exp` (+10 min). Guards missing `JWT_SECRET`.
- `verify_oauth_state(state)` — raises `HTTPException(400, "OAuth state expired — please try again")` on `ExpiredSignatureError`, and `HTTPException(400, "Invalid OAuth state")` on `InvalidTokenError`.
- `_store_pages_and_subscribe(pages, tenant_id)` — opens one connection, UPSERTs each page (SELECT-then-UPDATE-or-INSERT keyed by `(page_fb_id, tenant_id)`), calls `subscribe_page_webhook`, and either `conn.commit()` or `conn.rollback() → raise` on any exception. All SQL uses `?` placeholders.
- `GET /auth/facebook/start` — `Depends(get_current_tenant)`; returns `RedirectResponse(url=…, status_code=302)` to `https://www.facebook.com/v25.0/dialog/oauth?…` with `client_id`, `redirect_uri`, `scope="pages_show_list,pages_manage_metadata,pages_messaging"`, `state`, `response_type=code`.
- `GET /auth/facebook/callback` — validates state **before** any Graph API call, runs the 3-step exchange, returns `{"pages_connected": N}`. Auth is carried by the state JWT, not the Bearer scheme (callback is invoked by Facebook's browser redirect).

**Test suite (`tests/test_pages.py`)** — 6 PAGE-01 tests:
1. `test_oauth_start` — 302 redirect with correct URL-encoded params; 401 without Bearer.
2. `test_state_jwt` — decodes state, asserts tenant_id + nonce (≥16 chars) + exp within `[now, now+11 min]`.
3. `test_callback_invalid_state` — malformed JWT → 400.
4. `test_callback_expired_state` — exp 1 minute in the past → 400 with `"OAuth state expired — please try again"`.
5. `test_callback_webhook_failure_rollback` — mocks 3 GET calls to succeed, forces `subscribe_page_webhook` to raise `RuntimeError`; asserts `pytest.raises(RuntimeError)` **and** `SELECT COUNT(*)` returns 0 (proves rollback executed).
6. `test_callback_success` — full success path: 200 + `{"pages_connected": 1}`, DB row present with `access_token_enc != "page-tok"`, `decrypt_token(row) == "page-tok"` (Fernet round-trip), plus UPSERT idempotency check on re-invocation (still 1 row).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Starlette TestClient re-raises unhandled `RuntimeError` instead of converting to 500**
- **Found during:** Task 3 (test_callback_webhook_failure_rollback initial run)
- **Issue:** The plan specified `assert resp.status_code in (500, 502, 400)`, but Starlette's `TestClient` uses `raise_server_exceptions=True` by default, so the `RuntimeError("subscription failed")` from `_fail_subscribe` propagates through the test call rather than surfacing as an HTTP status code.
- **Fix:** Wrapped the callback call in `pytest.raises(RuntimeError, match="subscription failed")`. The DB assertion (`SELECT COUNT(*)` returns 0) remains the primary proof that `conn.rollback()` executed before propagation.
- **Files modified:** `tests/test_pages.py` (test_callback_webhook_failure_rollback)
- **Commit:** `35bc218`
- **Threat coverage preserved:** T-12-06 (INSERT rollback on subscription failure) — the DB-count assertion is the load-bearing verification; the exception propagation is expected behavior of the TestClient, not a functional gap.

### Non-issues (verify command shape)

- The plan's `<automated>` verify command for Task 2 uses `routes = {r.path for r in app.routes}`. In the installed FastAPI version, `include_router` produces `_IncludedRouter` objects whose top-level `path` attribute is `None`; the wrapped Route objects only surface via HTTP request (or by recursing into internal `router.routes`, which isn't exposed in this version). The routes **are** correctly registered — verified via `TestClient` returning `401` for `/auth/facebook/start` (auth-gated) and `400 {"detail":"Invalid OAuth state"}` for `/auth/facebook/callback`. This is a plan-verifier limitation, not a code defect; no plan drift required. All 6 PAGE-01 tests exercise both routes via TestClient.

## Threat Coverage (STRIDE)

All in-scope threats from the plan's `<threat_model>` are mitigated by tests:

| Threat ID | Category | Mitigation | Test |
|-----------|----------|-----------|------|
| T-12-01 | Spoofing (crafted callback) | `verify_oauth_state` runs before any Graph API call | `test_callback_invalid_state` |
| T-12-02 | EoP (state replay) | 10-min `exp`; `ExpiredSignatureError` → 400 | `test_callback_expired_state` |
| T-12-03 | Info Disclosure (plaintext token) | Fernet `encrypt_token` before INSERT/UPDATE | `test_callback_success` (decrypt round-trip + non-equality) |
| T-12-04 | Info Disclosure (fb_app_secret leak) | Secret used only as `httpx` param value; no logs, no error-response echoing | Code inspection (no `settings.fb_app_secret` in prints/details) |
| T-12-05 | Tampering (SQLi via page_fb_id) | `?` placeholders throughout | Plan grep gate + `test_callback_success` UPSERT |
| T-12-06 | Tampering (webhook orphan) | Try/except with `conn.rollback()` before `raise` | `test_callback_webhook_failure_rollback` (0 rows after failure) |

## Verification Results

- `pytest tests/ -q` → **43 passed** (37 pre-existing + 6 PAGE-01)
- `grep -c 'GRAPH_BASE = "https://graph.facebook.com/v25.0"' app/fb_client.py` → **1** (v25.0 enforced)
- `grep -c 'timedelta(minutes=10)' app/routers/pages.py` → **1** (state JWT expiry enforced)
- `grep -E "f-?'.*WHERE.*\{" app/routers/pages.py` → **0 matches** (no f-strings in SQL)
- `fb_app_secret` grep in `app/fb_client.py` → used only inside function bodies as `httpx` param value; never in module-level statements, prints, or exception details

## Authentication Gates

None. All Graph API calls were mocked via `monkeypatch` in tests; no live Facebook credentials required. The real OAuth flow (with valid `FACEBOOK_APP_ID/SECRET/REDIRECT_URI`) is a Manual-Only verification per `12-VALIDATION.md`.

## Known Stubs

None. The plan's scope is PAGE-01 only (start + callback). PAGE-02/03/04 endpoints (`GET /pages`, `DELETE /pages/{id}`, `GET /pages/{id}/health`) are intentionally out of scope for this plan — they will be delivered by plan 12-02.

## Self-Check: PASSED

- Created files:
  - `FOUND: app/fb_client.py`
  - `FOUND: app/routers/pages.py`
  - `FOUND: tests/test_pages.py`
  - `FOUND: .planning/phases/12-page-connection-api-facebook-oauth/12-01-SUMMARY.md`
- Modified files:
  - `FOUND: app/config.py` (has fb_app_id / fb_app_secret / fb_redirect_uri)
  - `FOUND: .env.example` (has FACEBOOK_APP_ID / FACEBOOK_APP_SECRET / FACEBOOK_REDIRECT_URI)
  - `FOUND: app/main.py` (imports and mounts pages.router)
  - `FOUND: tests/conftest.py` (monkeypatches fernet_key + 3 fb_* fields)
- Commits: `FOUND: 539d986`, `FOUND: c43e706`, `FOUND: 35bc218`
- Test suite: `43 passed` (target met)
