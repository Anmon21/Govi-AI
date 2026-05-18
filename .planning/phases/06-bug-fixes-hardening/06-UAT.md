---
status: partial
phase: 06-bug-fixes-hardening
source:
  - 06-01-SUMMARY.md
started: "2026-05-18T00:00:00.000Z"
updated: "2026-05-18T00:00:00.000Z"
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running messenger-bot process. From `messenger-bot/`, run `npm run dev`. The bot should boot without errors and log "Messenger bot listening on port 3000". No unhandled exceptions in the first 5 seconds.
result: pass
notes: Bot booted and logged "Messenger bot listening on port 3001". setupMessengerProfile() failed with 400 (expected — dummy token). No crash. `npm run build` + `node dist/index.js` clean.

### 2. VERIFY_TOKEN startup guard
expected: With FACEBOOK_VERIFY_TOKEN unset or blank, the process exits immediately (before "listening on port...") with message: `FACEBOOK_VERIFY_TOKEN is not set — refusing to start. Configure it in messenger-bot/.env and restart.`
result: pass
notes: Tested with both unset and empty-string. Printed correct stderr message and exited with code 1 in both cases, before app.listen ran.

### 3. Product Help persistent menu tap
expected: Tap "Product Help" in Messenger persistent menu → bot replies with "Pick a topic:" and category quick-reply buttons.
result: blocked
blocked_by: server
reason: Bot not yet deployed and connected to a Facebook Page. Requires live Messenger environment.

### 4. Main Menu persistent menu tap
expected: Tap "Main Menu" in Messenger persistent menu → bot replies with welcome message and Product Help / Contact Human quick replies.
result: blocked
blocked_by: server
reason: Bot not yet deployed and connected to a Facebook Page. Requires live Messenger environment.

### 5. Webhook crash isolation
expected: One bad event does not crash the bot or block subsequent events in the same batch.
result: pass
notes: DEBT-02 automated test (debt-fixes.test.ts Test D) confirmed: Event 1 throws, Event 2 still processed, axios.post called exactly twice. 27/27 tests green.

## Summary

total: 5
passed: 3
issues: 0
skipped: 0
blocked: 2
pending: 0

## Gaps

[none]
