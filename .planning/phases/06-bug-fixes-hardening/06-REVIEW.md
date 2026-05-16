---
phase: 06-bug-fixes-hardening
reviewed: 2026-05-16T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - messenger-bot/src/index.ts
  - messenger-bot/src/tests/debt-fixes.test.ts
  - messenger-bot/src/tests/handlers.test.ts
  - messenger-bot/src/tests/escalation.test.ts
  - messenger-bot/src/tests/hmac.test.ts
  - messenger-bot/src/tests/qa-flow.test.ts
  - messenger-bot/src/tests/sendMessage.test.ts
  - messenger-bot/src/tests/setup.test.ts
findings:
  critical: 0
  warning: 4
  info: 2
  total: 6
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-05-16
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

This phase applied four surgical fixes to `messenger-bot/src/index.ts` (DEBT-01 through DEBT-04) and updated all six existing test files to set `FACEBOOK_VERIFY_TOKEN` before requiring `../index`, satisfying the new startup guard. A new `debt-fixes.test.ts` covers the four fixes.

The production code changes are broadly correct. DEBT-01 (routing), DEBT-03 (fail-fast guard), and DEBT-04 (error log sanitization) are implemented soundly. DEBT-02 (per-event try/catch) is implemented correctly in production, but its dedicated test does not actually exercise the isolation path it claims to test. Several secondary issues exist: a misleading warn message, log spam when `FACEBOOK_APP_SECRET` is absent, a missing startup guard for the equally critical `FACEBOOK_PAGE_ACCESS_TOKEN`, and a stale internal label in the DEBT-02 test comment.

---

## Warnings

### WR-01: DEBT-02 test does not actually verify per-event isolation

**File:** `messenger-bot/src/tests/debt-fixes.test.ts:112-164`

**Issue:** Test D claims to verify that a throwing event does not block the next event in the loop. However, `sendMessage` already swallows its own errors in its own `try/catch` block (index.ts:127-150) and does **not** rethrow. As a result, `handleWebhookEvent` never throws back to the caller — the test's outer `try/catch` wrapper at line 148 is never entered, and the assertion `callCount === 2` passes trivially whether or not the production loop has per-event isolation.

To actually test DEBT-02 isolation, the test would need `handleWebhookEvent` itself to throw (e.g., by mocking at the `handleWebhookEvent` level rather than at `axios.post`), then confirm the production inner loop's catch block catches it and continues.

**Fix:**
```typescript
// Replace the test with one that makes handleWebhookEvent itself throw on the first call,
// then verify the production loop (via HTTP POST /webhook) or by wrapping handleWebhookEvent:
let callCount = 0;
const origHandle = handleWebhookEvent;
// Temporarily replace handleWebhookEvent... or drive through POST /webhook using supertest
// so the real production loop runs.
// Simpler: patch sendWelcomeMessage to throw on the first call:
const mod = require("../index");
const orig = mod.sendWelcomeMessage;
let callCount = 0;
mod.sendWelcomeMessage = async (id: string) => {
  callCount++;
  if (callCount === 1) throw new Error("boom");
  return orig(id);
};
// Now call handleWebhookEvent directly twice; the first should throw to the event loop,
// the second should still execute.
```

---

### WR-02: Misleading warn message when `X-Hub-Signature-256` header is absent

**File:** `messenger-bot/src/index.ts:45`

**Issue:** When the `x-hub-signature-256` header is entirely missing, the code logs `"Webhook signature mismatch — check FACEBOOK_APP_SECRET"`. The message says "mismatch" but the signatures were never compared — the header simply was not present. In production, this causes an operator looking at logs to misdiagnose the root cause: they will check whether their `FACEBOOK_APP_SECRET` is wrong, when the real issue is a missing header on the inbound request (possible probe or misconfigured sender).

**Fix:**
```typescript
if (!signature) {
  console.warn("Webhook rejected — X-Hub-Signature-256 header missing");
  res.sendStatus(403);
  return;
}
```

---

### WR-03: `FACEBOOK_APP_SECRET` absence warning fires on every webhook request, not just at startup

**File:** `messenger-bot/src/index.ts:17-19` and `messenger-bot/src/index.ts:29-31`

