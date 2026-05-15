---
phase: 04-human-escalation
plan: "02"
subsystem: messenger-bot
tags: [escalation, handover, facebook-messenger, pass-thread-control]

dependency_graph:
  requires: ["04-01"]
  provides: ["ESC-01", "ESC-02", "ESC-03", "ESC-04"]
  affects: ["messenger-bot/src/index.ts"]

tech_stack:
  added: []
  patterns:
    - "Module-level Map for in-process last-message cache"
    - "passThreadControl uses existing axios + SEC-03 error-narrowing pattern"
    - "ADMIN_PSID read via process.env inside handleEscalation (not module-level const) for test compatibility"

key_files:
  modified:
    - messenger-bot/src/index.ts

decisions:
  - "Read ADMIN_PSID dynamically (process.env.ADMIN_PSID inside handleEscalation) rather than capturing at module level — required for tests to set env var after module load"
  - "MENU_CONTACT_HUMAN postback branch added between GET_STARTED and catch-all postback log"
  - "lastMessageCache.set only in free-text branch to prevent Pitfall 4 (quick-reply labels corrupting cache)"
  - "Customer confirmation sent BEFORE passThreadControl to prevent Graph API error 551 (Pitfall 1)"

metrics:
  duration: "~20 minutes"
  completed: "2026-05-15T03:19:14Z"
  tasks_completed: 1
  tasks_total: 2
  files_modified: 1
---

# Phase 04 Plan 02: Escalation Implementation Summary

**One-liner:** Full end-to-end human escalation via Facebook Handover Protocol — admin notification, customer confirmation, thread passthrough to Page Inbox with graceful ADMIN_PSID-absent degradation.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement escalation in index.ts | 1795868 | messenger-bot/src/index.ts |
| 2 | Manual verification checkpoint | — | (awaiting user) |

## Task 1: Implementation Detail

Added to `messenger-bot/src/index.ts`:

**Module-level additions (after GRAPH_API_VERSION):**
- `export const PAGE_INBOX_APP_ID = "263902037430900"` — canonical Page Inbox app ID
- `export const lastMessageCache = new Map<string, string>()` — in-process last-message cache

**New exported functions:**

`passThreadControl(recipientId)` — POSTs `{ recipient: { id }, target_app_id: PAGE_INBOX_APP_ID }` to `https://graph.facebook.com/v21.0/me/pass_thread_control` with `access_token` in params. Uses SEC-03 pattern (axios.isAxiosError narrowing, no full error object logged).

`handleEscalation(senderId)` — reads `process.env.ADMIN_PSID` dynamically. Soft-fail if absent: logs warning, sends customer "be in touch" message, returns. Otherwise: admin notify → customer confirm → passThreadControl (Pitfall 1 ordering enforced).

**Wiring changes in handleWebhookEvent:**
- Quick reply branch: `MENU_CONTACT_HUMAN` now calls `await handleEscalation(senderId)` (replaced Phase 3 no-op stub)
- Postback branch: new `MENU_CONTACT_HUMAN` check added before the catch-all postback log
- Free-text branch: `lastMessageCache.set(senderId, event.message.text)` added before `sendFallbackMessage` (NOT in quick_reply branch — Pitfall 4 avoided)

## Test Results

| File | Before | After |
|------|--------|-------|
| escalation.test.ts (7 tests) | 7 skipped | 7 PASS |
| handlers.test.ts (7 tests) | 7 PASS | 7 PASS |
| All other tests (7 tests) | 7 PASS | 7 PASS |
| **Total** | **14 pass, 7 skip** | **21 pass, 0 skip, 0 fail** |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Read ADMIN_PSID dynamically inside handleEscalation**
- **Found during:** Task 1 analysis
- **Issue:** The plan described `const ADMIN_PSID = process.env.ADMIN_PSID` at module level (SCREAMING_SNAKE_CASE convention). However, tests set `process.env.ADMIN_PSID` after `require("../index")` completes — a module-level capture would always read `undefined`. The tests explicitly test both "ADMIN_PSID set" and "ADMIN_PSID absent" paths by mutating `process.env.ADMIN_PSID` between test cases.
- **Fix:** Read `const adminPsid = process.env.ADMIN_PSID` inside `handleEscalation` function body instead. No module-level `ADMIN_PSID` constant declared. The SCREAMING_SNAKE_CASE convention applies to module-level env captures — the local `adminPsid` uses camelCase per TypeScript local variable convention.
- **Files modified:** messenger-bot/src/index.ts
- **Commit:** 1795868

**2. [Note] Plan acceptance criteria awk check produces false-positive failure**
- The plan's postback-ordering awk check (`awk '/MENU_CONTACT_HUMAN/{a=NR}...'`) updates `a` on every match of `MENU_CONTACT_HUMAN`, ending on line 380 (the persistent_menu array entry), which comes after the catch-all comment on line 312. This makes the check report failure even though the dispatch code on line 306 correctly precedes line 312.
- The actual behavior is correct and verified by the passing test suite (ESC-01 postback test).
- A tighter awk using `event\.postback\?\.payload === "MENU_CONTACT_HUMAN"` confirms correct ordering (line 306 before line 312).

## Known Stubs

None. The implementation is complete for the automated portion. Task 2 (manual verification) covers the live Messenger end-to-end test which requires human action.

## Threat Flags

None. No new network endpoints, auth paths, or schema changes introduced beyond what was planned and covered by the threat model.

## v2 Deferral Note (T-4-03)

`lastMessageCache` is an unbounded in-process `Map`. For v1 with a small user base, this is acceptable. A v2 concern: add TTL/eviction (e.g., delete entry after 24 hours, or cap at N entries) to prevent unbounded memory growth in production. Documented as deferred — no action this phase.

## Live Checkpoint Outcomes

Task 2 awaits user verification. The following live steps must be confirmed before this plan is marked complete:

1. Facebook Page Advanced Messaging configured (Govi app = Primary Receiver, Page Inbox = Secondary Receiver)
2. ADMIN_PSID obtained and set in `messenger-bot/.env`
3. Customer free-text message triggers cache; escalation via quick reply delivers admin notification with last-message context
4. Thread transfer to Page Inbox confirmed (admin can reply from Page Inbox → customer receives it)
5. Escalation via persistent menu postback produces identical outcome
6. Soft-fail path verified with ADMIN_PSID unset
7. Token leak check confirms no PAGE_ACCESS_TOKEN or ADMIN_PSID value in logs

## Self-Check: PASSED

- [x] messenger-bot/src/index.ts exists and contains all required exports
- [x] Commit 1795868 exists in git log
- [x] 21/21 tests pass, 0 skip, 0 fail
- [x] PAGE_INBOX_APP_ID = "263902037430900" exported
- [x] lastMessageCache exported as Map<string, string>
- [x] passThreadControl exported and posts to /me/pass_thread_control
- [x] handleEscalation exported with soft-fail guard
- [x] MENU_CONTACT_HUMAN wired in both quick_reply and postback branches
- [x] lastMessageCache.set only in free-text branch (verified by test ESC-04)
- [x] No ADMIN_PSID interpolated in any log line
