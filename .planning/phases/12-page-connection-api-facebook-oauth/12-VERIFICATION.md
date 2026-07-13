---
phase: 12-page-connection-api-facebook-oauth
verified: 2026-07-14T00:00:00Z
status: human_needed
score: 8/8 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Real Facebook OAuth flow end-to-end"
    expected: "Click 'Connect with Facebook' in a browser, complete the Meta login/consent dialog with a test Page, and see the Page appear in GET /pages with status='active'. The stored access_token_enc must decrypt back to a real Facebook long-lived Page token (not a mock)."
    why_human: "Requires a registered Facebook App with valid FACEBOOK_APP_ID/SECRET/REDIRECT_URI matching a Meta App Dashboard entry, plus an interactive browser session to complete the OAuth consent dialog. Cannot be automated without live Meta credentials."
  - test: "App Review submission for pages_messaging Advanced Access"
    expected: "pages_messaging permission submitted for App Review in Meta App Dashboard. Required for Live mode message delivery (Development mode only works for admin/tester roles)."
    why_human: "Meta's review process is external and manual; typically days-to-weeks turnaround. Blocks production PAGE-01 use but not code-level correctness."
  - test: "Webhook delivery to running bot for a connected Page"
    expected: "After connecting a Page via the real OAuth flow, send a test Messenger message from a tester account; the bot's /webhook endpoint receives the event, the correct Page token is loaded, and the bot responds."
    why_human: "Requires a publicly reachable HTTPS bot instance, a subscribed Page, and a real Facebook user account. subscribe_page_webhook was invoked with mocked Graph API in tests — no proof yet that Facebook actually routes events after a real subscription."
  - test: "Cross-tenant leak check under adversarial input"
    expected: "Craft two client JWTs (A and B), attempt to GET /pages/{id}/health and DELETE /pages/{id} with A's token targeting B's real page id — all should return 404. Test suite covers this at the unit level, but manual review of production logs after first real use is worth doing once."
    why_human: "Behavioral test coverage exists (test_pages_isolation, test_disconnect_not_found, test_token_health cross-tenant clause). Manual re-check under production traffic is recommended but not required for phase closure."
---

# Phase 12: Page Connection API + Facebook OAuth — Verification Report

**Phase Goal (ROADMAP.md):** Clients can connect their Facebook Pages via OAuth with full 3-step token exchange and automatic webhook subscription; token health is visible per Page.

**Verified:** 2026-07-14
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (Roadmap Success Criteria + PAGE requirements)

Every truth was verified against the actual codebase (files under `app/routers/pages.py`, `app/fb_client.py`, `app/config.py`, `tests/test_pages.py`, `tests/conftest.py`) and by running the full pytest suite.

