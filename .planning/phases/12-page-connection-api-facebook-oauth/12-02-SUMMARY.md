---
phase: 12-page-connection-api-facebook-oauth
plan: 02
subsystem: pages
tags: [pages, api, facebook, oauth, multi-tenant]
requires:
  - 12-01 (OAuth start/callback, PageResponse, fb_client helpers)
provides:
  - "GET /pages — list active pages with lazy token health"
  - "DELETE /pages/{page_id} — soft-delete + webhook unsubscribe"
  - "GET /pages/{page_id}/health — per-page token validity + expiry"
  - "PageResponse and HealthResponse Pydantic models"
affects:
  - app/routers/pages.py
  - tests/test_pages.py
tech_stack:
  added: []
  patterns:
    - "Two-part tenant scope check: WHERE id = ? AND tenant_id = ? on every per-row query (T-12-09/T-12-10)"
    - "Best-effort webhook unsubscribe: swallowed inside fb_client.unsubscribe_page_webhook so Graph failures do not block soft-delete"
    - "Bad-ciphertext degradation: decrypt_token wrapped in try/except ValueError → status='revoked' / is_valid=False (T-12-13)"
    - "expires_at normalization: Facebook 0 → None (non-expiring Page token)"
key_files:
  created: []
  modified:
    - app/routers/pages.py
    - tests/test_pages.py
decisions:
  - "Handlers call fb_client.httpx.get through the module (not import httpx directly) so tests can monkeypatch app.fb_client.httpx.get uniformly across list_pages, page_health, and existing fb_client.check_token_health."
  - "GET /pages issues one debug_token call per row synchronously — per T-12-12 this DoS surface is accepted for v1.2 (small-N admin tool), deferred to v1.3 per REQUIREMENTS.md future work."
  - "DELETE tenant-scope violation returns 404 (not 403) to avoid leaking the existence of another tenant's page ids (T-12-10)."
metrics:
  duration: "~25 min"
  completed: "2026-07-13T20:42:08Z"
  tests_before: 43
  tests_after: 49
  tests_added: 6
  commits: 2
---

# Phase 12 Plan 02: Page Listing, Disconnect, and Token Health Summary

Extended the Plan 01 pages router with three tenant-scoped lifecycle endpoints (list, disconnect, per-page token health) and added six behavioral tests covering PAGE-02/03/04 including cross-tenant isolation.

## Commits

- `6298a7b` — feat(12-02): add list, disconnect, and health endpoints for pages
- `412ef9c` — test(12-02): add PAGE-02/03/04 behavioral tests for pages endpoints

## What Shipped

### `app/routers/pages.py`

Two Pydantic response models (`PageResponse`, `HealthResponse`) and three async handlers appended to the Plan 01 file. The existing OAuth start/callback handlers and helpers are untouched.

- **`GET /pages`** — reads `pages WHERE tenant_id = ? AND is_active = 1 ORDER BY id ASC`, decrypts each row's token (degrading to `page_token=None` on `ValueError`), calls `fb_client.check_token_health(page_token)` per row, and returns `PageResponse` with `status="active"|"revoked"`. `access_token_enc` is intentionally omitted from the response model (T-12-11).
- **`DELETE /pages/{page_id}`** — SELECT with both `id = ? AND tenant_id = ?` before mutating (raises 404 on miss), best-effort `fb_client.unsubscribe_page_webhook` with the decrypted Page token, then UPDATE `is_active = 0` with the same two-predicate WHERE, commit. Returns `{"detail": "Page {id} disconnected"}`.
- **`GET /pages/{page_id}/health`** — SELECT with `id = ? AND tenant_id = ?` (404 on miss); if no encrypted token or decrypt raises, returns `HealthResponse(is_valid=False, expires_at=None)`. Otherwise calls `fb_client.httpx.get(GRAPH_BASE + "/debug_token", ...)` (qualified via module so tests can monkeypatch), reads `data.is_valid` and `data.expires_at`, and normalizes Facebook's `0` sentinel to `None`.

### `tests/test_pages.py`

Added `_seed_page(db_path, tenant_id, page_fb_id, page_name, page_token)` helper (inserts a row with `encrypt_token(page_token)` and returns `lastrowid`) plus six new tests:

- `test_list_pages` — two seeded pages, all-active `debug_token` mock, asserts response shape and both `page_fb_id`s present.
- `test_list_pages_revoked` — one seeded page, revoked-shape mock, asserts `status == "revoked"`.
- `test_pages_isolation` — two tenants with distinct pages; each tenant's `GET /pages` sees only their own row (T-12-09 SC).
- `test_disconnect_page` — captures `httpx.delete` params; asserts the decrypted token `tok-D` (not the encrypted blob) is passed as `access_token` to Graph, that the DB row's `is_active` flipped to 0, and that subsequent `GET /pages` returns `[]`.
- `test_disconnect_not_found` — cross-tenant DELETE returns 404 and A's row remains `is_active=1`; unknown id returns 404; double-DELETE returns 200 then 404 (T-12-10 SC).
- `test_token_health` — three swap-in mock phases (non-expiring / revoked / real expiry) plus cross-tenant 404.

## Threat Coverage

| Threat  | Coverage |
|---------|----------|
| T-12-09 (cross-tenant read)   | Both `list_pages` and `page_health` require `tenant_id` in WHERE; `test_pages_isolation` + `test_token_health` cross-tenant check |
| T-12-10 (cross-tenant DELETE) | `disconnect_page` SELECT + UPDATE both include `tenant_id`; `test_disconnect_not_found` proves B cannot mutate A's row |
| T-12-11 (token leak)          | `PageResponse` / `HealthResponse` omit token fields; `test_disconnect_page` proves decrypted token only appears in outbound Graph params |
| T-12-13 (bad ciphertext)      | `try/except ValueError` around `decrypt_token` in both `list_pages` and `page_health` |
| T-12-12 (DoS via N debug calls) | Accepted; documented in decisions |
| T-12-14 (forged Bearer)       | Inherited from Phase 11 via `Depends(get_current_tenant)` |
| T-12-15 (no audit)            | Accepted; deferred |

## Verification

```
python3 -m pytest tests/ -q           → 49 passed, 0 skipped, 0 failed
python3 -m pytest tests/test_pages.py → 12 passed (6 PAGE-01 + 6 new)
grep -c 'WHERE id = ? AND tenant_id = ?' app/routers/pages.py → 3
grep -E 'WHERE.*\{[a-z_]+\}' app/routers/pages.py             → 0 matches
```

## Deviations from Plan

None. Plan executed exactly as written.

## Requirements Satisfied

- PAGE-02: list pages with lazy token health, tenant-scoped
- PAGE-03: disconnect page with best-effort webhook unsubscribe + soft-delete
- PAGE-04: per-page token health inspection

## Self-Check: PASSED

- `app/routers/pages.py` exists with `PageResponse`, `HealthResponse`, and three new route handlers.
- `tests/test_pages.py` contains 12 test functions (verified via grep).
- Commit `6298a7b` present in `git log`.
- Commit `412ef9c` present in `git log`.
- Full pytest suite: 49 passed, 0 failed.
