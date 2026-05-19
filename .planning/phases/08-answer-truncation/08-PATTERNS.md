# Phase 8: Answer Truncation - Pattern Map

**Mapped:** 2026-05-19
**Files analyzed:** 2 (1 modified, 1 new)
**Analogs found:** 2 / 2

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `messenger-bot/src/index.ts` | service / webhook handler | request-response + CRUD | itself (existing `sendAnswer`, `sendQuestionMenu`) | exact — same file |
| `messenger-bot/src/tests/truncation.test.ts` | test | request-response | `messenger-bot/src/tests/feedback.test.ts` | exact |

---

## Pattern Assignments

### `messenger-bot/src/index.ts` (modified — service, request-response)

**Analog:** `messenger-bot/src/index.ts` — existing functions in the same file provide all needed patterns.

---

#### Constants pattern (lines 226–230):

Add `PAYLOAD_PREFIX_READ_MORE` immediately after `PAYLOAD_PREFIX_QUESTION` to keep prefix constants grouped.

```typescript
// Current block (index.ts:226-230) — insert READ_MORE after line 230
export const PAYLOAD_HELPFUL_YES = "HELPFUL_YES";
export const PAYLOAD_HELPFUL_NO  = "HELPFUL_NO";

export const PAYLOAD_PREFIX_CATEGORY = "CATEGORY:";
export const PAYLOAD_PREFIX_QUESTION = "QUESTION:";
// NEW — insert here:
export const PAYLOAD_PREFIX_READ_MORE = "READ_MORE:";
```

---

#### Truncation logic pattern — to insert inside `sendAnswer` (lines 302–322):

The current `sendAnswer` sends the body unconditionally with `FEEDBACK_QUICK_REPLIES`. Phase 8 branches on `body.length > 200` before that send. The word-boundary algorithm uses `String.prototype.lastIndexOf`.

Current `sendAnswer` (lines 302–322) — this is the baseline to modify:

```typescript
// index.ts:302-322 — FULL CURRENT sendAnswer (baseline)
export async function sendAnswer(recipientId: string, questionId: string): Promise<void> {
  await sendTypingIndicator(recipientId, "typing_on");
  try {
    const response = await axios.get(`${GOVI_AI_URL}/content/${encodeURIComponent(questionId)}`);
    const body: string | undefined = response.data?.body;
    if (typeof body !== "string" || body.length === 0) {
      await sendApologyWithMenu(recipientId);
      return;
    }
    await sendMessage(recipientId, body, FEEDBACK_QUICK_REPLIES);
  } catch (err: unknown) {
    if (axios.isAxiosError(err)) {
      console.error("sendAnswer failed:", err.message, err.response?.data);
    } else {
      console.error("sendAnswer failed (unexpected error):", err instanceof Error ? err.message : String(err));
    }
    await sendApologyWithMenu(recipientId);
  } finally {
    await sendTypingIndicator(recipientId, "typing_off");
  }
}
```

The line `await sendMessage(recipientId, body, FEEDBACK_QUICK_REPLIES);` (line 311) is the insertion point for the truncation branch:

```typescript
// Replace line 311 with this branch:
const ANSWER_THRESHOLD = 200;
if (body.length > ANSWER_THRESHOLD) {
  const cutIndex = body.lastIndexOf(" ", ANSWER_THRESHOLD);
  const preview = cutIndex > 0
    ? body.slice(0, cutIndex) + "..."
    : body.slice(0, ANSWER_THRESHOLD) + "...";
  const readMoreReply: QuickReply = {
    content_type: "text",
    title: "Read more",  // 9 chars — within 20-char Facebook limit
    payload: `${PAYLOAD_PREFIX_READ_MORE}${questionId}`,
  };
  await sendMessage(recipientId, preview, [readMoreReply]);
} else {
  await sendMessage(recipientId, body, FEEDBACK_QUICK_REPLIES);
}
```