| # | Truth (Roadmap SC / REQUIREMENTS.md) | Status | Evidence |
|---|---|---|---|
| 1 | (SC1 / PAGE-01) OAuth start redirects to Facebook OAuth dialog with correct scope + CSRF-protected state | VERIFIED | `app/routers/pages.py:98-112` builds `https://www.facebook.com/v25.0/dialog/oauth?...` with `client_id`, `redirect_uri`, `scope=pages_show_list,pages_manage_metadata,pages_messaging`, `state`, `response_type=code`. State JWT is HS256-signed with `settings.jwt_secret` and carries `tenant_id` + `nonce` + 10-min `exp` (`create_oauth_state` lines 34-43). `test_oauth_start` and `test_state_jwt` confirm 302 + URL shape + decodable state. |
| 2 | (SC1 / PAGE-01) Callback completes 3-step token exchange, Fernet-encrypts the Page token, atomically UPSERTs and subscribes webhook, rolls back on failure | VERIFIED | `_store_pages_and_subscribe` (lines 57-95) runs `encrypt_token()` then SELECT-then-UPDATE-or-INSERT then `fb_client.subscribe_page_webhook()` inside one try/except with `conn.rollback(); raise` on any exception, `conn.commit()` on success. `test_callback_success` proves Fernet round-trip (`decrypt_token(row) == "page-tok"`) + UPSERT idempotency (`pages_connected==1` on re-run, 1 row total). `test_callback_webhook_failure_rollback` proves 0 rows committed after simulated subscribe failure. |
| 3 | (SC2 / PAGE-02) `GET /pages` returns the client's connected Pages with active/revoked status | VERIFIED | `list_pages` handler (lines 127-160) filters `WHERE tenant_id = ? AND is_active = 1`, decrypts each token, calls `fb_client.check_token_health()`, and maps result to `PageResponse.status='active'|'revoked'`. `test_list_pages` asserts both fb_ids present + status='active'; `test_list_pages_revoked` asserts status='revoked' when `is_valid=false`. `access_token_enc` intentionally omitted from response model (T-12-11 mitigated). |
| 4 | (SC2 / PAGE-02) No cross-tenant leakage on `GET /pages` | VERIFIED | SELECT binds `tenant_id = int(current["sub"])`. `test_pages_isolation` seeds pages under two tenants and asserts each tenant's response contains only their own `page_fb_id` — behavioral proof of T-12-09 mitigation. |
| 5 | (SC3 / PAGE-03) `DELETE /pages/{id}` unsubscribes webhook (best-effort) + soft-deletes row; 404 on cross-tenant or unknown id | VERIFIED | `disconnect_page` (lines 163-195) SELECTs `WHERE id = ? AND tenant_id = ? AND is_active = 1` → 404 if missing; decrypts, calls `fb_client.unsubscribe_page_webhook`, UPDATEs `is_active = 0` with same two-predicate WHERE, commits. `test_disconnect_page` proves the *decrypted* token `tok-D` is passed to Graph (not the encrypted blob), row flips to `is_active=0`, and subsequent `GET /pages` returns `[]`. `test_disconnect_not_found` proves cross-tenant DELETE returns 404 AND does not mutate the row (T-12-10 mitigation). |
| 6 | (SC4 / PAGE-04) `GET /pages/{id}/health` returns `is_valid` + `expires_at` from Facebook debug_token; enables client-driven reconnect flow | VERIFIED (backend contract) | `page_health` (lines 198-241) calls `fb_client.httpx.get(GRAPH_BASE + "/debug_token", ...)` and returns `HealthResponse(is_valid, expires_at)`. Facebook's `expires_at=0` sentinel (non-expiring Page token) normalized to `None`. Bad ciphertext degrades to `is_valid=False` (T-12-13). `test_token_health` covers 3 phases: non-expiring, revoked, real expiry, plus cross-tenant 404. **Note:** the SC4 "Reconnect indicator" UI badge itself lives in Phase 15 (Admin Panel UI) — this phase provides only the backend health data. |
| 7 | (from must_haves) All in-scope routes registered on `app.main.app` and reachable | VERIFIED | Behavioral probe via `TestClient`: `/auth/facebook/start` → 401 unauth, `/auth/facebook/callback` → 400 (invalid state), `/pages` → 401 unauth, `/pages/{page_id}` DELETE → 401 unauth, `/pages/{page_id}/health` → 401 unauth. `app/main.py:6` imports pages, `app/main.py:30` calls `app.include_router(pages.router)`. |
| 8 | (from must_haves) Full pytest suite green | VERIFIED | `.venv/bin/python -m pytest tests/ -q` reports **49 passed, 0 failed, 0 skipped**. `tests/test_pages.py` alone reports **12 passed** (6 PAGE-01 + 3 PAGE-02 + 2 PAGE-03 + 1 PAGE-04). |

**Score:** 8/8 truths verified.

---

## Required Artifacts

