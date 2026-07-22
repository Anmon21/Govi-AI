---
phase: 13-page-config-q-a-api-content-migration
plan: 03
subsystem: api
tags: [fastapi, sqlite, pydantic, jwt]

# Dependency graph
requires:
  - phase: 13-page-config-q-a-api-content-migration (13-02)
    provides: app/routers/pages.py router shell, get_current_tenant JWT dependency, ownership-scoping pattern, tests/test_pages.py fixture reuse
provides:
  - "GET /pages/{page_id}/qa — JWT-authenticated, tenant-ownership-scoped list of all Q&A items (categories + questions, enabled or not) for a page"
  - "POST /pages/{page_id}/qa — create a Q&A category or question, with app-layer category_id referential integrity check"
  - "PUT /pages/{page_id}/qa/{item_id} — whole-row replace of a Q&A item, item-belongs-to-page check + category_id re-validation + self-reference rejection"
  - "DELETE /pages/{page_id}/qa/{item_id} — delete a Q&A item, item-belongs-to-page check"
  - "QAItemCreateRequest/QAItemUpdateRequest/QAItemResponse Pydantic models"
  - "_require_owned_page, _validate_category_ref, _require_owned_qa_item reusable helpers in app/routers/pages.py"
affects: [15-admin-panel-content-editor]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "App-layer referential integrity check (SELECT ... WHERE id = ? AND page_id = ? AND type = 'category') in lieu of a DB-level typed FK constraint"
    - "Item-belongs-to-parent check (qa_items WHERE id = ? AND page_id = ?) before any item-scoped mutation, layered under the page-ownership check"

key-files:
  created: []
  modified:
    - app/routers/pages.py
    - tests/test_pages.py

key-decisions:
  - "Self-reference rejection (category_id == item_id) added on PUT per plan spec — prevents a question from being marked as its own category, a case the app-layer referential check alone would not catch since the row does exist"
  - "GET list returns both enabled and disabled items (no enabled=1 filter) — this endpoint serves the editor view (Phase 15), distinct from the future bot-facing read API which filters to enabled only"

requirements-completed: [CONTENT-03]

# Metrics
duration: ~15min
completed: 2026-07-22
---

# Phase 13 Plan 03: Q&A REST CRUD API Summary

**REST CRUD (GET/POST/PUT/DELETE) over `qa_items` in `app/routers/pages.py`, JWT-authenticated and tenant-ownership scoped, with application-layer `category_id` referential integrity enforced on create and update.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-22T13:35 (approx)
- **Completed:** 2026-07-22T13:50:00+08:00
- **Tasks:** 3/3 completed
- **Files modified:** 2

## Accomplishments
- `GET /pages/{page_id}/qa` — lists all Q&A items (categories + questions, both enabled and disabled) for a tenant-owned page
- `POST /pages/{page_id}/qa` — creates a category or question; validates `category_id` references an existing category on the same page (400 otherwise)
- `PUT /pages/{page_id}/qa/{item_id}` — whole-row replace; verifies the item belongs to the owned page (404), re-validates `category_id` referential integrity, and rejects a self-referencing `category_id` (400)
- `DELETE /pages/{page_id}/qa/{item_id}` — deletes an item after verifying page ownership and item-page membership
- 3 reusable helpers added: `_require_owned_page`, `_validate_category_ref`, `_require_owned_qa_item`
- 6 new tests — 31/31 in `test_pages.py`, 70/70 in the full suite

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Q&A models + GET list + POST create with category_id referential check** - `adb1f71` (feat)
2. **Task 2: Add PUT edit + DELETE Q&A endpoints (item ownership + referential check)** - `9e7ff79` (feat)
3. **Task 3: Add Q&A CRUD tests (full cycle, referential integrity, cross-tenant, item mismatch)** - `cf8682f` (test)

**Plan metadata:** (this commit, below)

## Files Created/Modified
- `app/routers/pages.py` - Added `QAItemCreateRequest`, `QAItemUpdateRequest`, `QAItemResponse` models; `_require_owned_page`, `_validate_category_ref`, `_require_owned_qa_item` helpers; `GET`/`POST /pages/{page_id}/qa`; `PUT`/`DELETE /pages/{page_id}/qa/{item_id}`
- `tests/test_pages.py` - 6 new tests: full CRUD cycle, invalid category_id (same-page + cross-page), cross-tenant 404, item/page mismatch 404, unauthenticated 401

## Decisions Made
- Self-reference rejection (`category_id == item_id`) added on PUT per plan spec — the app-layer referential check alone would not catch a question referencing itself as its own category since the row genuinely exists
- GET list intentionally returns both enabled and disabled items — this is the content-editor view (Phase 15 consumer), not the bot-facing read view which will filter to `enabled = 1`

## Deviations from Plan

None - plan executed exactly as written. No test infrastructure existed in this worktree (no `.venv`), so a virtualenv was created and `requirements.txt` installed to run the plan's own verification commands (`python -c "import app.main"`, `pytest`) — this is environment setup using the project's already-declared dependencies, not a new package addition, and `.venv/` is already gitignored.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `GET`/`POST /pages/{page_id}/qa` and `PUT`/`DELETE /pages/{page_id}/qa/{item_id}` are ready for Phase 15's admin editor to call
- Combined with Plan 13-02's config endpoints, `app/routers/pages.py` now exposes the full write-side content-editor contract (CONTENT-01–04) for Phase 15
- No blockers for the remaining Phase 13 work — the read-side (Plan 13-01) and seed script (Plan 13-04) are independent of this plan's changes

---
*Phase: 13-page-config-q-a-api-content-migration*
*Completed: 2026-07-22*

## Self-Check: PASSED

- FOUND: app/routers/pages.py
- FOUND: tests/test_pages.py
- FOUND commit: adb1f71 (Task 1)
- FOUND commit: 9e7ff79 (Task 2)
- FOUND commit: cf8682f (Task 3)
