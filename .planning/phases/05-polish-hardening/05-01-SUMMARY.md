---
phase: "05"
plan: "01"
subsystem: messenger-bot/tests
tags:
  - typescript
  - tdd
  - typing-indicator
  - red-state

dependency_graph:
  requires:
    - "03-02 (sendAnswer implementation and qa-flow.test.ts test infrastructure)"
  provides:
    - "RED state test contract for POLISH-01 typing indicator behavior"
  affects:
    - "05-02 (Wave 1 must satisfy these tests to turn them GREEN)"

tech_stack:
  added: []
  patterns:
    - "TDD RED phase: test contract written before implementation"
    - "assert.ok(expr === value) for literal grep-verifiable assertions"

key_files:
  created: []
  modified:
    - "messenger-bot/src/tests/qa-flow.test.ts"

decisions:
  - "Used assert.ok(expr === value) form instead of assert.strictEqual to satisfy plan acceptance criteria grep patterns"
  - "Both tasks committed in a single test commit since both modify the same file with no production code changes"

metrics:
  duration: "~5 minutes"
  completed: "2026-05-15"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 1
---

# Phase 05 Plan 01: Typing Indicator TDD Red State Summary

Wave 0 of Phase 05: updated qa-flow.test.ts to assert 3-POST typing_on/sendMessage/typing_off sequence and added an error-path test — both fail (RED) until Plan 02 implements `sendTypingIndicator` in `sendAnswer`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Update QUESTION test assertion (postCalls.length 1→3) | 1a2e109 | messenger-bot/src/tests/qa-flow.test.ts |
| 2 | Add error-path test for typing_off in finally block | 1a2e109 | messenger-bot/src/tests/qa-flow.test.ts |

## What Was Built

**Task 1:** In the existing `qa-flow: QUESTION:<id> triggers sendAnswer with body text and main menu re-anchor` test:
- Changed `postCalls.length` assertion from `1` to `3` with message "typing_on + sendMessage + typing_off for answer delivery"
- Added `assert.ok(stubs.postCalls[0].body?.sender_action === "typing_on", ...)` assertion
- Added `assert.ok(stubs.postCalls[2].body?.sender_action === "typing_off", ...)` assertion
- Changed message lookup from `postCalls[0].body?.message` to `postCalls[1].body?.message`

**Task 2:** Appended new test `qa-flow: sendAnswer typing_off fires even when API fetch fails`:
- Stubs `axios.get` to throw `ECONNREFUSED`
- Asserts exactly 3 POSTs: typing_on, apology sendMessage with MAIN_MENU_QUICK_REPLIES, typing_off
- Follows same stub + console.error-mute pattern as existing API-error test

## Verification Results

```
tests 22
pass 20
fail 2
```

Failing (expected RED):
- `qa-flow: QUESTION:<id> triggers sendAnswer ...` — actual: 1, expected: 3
- `qa-flow: sendAnswer typing_off fires even when API fetch fails` — actual: 1, expected: 3

All 20 other tests remain passing. This is the correct RED state for the TDD contract.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. This plan only modifies test assertions; no production code was added or modified.

## Threat Flags

No new threat surface introduced. Test file only; axios stubs prevent real network calls. No PAGE_ACCESS_TOKEN referenced.

## Self-Check: PASSED

- [x] `messenger-bot/src/tests/qa-flow.test.ts` modified with correct assertions
- [x] Commit 1a2e109 exists and is on main
- [x] `npm test` shows 22 tests, 20 pass, 2 fail (expected RED state)
- [x] No production code modified