Every artifact declared in `12-01-PLAN.md` and `12-02-PLAN.md` `must_haves.artifacts` was checked at all three levels (exists, substantive, wired) + data-flow trace.

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `app/config.py` | Settings has `fb_app_id`, `fb_app_secret`, `fb_redirect_uri` (empty string defaults) | VERIFIED | Lines 14-16 declare all three fields, defaults `""`. Post-executor commit `2760a8f` added `"extra": "ignore"` to `model_config` (line 18) — tolerates legacy env keys (e.g. `PAGE_ACCESS_TOKEN`, `VERIFY_TOKEN`) that would otherwise cause pydantic-settings `ValidationError` at import. This is a compatibility fix, not a scope change. |
| `.env.example` | Documents `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_REDIRECT_URI` | VERIFIED | Lines 10-13 present with comment header "Facebook OAuth — must match Meta App Dashboard registration exactly". `FACEBOOK_REDIRECT_URI` includes example value. |
| `app/fb_client.py` | New helper module with `GRAPH_BASE` + 6 exported functions using v25.0 URLs | VERIFIED | 105 lines. All 6 functions present + `_require_fb_settings` guard. `GRAPH_BASE = "https://graph.facebook.com/v25.0"` (line 7). Token-exchange functions call `resp.raise_for_status()` **and** check `"error" in data` (Pitfall 2 defense). `unsubscribe_page_webhook` swallows errors; `check_token_health` swallows and returns `False`. **No prints, no logs, no secret leaks in exception messages** — verified by grep. |
| `app/routers/pages.py` | Router + 2 OAuth handlers + 3 lifecycle handlers + `PageResponse` + `HealthResponse` | VERIFIED | 242 lines. `router = APIRouter(tags=["pages"])` (no prefix). 5 route handlers registered: `/auth/facebook/start`, `/auth/facebook/callback`, `/pages`, `/pages/{page_id}` (DELETE), `/pages/{page_id}/health`. Helpers `create_oauth_state`, `verify_oauth_state`, `_store_pages_and_subscribe` present. Models `PageResponse` and `HealthResponse` present (T-12-11: neither includes `access_token`). All SQL uses `?` placeholders — grep `WHERE.*\{[a-z_]+\}` returns 0 matches; grep `WHERE id = ? AND tenant_id = ?` returns 3 (SELECT + UPDATE in disconnect + SELECT in page_health). |
| `app/main.py` | Registers `pages.router` | VERIFIED | Line 6 imports `pages`; line 30 calls `app.include_router(pages.router)`. |
| `tests/conftest.py` | `db_client` fixture monkeypatches `fernet_key` + `fb_app_id` + `fb_app_secret` + `fb_redirect_uri` | VERIFIED | Lines 44-47 monkeypatch all four; `from cryptography.fernet import Fernet` at line 4. |
| `tests/test_pages.py` | 12 test functions (6 PAGE-01 + 6 PAGE-02..04) + `MockResponse` helper + `_seed_page` helper | VERIFIED | 466 lines. All 12 test names present via grep. `MockResponse` class at line 19. `_seed_page` at line 42 (uses `encrypt_token`). All 12 tests pass individually and as a group. |

---

## Key Link Verification

Every key link declared in plan `must_haves.key_links` was verified against the running code.

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `create_oauth_state` | `settings.jwt_secret` | `jwt.encode(payload, settings.jwt_secret, algorithm="HS256")` | WIRED | `app/routers/pages.py:43`. Guarded by `if not settings.jwt_secret: raise RuntimeError(...)` at line 36. |
| Callback handler | `app.crypto.encrypt_token` | `encrypt_token(page_token)` before INSERT/UPDATE | WIRED | `app/routers/pages.py:66`. `test_callback_success` proves the stored `access_token_enc != "page-tok"` and `decrypt_token(access_token_enc) == "page-tok"`. |
| `_store_pages_and_subscribe` | `subscribe_page_webhook` | Called inside try; failures trigger `conn.rollback(); raise` | WIRED | `app/routers/pages.py:86` inside try; lines 90-92 handle rollback. `test_callback_webhook_failure_rollback` proves 0 rows committed on failure. |
| `app/fb_client.py` | `https://graph.facebook.com/v25.0` | `GRAPH_BASE` module constant used for every `httpx` URL | WIRED | Constant defined once (line 7) and referenced in every `httpx.get/post/delete` call (lines 20, 38, 56, 68, 83, 94). |
| `GET /pages` handler | `pages` table with tenant filter | `WHERE tenant_id = ? AND is_active = 1` | WIRED | `app/routers/pages.py:134`. `test_pages_isolation` proves no cross-tenant bleed. |
| `GET /pages` per-row | `fb_client.check_token_health` | Decrypt token, pass to `check_token_health`, map to status | WIRED | Lines 145-156. |
| `DELETE /pages/{id}` handler | `fb_client.unsubscribe_page_webhook` | Best-effort call before UPDATE | WIRED | Line 186 (conditional on decrypted `page_token`). `test_disconnect_page` proves the decrypted token is passed, not the ciphertext. |
| `GET /pages/{id}/health` | `fb_client.httpx.get` `/debug_token` | `fb_client.httpx.get(GRAPH_BASE + "/debug_token", ...)` | WIRED | Line 226. Deliberately routed through `fb_client.httpx` so tests can monkeypatch `"app.fb_client.httpx.get"` uniformly. |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `list_pages` response | `result: list[PageResponse]` | SQLite `pages` table SELECT + `fb_client.check_token_health` per row | Yes — real DB read; `check_token_health` hits Graph API (mockable) | FLOWING |
| `page_health` response | `HealthResponse` | SQLite SELECT + Graph API `/debug_token` call | Yes | FLOWING |
| `disconnect_page` mutation | `pages.is_active` column | SQLite UPDATE | Yes — persisted; `test_disconnect_page` verifies `is_active=0` via direct SELECT | FLOWING |
| Callback token store | `pages.access_token_enc` | Fernet-encrypted long-lived Page token from `get_user_pages` | Yes — round-trip verified in `test_callback_success` | FLOWING |

