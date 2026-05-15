---
phase: 05-polish-hardening
reviewed: 2026-05-15T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - messenger-bot/src/index.ts
  - messenger-bot/src/tests/qa-flow.test.ts
  - messenger-bot/.env.example
findings:
  critical: 2
  warning: 6
  info: 3
  total: 11
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-05-15T00:00:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Three files reviewed: the main bot entry point (`index.ts`), the QA-flow test suite (`qa-flow.test.ts`), and the environment example file (`.env.example`). The implementation is substantially correct and covers the happy paths well. Two critical bugs were found — one that silently swallows the persistent-menu "Product Help" tap and one that produces an unhandled promise rejection when a webhook payload is malformed JSON or a non-object. Six warnings cover missing runtime guards, token exposure risk, and logic inconsistencies. Three info items flag type safety gaps and test fragility.

---

## Critical Issues

### CR-01: Persistent-menu "Product Help" postback is never handled — user receives no response

**File:** `messenger-bot/src/index.ts:327-341`

**Issue:** `setupMessengerProfile` registers a persistent-menu item `{ type: "postback", payload: "MENU_PRODUCT_HELP" }` (line 404). In `handleWebhookEvent`, the postback branch (lines 327-341) handles only `GET_STARTED` and `MENU_CONTACT_HUMAN`. `MENU_PRODUCT_HELP` is handled exclusively in the `quick_reply` branch (line 347). When a user taps "Product Help" from the persistent menu, the event has `event.postback.payload === "MENU_PRODUCT_HELP"` — it hits the catch-all `console.log("Postback received:", ...)` at line 339 and returns with no message sent to the user. The customer sees a complete dead end.

**Fix:**
```typescript
// In handleWebhookEvent, extend the postback section:
if (event.postback?.payload === "GET_STARTED") {
  await sendWelcomeMessage(senderId);
  return;
}
if (event.postback?.payload === "MENU_CONTACT_HUMAN") {
  await handleEscalation(senderId);
  return;
}
if (event.postback?.payload === "MENU_PRODUCT_HELP") {
  await sendCategoryMenu(senderId);
  return;
}
if (event.postback?.payload === "MENU_MAIN") {
  await sendWelcomeMessage(senderId);
  return;
}
```

---

### CR-02: Async webhook loop has no try/catch — unhandled promise rejection on any event-handler failure

**File:** `messenger-bot/src/index.ts:100-104`

**Issue:** Express 4 does not catch rejected promises from async route handlers. The loop at lines 100-104 runs after `res.sendStatus(200)` has already been sent. If `handleWebhookEvent` throws (e.g., if `body.entry` elements are malformed and an internal function throws unexpectedly), the rejection propagates to Node's `unhandledRejection` event. This terminates the process in Node 15+ under `--unhandled-rejections=throw` (the default). Additionally, line 92 (`body.object`) executes before `res.sendStatus(200)` — if `parsedBody` is a JSON array or non-object, `body.object` returns `undefined` (not a throw) and responds 404, but if `parsedBody` is `null`, `body.object` throws a TypeError inside the async handler before the 200 is sent, and Express 4 will not catch it.

**Fix:**
```typescript
app.post(
  "/webhook",
  express.raw({ type: "*/*" }),
  verifySignature,
  async (req: Request, res: Response) => {
    const body = (req as any).parsedBody;

    if (!body || typeof body !== "object" || Array.isArray(body)) {
      res.sendStatus(400);
      return;
    }

    if (body.object !== "page") {
      res.sendStatus(404);
      return;
    }

    res.sendStatus(200);

    try {
      for (const entry of body.entry ?? []) {
        for (const event of entry.messaging ?? []) {
          await handleWebhookEvent(event);
        }
      }
    } catch (err: unknown) {
      console.error("Unhandled error processing webhook events:", err);
    }
  }
);
```

---

## Warnings

### WR-01: Missing runtime guard on required environment variables — bot starts silently broken

**File:** `messenger-bot/src/index.ts:8-9`

