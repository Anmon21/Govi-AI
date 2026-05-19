---
phase: "08-answer-truncation"
plan: "01"
subsystem: "messenger-bot"
tags:
  - typescript
  - messenger
  - truncation
  - quick-reply
  - tdd
dependency_graph:
  requires:
    - "07-helpfulness-feedback/07-01 (FEEDBACK_QUICK_REPLIES, sendAnswer, PAYLOAD_PREFIX_QUESTION)"
  provides:
    - "ANSWER_THRESHOLD constant"
    - "PAYLOAD_PREFIX_READ_MORE constant"
    - "sendReadMoreAnswer function"
    - "READ_MORE: dispatch case in handleWebhookEvent"
    - "truncation branch in sendAnswer"
  affects:
    - "messenger-bot/src/index.ts (sendAnswer modified, new exports added)"
tech_stack:
  added: []
  patterns:
    - "TDD RED/GREEN cycle (skipped sentinel tests → full implementation)"
    - "Stateless re-fetch via questionId embedded in quick reply payload"
    - "DEBT-04 error sanitization in new catch block"
key_files:
  created:
    - "messenger-bot/src/tests/truncation.test.ts"
  modified:
    - "messenger-bot/src/index.ts"
decisions:
  - "Word-boundary truncation at lastIndexOf(' ', 200) with hard-cut fallback at 200 — avoids mid-word splits"
  - "Re-fetch on Read more tap (stateless) instead of in-memory cache — consistent with D-01 decision"
  - "Preview carries only [Read more] quick reply — no feedback buttons on truncated preview"
  - "sendReadMoreAnswer placed immediately after sendAnswer for code locality"
metrics:
  duration_seconds: 258
  completed_date: "2026-05-19T07:27:39Z"
  tasks_completed: 3
  tasks_total: 3
  files_created: 1
  files_modified: 1
---

# Phase 08 Plan 01: Answer Truncation Summary

**One-liner:** Answer truncation at 200 chars with word-boundary preview and stateless READ_MORE re-fetch via payload-embedded questionId.

## What Was Built

Added answer-length truncation to the Messenger bot. Answers longer than 200 characters are delivered as a word-boundary-cut preview ending in "..." with a single [Read more] quick reply. Tapping [Read more] triggers a `READ_MORE:{questionId}` payload that routes to a new `sendReadMoreAnswer` function, which re-fetches the full vault answer and delivers it with `FEEDBACK_QUICK_REPLIES` attached.

## Files Changed

| File | Change |
|------|--------|
| `messenger-bot/src/index.ts` | Added `ANSWER_THRESHOLD`, `PAYLOAD_PREFIX_READ_MORE`, truncation branch in `sendAnswer`, new `sendReadMoreAnswer` function, `READ_MORE:` dispatch in `handleWebhookEvent` |
| `messenger-bot/src/tests/truncation.test.ts` | New file: 9 test cases covering UX-04, UX-05, and 3 regressions |

## New Exports

| Export | Type | Value / Signature |
|--------|------|-------------------|
| `ANSWER_THRESHOLD` | `const number` | `200` |
| `PAYLOAD_PREFIX_READ_MORE` | `const string` | `"READ_MORE:"` |
| `sendReadMoreAnswer` | `async function` | `(recipientId: string, questionId: string): Promise<void>` |

## Test Count Change

**32 → 41** (+9 new truncation tests, all green, 0 skipped in final state)

## Requirements Closed

- **UX-04:** Answer truncation — preview at 200 chars with [Read more] quick reply. Observable by test `"UX-04: sendAnswer body 250 chars sends truncated preview with single [Read more] quick reply"`.
- **UX-05:** Read more tap re-fetches full answer with FEEDBACK_QUICK_REPLIES. Observable by test `"UX-05: READ_MORE:q1 quick reply tap calls vault GET and posts full body with FEEDBACK_QUICK_REPLIES"`.

## Task Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1: truncation.test.ts (TDD RED) | `0fa1223` | 9 skipped truncation tests via sentinel guard |
| Task 2: index.ts implementation (TDD GREEN) | `ed30a62` | All 5 edits applied; 9 previously-skipped tests now pass |
| Task 3: Validation | (no commit — verification only) | 41/41/0 fail/0 skip; tsc clean; DEBT-04 hygiene confirmed |

## Deviations from Plan

### Minor: FEEDBACK_QUICK_REPLIES non-comment grep count

The plan acceptance criterion for Task 2 stated "at least 4" occurrences of `FEEDBACK_QUICK_REPLIES` in non-comment lines. The actual count is 3 (export declaration + `sendAnswer` else branch + `sendReadMoreAnswer` success branch). The plan's count was over-specified — no additional references exist. All behavioral tests pass, confirming the implementation is correct. No code change required; criterion was overcounted in the plan.

### Minor: err instanceof Error count baseline

The plan stated "existing 6 + new 1 = 7" but the actual pre-edit count in the main repo was 8 (Phase 6 added more sanitized branches than noted). Post-edit count is 9. Criterion of "at least 7" is satisfied.

## DEBT-04 Hygiene

`sendReadMoreAnswer` catch block uses:
- `err.message` and `err.response?.data` for Axios errors
- `err instanceof Error ? err.message : String(err)` for non-Axios errors

No raw `err` object is logged in any new production code path. Verified by:
```
grep -v '^[[:space:]]*//' messenger-bot/src/index.ts | grep -E 'console\.error\(.*, err\)'
```
Returns zero matches.

## Threat Surface Scan

No new network endpoints, auth paths, or trust boundary changes beyond what the plan's threat model covered:
- T-08-01 mitigated: `encodeURIComponent(questionId)` used in `sendReadMoreAnswer` URL construction
- T-08-02 mitigated: DEBT-04 convention applied in `sendReadMoreAnswer` catch block

## Known Stubs

None — all data paths are wired through the vault API.

## Self-Check: PASSED

- `messenger-bot/src/tests/truncation.test.ts` exists: FOUND
- `messenger-bot/src/index.ts` modified with all 5 changes: FOUND
- Commit `0fa1223` exists: FOUND
- Commit `ed30a62` exists: FOUND
- Test suite: 41 tests / 41 pass / 0 fail / 0 skipped
- tsc --noEmit: exits 0