No hollow props, no hardcoded empty returns. Every handler's response is populated from live DB queries or Graph API responses.

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Module imports without side effects | `.venv/bin/python -c "from app.routers import pages"` | exit 0 | PASS |
| GRAPH_BASE is v25.0 | `.venv/bin/python -c "from app import fb_client; print(fb_client.GRAPH_BASE)"` | `https://graph.facebook.com/v25.0` | PASS |
| All 5 phase-12 routes reachable via TestClient | Probe `/auth/facebook/start`, `/auth/facebook/callback`, `/pages`, `/pages/1`, `/pages/1/health` | 401/400/401/401/401 (all handlers responding — none returning 404 "route not found") | PASS |
| Full pytest suite | `.venv/bin/python -m pytest tests/ -q` | `49 passed, 0 failed, 0 skipped` in 13.4s | PASS |
| PAGE-01..04 tests only | `.venv/bin/python -m pytest tests/test_pages.py -v` | `12 passed` — all named tests from validation map | PASS |
| No f-string SQL interpolation | `grep -E "WHERE.*\{[a-z_]+\}" app/routers/pages.py` | 0 matches | PASS |
| Two-predicate tenant scope | `grep -c 'WHERE id = ? AND tenant_id = ?' app/routers/pages.py` | 3 (delete SELECT, delete UPDATE, health SELECT) | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| **PAGE-01** | 12-01-PLAN | Client can connect a Facebook Page via OAuth — full 3-step token exchange with webhook subscription | SATISFIED (backend) | OAuth start + callback + atomic UPSERT + webhook subscribe implemented and tested by 6 named tests. `test_callback_success` proves happy path with Fernet round-trip; `test_callback_webhook_failure_rollback` proves atomicity. **Manual verification of the real Meta OAuth handshake in a browser is required for full acceptance** — see human verification items. |
| **PAGE-02** | 12-02-PLAN | Client can view a list of their connected Pages and connection status | SATISFIED | `GET /pages` implemented, tenant-scoped, `active/revoked` status derived from live debug_token. 3 tests: `test_list_pages`, `test_list_pages_revoked`, `test_pages_isolation`. |
| **PAGE-03** | 12-02-PLAN | Client can disconnect a Page (removes stored token and webhook subscription) | SATISFIED (backend) | `DELETE /pages/{id}` soft-deletes row + best-effort webhook unsubscribe with decrypted token. 2 tests: `test_disconnect_page`, `test_disconnect_not_found`. **Note:** implementation is soft-delete (`is_active=0`) with `access_token_enc` still present in the row. ROADMAP.md SC3 says "the stored token is deleted" — the token is **rendered inactive** rather than removed. Since the row is filtered out of all subsequent reads by `is_active=1` and re-connect UPSERTs a fresh token, this satisfies the intent (the token is unusable after disconnect) but not the literal "deleted" wording. Documented in the 12-02-SUMMARY.md as an accepted soft-delete pattern. |
| **PAGE-04** | 12-02-PLAN | Client can see a token health indicator per Page and trigger reconnect if revoked | SATISFIED (backend) | `GET /pages/{id}/health` implemented; `test_token_health` covers valid non-expiring, revoked, real-expiry, and cross-tenant 404. The reconnect UI ("Reconnect" button/badge) is UI territory — deferred to Phase 15 per ROADMAP. The Phase 12 contract delivers the backend data the UI will consume. |

