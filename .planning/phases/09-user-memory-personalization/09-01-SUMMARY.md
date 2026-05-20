---
phase: 09-user-memory-personalization
plan: "01"
subsystem: messenger-bot
tags: [personalization, name-cache, graph-api, tdd, ux]
dependency_graph:
  requires: []
  provides: [userNameCache, fetchUserName]
  affects: [handleWebhookEvent, sendWelcomeMessage]
tech_stack:
  added: []
  patterns: [in-memory-map-cache, fetch-once-sentinel, sec-03-error-logging]
key_files:
  created:
    - messenger-bot/src/tests/personalization.test.ts
  modified:
    - messenger-bot/src/index.ts
    - messenger-bot/src/tests/debt-fixes.test.ts
decisions:
  - "Sentinel pattern uses Map.has() not truthiness — empty string stored on error/no-field allows cache hit on retry prevention"
  - "fetchUserName placed after lastMessageCache declaration following existing export const Map pattern"
  - "debt-fixes.test.ts DEBT-01c assertion updated to filter out Graph API calls (Phase 9 expected behavior)"
metrics:
  duration: "3m 8s"
  completed: "2026-05-20T08:34:45Z"
  tasks: 2
  files: 3
---

# Phase 9 Plan 01: User Memory & Personalization Summary

**One-liner:** In-memory PSID name cache populated from Facebook Graph API on first contact, enabling personalized "Welcome back, {name}!" greeting via `userNameCache` Map with fetch-once sentinel.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | RED: Write personalization.test.ts with 9 failing test cases | 324f9c4 | messenger-bot/src/tests/personalization.test.ts (created) |
| 2 | GREEN: Implement four insertions in index.ts to pass all tests | 81e7914 | messenger-bot/src/index.ts, messenger-bot/src/tests/debt-fixes.test.ts |

## Verification Output

### Final npm test (all 50 pass):

```
ℹ tests 50
ℹ suites 0
ℹ pass 50
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 2494.585417
```

All 9 personalization tests pass (UX-06 and UX-07). All 41 pre-existing tests continue to pass.

### TypeScript build:

`npm run build` exits 0 — no type errors.

### Source assertions:

- `grep -c "userNameCache" index.ts` → 5 (>= 4 required)
- `fetchUserName` appears at declaration (line 122) and call site in `handleWebhookEvent` (line 400)
- `"Welcome back,"` appears exactly once (line 382, sendWelcomeMessage personalized branch)
- `userNameCache.has` appears in `handleWebhookEvent` (line 399)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated debt-fixes.test.ts DEBT-01c assertion for Phase 9 behavior**

- **Found during:** Task 2 (GREEN phase), after implementing fetch-once guard
- **Issue:** `DEBT-01: unknown postback payload is silently dropped — no axios calls` test was asserting `getCalls.length === 0`. With Phase 9's `handleWebhookEvent` fetch-once guard, any unknown PSID now triggers `fetchUserName` → `axios.get` on `graph.facebook.com` before routing. This is correct new behavior, not a bug — but it broke the existing test's over-broad assertion.
- **Fix:** Changed `getCalls.length === 0` assertion to filter out Graph API calls and only check Govi AI calls: `getCalls.filter(url => !url.includes("graph.facebook.com")).length === 0`. Added a comment explaining the Phase 9 behavioral change.
- **Files modified:** `messenger-bot/src/tests/debt-fixes.test.ts`
- **Commit:** 81e7914

## Business Asset User Profile Access (Manual UAT)

The `fetchUserName` function calls `https://graph.facebook.com/v21.0/{psid}?fields=first_name`. This requires the Facebook App to have **Business Asset User Profile Access** permission.

**Current status:** Not yet verified in live environment. In development, `fetchUserName` will receive a 4xx error and store the empty-string sentinel — the bot will fall back to the generic greeting. This is the correct degraded-mode behavior.

**To enable personalization in production:**
1. In Facebook App Dashboard → Advanced → Business Asset User Profile Access → Request
2. Or verify the app already has `pages_messaging` scope which may include profile read access
3. Send GET_STARTED from a Messenger account with a known first name to confirm the greeting contains the name

## Known Stubs

None. All four insertions are fully wired: cache declaration, fetch helper, guard, and greeting branch.

## Threat Flags

No new security-relevant surface beyond what was defined in the plan's threat model. The `fetchUserName` implementation correctly follows SEC-03 (never logs raw axios error objects that contain PAGE_ACCESS_TOKEN).

## TDD Gate Compliance

- RED gate commit: 324f9c4 (`test(09-01): add failing personalization tests (RED phase)`)
- GREEN gate commit: 81e7914 (`feat(09-01): implement personalized greetings via in-memory name cache (GREEN phase)`)
- REFACTOR: not needed — implementation was clean on first pass

## Self-Check: PASSED
