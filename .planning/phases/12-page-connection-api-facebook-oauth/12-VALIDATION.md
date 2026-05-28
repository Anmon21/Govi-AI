---
phase: 12
slug: page-connection-api-facebook-oauth
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-28
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (installed) |
| **Config file** | none — pytest discovers `tests/` by convention |
| **Quick run command** | `python3 -m pytest tests/test_pages.py -x -q` |
| **Full suite command** | `python3 -m pytest tests/ -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/test_pages.py -x -q`
- **After every plan wave:** Run `python3 -m pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 12-01-01 | 01 | 1 | PAGE-01 | — | N/A | unit | `pytest tests/test_pages.py -k "test_oauth_start" -x` | ❌ W0 | ⬜ pending |
| 12-01-02 | 01 | 1 | PAGE-01 | — | CSRF state JWT verified before proceeding | unit | `pytest tests/test_pages.py -k "test_state_jwt" -x` | ❌ W0 | ⬜ pending |
| 12-01-03 | 01 | 1 | PAGE-01 | — | Invalid state returns 400 | unit | `pytest tests/test_pages.py -k "test_callback_invalid_state" -x` | ❌ W0 | ⬜ pending |
| 12-01-04 | 01 | 1 | PAGE-01 | — | Expired state returns 400 | unit | `pytest tests/test_pages.py -k "test_callback_expired_state" -x` | ❌ W0 | ⬜ pending |
| 12-01-05 | 01 | 1 | PAGE-01 | — | Webhook failure rolls back DB insert | integration | `pytest tests/test_pages.py -k "test_callback_webhook_failure_rollback" -x` | ❌ W0 | ⬜ pending |
| 12-01-06 | 01 | 1 | PAGE-01 | — | Successful callback stores encrypted token + subscribes webhook | integration | `pytest tests/test_pages.py -k "test_callback_success" -x` | ❌ W0 | ⬜ pending |
| 12-02-01 | 02 | 2 | PAGE-02 | — | Tenant isolation — no cross-tenant page access | integration | `pytest tests/test_pages.py -k "test_pages_isolation" -x` | ❌ W0 | ⬜ pending |
| 12-02-02 | 02 | 2 | PAGE-02 | — | N/A | integration | `pytest tests/test_pages.py -k "test_list_pages" -x` | ❌ W0 | ⬜ pending |
| 12-02-03 | 02 | 2 | PAGE-02 | — | N/A | integration | `pytest tests/test_pages.py -k "test_list_pages_revoked" -x` | ❌ W0 | ⬜ pending |
| 12-02-04 | 02 | 2 | PAGE-03 | — | DELETE returns 404 for other tenant's page | unit | `pytest tests/test_pages.py -k "test_disconnect_not_found" -x` | ❌ W0 | ⬜ pending |
| 12-02-05 | 02 | 2 | PAGE-03 | — | N/A | integration | `pytest tests/test_pages.py -k "test_disconnect_page" -x` | ❌ W0 | ⬜ pending |
| 12-02-06 | 02 | 2 | PAGE-04 | — | N/A | unit | `pytest tests/test_pages.py -k "test_token_health" -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_pages.py` — stubs for all PAGE-01 through PAGE-04 tests (12 test functions, initially xfail or placeholder)
- [ ] `tests/conftest.py` — verify/add fixtures: auth headers for test tenant, test DB with pages table, httpx mock helper

*Existing infrastructure: `tests/conftest.py` exists from Phase 11 with auth fixtures and test DB. Wave 0 adds `test_pages.py` and any missing page-specific fixtures.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real Facebook OAuth flow end-to-end (requires Facebook App credentials and live redirect URI) | PAGE-01 | External dependency — requires registered Facebook App with valid redirect_uri, cannot mock the browser redirect | Set up Facebook App in Dev mode, configure FACEBOOK_APP_ID/SECRET, click "Connect with Facebook" at GET /auth/facebook/start, complete OAuth in browser, verify page appears in GET /pages |
| App Review submission | PAGE-01 (production) | Meta's review process is manual and external | Submit pages_messaging permission via Meta App Dashboard during Phase 12 execution |
| Webhook delivery to running bot | PAGE-01 | Requires public HTTPS URL + running bot | After connecting a page, send a test message from a non-admin account (in Dev mode: tester account), verify bot responds |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
