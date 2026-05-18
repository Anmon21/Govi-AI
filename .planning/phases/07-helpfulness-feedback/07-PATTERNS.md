# Phase 7: Helpfulness Feedback — Pattern Map

**Mapped:** 2026-05-18
**Files analyzed:** 3 (1 modified — index.ts, 1 new — feedback.test.ts, 1 updated assertion — qa-flow.test.ts)
**Analogs found:** 3 / 3

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `messenger-bot/src/index.ts` | event handler + constants | event-driven (quick reply dispatch) | itself — two-point surgical edit | exact |
| `messenger-bot/src/tests/feedback.test.ts` | test | event-driven (unit, stub-based) | `messenger-bot/src/tests/qa-flow.test.ts` | exact |
| `messenger-bot/src/tests/qa-flow.test.ts` | test (assertion update only) | event-driven (unit, stub-based) | itself — single assertion swap | exact |

---

## Pattern Assignments

### `messenger-bot/src/index.ts` — Touch 1: New constant block (near line 216)

**Analog:** `messenger-bot/src/index.ts` lines 216–219 (existing `MAIN_MENU_QUICK_REPLIES` block)

**Existing constant pattern to copy** (lines 216–219):
```typescript
export const MAIN_MENU_QUICK_REPLIES: QuickReply[] = [
  { content_type: "text", title: "Product Help", payload: "MENU_PRODUCT_HELP" },
  { content_type: "text", title: "Contact Human", payload: "MENU_CONTACT_HUMAN" },
];
```

**New constants to insert immediately after line 219:**
```typescript
export const FEEDBACK_QUICK_REPLIES: QuickReply[] = [
  { content_type: "text", title: "Was it helpful? Yes", payload: "HELPFUL_YES" },
  { content_type: "text", title: "Was it helpful? No",  payload: "HELPFUL_NO" },
];

export const PAYLOAD_HELPFUL_YES = "HELPFUL_YES";
export const PAYLOAD_HELPFUL_NO  = "HELPFUL_NO";
```

- Titles must not exceed 20 chars. "Was it helpful? Yes" = 20 chars (at limit). "Was it helpful? No" = 19 chars.
- Follow the same `export const NAME: QuickReply[]` declaration form used for `MAIN_MENU_QUICK_REPLIES`.

---

### `messenger-bot/src/index.ts` — Touch 2: Swap in `sendAnswer` (line 303)

**Analog:** `messenger-bot/src/index.ts` lines 294–314 (`sendAnswer` function)

**Current line 303 (to change):**
```typescript
await sendMessage(recipientId, body, MAIN_MENU_QUICK_REPLIES);
```

**Replacement:**
```typescript
await sendMessage(recipientId, body, FEEDBACK_QUICK_REPLIES);
```

No other line in `sendAnswer` changes. The error path (`sendApologyWithMenu`) still uses `MAIN_MENU_QUICK_REPLIES` — do not touch it.

---

### `messenger-bot/src/index.ts` — Touch 3: Two new cases in quick reply dispatch (before line 393)

**Analog:** `messenger-bot/src/index.ts` lines 362–395 (existing quick reply dispatch block)

**Existing pattern to replicate** (lines 366–390):
```typescript
if (payload === "MENU_PRODUCT_HELP") {
  await sendCategoryMenu(senderId);
  return;
}
if (payload === "MENU_MAIN") {
  await sendWelcomeMessage(senderId);
  return;
}
if (payload === "MENU_CONTACT_HUMAN") {
  await handleEscalation(senderId);
  return;
}
```

**New cases to insert before line 392** (`// Unknown / malformed payload — re-anchor instead of going silent`):
```typescript
if (payload === "HELPFUL_YES") {
  await sendMessage(
    senderId,
    "Glad that helped! Let me know if you need anything else.",
    MAIN_MENU_QUICK_REPLIES
  );
  return;
}
if (payload === "HELPFUL_NO") {
  await handleEscalation(senderId);
  return;
}
```

Insertion point is before line 392–394:
```typescript
// Unknown / malformed payload — re-anchor instead of going silent
await sendFallbackMessage(senderId);
return;
```