**Issue:** `VERIFY_TOKEN` and `PAGE_ACCESS_TOKEN` use the TypeScript non-null assertion operator (`!`) but there is no runtime check. If either is unset in `.env`, `VERIFY_TOKEN` is `undefined` at runtime. Webhook verification at line 76 will then match any request where `token === undefined` (i.e., when Facebook omits the token), which either opens a security hole or silently fails. `PAGE_ACCESS_TOKEN` being `undefined` causes every Graph API call to succeed at the HTTP level (the token is sent as a query param) but Facebook will reject all requests with an OAuth error — the bot appears to start but all message sends silently fail.

**Fix:**
```typescript
const VERIFY_TOKEN = process.env.FACEBOOK_VERIFY_TOKEN;
const PAGE_ACCESS_TOKEN = process.env.FACEBOOK_PAGE_ACCESS_TOKEN;

if (!VERIFY_TOKEN || !PAGE_ACCESS_TOKEN) {
  console.error("FATAL: FACEBOOK_VERIFY_TOKEN and FACEBOOK_PAGE_ACCESS_TOKEN must be set");
  process.exit(1);
}
```

---

### WR-02: `verifySignature` emits the same warning twice when `FACEBOOK_APP_SECRET` is absent

**File:** `messenger-bot/src/index.ts:13` and `25`

**Issue:** The module-level check at line 12-14 logs `"FACEBOOK_APP_SECRET not set — skipping webhook signature verification"`. The middleware `verifySignature` logs the same string again at line 25 on every single request that arrives. In production this fills logs with repeated noise and masks genuine security events.

**Fix:** Remove the log from module-level (line 13) and keep only the middleware log, or vice versa. The middleware log is sufficient because it fires once per request; the module-level log is the right place for a one-time startup warning.

```typescript
// Remove lines 12-14 from module scope:
// if (!process.env.FACEBOOK_APP_SECRET) {
//   console.warn("FACEBOOK_APP_SECRET not set — skipping webhook signature verification");
// }
// The middleware already warns once per request, which is noisy enough.
// Prefer a single startup warning and remove the per-request repetition:
// in verifySignature, remove line 25's console.warn.
```

---

### WR-03: `sendCategoryMenu` caps at 13 quick replies with no "Main menu" escape hatch

**File:** `messenger-bot/src/index.ts:235-240`

**Issue:** `sendCategoryMenu` slices to 13 items (`items.slice(0, 13)`). Facebook's quick reply limit is 13. If there are 13 or more categories, all 13 slots are consumed by category replies and the user has no way to go back to the main menu except through the persistent menu (which requires tapping the hamburger icon — non-obvious for many users). By contrast, `sendQuestionMenu` consistently reserves one slot for a "Main menu" escape hatch when items exceed 12 (line 271-273). The two functions are inconsistent.

**Fix:**
```typescript
const MAX_CATEGORY_QRS = 12; // reserve 1 slot for escape hatch
const quickReplies: QuickReply[] = items.slice(0, MAX_CATEGORY_QRS).map((item) => ({
  content_type: "text",
  title: item.title,
  payload: `${PAYLOAD_PREFIX_CATEGORY}${item.id}`,
}));
if (items.length > MAX_CATEGORY_QRS) {
  quickReplies.push({ content_type: "text", title: "Main menu", payload: "MENU_MAIN" });
}
await sendMessage(recipientId, "Pick a topic:", quickReplies);
```

---

### WR-04: `lastMessage` content is embedded unguarded in admin notification — can exceed Graph API length limit

**File:** `messenger-bot/src/index.ts:200-201`

