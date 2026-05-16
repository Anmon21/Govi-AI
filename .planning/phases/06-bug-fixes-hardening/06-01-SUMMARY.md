---
phase: 06-bug-fixes-hardening
plan: "01"
subsystem: messenger-bot
tags:
  - bug-fix
  - hardening
  - security
  - debt
dependency_graph:
  requires: []
  provides:
    - DEBT-01-routing
    - DEBT-02-catch-isolation
    - DEBT-03-startup-guard
    - DEBT-04-log-sanitization
  affects:
    - messenger-bot/src/index.ts
tech_stack:
  added: []
  patterns:
    - fail-fast startup validation (process.exit on missing env var)
    - per-event try/catch in webhook inner loop
    - err instanceof Error ? err.message : String(err) sanitization pattern
key_files:
  created:
    - messenger-bot/src/tests/debt-fixes.test.ts
  modified:
    - messenger-bot/src/index.ts
decisions:
  - DEBT-01: Surgical if-blocks inserted before catch-all — no dispatch-map refactor per D-01
  - DEBT-02: Per-event (inner loop) try/catch — outer entry loop untouched per D-03
  - DEBT-03: Guard only FACEBOOK_VERIFY_TOKEN — FACEBOOK_PAGE_ACCESS_TOKEN excluded per D-06
  - DEBT-04: err instanceof Error ? err.message : String(err) in all 7 non-Axios else branches + DEBT-02 catch
metrics:
  duration: "4m 45s"
  completed: "2026-05-16"
  tasks_completed: 5
  tasks_total: 5
  files_modified: 1
  files_created: 1
---

# Phase 06 Plan 01: DEBT Fixes & Hardening Summary

**One-liner:** Four surgical patches to messenger-bot/src/index.ts closing DEBT-01 through DEBT-04 — postback routing, per-event catch isolation, startup fail-fast guard, and non-Axios error log sanitization.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | DEBT-03: fail-fast VERIFY_TOKEN startup guard | beedc5a | messenger-bot/src/index.ts (+5) |
| 2 | DEBT-04: sanitize 7 non-Axios error log branches | d0a095e | messenger-bot/src/index.ts (+7/-7) |
| 3 | DEBT-01: route MENU_PRODUCT_HELP and MENU_MAIN postbacks | a152e30 | messenger-bot/src/index.ts (+10) |
| 4 | DEBT-02: per-event try/catch around handleWebhookEvent | 0dd5c9a | messenger-bot/src/index.ts (+5/-1) |
| 5 | Add debt-fixes.test.ts (5 tests, DEBT-01/02/04) | 3779f11 | messenger-bot/src/tests/debt-fixes.test.ts (+204) |

## Changes Made

### messenger-bot/src/index.ts

**DEBT-03 (Task 1):** Added fail-fast guard after `import "dotenv/config"`, before `const app = express()`. If `FACEBOOK_VERIFY_TOKEN` is absent, `console.error` prints a clear message and `process.exit(1)` runs before any HTTP listener binds. +5 lines.

**DEBT-04 (Task 2):** Seven mechanical replacements in `else` branches (after `axios.isAxiosError` check) across `sendMessage`, `passThreadControl`, `sendTypingIndicator`, `sendCategoryMenu`, `sendQuestionMenu`, `sendAnswer`, `setupMessengerProfile`. Changed `err` → `err instanceof Error ? err.message : String(err)`. Net 0 lines (7 insertions, 7 deletions).

**DEBT-01 (Task 3):** Two new `if` blocks inserted between the `MENU_CONTACT_HUMAN` block and the catch-all `if (event.postback)` block in `handleWebhookEvent`:
- `MENU_PRODUCT_HELP` → `sendCategoryMenu(senderId)`
- `MENU_MAIN` → `sendWelcomeMessage(senderId)`
Catch-all unchanged. +10 lines.

**DEBT-02 (Task 4):** Wrapped `await handleWebhookEvent(event)` in the inner for-loop with try/catch. Catch logs `"handleWebhookEvent failed (unexpected):"` + sanitized error string per D-05. `res.sendStatus(200)` and outer loop untouched. +5/-1 lines.

### messenger-bot/src/tests/debt-fixes.test.ts (new)

Five test cases using the established `node:test` + `node:assert/strict` harness:
- Test A: MENU_PRODUCT_HELP postback → `axios.get` to `/content?type=category`
- Test B: MENU_MAIN postback → `axios.post` with "Welcome to Govi" text
- Test C (negative): UNKNOWN_XYZ postback → zero axios calls
- Test D: two-event batch, Event 1 rejects, Event 2 still processed, `callCount === 2`
- Test E: non-Error throw in `sendMessage` → logged as string `"plain-string-error"`

## Test Results

- **Prior tests:** 22/22 passing (handlers, escalation, qa-flow, sendMessage, setup, hmac)
- **New tests:** 5/5 passing (debt-fixes)
- **Total:** 27/27 passing, 0 failing
- All tests run via `TS_NODE_TRANSPILE_ONLY=true` with `NODE_PATH` pointing to main repo `node_modules` (worktree has no local `node_modules`)

## Deviations from Plan

None — plan executed exactly as written. All four DEBT items patched surgically per D-01 through D-07.

## Requirements Closed

| ID | Description | Status |
|----|-------------|--------|
| DEBT-01 | Postback handler dispatches MENU_PRODUCT_HELP/MENU_MAIN from persistent menu | Closed |
| DEBT-02 | Webhook async loop wrapped in try/catch (per-event isolation) | Closed |
| DEBT-03 | VERIFY_TOKEN fail-fast validation at startup | Closed |
| DEBT-04 | Non-Axios error branches sanitize logs to prevent token leak | Closed |

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. All changes are purely defensive patches to the existing webhook handler and startup sequence. Threat model items T-06-01, T-06-02, T-06-03 mitigated as planned; T-06-04 and T-06-05 accepted as documented.

## Known Stubs

None — all changes are behavioral fixes with no placeholder values.

## Self-Check: PASSED

- [x] `messenger-bot/src/index.ts` modified: confirmed via `git log --oneline`
- [x] `messenger-bot/src/tests/debt-fixes.test.ts` created: confirmed via `test -f`
- [x] Commits beedc5a, d0a095e, a152e30, 0dd5c9a, 3779f11 exist in git log
- [x] 27/27 tests pass, 0 fail
- [x] DEBT-03 guard in lines 6–8 (first 20 of file): confirmed
- [x] 8 `err instanceof Error` expressions: confirmed
- [x] MENU_PRODUCT_HELP and MENU_MAIN in postback dispatch: confirmed
- [x] try/catch around handleWebhookEvent inner loop: confirmed
