---
phase: 01-security-bot-foundation
plan: "03"
subsystem: messenger-bot
tags: [bot, navigation, messenger-profile, event-dispatch, quick-replies]
dependency_graph:
  requires: [01-02]
  provides: [CORE-01, CORE-02, CORE-03, CORE-04]
  affects: [messenger-bot/src/index.ts]
tech_stack:
  added: []
  patterns:
    - "Event dispatcher: postback -> quick_reply -> text (PITFALL-6 guard)"
    - "Fire-and-forget Messenger profile setup at app startup"
    - "GRAPH_API_VERSION constant — single source of truth for Graph API version"
    - "Shared MAIN_MENU_QUICK_REPLIES constant used by both welcome and fallback handlers"
key_files:
  created: []
  modified:
    - messenger-bot/src/index.ts
decisions:
  - "MAIN_MENU_QUICK_REPLIES has 2 items (Product Help, Contact Human) — 3rd item (Main Menu) is reachable only via hamburger; mirrors D-02 sensible default"
  - "handleWebhookEvent exported as standalone function so handlers.test.ts can test dispatch logic without spinning up Express"
  - "GOVI_AI_URL constant retained in file for future phases even though no longer used in any function body"
  - "Messenger Profile setup is fire-and-forget (not awaited) — bot must not fail to start if Facebook API is unreachable"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-14"
  tasks: 2
  files_modified: 1
---

# Phase 1 Plan 03: Bot Navigation Foundation Summary

Complete navigation skeleton for the Govi Messenger bot — GET_STARTED postback triggers welcome with quick replies, persistent hamburger menu configured at startup, free-text always gets a re-anchor fallback, and quick-reply taps are correctly guarded from triggering the fallback handler.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add Messenger Profile setup + GRAPH_API_VERSION + MAIN_MENU_QUICK_REPLIES | 73c705b | messenger-bot/src/index.ts |
| 2 | Add handleWebhookEvent dispatcher + sendWelcomeMessage + sendFallbackMessage; retire AI passthrough | c455509 | messenger-bot/src/index.ts |

## What Was Built

**Task 1 — Messenger Profile setup (CORE-02):**
- `GRAPH_API_VERSION = "v21.0"` exported constant; `sendMessage` URL uses template literal referencing it (single source of truth)
- `MAIN_MENU_QUICK_REPLIES: QuickReply[]` with Product Help and Contact Human entries
- `setupMessengerProfile()` posts `get_started` + `greeting` + `persistent_menu` (3 items) to Graph API at startup
- Safe error logging in catch block (SEC-03 pattern — never logs full AxiosError which carries PAGE_ACCESS_TOKEN)
- Called fire-and-forget from `app.listen` callback; bot continues even if setup fails

**Task 2 — Event dispatcher + handlers (CORE-01, CORE-03, CORE-04):**
- `sendWelcomeMessage(recipientId)`: sends welcome copy + MAIN_MENU_QUICK_REPLIES (CORE-01 + CORE-03)
- `sendFallbackMessage(recipientId)`: sends D-01 re-anchor text + MAIN_MENU_QUICK_REPLIES (CORE-04)
- `handleWebhookEvent(event)`: exported dispatcher with order postback -> quick_reply -> text
  - GET_STARTED postback -> sendWelcomeMessage
  - Other postbacks -> log + return (Phase 3 routing placeholder)
  - quick_reply taps -> log + return (PITFALL-6 guard: does NOT fall through to text branch)
  - free text -> log + sendFallbackMessage
- POST /webhook event loop replaced with `await handleWebhookEvent(event)` — clean two-level loop
- Govi AI passthrough (`/ai/chat` axios call) fully removed per ROADMAP Phase 1 retirement

## Test Results

All 10 tests green (0 skipped, 0 failed):
- 3 HMAC signature verification tests (Plan 02)
- 2 sendMessage Graph API tests (Plan 02)
- 1 setupMessengerProfile test (this plan, Task 1)
- 4 handleWebhookEvent / sendWelcomeMessage / sendFallbackMessage tests (this plan, Task 2)

`npm run build` exits 0 — strict TypeScript clean.

## Deviations from Plan

None — plan executed exactly as written.

The `npm install` step was required in the worktree (node_modules are gitignored and not present in fresh worktrees). A second `npm install --legacy-peer-deps` was needed to pull in a transitive dependency (`object-inspect`) missing after the initial install. This is a worktree environment issue, not a code deviation.

## Known Stubs

The following are intentional Phase 3+ placeholders per the plan:
- `if (event.postback)` branch (non-GET_STARTED): logs payload and returns — navigation routing arrives in Phase 3
- `if (event.message?.quick_reply)` branch: logs payload and returns — navigation routing arrives in Phase 3
- `GOVI_AI_URL` constant retained in file but not referenced by any function body — reserved for future phases

These do not prevent Phase 1 goals from being achieved. Phase 1 success criteria are fully satisfied.

## Threat Surface Scan

No new trust boundaries introduced beyond what the plan's threat model documents. All mitigations from the threat register (T-1-02-01 through T-1-02-05) are implemented:
- T-1-02-01: setupMessengerProfile catch logs only `axiosErr.message` + `axiosErr.response?.data` (never full err)
- T-1-02-02: setupMessengerProfile failure logs error and continues — bot does not crash
- T-1-02-03: handleWebhookEvent trusts postback payload only as a switch-key string, never eval'd
- T-1-02-04: sendFallbackMessage uses hardcoded copy — user input never reflected in outgoing messages
- T-1-02-05: quick_reply branch precedes text branch in handleWebhookEvent; unit test 4 is a regression guard

## Self-Check: PASSED

- messenger-bot/src/index.ts: FOUND
- Commit 73c705b: FOUND
- Commit c455509: FOUND
- All 10 tests passing: VERIFIED (npm test output above)
- npm run build exits 0: VERIFIED
- All 5 exported symbols present: VERIFIED (grep output confirmed)
- No /ai/chat in index.ts: VERIFIED (grep -c returns 0)
- quick_reply before text in dispatch: VERIFIED (awk check passed)