Key rules:
- `ANSWER_THRESHOLD` constant placed near the other constants block (around line 230).
- Condition is strictly `> 200` — a body of exactly 200 chars takes the `else` branch (no truncation).
- `lastIndexOf(" ", 200)` with guard: if result is `<= 0`, hard-cut at 200.
- Preview message carries only the `[Read more]` quick reply — no `FEEDBACK_QUICK_REPLIES`.
- Short answers carry `FEEDBACK_QUICK_REPLIES` unchanged (existing Phase 7 behaviour preserved).

---

#### New function pattern — `sendReadMoreAnswer` (mirrors `sendAnswer` exactly):

**Analog:** `sendAnswer` (index.ts:302–322) — identical structure: `typing_on` before try, vault re-fetch, `sendApologyWithMenu` on failure, `typing_off` in finally.

```typescript
// NEW function — place after sendAnswer (after line 322)
export async function sendReadMoreAnswer(recipientId: string, questionId: string): Promise<void> {
  await sendTypingIndicator(recipientId, "typing_on");
  try {
    const response = await axios.get(`${GOVI_AI_URL}/content/${encodeURIComponent(questionId)}`);
    const body: string | undefined = response.data?.body;
    if (typeof body !== "string" || body.length === 0) {
      await sendApologyWithMenu(recipientId);
      return;
    }
    await sendMessage(recipientId, body, FEEDBACK_QUICK_REPLIES);
  } catch (err: unknown) {
    if (axios.isAxiosError(err)) {
      console.error("sendReadMoreAnswer failed:", err.message, err.response?.data);
    } else {
      console.error("sendReadMoreAnswer failed (unexpected error):", err instanceof Error ? err.message : String(err));
    }
    await sendApologyWithMenu(recipientId);
  } finally {
    await sendTypingIndicator(recipientId, "typing_off");
  }
}
```

Key rules:
- `encodeURIComponent(questionId)` — same as `sendAnswer` line 305; prevents URL injection on special chars.
- Full body sent with `FEEDBACK_QUICK_REPLIES` — consistent with short-answer path.
- Error logging follows Phase 6 DEBT-04 convention: `err instanceof Error ? err.message : String(err)` for non-Axios errors (never log raw error object).
- `typing_off` is in `finally` — mandatory, mirrors `sendAnswer`.

---

#### Payload dispatch insertion pattern (lines 393–399 — `QUESTION:` handler):

**Analog:** `QUESTION:` case at index.ts:393–399. New `READ_MORE:` case slots in after it, before the `HELPFUL_YES` check at line 400.

Existing `QUESTION:` case (lines 393–399):

```typescript
// index.ts:393-399 — existing QUESTION: dispatch
if (payload.startsWith(PAYLOAD_PREFIX_QUESTION)) {
  const questionId = payload.slice(PAYLOAD_PREFIX_QUESTION.length);
  if (questionId) {
    await sendAnswer(senderId, questionId);
    return;
  }
}
```

New `READ_MORE:` case — insert immediately after line 399, before `HELPFUL_YES`:

```typescript
// NEW — insert after QUESTION: case, before HELPFUL_YES check
if (payload.startsWith(PAYLOAD_PREFIX_READ_MORE)) {
  const questionId = payload.slice(PAYLOAD_PREFIX_READ_MORE.length);
  if (questionId) {
    await sendReadMoreAnswer(senderId, questionId);
    return;
  }
}
```

Empty `questionId` guard (`if (questionId)`) falls through to `sendFallbackMessage` — consistent with `QUESTION:` guard behaviour.

---

### `messenger-bot/src/tests/truncation.test.ts` (new — test, request-response)

**Analog:** `messenger-bot/src/tests/feedback.test.ts` — exact structural template. Copy the full file structure; adapt imports, sentinel exports, and test cases.

---

#### File header and imports pattern (feedback.test.ts:1–31):

