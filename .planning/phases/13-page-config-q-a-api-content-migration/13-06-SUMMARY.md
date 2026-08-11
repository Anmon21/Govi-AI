---
phase: 13-page-config-q-a-api-content-migration
plan: 13-06
subsystem: database
tags: [pytest, sqlite, fail-closed, gap-closure]

# Dependency graph
requires:
  - phase: 13-page-config-q-a-api-content-migration
    provides: scripts/seed_qa.py and tests/test_seed_qa.py from Plan 13-04 (the one-time vault-to-DB migration script and its baseline test coverage)
provides:
  - Fail-closed guard in seed() that refuses to run (SystemExit 1) when load_vault_items() returns an empty list, before the destructive DELETE FROM qa_items
  - Regression coverage (4 new test instances) for the empty/misconfigured-vault-path destructive path across unset, missing-directory, empty-directory, and real CLI subprocess triggers
affects: [13-07, verification, DB-02]

# Tech tracking
tech-stack:
  added: []
  patterns: ["fail-closed guard mirroring the existing unknown-page sys.exit(1) idiom in the same function"]

key-files:
  created: []
  modified:
    - scripts/seed_qa.py
    - tests/test_seed_qa.py

key-decisions:
  - "Guard keys off `not items` (the returned list), not off settings.vault_path or os.path.isdir, so an existing-but-empty vault directory is caught by the same branch as an unset/missing one"
  - "Scope held to the single `if not items: print(...); sys.exit(1)` guard only — did not add --force, --dry-run, or a row-count precheck (WR-12), which would break the passing test_seed_is_idempotent and contradict locked decision D-03"

patterns-established: []

requirements-completed: [DB-02]

# Metrics
duration: 12min
completed: 2026-08-11
---

# Phase 13 Plan 13-06: Fail-closed empty-vault guard for seed_qa.py Summary

**Added a four-line fail-closed guard in `scripts/seed_qa.py` plus 4 new regression test instances that stop `seed()` from silently wiping a page's `qa_items` rows and printing a false success message when `settings.vault_path` is unset, missing, or empty — closing 13-REVIEW.md CR-01 / 13-VERIFICATION.md truth #25.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-08-11T03:00:00Z (approx)
- **Completed:** 2026-08-11T03:12:00Z
- **Tasks:** 2 completed
- **Files modified:** 2

## Accomplishments
- `seed()` now refuses to run when `load_vault_items()` returns an empty list, exiting with status 1 before reaching the destructive `DELETE FROM qa_items` statement or `conn.commit()`
- All three misconfiguration triggers (unset `vault_path`, nonexistent directory, existing-but-empty directory) fail closed identically, proven by a parametrized test
- A real subprocess CLI invocation (`scripts/seed_qa.py --page-fb-id ...`) with a bad `VAULT_PATH` now exits non-zero and leaves all 5 pre-existing `qa_items` rows in place
- D-03's idempotent wipe+reload behavior against a valid vault is unchanged and still passes (`test_seed_is_idempotent`)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add regression tests for the empty/misconfigured vault path (must FAIL against current code)** - `5b23d20` (test)
2. **Task 2: Add the fail-closed empty-vault guard to seed() before the destructive DELETE** - `e9bf14a` (feat)

_TDD gate sequence: RED (`test(13-06)`) then GREEN (`feat(13-06)`), verified in git log below._

## Files Created/Modified
- `tests/test_seed_qa.py` - Added `import subprocess`/`import sys`, plus two new test functions: `test_seed_refuses_and_preserves_content_when_vault_yields_nothing` (parametrized over `unset`/`missing_dir`/`empty_dir`, 3 instances) and `test_seed_cli_exits_non_zero_and_preserves_content_on_bad_vault_path` (1 instance, real subprocess)
- `scripts/seed_qa.py` - Inserted `if not items: print(f"Refusing to seed: ..."); sys.exit(1)` between `items = load_vault_items()` and `conn.execute("DELETE FROM qa_items WHERE page_id = ?", (page_id,))`

## Decisions Made
- Followed the plan's explicit scope boundary: only the empty-items guard was added. Did not add `--force`, `--dry-run`, or a row-count precheck (out of scope per the plan's `<objective>` and incompatible with locked decision D-03).
- Resolved a wording conflict between the plan's `<action>` text (which suggested quoting the literal pytest failure string `DID NOT RAISE <class 'SystemExit'>` in a test docstring) and the plan's own acceptance criteria (which greps the diff for that exact substring and requires zero matches). Rephrased the docstring to convey the same information ("the `pytest.raises(SystemExit)` block below fails because today seed() returns normally...") without using the banned substring, satisfying the mechanically-checked acceptance criterion while preserving the intended documentation value.

## Deviations from Plan

None — plan executed exactly as written, with one clarifying substitution documented above (docstring wording, not a functional change) to satisfy the acceptance criteria's exact-match grep.

## Issues Encountered

**Worktree base drift:** At startup, `git merge-base HEAD <expected-base>` showed the expected base commit (`a5248ae`) was actually a descendant of the worktree's current HEAD (i.e., the worktree was created before plan 13-06 was committed to `main`). Per the `<worktree_branch_check>` protocol, ran `git reset --hard a5248ae5c0712fcd74d51057e2a0788cff315049` to bring the worktree to the correct base before starting task work. This is a sanctioned recovery step, not a deviation from the plan's scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

DB-02 moves from "⚠️ PARTIALLY SATISFIED" to satisfied per this plan's `must_haves.truths`. `tests/test_seed_qa.py` collects and passes 9 tests (5 pre-existing + 4 new); the full suite passes 76 (was 72 before this plan). `git diff --stat` against the base commit touches exactly `scripts/seed_qa.py` (4 insertions) and `tests/test_seed_qa.py` (115 insertions) — no changes under `app/`, `messenger-bot/`, `.env`, or `requirements.txt`. No blockers for subsequent phase-13 verification.

---
*Phase: 13-page-config-q-a-api-content-migration*
*Completed: 2026-08-11*
