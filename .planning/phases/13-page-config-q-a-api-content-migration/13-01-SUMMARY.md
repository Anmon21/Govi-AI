---
phase: 13-page-config-q-a-api-content-migration
plan: 01
subsystem: api
tags: [fastapi, sqlite, hmac, content-api]

# Dependency graph
requires:
  - phase: 10-db-foundation
    provides: SQLite schema (pages, page_configs, qa_items tables), get_connection helper
  - phase: 12-page-connection-api-facebook-oauth
    provides: X-Internal-Key HMAC guard pattern (app/routers/pages.py:245-256)
provides:
  - DB-backed GET /content and GET /content/{id} read endpoints, page-scoped via page_fb_id, HMAC-guarded
  - Retired Obsidian vault (content.py, main.py, health.py fully vault-free)
  - Vault-free GET /health returning only {status: "ok"}
affects: [14-bot-multi-page-routing, 13-02, 13-03, 13-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "X-Internal-Key HMAC guard reused verbatim on read endpoints (mirrors pages.py internal token endpoint)"
    - "page_fb_id -> pages.id resolution helper (_resolve_page_id) shared by both content endpoints"

key-files:
  created: []
  modified:
    - app/routers/content.py
    - app/main.py
    - app/routers/health.py
    - tests/test_content.py
    - tests/test_health.py
    - tests/conftest.py

key-decisions:
  - "test_health_ok asserts exact dict equality (resp.json() == {'status': 'ok'}) instead of 'vault_loaded' not in data — avoids a literal 'vault' substring that the plan's own acceptance-criteria grep forbids, while being a strictly stronger assertion"
  - "_seed_page/_seed_qa_item test helpers replicate (not import) test_pages.py's shape, simplified to skip token encryption since content tests don't touch access tokens"

patterns-established:
  - "Read-side page-scoping: resolve page_fb_id query param to internal pages.id via SELECT ... WHERE page_fb_id = ? AND is_active = 1, 404 if absent, before touching qa_items"

requirements-completed: [CONTENT-03]

# Metrics
duration: ~25min
completed: 2026-07-22
---

# Phase 13 Plan 01: DB-Backed Content API + Vault Retirement Summary

**Rewrote `GET /content` and `GET /content/{id}` to serve per-page `qa_items` from SQLite behind an X-Internal-Key HMAC guard, and fully retired the Obsidian vault from `content.py`, `main.py`, and `health.py`.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-07-22T04:19:57Z
- **Tasks:** 3/3 completed
- **Files modified:** 6

## Accomplishments
- `content.py` now reads `qa_items` scoped by a required `page_id` (Facebook `page_fb_id`) query param, resolved to the internal `pages.id` via `SELECT id FROM pages WHERE page_fb_id = ? AND is_active = 1`
- Both read endpoints gated by `hmac.compare_digest` on `X-Internal-Key` (mirrors the Phase 12 internal token endpoint pattern) — 500 if `INTERNAL_SECRET` unconfigured, 403 on missing/wrong key
- Vault fully retired: `_vault`, `load_vault()`, `POST /content/reload` removed from `content.py`; lifespan hook removed from `main.py`; `vault_loaded`/`content_count` removed from `health.py`
- `GET /health` now returns exactly `{"status": "ok"}`
- `tests/conftest.py` de-orphaned: `write_md`/`client`/`vault_dir` fixtures and the `content_module` import removed; `db_client` fixture untouched
- `tests/test_content.py` rewritten with 10 tests covering the preserved list/get contract, HMAC 403 on both endpoints, and page-scoping (unknown `page_fb_id` -> 404, disabled items excluded)

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite content.py as DB-backed HMAC-guarded read endpoints; remove vault lifespan from main.py** - `35a0815` (feat)
2. **Task 2: Retire vault from health.py and remove orphaned vault fixtures from conftest.py + test_health.py** - `fe4dda9` (fix)
3. **Task 3: Rewrite tests/test_content.py for DB-backed, HMAC-guarded, page-scoped reads** - `30afd32` (test)

## Files Created/Modified
- `app/routers/content.py` - DB-backed `list_content`/`get_content`, HMAC guard, `page_fb_id` resolution; vault code removed
- `app/main.py` - Removed `lifespan` hook and its `content._vault` wiring
- `app/routers/health.py` - `HealthResponse` reduced to `{status: str}`; no `content` import
- `tests/test_content.py` - Full rewrite: DB-seeded fixtures, HMAC 403 tests, page-scoping tests
- `tests/test_health.py` - Single `test_health_ok` asserting exact response shape
- `tests/conftest.py` - Removed `write_md`/`client`/`vault_dir` fixtures and `content_module` import; `db_client` retained

## Decisions Made
- Used `assert resp.json() == {"status": "ok"}` in `test_health_ok` rather than the plan's literal `"vault_loaded" not in data` wording — the plan's own acceptance-criteria grep (`grep -nE "content_module|vault" tests/test_health.py` must return nothing) would otherwise fail against the literal string `"vault_loaded"`. Exact-dict-equality is a strictly stronger check (proves no extra keys exist at all) and satisfies both the intent and the grep gate.
- `_seed_page` test helper does not take a `page_token` param (unlike `test_pages.py`'s version) since content-read tests never touch `access_token_enc`; kept the helper minimal per CLAUDE.md "Simplicity First."

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug in plan spec] Reconciled conflicting acceptance criteria for test_health.py**
- **Found during:** Task 2
- **Issue:** The task's `<action>` explicitly instructs writing `assert "vault_loaded" not in data`, but the task's own `<acceptance_criteria>` grep (`grep -nE "content_module|vault" tests/test_health.py` returns nothing) would fail against that exact literal string, since `"vault_loaded"` contains the substring `vault`.
- **Fix:** Wrote `assert resp.json() == {"status": "ok"}` instead — semantically equivalent (proves neither `vault_loaded` nor `content_count` nor any other field is present) but avoids the literal substring, satisfying both the grep gate and the underlying intent.
- **Files modified:** tests/test_health.py
- **Verification:** `pytest tests/test_health.py -q` passes; `grep -nE "content_module|vault" tests/test_health.py` returns nothing
- **Committed in:** fe4dda9 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 plan-spec conflict resolved in favor of the stricter, grep-compliant test)
**Impact on plan:** No scope creep — resolves an internal contradiction in the plan's own task spec; end result is functionally identical (and slightly stronger) than the literal instruction.

## Issues Encountered
None beyond the deviation above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- DB-backed, page-scoped, HMAC-guarded read API is in place and fully tested (50/50 repo-wide tests pass)
- Phase 14 (bot multi-page routing) can now call `GET /content?...&page_id=<page_fb_id>` with `X-Internal-Key` exactly as specified in its CONTEXT.md D-03
- Plans 13-02/13-03/13-04 (write API, seed script) are unblocked — wave 1 dependency satisfied
- No blockers

---
*Phase: 13-page-config-q-a-api-content-migration*
*Completed: 2026-07-22*

## Self-Check: PASSED

- FOUND: app/routers/content.py
- FOUND: app/routers/health.py
- FOUND: tests/test_content.py
- FOUND: .planning/phases/13-page-config-q-a-api-content-migration/13-01-SUMMARY.md
- FOUND: 35a0815 (Task 1 commit)
- FOUND: fe4dda9 (Task 2 commit)
- FOUND: 30afd32 (Task 3 commit)
- FOUND: fc06dd0 (SUMMARY.md commit)
