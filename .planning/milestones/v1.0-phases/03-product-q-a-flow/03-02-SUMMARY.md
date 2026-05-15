---
phase: 03-product-q-a-flow
plan: "02"
subsystem: messenger-bot
tags: [typescript, messenger, quick-replies, q-and-a, payload-dispatch]

# Dependency graph
requires:
  - phase: 03-01
    provides: "GET /content?type=&category= listing endpoint and GET /content/{id} item endpoint"
provides:
  - "sendCategoryMenu — fetches category list, sends as quick replies with CATEGORY: payloads"
  - "sendQuestionMenu — fetches question list for a category, sends as quick replies with QUESTION: payloads"
  - "sendAnswer — fetches answer body by id, sends text + MAIN_MENU_QUICK_REPLIES re-anchor"
  - "PAYLOAD_PREFIX_CATEGORY and PAYLOAD_PREFIX_QUESTION exported constants"
  - "handleWebhookEvent quick_reply dispatcher extended with prefix-match routing"
  - "qa-flow.test.ts — four test cases covering the full dispatch → handler path"
affects:
  - 04-human-escalation

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Prefix-match payload dispatch (MENU_*, CATEGORY:, QUESTION:) inside handleWebhookEvent"
    - "encodeURIComponent on caller-supplied ids before URL construction (T-3-bot-01 mitigation)"
    - "Shared sendApologyWithMenu error-path helper reduces duplication across three handlers"
    - "t.skip dormancy guard in tests — tests skip gracefully when symbols not yet exported"

key-files:
  created:
    - "messenger-bot/src/tests/qa-flow.test.ts"
  modified:
    - "messenger-bot/src/index.ts"

key-decisions:
  - "Drive tests through handleWebhookEvent dispatcher (not handler functions directly) — tests both dispatch wiring and handler at once"
  - "encodeURIComponent on categoryId and questionId — blocks URL injection into FastAPI calls"
  - "Truncate question list to 12 + 'Main menu' escape if >12 items — respects Messenger 13-button cap"
  - "Empty items list treated as success with 'no questions yet' message, not error — avoids false error logs for empty categories"

patterns-established:
  - "Error path: axios.isAxiosError guard → log err.message + err.response?.data only (SEC-03 preserved)"
  - "Re-anchor pattern: every answer and every error path re-attaches MAIN_MENU_QUICK_REPLIES so customer never dead-ends"

requirements-completed:
  - QA-01
  - QA-02
  - QA-03

# Metrics
duration: recovered from git history (2026-05-15)
completed: 2026-05-15
---

# Phase 3, Plan 02: Q&A Flow Bot Handlers Summary

**Messenger bot wired to vault content API — full menu → category → question → answer flow with payload-prefix dispatch and error-safe re-anchoring**

## Performance

- **Duration:** ~4 min (recovered from git commits, 2026-05-15T10:21–10:28)
- **Started:** 2026-05-15T10:21:44Z
- **Completed:** 2026-05-15T10:28:02Z
- **Tasks:** 2 (RED test scaffolds, GREEN implementation + dispatcher)
- **Files modified:** 2

## Accomplishments
- Added `sendCategoryMenu`, `sendQuestionMenu`, `sendAnswer` to `index.ts` — three handlers that call the FastAPI content API and reply with quick reply buttons
- Extended `handleWebhookEvent` quick_reply branch with prefix-match dispatcher: exact matches (MENU_PRODUCT_HELP, MENU_MAIN, MENU_CONTACT_HUMAN) first, then prefix matches (CATEGORY:, QUESTION:), then fallback
- Added `PAYLOAD_PREFIX_CATEGORY = "CATEGORY:"` and `PAYLOAD_PREFIX_QUESTION = "QUESTION:"` as exported module constants
- Created `qa-flow.test.ts` with 4 tests covering: Product Help → categories, Category → questions, Question → answer + re-anchor, API error → apology + main menu (no crash)
- All 21 tests GREEN, TypeScript compiles cleanly (`npx tsc --noEmit` exit 0)

## Task Commits

1. **Task 1: Failing qa-flow tests (RED state)** — `3decf7e` (test(03-02))
2. **Task 2: sendCategoryMenu, sendQuestionMenu, sendAnswer + dispatcher (GREEN state)** — `dc06e2d` (feat(03-02))

## Files Created/Modified
- `messenger-bot/src/tests/qa-flow.test.ts` — Four test cases (created)
- `messenger-bot/src/index.ts` — Three new exported handlers, two payload-prefix constants, extended quick_reply dispatcher (modified)

## Decisions Made
- `encodeURIComponent` applied to `categoryId` (query param) and `questionId` (path segment) before building FastAPI URLs — blocks `?`, `&`, `#`, `/`, `..` injection (T-3-bot-01)
- Shared `sendApologyWithMenu` private helper avoids duplicating the apology + MAIN_MENU_QUICK_REPLIES call across all three error paths
- Empty `items: []` list is a polite "no questions yet" message, not an error — prevents false console.error noise when a category is empty

## Deviations from Plan
None — plan executed exactly as written. Both tasks followed the plan's action sections verbatim.

## Issues Encountered
None during execution. SUMMARY.md was not committed at time of execution (only STATE.md was updated in the summary commit `05b561c`); recovered by writing this file retroactively from git history.

## Verification Results

```
npm test — 2026-05-15 (current run):

✔ qa-flow: MENU_PRODUCT_HELP triggers sendCategoryMenu with CATEGORY: payloads
✔ qa-flow: CATEGORY:<id> triggers sendQuestionMenu with QUESTION: payloads
✔ qa-flow: QUESTION:<id> triggers sendAnswer with body text and main menu re-anchor
✔ qa-flow: API error sends apology + MAIN_MENU_QUICK_REPLIES (no crash)
✔ sendMessage logs Graph API error when response.data.error present
✔ sendMessage catch block does not log full axios error object (no PAGE_ACCESS_TOKEN leak)
✔ setupMessengerProfile posts get_started + persistent_menu to /me/messenger_profile
ℹ tests 21  ℹ pass 21  ℹ fail 0  ℹ skipped 0

npx tsc --noEmit — exit 0 (strict TypeScript clean)
```

## Next Phase Readiness
- Full product Q&A flow is live: MENU_PRODUCT_HELP → categories → questions → answers → main menu re-anchor
- `MENU_CONTACT_HUMAN` payload is a logged noop — Phase 4 owns escalation wiring
- Phase 4 (Human Escalation) can build on `MAIN_MENU_QUICK_REPLIES` re-anchor pattern and `handleWebhookEvent` dispatcher

## Self-Check: PASSED

---
*Phase: 03-product-q-a-flow*
*Completed: 2026-05-15*