**Issue:** The module-level block (lines 17-19) logs `console.warn("FACEBOOK_APP_SECRET not set...")` once at startup. The `verifySignature` middleware (lines 29-31) unconditionally logs the identical message again on **every** incoming POST to `/webhook`. In a production deployment receiving continuous traffic without `FACEBOOK_APP_SECRET` configured, this creates unbounded log spam, making it difficult to spot legitimate error messages.

**Fix:** Remove the per-request warn inside `verifySignature`; the startup warn at module load is sufficient:
```typescript
const appSecret = process.env.FACEBOOK_APP_SECRET;
if (!appSecret) {
  // Startup-time warn (lines 17-19) already covered this — do not repeat here
  let parsed: unknown;
  try {
    parsed = JSON.parse((req.body as Buffer).toString("utf8"));
  } catch {
    res.sendStatus(400);
    return;
  }
  (req as any).parsedBody = parsed;
  next();
  return;
}
```

---

### WR-04: Missing startup fail-fast guard for `FACEBOOK_PAGE_ACCESS_TOKEN`

**File:** `messenger-bot/src/index.ts:14`

**Issue:** DEBT-03 added a fail-fast guard for `FACEBOOK_VERIFY_TOKEN` (lines 6-9). `FACEBOOK_PAGE_ACCESS_TOKEN` is equally critical — it is used in every outbound call to the Graph API (`sendMessage`, `passThreadControl`, `sendTypingIndicator`, `setupMessengerProfile`). If it is absent from `.env`, line 14 silently assigns `undefined` (the `!` non-null assertion is a TypeScript compile-time bypass only). The bot starts successfully, every Graph API call silently uses `access_token=undefined`, Facebook returns 401s, and the bot becomes completely non-functional with no clear startup signal.

This is a direct asymmetry with the stated DEBT-03 goal: "refuse to start if critical env vars are absent."

**Fix:**
```typescript
if (!process.env.FACEBOOK_VERIFY_TOKEN) {
  console.error("FACEBOOK_VERIFY_TOKEN is not set — refusing to start.");
  process.exit(1);
}

if (!process.env.FACEBOOK_PAGE_ACCESS_TOKEN) {
  console.error("FACEBOOK_PAGE_ACCESS_TOKEN is not set — refusing to start. Configure it in messenger-bot/.env and restart.");
  process.exit(1);
}
```

---

## Info

### IN-01: Stale internal label "D-05" in DEBT-02 test comment

**File:** `messenger-bot/src/tests/debt-fixes.test.ts:157`

**Issue:** Comment reads `// (2) At least one recorded console.error has a string as second argument (D-05 sanitization)`. The sanitization fix is DEBT-04, not D-05. The file header on line 3 correctly names it `DEBT-04`. The stale label creates confusion when tracing a test failure back to the originating debt item.

**Fix:** Change `D-05 sanitization` to `DEBT-04 sanitization`.

---

### IN-02: DEBT-03 test coverage is indirect — no test verifies `process.exit(1)` is called

**File:** `messenger-bot/src/tests/debt-fixes.test.ts`

**Issue:** DEBT-03 (fail-fast startup guard for `FACEBOOK_VERIFY_TOKEN`) has no dedicated test. The other test files set `FACEBOOK_VERIFY_TOKEN` before `require("../index")` to avoid triggering the guard, but no test explicitly verifies that omitting the env var causes `process.exit(1)`. If the guard were accidentally removed, no test would catch the regression.

**Fix:** Add a test that spawns `index.ts` as a child process without `FACEBOOK_VERIFY_TOKEN` set and asserts the process exits with code 1. Example shape:
```typescript
import { spawnSync } from "child_process";

test("DEBT-03: missing FACEBOOK_VERIFY_TOKEN causes process.exit(1)", () => {
  const env = { ...process.env };
  delete env.FACEBOOK_VERIFY_TOKEN;
  const result = spawnSync(process.execPath, ["-r", "ts-node/register", "src/index.ts"], {
    env,
    cwd: /* messenger-bot root */,
    timeout: 3000,
  });
  assert.strictEqual(result.status, 1, "process should exit with code 1");
});
```

---

_Reviewed: 2026-05-16_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