No requirements orphaned: PAGE-01 declared in 12-01 `requirements:` frontmatter; PAGE-02/03/04 declared in 12-02 `requirements:` frontmatter. REQUIREMENTS.md maps PAGE-01..04 to Phase 12 — all four claimed.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| — | — | No `TBD/FIXME/XXX/TODO/HACK` markers in any file modified this phase | — | None. Grep returned zero hits across `app/routers/pages.py`, `app/fb_client.py`, `tests/test_pages.py`, `tests/conftest.py`, `app/main.py`, `app/config.py`, `.env.example`. |
| — | — | No `print(`, `console.log`, or debug logging in phase files | — | Silent — appropriate for prod. |
| — | — | No plaintext secret leakage — `settings.fb_app_secret` used only as `httpx` param value and inside `f"{fb_app_id}\|{fb_app_secret}"` app-token construction inside function bodies | — | T-12-04 mitigation intact. |
| `app/config.py` | 18 | `"extra": "ignore"` added to `model_config` post-executor (commit `2760a8f`) | INFO | Legitimate compatibility shim so pre-existing env keys (e.g. `PAGE_ACCESS_TOKEN`) don't fail `Settings()` validation. Does not weaken the fb_* field contracts — those still default to `""` and are checked by `_require_fb_settings()`. Called out for milestone-audit visibility. |

No blockers. No warnings.

---

## Deviations from Plan

Both SUMMARYs called out one deviation each; both are validated and acceptable:

1. **12-01: TestClient re-raises unhandled `RuntimeError`** — The Plan 01 verification originally expected `assert status_code in (500, 502, 400)` for the rollback test. Starlette's TestClient default `raise_server_exceptions=True` causes RuntimeError to propagate through `client.get()`. The executor pivoted to `pytest.raises(RuntimeError, match="subscription failed")` around the call. The **primary rollback proof (SELECT COUNT(*) FROM pages returns 0)** is preserved and passes. This is a test-infrastructure adaptation, not a contract weakening.

2. **12-02: none reported.**

3. **Post-hoc executor fix (commit `2760a8f`): `extra="ignore"` on Settings.** Not a deviation from the plan of PAGE-01..04 — a compatibility fix for pre-existing env vars (`PAGE_ACCESS_TOKEN`, `VERIFY_TOKEN`) that leak into the FastAPI process on developer machines. Without it, `Settings()` raises `ValidationError` at import. Additive and correct.

---

## Threat Model Coverage

All in-scope threats from both plans' STRIDE registers have code + test coverage:

| Threat ID | Category | Mitigation | Test |
|---|---|---|---|
| T-12-01 | Spoofing (forged callback) | `verify_oauth_state` runs before any Graph API call | `test_callback_invalid_state` |
| T-12-02 | EoP (state replay) | 10-min `exp`; `ExpiredSignatureError` → 400 | `test_callback_expired_state` |
| T-12-03 | Info Disclosure (plaintext token) | Fernet `encrypt_token` before INSERT/UPDATE | `test_callback_success` (round-trip + non-equality) |
| T-12-04 | Info Disclosure (app_secret leak) | Secret used only as `httpx` param value | Code inspection (no prints, no error-detail echoes) |
| T-12-05 | Tampering (SQLi) | `?` placeholders throughout | grep gate (0 f-string SQL) + `test_callback_success` UPSERT |
| T-12-06 | Tampering (webhook orphan) | `conn.rollback()` before re-raise | `test_callback_webhook_failure_rollback` |
| T-12-09 | Info Disclosure (cross-tenant read) | `WHERE tenant_id = ?` on every SELECT | `test_pages_isolation`, `test_token_health` cross-tenant clause |
| T-12-10 | Tampering (cross-tenant DELETE) | `WHERE id = ? AND tenant_id = ?` on SELECT + UPDATE | `test_disconnect_not_found` |
| T-12-11 | Info Disclosure (token in response) | `PageResponse`/`HealthResponse` omit token fields | `test_disconnect_page` (decrypted token appears only in outbound Graph params, not in HTTP body) |
| T-12-12 | DoS (N debug_token calls per list) | Accepted; deferred to v1.3 | Documented |
| T-12-13 | Info Disclosure (bad ciphertext) | `try/except ValueError` → `status='revoked'` / `is_valid=False` | Covered by defensive branch; no dedicated test but code path is present and reachable |
| T-12-14 | Spoofing (forged Bearer) | Inherited from Phase 11 `get_current_tenant` | Existing 401 test in `tests/test_auth.py` |
| T-12-15 | Repudiation | Audit log deferred | Accepted |

---

## Human Verification Required

Backend contract for PAGE-01..04 is fully implemented, wired, and unit-tested. The remaining items require external services (real Facebook App, live redirect, Meta App Review) that cannot be exercised without live credentials + a browser session. These are pre-declared in `12-VALIDATION.md` as "Manual-Only Verifications" and are the reason status is `human_needed` rather than `passed`.

### 1. Real Facebook OAuth flow end-to-end

**Test:** Configure `.env` with valid `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, and `FACEBOOK_REDIRECT_URI` registered in Meta App Dashboard. Boot the API (`python main.py`). In a browser, `GET /auth/facebook/start` with a valid Bearer token → follow to Facebook → grant permissions → land on `/auth/facebook/callback` → see JSON `{"pages_connected": N}`. Then `GET /pages` → the connected Page appears with `status="active"`.
**Expected:** Real Page appears in `GET /pages` with a real Fernet-encrypted long-lived token; `check_token_health` returns `True`; webhook events start arriving.
**Why human:** Requires registered Meta App + interactive browser OAuth consent + real Facebook user account. Cannot be mocked without live credentials.

### 2. App Review submission for pages_messaging Advanced Access

**Test:** Submit the `pages_messaging` permission for Advanced Access in Meta App Dashboard → App Review → Permissions and Features.
**Expected:** Meta approves Advanced Access so the bot can deliver messages to non-admin users in Live mode.
**Why human:** External approval process; days-to-weeks turnaround.

### 3. Webhook delivery to a connected Page

**Test:** After completing item 1, send a Messenger message from a tester account to the connected Page.
**Expected:** The bot's `/webhook` endpoint receives the event with the correct Page ID, resolves the stored Page token, and responds. Facebook actually routed the event → the `/{page_fb_id}/subscribed_apps` POST in `subscribe_page_webhook` had a real effect on Meta's routing.
**Why human:** Requires public HTTPS bot instance + subscribed Page + real message.

### 4. Cross-tenant leak sanity check on production traffic (optional)

**Test:** After first real client onboarding, review server access logs and confirm no client JWT ever received a page-row belonging to another `tenant_id`.
**Expected:** Isolation holds. Behavioral tests already cover this; manual re-check is belt-and-suspenders.
**Why human:** Production-log inspection.

---

## Gaps Summary

**None.** All 8 observable truths verify, all 7 required artifacts pass at levels 1-3 (exist, substantive, wired) and Level 4 data-flow trace, all 8 key links are wired, all 12 named tests pass, and no debt markers or stubs exist in the phase-modified files. Full suite is 49/49 green.

The `human_needed` status is not a gap — it is the pre-declared Manual-Only verification set from `12-VALIDATION.md`. Phase code is complete; further verification requires external Meta services and a browser.

---

_Verified: 2026-07-14_
_Verifier: Claude (gsd-verifier)_
