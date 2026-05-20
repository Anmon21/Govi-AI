# Phase 9: User Memory & Personalization - Pattern Map

**Mapped:** 2026-05-20
**Files analyzed:** 2 (1 modified, 1 new)
**Analogs found:** 2 / 2

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `messenger-bot/src/index.ts` | utility/handler | request-response + event-driven | `messenger-bot/src/index.ts` (self — existing patterns within) | exact |
| `messenger-bot/src/tests/personalization.test.ts` | test | request-response | `messenger-bot/src/tests/truncation.test.ts` | exact |

---

## Pattern Assignments

### `messenger-bot/src/index.ts` (modified — four insertion points)

**Analog:** `messenger-bot/src/index.ts` — existing `lastMessageCache`, `sendMessage`, `passThreadControl`, `handleWebhookEvent`

---

#### Insertion 1: `userNameCache` Map declaration

**Pattern source:** `messenger-bot/src/index.ts` line 119 — `lastMessageCache`

Copy this pattern exactly. Place `userNameCache` immediately after `lastMessageCache`:

```typescript
// index.ts line 119 — existing pattern to follow
export const lastMessageCache = new Map<string, string>();

// New — same pattern for user names (add directly below)
export const userNameCache = new Map<string, string>();
```

Key details:
- `export const` — module-level, exported (matches `lastMessageCache`)
- Type is `Map<string, string>` — key is PSID string, value is first_name or `""` sentinel
- No initializer argument — empty Map on startup

---

#### Insertion 2: `fetchUserName` helper

**Pattern source:** `messenger-bot/src/index.ts` lines 153–174 (`passThreadControl`) and lines 127–151 (`sendMessage`) — SEC-03 error logging pattern

```typescript
// SEC-03 error logging pattern (from passThreadControl, lines 166–173)
} catch (err: unknown) {
  // SEC-03: never log the full axios error (config.url contains PAGE_ACCESS_TOKEN)
  if (axios.isAxiosError(err)) {
    console.error("passThreadControl failed:", err.message, err.response?.data);
  } else {
    console.error("passThreadControl failed (unexpected):", err instanceof Error ? err.message : String(err));
  }
}
```

**axios.get pattern** (from `sendCategoryMenu`, lines 244–267):
```typescript
// index.ts lines 244-245 — axios.get with params
const response = await axios.get(`${GOVI_AI_URL}/content?type=category`);
const items: Array<{ id: string; title: string }> = response.data?.items ?? [];
```

**Full `fetchUserName` to implement** (combining both patterns + Graph API contract from RESEARCH.md):

