---
phase: 04-human-escalation
reviewed: 2026-05-15T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - messenger-bot/src/index.ts
  - messenger-bot/src/tests/escalation.test.ts
findings:
  critical: 1
  warning: 3
  info: 1
  total: 5
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-05-15
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Reviewed the human-escalation implementation in `index.ts` and its test suite in `escalation.test.ts`. The core escalation flow (message ordering, lastMessageCache scoping, soft-fail on missing ADMIN_PSID, passThreadControl error handling) is implemented correctly. The ordering requirement — customer confirmation before `passThreadControl` — is correct in the implementation. No log statements leak `PAGE_ACCESS_TOKEN` or the value of `ADMIN_PSID`.

One critical finding: the test suite does not assert the critical ordering constraint it was designed to guard, meaning a future refactor that reorders those calls would silently pass all tests. Three warnings cover: (1) a suppressed send failure before `passThreadControl` which can leave the customer without confirmation, (2) redundant double-logging of the Graph API error object, and (3) duplicate startup-vs-per-request APP_SECRET warnings. One info item covers the empty type-only import.

---

## Critical Issues

### CR-01: ESC-01 test does not assert that customer confirmation precedes `passThreadControl`

**File:** `messenger-bot/src/tests/escalation.test.ts:65-69`
**Issue:** The test that covers the "Pitfall 1" ordering requirement (customer confirmation must be sent *before* `passThreadControl` to avoid Graph API error 551) only asserts that both `ADM_1` and `USR_ESC_1` appear somewhere in the `calls` array. It does not assert their position relative to the `pass_thread_control` call. A refactor that moves `passThreadControl` before `sendMessage(senderId, ...)` would pass every assertion in this test while reintroducing the error-551 risk.

**Fix:** Assert the relative index of the customer confirmation call versus the `pass_thread_control` call:
```typescript
// After the existing recipientIds checks, add:
const confirmIdx = calls.findIndex(
  (c) => c.body?.recipient?.id === "USR_ESC_1" &&
         c.body?.message?.text?.includes("Connecting you with a human")
);
const passIdx = calls.findIndex((c) => c.url?.includes("pass_thread_control"));
assert.ok(confirmIdx !== -1, "customer confirmation call must exist");
assert.ok(passIdx !== -1, "pass_thread_control call must exist");
assert.ok(
  confirmIdx < passIdx,
  `customer confirmation (index ${confirmIdx}) must precede passThreadControl (index ${passIdx})`
);
```
This should also be mirrored in the postback variant of ESC-01 (lines 80-113) with `USR_ESC_2`.

---

## Warnings

### WR-01: Customer confirmation silently skipped if first `sendMessage` throws, then `passThreadControl` fires anyway

**File:** `messenger-bot/src/index.ts:178-181`
**Issue:** `sendMessage` swallows all errors internally (try/catch that never re-throws, lines 118-141). If the call to send the customer confirmation at line 180 fails (e.g., transient Graph API error), execution falls through to `passThreadControl` at line 181. Control passes to the human agent, but the customer received no confirmation message and does not know what happened. This is the mirror of error-551: instead of calling `passThreadControl` too early, the bot calls it after a silent message failure.

**Fix:** Either propagate the error from `sendMessage` to let `handleEscalation` decide, or check a return value:
```typescript
// Option A — let sendMessage throw on failure (change its catch to re-throw)
// and wrap the critical section in handleEscalation:
try {
  await sendMessage(senderId, "Connecting you with a human — we'll be with you shortly!");
} catch {
  // Customer message failed — do not pass thread; agent won't see the customer's context anyway
  console.error("handleEscalation: failed to confirm with customer, aborting passThreadControl");
  return;
}
await passThreadControl(senderId);
```
Or, at minimum, return a boolean from `sendMessage` indicating success, and check it before calling `passThreadControl`.

### WR-02: Graph API in-band error object logged twice (redundant and potentially noisy)

**File:** `messenger-bot/src/index.ts:132` and `155`
**Issue:** Both `sendMessage` and `passThreadControl` log the error like:
```typescript
console.error("Graph API error:", response.data.error.message, response.data.error);
```
The first argument after the label is `response.data.error.message` (a string extracted from the object), and the third argument is `response.data.error` (the full object, which already contains `.message`). The message field is therefore printed twice: once as a plain string and once embedded inside the serialized object. In high-volume error scenarios this doubles log noise and makes the output harder to read.

**Fix:**
```typescript
// Log either the full object OR the extracted message — not both:
console.error("Graph API error:", response.data.error);
// The structured object gives the full context; no need to extract .message separately.
```

### WR-03: `FACEBOOK_APP_SECRET` absence warning fires twice on every unauthenticated request

**File:** `messenger-bot/src/index.ts:12-14` and `24-26`
**Issue:** `console.warn("FACEBOOK_APP_SECRET not set — skipping webhook signature verification")` appears at module load time (line 13) and again inside `verifySignature` (line 25) which is called on every POST request. In a development environment without `APP_SECRET` set, every incoming Messenger event generates a duplicate warning: one from startup and one from the middleware. Over a test session this floods the log with identical lines, making other warnings harder to notice.

**Fix:** Remove the duplicate at module load (lines 12-14) and keep only the per-request warning inside `verifySignature`. One occurrence per request is enough context; the startup occurrence adds nothing since no request has failed yet:
```typescript
// Delete lines 12-14:
// if (!process.env.FACEBOOK_APP_SECRET) {
//   console.warn("FACEBOOK_APP_SECRET not set — skipping webhook signature verification");
// }
```

---

## Info

### IN-01: Empty type-only import in test file provides no compile-time safety

**File:** `messenger-bot/src/tests/escalation.test.ts:10`
**Issue:** `import type {} from "../index"` imports zero types. It forces the TypeScript compiler to resolve `../index` as a valid module, but since no types are selected, it catches no type mismatches between what the test expects and what the module exports. The intent (per the comment on line 9) seems to be to anchor the type-check, but it does not achieve that goal.

**Fix:** Either remove the import (it provides no compile-time value as written) or import the actual types that the test uses, which would give real type-safety:
```typescript
import type { QuickReply } from "../index";
// Then use QuickReply in type annotations within the test file
```

---

_Reviewed: 2026-05-15_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