Do NOT add any `sendMessage` call inside the `HELPFUL_NO` branch — `handleEscalation` already sends both the admin notification and the user-facing "Connecting you..." message.

---

### `messenger-bot/src/tests/feedback.test.ts` — NEW file

**Analog:** `messenger-bot/src/tests/qa-flow.test.ts` (full file — exact same structure)

**File header pattern** (lines 1–31 of `qa-flow.test.ts`):
```typescript
import { test } from "node:test";
import assert from "node:assert/strict";
import type {} from "../index";

process.env.FACEBOOK_VERIFY_TOKEN = "test-token";
process.env.PORT = "0";

type EventFn = (event: any) => Promise<void>;

let handleWebhookEvent: EventFn | undefined;
let FEEDBACK_QUICK_REPLIES: any[] | undefined;
let MAIN_MENU_QUICK_REPLIES: any[] | undefined;
let _feedbackExported = false;

try {
  const mod = require("../index");
  handleWebhookEvent = typeof mod.handleWebhookEvent === "function" ? mod.handleWebhookEvent as EventFn : undefined;
  FEEDBACK_QUICK_REPLIES = Array.isArray(mod.FEEDBACK_QUICK_REPLIES) ? mod.FEEDBACK_QUICK_REPLIES : undefined;
  MAIN_MENU_QUICK_REPLIES = Array.isArray(mod.MAIN_MENU_QUICK_REPLIES) ? mod.MAIN_MENU_QUICK_REPLIES : undefined;
  _feedbackExported = Array.isArray(mod.FEEDBACK_QUICK_REPLIES);
} catch {
  handleWebhookEvent = undefined;
  FEEDBACK_QUICK_REPLIES = undefined;
  MAIN_MENU_QUICK_REPLIES = undefined;
  _feedbackExported = false;
}
```

**`withAxiosStubs` helper pattern** (lines 33–55 of `qa-flow.test.ts` — copy verbatim):
```typescript
function withAxiosStubs(opts: { onGet?: (url: string) => any; onPost?: (url: string, body: any) => any }) {
  const axios = require("axios");
  const originalPost = axios.post;
  const originalGet = axios.get;
  const getCalls: { url: string }[] = [];
  const postCalls: { url: string; body: any }[] = [];
  axios.get = async (url: string) => {
    getCalls.push({ url });
    if (opts.onGet) return opts.onGet(url);
    return { data: {} };
  };
  axios.post = async (url: string, body: any) => {
    postCalls.push({ url, body });
    if (opts.onPost) return opts.onPost(url, body);
    return { data: {} };
  };
  return {
    getCalls,
    postCalls,
    restore() { axios.post = originalPost; axios.get = originalGet; },
  };
}
```

**Test skip guard pattern** (from `qa-flow.test.ts` line 58):
```typescript
if (!handleWebhookEvent || !_feedbackExported) { t.skip("pending Phase 7 implementation"); return; }
```

**`console.error` silence pattern** (from `qa-flow.test.ts` lines 152–153):
```typescript
const originalError = console.error;
console.error = () => {};
// ... in finally:
console.error = originalError;
```

**Five tests to write** (each follows the try/finally + stubs.restore() pattern from `qa-flow.test.ts`):

1. **UX-01 success:** Fire `QUESTION:<id>` quick reply event. Stub `axios.get` to return `{ data: { body: "ANSWER_TEXT" } }`. Assert `postCalls[1].body.message.quick_replies` deepStrictEquals `FEEDBACK_QUICK_REPLIES`.

2. **UX-01 error regression:** Stub `axios.get` to throw. Assert `postCalls[1].body.message.quick_replies` deepStrictEquals `MAIN_MENU_QUICK_REPLIES` (apology path — unchanged).

3. **UX-02:** Fire `{ message: { quick_reply: { payload: "HELPFUL_YES" }, text: "Was it helpful? Yes" }, sender: { id: "USR_X" } }`. Assert exactly 1 postCall. Assert `postCalls[0].body.message.text === "Glad that helped! Let me know if you need anything else."`. Assert `postCalls[0].body.message.quick_replies` deepStrictEquals `MAIN_MENU_QUICK_REPLIES`.