**Issue:** `handleEscalation` reads `lastMessageCache.get(senderId)` (arbitrary free text, up to 2000 characters per Facebook's limit) and injects it verbatim into the admin notification string (line 201). The composite string can therefore reach ~2060 characters. Facebook's Graph API message text limit is 2000 characters. If the limit is exceeded the admin notification silently fails (the error is logged by `sendMessage`, but the admin never sees the escalation context). No truncation is applied.

**Fix:**
```typescript
const MAX_PREVIEW = 200;
const preview = lastMessage
  ? lastMessage.length > MAX_PREVIEW
    ? lastMessage.slice(0, MAX_PREVIEW) + "…"
    : lastMessage
  : null;
const contextLine = preview ? `\nLast message: "${preview}"` : "";
```

---

### WR-05: `PAGE_ACCESS_TOKEN` could be logged via the `err` object in `sendTypingIndicator`'s non-Axios error branch

**File:** `messenger-bot/src/index.ts:183-185`

**Issue:** The `else` branch at line 184-185 logs the raw error object: `console.error("sendTypingIndicator failed (unexpected error):", err)`. If the error is not an Axios error (e.g., a custom Error thrown by a test stub or middleware), the full object is serialized. In production, non-Axios errors from networking libraries could theoretically include request config (containing the token URL). The same pattern appears in `sendMessage` (line 139) and `passThreadControl` (line 162). The Axios-specific branch already guards against token leakage — but the generic branch does not. This is the same pattern the code comments warn about for the Axios case (see "SEC-03" comments) but is not applied to the generic branch.

**Fix:** Restrict the generic error log to `err instanceof Error ? err.message : String(err)` to avoid serializing unknown objects:
```typescript
} else {
  console.error("sendTypingIndicator failed (unexpected error):", err instanceof Error ? err.message : String(err));
}
```
Apply the same fix to the corresponding `else` branches in `sendMessage` and `passThreadControl`.

---

### WR-06: `handleWebhookEvent` is called with `event.sender?.id` typed as `string` but is actually `string | undefined`

**File:** `messenger-bot/src/index.ts:324`

**Issue:** The explicit `: string` annotation on `senderId` at line 324 suppresses TypeScript's strict null checks. `event.sender?.id` evaluates to `undefined` when `event.sender` is absent, but the annotation lies to the compiler. The runtime guard `if (!senderId) return` at line 325 is correct, but TypeScript will not warn if downstream code (future additions) passes `senderId` where a guaranteed string is required, potentially masking bugs.

**Fix:**
```typescript
const senderId: string | undefined = event.sender?.id;
if (!senderId) return;
// TypeScript now knows senderId is string below this point
```

---

## Info

### IN-01: `import type {} from "../index"` is a no-op import

**File:** `messenger-bot/src/tests/qa-flow.test.ts:9`

**Issue:** `import type {} from "../index"` imports no types and has no effect. It appears to be a leftover from an earlier plan to import specific types that were ultimately loaded via `require("../index")` instead. It does not cause a runtime error but it is dead code.

**Fix:** Remove line 9.

---

### IN-02: `withAxiosStubs` patches the live Axios module instance globally — test isolation is incomplete

**File:** `messenger-bot/src/tests/qa-flow.test.ts:32-54`

**Issue:** The stub implementation replaces `axios.get` and `axios.post` on the Axios module singleton. The `restore()` call in each `finally` block restores the originals. However, if a test throws before reaching `try { ... } finally { stubs.restore() }` — i.e., before the `try` is entered — the stubs are never cleaned up and subsequent tests run with a broken Axios. In this file the pattern is always `const stubs = withAxiosStubs({...}); try { ... } finally { stubs.restore(); }` which is safe, but the helper itself does not protect against misuse.

**Fix:** This is acceptable as-is given the consistent usage pattern. For robustness, consider exposing stubs only within a callback:
```typescript
async function withAxiosStubs<T>(
  opts: { onGet?: ...; onPost?: ... },
  fn: (stubs: StubResult) => Promise<T>
): Promise<T> {
  const stubs = setupStubs(opts);
  try { return await fn(stubs); } finally { stubs.restore(); }
}
```

---

### IN-03: `PAGE_INBOX_APP_ID` is a hardcoded constant but documented as if it could change

**File:** `messenger-bot/src/index.ts:109` and `messenger-bot/.env.example:21-22`

**Issue:** `PAGE_INBOX_APP_ID = "263902037430900"` is exported as a module constant at line 109. The `.env.example` notes "This value does not change — it is not an env var." This is consistent. However, exporting it as a named constant on the module creates an implicit public API — downstream code could import and override it. Given it is truly invariant, consider using a locally-scoped constant and not exporting it, or at least making the intent explicit with a comment that it must not be changed without a platform migration.

**Fix:** If it truly never varies, remove the `export` keyword:
```typescript
const PAGE_INBOX_APP_ID = "263902037430900"; // Facebook canonical Page Inbox app ID — do not change
```

---

_Reviewed: 2026-05-15T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
