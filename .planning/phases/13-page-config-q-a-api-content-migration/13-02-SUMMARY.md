---
phase: 13-page-config-q-a-api-content-migration
plan: 02
subsystem: api
tags: [fastapi, sqlite, pydantic, jwt, hmac]

# Dependency graph
requires:
  - phase: 12-page-connection-api-facebook-oauth
    provides: pages table, get_current_tenant JWT dependency, X-Internal-Key HMAC guard pattern (get_internal_page_access_token)
provides:
  - "PUT /pages/{page_id}/config — JWT-authenticated, tenant-ownership-scoped whole-row replace of page_configs (welcome_text, menu_json, escalation_psid, escalation_message)"
  - "GET /internal/pages/{page_fb_id}/config — HMAC-guarded, bot-facing config read keyed on Facebook page_fb_id, with schema-default fallback when no config row exists"
  - "MenuItem/PageConfigRequest/PageConfigResponse/InternalPageConfigResponse Pydantic models with extra=forbid flat-array menu validation"
affects: [13-page-config-q-a-api-content-migration (13-03, 13-04), 14-remove-page-access-token-global, 15-admin-panel-content-editor]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Whole-row replace (insert-or-update keyed on a UNIQUE column) for single-row-per-parent tables"
    - "JSON-string DB column serialized/deserialized (json.dumps/json.loads) at the router boundary"
    - "Pydantic extra=forbid on a nested list-item model to reject malformed/nested request shapes at the validation layer (422 for free)"

key-files:
  created: []
  modified:
    - app/routers/pages.py
    - tests/test_pages.py

key-decisions:
  - "menu_json validated via Pydantic list[MenuItem] with extra=forbid rather than manual JSON-schema checks — malformed/nested menus 422 automatically before handler code runs"
  - "Internal config read returns schema defaults (empty welcome_text, empty menu, null escalation) for an active page with no config row, rather than 404 — keeps the bot-facing contract always-usable per plan spec"

requirements-completed: [CONTENT-01, CONTENT-02, CONTENT-04]

# Metrics
duration: ~15min
completed: 2026-07-22
---

# Phase 13 Plan 02: Page Config Write + Internal Read API Summary

**Consolidated `PUT /pages/{page_id}/config` whole-row replace endpoint plus HMAC-guarded `GET /internal/pages/{page_fb_id}/config` bot-facing read, both backed by SQLite `page_configs` with flat `{title,payload}` menu validation.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-22T13:2x (approx, session start)
- **Completed:** 2026-07-22T05:34:25Z
- **Tasks:** 3/3 completed
- **Files modified:** 2

## Accomplishments
- `PUT /pages/{page_id}/config` — JWT-authenticated, tenant-ownership-scoped, insert-or-update whole-row replace of `page_configs` keyed on the `UNIQUE page_id` column
- `menu_json` validated as a flat `[{title,payload}]` array via `MenuItem(extra="forbid")` — nested/unknown-key menus rejected with 422 automatically
- `GET /internal/pages/{page_fb_id}/config` — HMAC-guarded (`X-Internal-Key`), bot-facing read resolving Facebook `page_fb_id` -> internal `pages.id` -> `page_configs`, with schema-default fallback when no config row exists yet
- 9 new tests (5 config-write, 4 internal-config-read) — 25/25 in `test_pages.py`, 62/62 in the full suite

## Task Commits

Each task was committed atomically:

1. **Task 1: Add PUT /pages/{page_id}/config with whole-row replace, menu_json validation, and ownership scoping** - `2a924c6` (feat)
2. **Task 2: Add GET /internal/pages/{page_fb_id}/config (HMAC-guarded, bot-facing read)** - `738303e` (feat)
3. **Task 3: Add config-write and internal-config-read tests** - `863a72f` (test)

**Plan metadata:** (this commit, below)

## Files Created/Modified
- `app/routers/pages.py` - Added `MenuItem`, `PageConfigRequest`, `PageConfigResponse`, `InternalPageConfigResponse` models; `PUT /pages/{page_id}/config` (JWT + ownership); `GET /internal/pages/{page_fb_id}/config` (HMAC guard, defaults-on-missing-row)
- `tests/test_pages.py` - 9 new tests: create/update roundtrip, menu roundtrip, nested-menu 422, cross-tenant 404, unauthenticated 401, internal-read 403/200/404/defaults

## Decisions Made
- menu_json validated via Pydantic `list[MenuItem]` with `extra="forbid"` rather than manual JSON-schema checks — malformed/nested menus 422 automatically before handler code runs, matching the plan's D-04 "smallest contract to validate" guidance
- Internal config read returns schema defaults (empty `welcome_text`, empty `menu_json`, null escalation fields) for an active page with no `page_configs` row, rather than 404 — matches the plan's explicit "belt-and-suspenders" requirement so the bot always receives a usable config

## Deviations from Plan

None - plan executed exactly as written. No test infrastructure existed in the worktree (no `.venv`), so a virtualenv was created and `requirements.txt` installed to run the plan's own verification commands (`python -c "import app.main"`, `pytest`) — this is environment setup using the project's already-declared dependencies, not a new package addition, and `.venv/` is already gitignored.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `PUT /pages/{page_id}/config` and `GET /internal/pages/{page_fb_id}/config` are ready for Phase 15's admin editor (write side) and Phase 14's bot config-fetch (BOT-01, read side)
- No blockers for 13-03/13-04 (Q&A CRUD, content migration) — this plan's models/patterns (whole-row replace, JSON-column serialization) are directly reusable

---
*Phase: 13-page-config-q-a-api-content-migration*
*Completed: 2026-07-22*

## Self-Check: PASSED

- FOUND: app/routers/pages.py
- FOUND: tests/test_pages.py
- FOUND: .planning/phases/13-page-config-q-a-api-content-migration/13-02-SUMMARY.md
- FOUND commit: 2a924c6 (Task 1)
- FOUND commit: 738303e (Task 2)
- FOUND commit: 863a72f (Task 3)
- FOUND commit: ebb4084 (SUMMARY.md)