4. **UX-03:** Set `process.env.ADMIN_PSID = "ADMIN_1"`. Fire `{ message: { quick_reply: { payload: "HELPFUL_NO" }, text: "Was it helpful? No" }, sender: { id: "USR_X" } }`. Assert postCalls includes a message to `"ADMIN_1"` and a message to `"USR_X"` containing `"Connecting"`.

5. **Regression (unknown payload after feedback):** Fire event with `payload = "UNKNOWN_FEEDBACK_XYZ"`. Assert `postCalls[0].body.message.text` includes `"buttons below"` (the fallback text from `sendFallbackMessage`).

---

### `messenger-bot/src/tests/qa-flow.test.ts` — Assertion update at line 141

**Single line change** — swap the imported symbol in the assertion:

**Current line 141:**
```typescript
assert.deepStrictEqual(msg?.quick_replies, MAIN_MENU_QUICK_REPLIES,
  "main menu quick replies must be re-attached after every answer");
```

**Updated line 141:**
```typescript
assert.deepStrictEqual(msg?.quick_replies, FEEDBACK_QUICK_REPLIES,
  "feedback quick replies must be attached after every answer");
```

Also requires: import `FEEDBACK_QUICK_REPLIES` from the module in the try block at line 25 of `qa-flow.test.ts`:
```typescript
// Add alongside the existing MAIN_MENU_QUICK_REPLIES import in the try block (line 25):
FEEDBACK_QUICK_REPLIES = Array.isArray(mod.FEEDBACK_QUICK_REPLIES) ? mod.FEEDBACK_QUICK_REPLIES : undefined;
```

And declare the variable at the top of the file:
```typescript
let FEEDBACK_QUICK_REPLIES: any[] | undefined;
```

The test skip guard at line 119 must also reference `FEEDBACK_QUICK_REPLIES`:
```typescript
if (!handleWebhookEvent || !FEEDBACK_QUICK_REPLIES || !_sendCategoryMenuExported) { t.skip("..."); return; }
```

---

## Shared Patterns

### Axios stub and restore
**Source:** `messenger-bot/src/tests/qa-flow.test.ts` lines 33–55
**Apply to:** All tests in `feedback.test.ts`

The `withAxiosStubs` helper is the only stub mechanism in the project. Every test follows: set up stubs → fire event in try block → assert in try block → `stubs.restore()` in finally block.

### Module import in tests
**Source:** `messenger-bot/src/tests/qa-flow.test.ts` lines 21–31 and `messenger-bot/src/tests/debt-fixes.test.ts` lines 19–27
**Apply to:** `feedback.test.ts` header

Pattern: `require("../index")` wrapped in try/catch. Guard exports with typeof/Array.isArray before use. Set `process.env.FACEBOOK_VERIFY_TOKEN = "test-token"` and `process.env.PORT = "0"` before the require.

### Quick reply dispatch case
**Source:** `messenger-bot/src/index.ts` lines 366–394
**Apply to:** Both new cases in `handleWebhookEvent`

Pattern: `if (payload === "EXACT_STRING") { await fn(senderId); return; }`. No else. No fall-through. Always `return` after the await.

### Export all constants
**Source:** `messenger-bot/src/index.ts` lines 216–219 and 221–222
**Apply to:** New `FEEDBACK_QUICK_REPLIES`, `PAYLOAD_HELPFUL_YES`, `PAYLOAD_HELPFUL_NO` constants

Pattern: `export const NAME = value`. Tests import via `mod.NAME` — constants must be exported or tests cannot assert exact values without string literals.

---

## No Analog Found

None. All three files have exact analogs in the codebase.

---

## Metadata

**Analog search scope:** `messenger-bot/src/` and `messenger-bot/src/tests/`
**Files scanned:** 4 (index.ts, qa-flow.test.ts, debt-fixes.test.ts, 07-RESEARCH.md)
**Pattern extraction date:** 2026-05-18
