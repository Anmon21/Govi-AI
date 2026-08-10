---
phase: 13-page-config-q-a-api-content-migration
plan: 05
subsystem: api
tags: [fastapi, sqlite, referential-integrity, gap-closure]

# Dependency graph
requires:
  - phase: 13-page-config-q-a-api-content-migration
    provides: "13-03 Q&A CRUD API (POST/GET/PUT/DELETE /pages/{page_id}/qa)"
provides:
  - "Page-scoped dependent-row guard (_has_dependent_qa_items) shared by update_qa and delete_qa"
  - "400 rejection when retyping a category that other qa_items rows still reference via category_id"
  - "409 rejection when deleting a category that still has dependent questions (replaces unhandled sqlite3.IntegrityError / 500)"
  - "2 regression tests reproducing 13-REVIEW.md CR-01 and WR-01"
affects: [content-migration, qa-admin-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Inbound-reference guard sits next to the existing outbound-reference guard (_validate_category_ref) in app/routers/pages.py, both taking conn first and raising HTTPException directly"
    - "Dependent-row check evaluated fresh per request (no caching) so guards release once the last dependent is removed"

key-files:
  created: []
  modified:
    - app/routers/pages.py
    - tests/test_pages.py

key-decisions:
  - "Single shared page-scoped SELECT (SELECT 1 FROM qa_items WHERE category_id = ? AND page_id = ? LIMIT 1) used by both update_qa (400) and delete_qa (409) rather than duplicating the query"
  - "Detail strings kept static (no row ids/titles/counts) to avoid leaking information about other rows, per T-13-18 in the threat model"
  - "409 (not 400) for delete-with-dependents: the request is well-formed, it conflicts with current state"

patterns-established:
  - "Dependent-row guards run inside the existing try/finally block so the connection still closes on the error path; no try/except added around the DB calls per project convention (no try/except in Python routers)"

requirements-completed: [CONTENT-03]

# Metrics
duration: ~20min
completed: 2026-08-10
---

# Phase 13 Plan 05: Q&A Referential Integrity Guards Summary

**Page-scoped dependent-row guard in app/routers/pages.py closes CR-01 (silent category-orphaning on retype) and WR-01 (unhandled sqlite3.IntegrityError on delete) from 13-REVIEW.md, with 2 new regression tests.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-08-10T02:21:20Z
- **Tasks:** 2/2 completed
- **Files modified:** 2

## Accomplishments
- Added `_has_dependent_qa_items(conn, page_id, item_id)` helper — single page-scoped `SELECT 1 FROM qa_items WHERE category_id = ? AND page_id = ? LIMIT 1` lookup shared by both write handlers
- `update_qa` now rejects retyping a category away from `'category'` with `400 "Cannot change type: this category is referenced by questions"` while dependent questions exist, leaving the stored row unchanged (CR-01 fix)
- `delete_qa` now rejects deleting a category with dependent questions with `409 "Category has questions; delete or reassign them first"` instead of crashing with an unhandled `sqlite3.IntegrityError` (WR-01 fix)
- Both guards are state-based, not sticky: verified that a previously-blocked category becomes retypable/deletable (200) once its last dependent question is removed
- 2 new regression tests added to `tests/test_pages.py`, confirmed RED against pre-fix code, GREEN after the fix

## Task Commits

Each task was committed atomically:

1. **Task 1: Add regression tests reproducing CR-01 and WR-01** - `bcc0fa8` (test)
2. **Task 2: Add the page-scoped dependent-row guard to update_qa (400) and delete_qa (409)** - `195c5ce` (fix)

_No plan-metadata commit in this run — SUMMARY.md is committed separately per worktree-agent protocol (STATE.md/ROADMAP.md updates owned by the orchestrator)._

## Files Created/Modified
- `app/routers/pages.py` - Added `_has_dependent_qa_items` helper next to `_validate_category_ref`; added the 400 guard in `update_qa` before the UPDATE statement and the 409 guard in `delete_qa` before the DELETE statement
- `tests/test_pages.py` - Added `test_qa_put_retype_referenced_category_400` and `test_qa_delete_referenced_category_409` under a new `CONTENT-03 — referential integrity regressions (13-REVIEW.md CR-01 / WR-01)` banner

## Decisions Made
- Single shared helper (not duplicated SQL per handler) — acceptance criteria enforced this via `grep -c` on the SQL string
- Static, information-free detail strings on both new HTTPExceptions (no row ids/titles/counts) per threat T-13-18
- No schema change, no `ON DELETE CASCADE`, no cascade/reassign behavior — rejecting is the specified product behavior; the guard prevents the FK violation rather than catching it

## Deviations from Plan

None - plan executed exactly as written. Both tasks matched their `<action>` and `<acceptance_criteria>` blocks verbatim; all specified `grep` checks and test counts (33 in test_pages.py, 72 overall) passed on the first attempt.

One environment note (not a deviation, no plan change required): this execution ran inside a git worktree at `.claude/worktrees/agent-abcb779faf2373ad2`, which does not have its own `.venv` (gitignored, not copied into worktrees). All `<verify>` commands were run using the main repo's interpreter by absolute path (`/Users/anmon/Code/Govi-AI/.venv/bin/python`) invoked with the worktree as the working directory, so imports resolved against the worktree's copy of `app/` and `tests/`. Baselines matched the plan's stated numbers exactly (31 passed / 70 passed before this plan's changes).

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- CONTENT-03 moves from "PARTIALLY SATISFIED" to fully satisfied: create, edit, and delete all behave correctly for a category that has questions
- 13-VERIFICATION.md truths #16 and #17 are now demonstrably true
- `app/routers/content.py`, `app/db.py`, and `scripts/seed_qa.py` remain untouched, as scoped
- No blockers for downstream phases (content-migration cutover, QA admin UI work)

---
*Phase: 13-page-config-q-a-api-content-migration*
*Completed: 2026-08-10*