```typescript
export async function fetchUserName(psid: string): Promise<void> {
  try {
    const response = await axios.get(
      `https://graph.facebook.com/${GRAPH_API_VERSION}/${psid}`,
      { params: { fields: "first_name", access_token: PAGE_ACCESS_TOKEN } }
    );
    const firstName: string = response.data?.first_name ?? "";
    userNameCache.set(psid, firstName);
  } catch (err: unknown) {
    // SEC-03: never log the full axios error (config.url contains PAGE_ACCESS_TOKEN)
    if (axios.isAxiosError(err)) {
      console.error("fetchUserName failed:", err.message, err.response?.data);
    } else {
      console.error("fetchUserName failed (unexpected):", err instanceof Error ? err.message : String(err));
    }
    userNameCache.set(psid, "");
  }
}
```

Critical: sentinel `""` is written in BOTH success and catch branches. The catch branch writes `""` so `userNameCache.has(psid)` returns `true` on subsequent events (no retry).

---

#### Insertion 3: fetch-once guard in `handleWebhookEvent`

**Pattern source:** `messenger-bot/src/index.ts` lines 375–378 — existing `handleWebhookEvent` top-of-function guard

```typescript
// index.ts lines 375-378 — existing guard pattern
export async function handleWebhookEvent(event: any): Promise<void> {
  const senderId: string = event.sender?.id;
  if (!senderId) return;

  // INSERT HERE — before any routing
  if (!userNameCache.has(senderId)) {
    await fetchUserName(senderId);
  }

  // existing routing unchanged from here ...
  if (event.postback?.payload === "GET_STARTED") {
```

The guard uses `userNameCache.has(senderId)` — NOT truthiness of the value. This is the correct sentinel check. `""` (failure sentinel) causes `has()` to return `true` and skip the retry.

---

#### Insertion 4: Modified `sendWelcomeMessage`

**Pattern source:** `messenger-bot/src/index.ts` lines 359–365 — existing `sendWelcomeMessage`

```typescript
// index.ts lines 359-365 — current implementation (replace this)
export async function sendWelcomeMessage(recipientId: string): Promise<void> {
  await sendMessage(
    recipientId,
    "Welcome to Govi! I can help with product questions or connect you with a human.",
    MAIN_MENU_QUICK_REPLIES
  );
}
```

Replace with (exact copy strings from UI-SPEC — do not paraphrase):

```typescript
export async function sendWelcomeMessage(recipientId: string): Promise<void> {
  const firstName = userNameCache.get(recipientId);
  const text = firstName
    ? `Welcome back, ${firstName}! How can I help you today?`
    : "Welcome to Govi! I can help with product questions or connect you with a human.";
  await sendMessage(recipientId, text, MAIN_MENU_QUICK_REPLIES);
}
```

Branch condition: `firstName` (truthiness) — empty string `""` is falsy, `undefined` is falsy, a real name like `"Alice"` is truthy. This correctly produces the generic greeting for both the failure sentinel and the not-yet-populated case.

---

### `messenger-bot/src/tests/personalization.test.ts` (new test file)

**Analog:** `messenger-bot/src/tests/truncation.test.ts` (most recent test file — covers Phase 8, same test framework and stub patterns)

---

#### File header and imports pattern

**Source:** `truncation.test.ts` lines 1–11

```typescript
// Covers: UX-06 — ...
//         UX-07 — ...

import { test } from "node:test";
import assert from "node:assert/strict";
import type {} from "../index";

process.env.FACEBOOK_VERIFY_TOKEN = "test-token";
process.env.PORT = "0";
```

`PORT = "0"` prevents the Express server from binding to port 3000 during tests. This is required in every test file.

---

#### Module require pattern

**Source:** `truncation.test.ts` lines 23–41

```typescript
// truncation.test.ts lines 23-41 — safe require pattern
let handleWebhookEvent: EventFn | undefined;
let fetchUserName: ((psid: string) => Promise<void>) | undefined;
let userNameCache: Map<string, string> | undefined;

try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const mod = require("../index");
  handleWebhookEvent = typeof mod.handleWebhookEvent === "function" ? mod.handleWebhookEvent as EventFn : undefined;
  fetchUserName = typeof mod.fetchUserName === "function" ? mod.fetchUserName : undefined;
  userNameCache = mod.userNameCache instanceof Map ? mod.userNameCache : undefined;
} catch {
  handleWebhookEvent = undefined;
  fetchUserName = undefined;
  userNameCache = undefined;
}
```

Note: All test files import the same `../index` module. Because `require` caches modules, `userNameCache` in the test is the same Map instance as the one in the running module. Mutations made by `fetchUserName` are visible via `userNameCache.get(psid)` in the test.

---

#### `withAxiosStubs` helper pattern

**Source:** `truncation.test.ts` lines 43–65 (identical copy also in `feedback.test.ts` lines 33–55)

```typescript
// truncation.test.ts lines 43-65 — canonical withAxiosStubs
function withAxiosStubs(opts: { onGet?: (url: string) => any; onPost?: (url: string, body: any) => any }) {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
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

The default `onGet` return `{ data: {} }` is correct for Graph API calls where the app lacks Business Asset User Profile Access — it produces an empty-object response, which `fetchUserName` handles by storing `""`.

**Important for Phase 9 tests:** Every `handleWebhookEvent` call for an unknown PSID will trigger `fetchUserName` → `axios.get`. Always use `withAxiosStubs` before firing any event. The `onGet` handler receives Graph API URLs like `https://graph.facebook.com/v21.0/{psid}` as well as Govi AI vault URLs. Route by URL content:

```typescript
onGet: (url) => {
  if (url.includes("graph.facebook.com")) {
    return { data: { first_name: "Alice" } }; // or { data: {} } for no-name case
  }
  if (url.includes("/content/")) {
    return { data: { body: "ANSWER" } };
  }
  return { data: {} };
},
```

---

#### Test structure pattern

**Source:** `truncation.test.ts` lines 67–85 — try/finally with restore

```typescript
// truncation.test.ts lines 67-84 — test structure
test("UX-06: ...", async (t) => {
  if (!fetchUserName || !userNameCache) { t.skip("pending Phase 9 implementation"); return; }
  const stubs = withAxiosStubs({
    onGet: (url) => {
      if (url.includes("graph.facebook.com")) return { data: { first_name: "Alice" } };
      return { data: {} };
    },
  });
  try {
    // clear cache so PSID is unknown
    userNameCache!.clear();
    await fetchUserName!("PSID_1");
    assert.strictEqual(userNameCache!.get("PSID_1"), "Alice", "...");
  } finally { stubs.restore(); }
});
```

Pattern notes:
- `t.skip(...)` guard with readable pending message — matches all existing tests
- `try/finally` ensures `stubs.restore()` always runs
- `userNameCache!.clear()` before each test that relies on PSID being unknown (module-level Map persists across tests in same file)

---

#### console.error suppression pattern

**Source:** `feedback.test.ts` lines 83–85, 96 and `truncation.test.ts` lines 177–178, 189

```typescript
// truncation.test.ts lines 177-178 + 189 — suppress expected error logs
const originalError = console.error;
console.error = () => {};
try {
  // ... test code that triggers error path ...
} finally {
  stubs.restore();
  console.error = originalError;
}
```

Use this in tests that deliberately trigger the `fetchUserName` catch branch (network error, 4xx), to avoid polluting test output with expected error logs.

---

## Shared Patterns

### SEC-03: Never log PAGE_ACCESS_TOKEN

**Source:** `messenger-bot/src/index.ts` lines 143–149 (`sendMessage`), lines 166–173 (`passThreadControl`), lines 189–194 (`sendTypingIndicator`)
**Apply to:** `fetchUserName` catch block

```typescript
// index.ts lines 143-149 — canonical SEC-03 pattern
} catch (err: unknown) {
  // SEC-03: Never log the full axios error object (contains PAGE_ACCESS_TOKEN in config.url)
  if (axios.isAxiosError(err)) {
    console.error("sendMessage failed:", err.message, err.response?.data);
  } else {
    console.error("sendMessage failed (unexpected error):", err instanceof Error ? err.message : String(err));
  }
}
```

`fetchUserName` uses the same two-branch structure. Never pass `err` directly to `console.error`.

### Module-level Map pattern

**Source:** `messenger-bot/src/index.ts` line 119
**Apply to:** `userNameCache` declaration

```typescript
// index.ts line 119 — existing export pattern
export const lastMessageCache = new Map<string, string>();
```

All module-level state in `index.ts` is `export const`. `userNameCache` must follow the same form.

### axios.get with params object pattern

**Source:** `messenger-bot/src/index.ts` lines 128–136 (`sendMessage` → `axios.post`) and lines 153–162 (`passThreadControl`)

```typescript
// index.ts lines 153-162 — params passed as second arg options object
const response = await axios.post(
  `https://graph.facebook.com/${GRAPH_API_VERSION}/me/pass_thread_control`,
  { recipient: { id: recipientId }, target_app_id: PAGE_INBOX_APP_ID },
  { params: { access_token: PAGE_ACCESS_TOKEN } }
);
```

For `fetchUserName` (GET not POST), the params object is the second argument:

```typescript
await axios.get(
  `https://graph.facebook.com/${GRAPH_API_VERSION}/${psid}`,
  { params: { fields: "first_name", access_token: PAGE_ACCESS_TOKEN } }
);
```

---

## No Analog Found

None. Both files have strong analogs in the existing codebase.

---

## Metadata

**Analog search scope:** `messenger-bot/src/`, `messenger-bot/src/tests/`
**Files scanned:** `index.ts`, `feedback.test.ts`, `truncation.test.ts`, `handlers.test.ts`
**Pattern extraction date:** 2026-05-20
