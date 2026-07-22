---
phase: 13-page-config-q-a-api-content-migration
plan: 04
subsystem: database
tags: [sqlite, migration, cli, python-frontmatter, obsidian-vault]

# Dependency graph
requires:
  - phase: 10-db-foundation
    provides: SQLite schema (pages, page_configs, qa_items) via app/db.py::init_schema
provides:
  - "scripts/seed_qa.py — one-time CLI to migrate vault Q&A content into qa_items for a given page"
  - "load_vault_items() — self-contained vault frontmatter parser (no dependency on the retired content router)"
  - "seed(page_fb_id) — callable migration function (page resolution, wipe+reload, category_id FK resolution, default page_configs row)"
affects: [13-01-page-config-q-a-api-content-migration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "One-time migration script follows scripts/init_db.py conventions (sys.path shim, settings/get_connection, print() progress, __main__ guard)"
    - "Two-pass insert for self-referencing FK: categories first (building vault-string-id -> new-int-id map), then questions resolving category_id through that map"
    - "Wipe+reload idempotency: unconditional DELETE FROM qa_items WHERE page_id before re-insert (D-03), vs. init_db.py's guard-and-skip idempotency style"

key-files:
  created:
    - scripts/seed_qa.py
    - tests/test_seed_qa.py
  modified: []

key-decisions:
  - "seed_qa.py reproduces load_vault's frontmatter-parsing logic locally rather than importing app.routers.content — keeps the script working independently of Plan 13-01's rewrite/deletion of that router"
  - "Page resolution query omits is_active filtering (unlike the read-API's page_fb_id lookup) so an operator can deliberately seed an inactive/test page"
  - "seed() is a plain callable (not embedded in __main__ only) so tests can invoke it directly without subprocess"

patterns-established:
  - "CLI migration scripts: argparse for required flags, plain print() progress lines, seed()/load_*() as testable top-level functions, __main__ guard only parses args and calls the callable"

requirements-completed: [DB-02]

# Metrics
duration: ~12min
completed: 2026-07-22
---

# Phase 13 Plan 04: Vault-to-DB Q&A Seed Script Summary

**One-time CLI (`scripts/seed_qa.py`) that migrates Obsidian vault Q&A content into `qa_items` for a resolved page, with idempotent wipe+reload and a guaranteed default `page_configs` row.**

## Performance

- **Duration:** ~12 min
- **Completed:** 2026-07-22
- **Tasks:** 2/2 completed
- **Files modified:** 2 (both new)

## Accomplishments
- `scripts/seed_qa.py` resolves `--page-fb-id` to the internal `pages.id`, wipes and reloads that page's `qa_items` from the vault every run (idempotent, no duplicates), and ensures a default `page_configs` row exists
- Two-pass insert correctly resolves each question's `category_id` FK to the newly-inserted integer id of its vault category (verified against `vault-sample/` fixtures: 2 categories, 3 questions)
- `tests/test_seed_qa.py` proves migration counts, FK resolution, idempotency across re-runs, `page_configs` defaults, and non-zero exit + zero writes for an unknown `--page-fb-id`

## Task Commits

Each task was committed atomically:

1. **Task 1: Write scripts/seed_qa.py** - `cafbf9f` (feat)
2. **Task 2: Write tests/test_seed_qa.py** - `b94b4ce` (test)

**Plan metadata:** committed separately by the orchestrator after wave merge (worktree mode — this agent does not update STATE.md/ROADMAP.md)

## Files Created/Modified
- `scripts/seed_qa.py` - Self-contained vault->DB Q&A migration CLI: `load_vault_items()` (frontmatter parser, lifted from `content.py::load_vault`), `seed(page_fb_id)` (page resolution, wipe+reload two-pass insert, default `page_configs` row), `__main__` argparse entrypoint
- `tests/test_seed_qa.py` - 5 tests against a tmp-path SQLite DB + `vault-sample/` fixtures, covering migration counts, category_id FK resolution, idempotency, page_configs defaults, and unknown-page exit behavior

## Decisions Made
- Reproduced `load_vault`'s parsing logic locally instead of importing `app.routers.content`, per the plan's explicit instruction (that router is rewritten/retired by Plan 13-01, and this plan must not depend on its file state)
- Page lookup (`SELECT id FROM pages WHERE page_fb_id = ?`) intentionally does not filter `is_active` — an operator may need to seed a test/inactive page; this matches the plan's task instructions
- Reused `vault-sample/` directly as the test fixture directory (plan explicitly permits this) rather than copying files into `tmp_path`, since the fixture is read-only content already tracked in the repo

## Deviations from Plan

None - plan executed exactly as written. One minor self-correction during execution: an early draft of a docstring comment (`app/routers/content.py::load_vault`) accidentally matched the acceptance criteria's `grep -n "app.routers.content"` no-match check because grep's basic-regex `.` matches `/`. Reworded the docstring before committing so no code or comment contains that pattern; this was caught and fixed prior to the Task 1 commit, not a deviation from the shipped code.

## Issues Encountered
- This worktree's checked-out base was behind the phase-13 planning commits (`HEAD` was at `4a66f32`, an older Phase 12 commit, instead of the expected `b66fc5a`). Corrected via the mandated `worktree_branch_check` `git reset --hard` to the expected base before any file edits — this is the sanctioned recovery path for that step, not a destructive-git violation.
- No system Python interpreter had the project's dependencies (`python-frontmatter`, `fastapi`, `pytest`, etc.) installed; discovered and used the existing `.venv` at the main repo root (`/Users/anmon/Code/Govi-AI/.venv`) to run the script and test suite. No new dependencies were added — `python-frontmatter` was already in `requirements.txt`.

## User Setup Required

None - no external service configuration required. This is a locally-run operator CLI (`python scripts/seed_qa.py --page-fb-id <fb_id>`), not a network-exposed service.

## Next Phase Readiness
- `scripts/seed_qa.py` is ready to run once Plan 13-01/13-02's page-creation flow exists in the target environment (needs a `pages` row with a matching `page_fb_id` to resolve against)
- Plan 13-01 (content.py rewrite to DB-backed read endpoints) can now rely on `qa_items`/`page_configs` being populated via this script for manual/integration testing
- No blockers for downstream Phase 13 plans

---
*Phase: 13-page-config-q-a-api-content-migration*
*Completed: 2026-07-22*

## Self-Check: PASSED

- FOUND: scripts/seed_qa.py
- FOUND: tests/test_seed_qa.py
- FOUND: .planning/phases/13-page-config-q-a-api-content-migration/13-04-SUMMARY.md
- FOUND commit: cafbf9f
- FOUND commit: b94b4ce