```typescript
// Copy from feedback.test.ts:1-31 — adapt sentinel export name
import { test } from "node:test";
import assert from "node:assert/strict";
import type {} from "../index";

process.env.FACEBOOK_VERIFY_TOKEN = "test-token";
process.env.PORT = "0";

type EventFn = (event: any) => Promise<void>;

let handleWebhookEvent: EventFn | undefined;
let FEEDBACK_QUICK_REPLIES: any[] | undefined;
let MAIN_MENU_QUICK_REPLIES: any[] | undefined;
let sendAnswer: ((recipientId: string, questionId: string) => Promise<void>) | undefined;
let sendReadMoreAnswer: ((recipientId: string, questionId: string) => Promise<void>) | undefined;
let PAYLOAD_PREFIX_READ_MORE: string | undefined;
let _readMoreExported = false;  // sentinel — tests skip until Phase 8 lands

try {
  const mod = require("../index");
  handleWebhookEvent = typeof mod.handleWebhookEvent === "function" ? mod.handleWebhookEvent : undefined;
  FEEDBACK_QUICK_REPLIES = Array.isArray(mod.FEEDBACK_QUICK_REPLIES) ? mod.FEEDBACK_QUICK_REPLIES : undefined;
  MAIN_MENU_QUICK_REPLIES = Array.isArray(mod.MAIN_MENU_QUICK_REPLIES) ? mod.MAIN_MENU_QUICK_REPLIES : undefined;
  sendAnswer = typeof mod.sendAnswer === "function" ? mod.sendAnswer : undefined;
  sendReadMoreAnswer = typeof mod.sendReadMoreAnswer === "function" ? mod.sendReadMoreAnswer : undefined;
  PAYLOAD_PREFIX_READ_MORE = typeof mod.PAYLOAD_PREFIX_READ_MORE === "string" ? mod.PAYLOAD_PREFIX_READ_MORE : undefined;
  _readMoreExported = typeof mod.PAYLOAD_PREFIX_READ_MORE === "string";
} catch {
  handleWebhookEvent = undefined;
  FEEDBACK_QUICK_REPLIES = undefined;
  MAIN_MENU_QUICK_REPLIES = undefined;
  sendAnswer = undefined;
  sendReadMoreAnswer = undefined;
  PAYLOAD_PREFIX_READ_MORE = undefined;
  _readMoreExported = false;
}
```

---

#### `withAxiosStubs` helper (feedback.test.ts:33–55):

Copy verbatim — identical pattern required in every test file:

```typescript
// Copy verbatim from feedback.test.ts:33-55
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

---

#### Test case pattern — success path with postCall index assertions (feedback.test.ts:57–77):

All test cases follow this shape: stub axios, fire event or call function, assert on `postCalls` by index, restore in `finally`.

```typescript
// Template from feedback.test.ts:57-77 — adapt for truncation scenarios
test("UX-04: sendAnswer body ≤ 200 chars sends as-is with FEEDBACK_QUICK_REPLIES", async (t) => {
  if (!handleWebhookEvent || !_readMoreExported) { t.skip("pending Phase 8 implementation"); return; }
  const stubs = withAxiosStubs({
    onGet: (url) => {
      if (url.includes("/content/")) return { data: { body: "A".repeat(200) } };
      return { data: {} };
    },
  });
  try {
    await handleWebhookEvent!({
      message: { quick_reply: { payload: "QUESTION:q1" }, text: "q" },
      sender: { id: "USR_1" },
    });
    // postCalls[0] = typing_on, postCalls[1] = sendMessage, postCalls[2] = typing_off
    assert.strictEqual(stubs.postCalls.length, 3, "typing_on + sendMessage + typing_off");
    assert.deepStrictEqual(
      stubs.postCalls[1].body.message.quick_replies,
      FEEDBACK_QUICK_REPLIES,
      "short answer must carry FEEDBACK_QUICK_REPLIES"
    );
    assert.ok(
      !stubs.postCalls[1].body.message.text.endsWith("..."),
      "body at threshold must not be truncated"
    );
  } finally { stubs.restore(); }
});
```

Skip guard: `t.skip("pending Phase 8 implementation")` — matches the `t.skip` convention from feedback.test.ts:58.

---

#### Test case pattern — error path with console.error suppression (feedback.test.ts:79–99):

```typescript
// Template from feedback.test.ts:79-99 — error path with console.error suppression
test("UX-05 regression: sendReadMoreAnswer failure calls sendApologyWithMenu", async (t) => {
  if (!sendReadMoreAnswer || !_readMoreExported) { t.skip("pending Phase 8 implementation"); return; }
  const stubs = withAxiosStubs({
    onGet: async () => { throw new Error("ECONNREFUSED"); },
  });
  const originalError = console.error;
  console.error = () => {};
  try {
    await sendReadMoreAnswer!("USR_1", "q1");
    // postCalls[0] = typing_on, postCalls[1] = apology, postCalls[2] = typing_off
    assert.strictEqual(stubs.postCalls.length, 3, "typing_on + apology + typing_off on re-fetch error");
    assert.deepStrictEqual(
      stubs.postCalls[1].body.message.quick_replies,
      MAIN_MENU_QUICK_REPLIES,
      "apology must use MAIN_MENU_QUICK_REPLIES"
    );
  } finally {
    stubs.restore();
    console.error = originalError;
  }
});
```

---

## Shared Patterns

### Error Logging (Phase 6 DEBT-04 — apply to all new catch blocks)

**Source:** `messenger-bot/src/index.ts:312–317` (inside `sendAnswer`)
**Apply to:** Every `catch (err: unknown)` block in Phase 8 changes

```typescript
// index.ts:312-317
} catch (err: unknown) {
  if (axios.isAxiosError(err)) {
    console.error("sendAnswer failed:", err.message, err.response?.data);
  } else {
    console.error("sendAnswer failed (unexpected error):", err instanceof Error ? err.message : String(err));
  }
  await sendApologyWithMenu(recipientId);
}
```

Rule: non-Axios errors must use `err instanceof Error ? err.message : String(err)` — never log the raw `err` object (prevents leaking `PAGE_ACCESS_TOKEN` embedded in axios config URLs).

---

### Typing Indicator Sandwich (apply to `sendReadMoreAnswer`)

**Source:** `messenger-bot/src/index.ts:303, 320` (inside `sendAnswer`)
**Apply to:** `sendReadMoreAnswer`

```typescript
// index.ts:303 and 320
await sendTypingIndicator(recipientId, "typing_on");   // before try
try {
  // ...
} finally {
  await sendTypingIndicator(recipientId, "typing_off"); // in finally — mandatory
}
```

Rule: `typing_off` must be in `finally`, not in `try`. Without `finally`, a thrown error leaves Messenger showing a perpetual typing indicator.

---

### Silent Error Recovery (apply to `sendReadMoreAnswer`)

**Source:** `messenger-bot/src/index.ts:318` and `messenger-bot/src/index.ts:264, 298`
**Apply to:** Any new helper function that calls the vault

```typescript
// Pattern: log + fall back to apology menu — never surface raw errors to the user
await sendApologyWithMenu(recipientId);
```

---

### QuickReply Inline Object (apply to preview message construction)

**Source:** `messenger-bot/src/index.ts:252–256` (inside `sendQuestionMenu`)
**Apply to:** Building the `[Read more]` quick reply

```typescript
// index.ts:252-256 — inline QuickReply object literal pattern
const quickReplies: QuickReply[] = items.slice(0, 13).map((item) => ({
  content_type: "text",
  title: item.title,
  payload: `${PAYLOAD_PREFIX_CATEGORY}${item.id}`,
}));
```

For Phase 8, the single `Read more` reply follows the same inline object shape:

```typescript
const readMoreReply: QuickReply = {
  content_type: "text",
  title: "Read more",
  payload: `${PAYLOAD_PREFIX_READ_MORE}${questionId}`,
};
```

---

### Test Console Suppression (apply to error-path tests)

**Source:** `messenger-bot/src/tests/feedback.test.ts:84–86, 97`
**Apply to:** Any test that triggers a code path calling `console.error`

```typescript
const originalError = console.error;
console.error = () => {};
try {
  // ... test body
} finally {
  console.error = originalError;
}
```

---

## No Analog Found

None — all patterns for Phase 8 are fully covered by existing code in `index.ts` and `feedback.test.ts`.

---

## Metadata

**Analog search scope:** `messenger-bot/src/`, `messenger-bot/src/tests/`
**Files scanned:** `index.ts`, `feedback.test.ts`, `qa-flow.test.ts`
**Pattern extraction date:** 2026-05-19
