---
phase: 03-product-q-a-flow
reviewed: 2026-05-15T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - app/routers/content.py
  - messenger-bot/src/index.ts
  - messenger-bot/src/tests/qa-flow.test.ts
findings:
  critical: 2
  warning: 5
  info: 3
  total: 10
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-05-15T00:00:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Phase 03 delivers the Product Q&A flow: a FastAPI content vault router (`content.py`) and an extended Messenger bot dispatcher (`index.ts`) that routes quick reply payloads through category → question → answer menus. Test coverage is provided in `qa-flow.test.ts`.

The implementation is structurally sound and the happy-path flow is correct. Two critical issues require fixes before shipping: an authentication bypass on the webhook verification endpoint (when `FACEBOOK_VERIFY_TOKEN` is absent from the environment) and an unauthenticated admin-privilege endpoint (`POST /content/reload`). Five additional warnings cover a user-visible silent dead end, an unhandled async error path in Express 4, a quick reply cap inconsistency, a missing message body length guard, and a test-time side effect.

---

## Critical Issues

### CR-01: Webhook Verification Bypass When `FACEBOOK_VERIFY_TOKEN` Is Not Set

**File:** `messenger-bot/src/index.ts:8,76`

**Issue:** `VERIFY_TOKEN` is assigned with a non-null assertion (`!`) from `process.env.FACEBOOK_VERIFY_TOKEN`. If that env var is missing at runtime (including during tests or a misconfigured deploy), `VERIFY_TOKEN` is `undefined`. At line 76 the comparison is `token === VERIFY_TOKEN`. When a GET request arrives with no `hub.verify_token` query parameter, `req.query["hub.verify_token"]` is also `undefined`. The comparison `undefined === undefined` evaluates to `true`, so Facebook's webhook challenge succeeds without any valid token — an attacker can register an arbitrary webhook endpoint against this server.

```
node -e "let v = undefined; let t = undefined; console.log(t === v)"
// → true
```

**Fix:** Validate that `VERIFY_TOKEN` is a non-empty string at startup and reject any comparison when either side is falsy:

```typescript
// Startup guard (fail fast)
if (!process.env.FACEBOOK_VERIFY_TOKEN) {
  console.error("FATAL: FACEBOOK_VERIFY_TOKEN is required");
  process.exit(1);
}
const VERIFY_TOKEN: string = process.env.FACEBOOK_VERIFY_TOKEN;

// In the GET /webhook handler
if (
  typeof token === "string" &&
  token.length > 0 &&
  mode === "subscribe" &&
  token === VERIFY_TOKEN
) {
  // verified
}
```

---

### CR-02: `POST /content/reload` Is Unauthenticated

**File:** `app/routers/content.py:110-115`

**Issue:** The `/content/reload` endpoint allows any caller on the network to force a full vault reload from disk. There is no authentication or authorization guard. While a disk read is not data-destructive in itself, the endpoint constitutes an unauthenticated admin-privilege operation: it can be used to cause repeated file system reads (denial-of-service via reload flooding) and, more importantly, to force a hot-swap of vault content in ways the operator did not initiate. In a production environment with `allow_origins=["*"]`, this endpoint is reachable from any origin.

**Fix:** Add a simple bearer token check using an env-sourced secret, or restrict the route to loopback-only via middleware. Minimal fix:

```python
from fastapi import APIRouter, HTTPException, Query, Header
from app.config import settings  # add reload_secret: str = "" to Settings

@router.post("/reload")
async def reload_vault(authorization: str = Header(default="")):
    if not settings.reload_secret or authorization != f"Bearer {settings.reload_secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    global _vault
    new_vault = load_vault()
    _vault = new_vault
    return {"reloaded": True, "content_count": len(_vault)}
```

---

## Warnings

### WR-01: `MENU_CONTACT_HUMAN` Quick Reply Returns Silently — User Gets No Response

**File:** `messenger-bot/src/index.ts:282-285`

**Issue:** When a user taps the "Contact Human" quick reply button, the handler returns without sending any message back. From the user's perspective the bot goes silent — no acknowledgement, no "we'll connect you shortly," nothing. The comment says "Phase 4 owns the escalation flow," which is fair, but the current behavior is a silent dead end that violates the stated design principle ("never a silent dead end" — see CORE-04 comment at line 307). Phase 4 may ship after users start testing Phase 3.

**Fix:** Send a holding message so the user knows their request was received:

```typescript
if (payload === "MENU_CONTACT_HUMAN") {
  await sendMessage(
    senderId,
    "Connecting you to a human agent — someone will be with you shortly.",
    MAIN_MENU_QUICK_REPLIES
  );
  return;
}
```

---

### WR-02: Express 4 Async Error Propagation — Unhandled Rejection on Unexpected Throw

**File:** `messenger-bot/src/index.ts:100-103`

**Issue:** The POST `/webhook` handler calls `await handleWebhookEvent(event)` inside an Express route handler that is `async` but Express 4 does not automatically forward unhandled promise rejections to the error middleware. If `handleWebhookEvent` throws unexpectedly (e.g., a bug in a future change that bypasses the inner try/catches), the rejection is unhandled at the framework level. In Node.js this generates an `UnhandledPromiseRejection` warning and in Node ≥15 causes process termination.

The Facebook 200 acknowledgement has already been sent (line 98), so error recovery for the user is not possible at that point — but the process crash risk is real.

**Fix:** Wrap the event loop in a try/catch:

```typescript
try {
  for (const entry of body.entry ?? []) {
    for (const event of entry.messaging ?? []) {
      await handleWebhookEvent(event);
    }
  }
} catch (err: unknown) {
  console.error("Unhandled error in webhook event loop:", err);
}
```

---

### WR-03: Quick Reply Count Cap Is Inconsistent Between Category and Question Menus

**File:** `messenger-bot/src/index.ts:170,199,206-207`

**Issue:** Facebook's limit is 13 quick replies per message. `sendCategoryMenu` slices to `items.slice(0, 13)` (line 170) and silently drops any additional categories — there is no indication to the user that more categories exist. `sendQuestionMenu` slices to `items.slice(0, 12)` and conditionally appends a "Main menu" escape-hatch button when there are more items (lines 206-207). The inconsistency means:

1. If a vault has >13 categories, users can never reach categories 14+, with no indication they're missing.
2. The "more than 12" escape-hatch logic in `sendQuestionMenu` fires when `items.length > 12` (line 206), but the slice is to 12. So when exactly 13 questions exist, the escape hatch IS added, giving 13 quick replies total — correct. However, when >13 questions exist, the 13th slot is taken by "Main menu" and questions 13+ are silently lost alongside categories 14+.

**Fix:** Apply the same escape-hatch pattern to `sendCategoryMenu`:

```typescript
const quickReplies: QuickReply[] = items.slice(0, 12).map((item) => ({
  content_type: "text",
  title: item.title,
  payload: `${PAYLOAD_PREFIX_CATEGORY}${item.id}`,
}));
if (items.length > 12) {
  quickReplies.push({ content_type: "text", title: "Main menu", payload: "MENU_MAIN" });
}
```

---

### WR-04: Answer Body Has No Length Cap — Silent Failure if Body Exceeds Facebook's 2000-Character Limit

**File:** `messenger-bot/src/index.ts:224-228` / `app/routers/content.py:79`

**Issue:** The vault stores `post.content` with no length constraint. Facebook's Send API rejects message text exceeding 2000 characters. When an answer body is too long, `sendMessage` makes the Graph API call, receives an error, logs it, and swallows it (lines 132-139). No fallback is sent to the user. The result is the user taps a question and receives no reply — a silent failure with no error path recovery.

**Fix (bot side):** Truncate or detect oversized bodies before sending:

```typescript
const MAX_FB_TEXT = 2000;
const displayBody = body.length > MAX_FB_TEXT
  ? body.slice(0, MAX_FB_TEXT - 3) + "..."
  : body;
await sendMessage(recipientId, displayBody, MAIN_MENU_QUICK_REPLIES);
```

Alternatively, validate body length in `load_vault()` and warn/skip vault entries whose body exceeds the limit.

---

### WR-05: Test Module Load Triggers `setupMessengerProfile()` — Makes Real Network Call in Test Environment

**File:** `messenger-bot/src/tests/qa-flow.test.ts:22` / `messenger-bot/src/index.ts:351-354`

**Issue:** At line 22, `require("../index")` executes the module which calls `app.listen(port, callback)`. The `listen` callback unconditionally calls `setupMessengerProfile()` (line 353), which makes a real HTTP POST to `https://graph.facebook.com/${GRAPH_API_VERSION}/me/messenger_profile`. In a CI/test environment where `FACEBOOK_PAGE_ACCESS_TOKEN` is absent, this generates a network request (which fails and is caught), but it adds latency, produces console noise, and would make a real API call if tokens happen to be set in the environment.

The `withAxiosStubs` helper only stubs `axios.get` and `axios.post` — it is not installed before `require("../index")` executes, so this particular axios.post call is NOT intercepted.

**Fix:** Guard `setupMessengerProfile()` behind an env check, or export it without auto-calling, so tests can isolate it:

```typescript
// Only auto-configure in non-test environments
if (process.env.NODE_ENV !== "test") {
  app.listen(port, () => {
    console.log(`Messenger bot listening on port ${port}`);
    setupMessengerProfile();
  });
}
```

---

## Info

### IN-01: `type` Parameter Shadows Python Built-in in `list_content`

**File:** `app/routers/content.py:87`

**Issue:** The query parameter is named `type`, which shadows the Python `type()` built-in for the duration of the function. It is not called as a built-in inside the function, so there is no runtime error, but it will trigger linting tools (flake8 A002 / ruff) and can mislead readers.

**Fix:** Rename to `item_type` and use an alias for the HTTP query parameter:

```python
async def list_content(
    item_type: str = Query("", alias="type", description="..."),
    category: Optional[str] = Query(None),
):
    if not item_type:
        raise HTTPException(status_code=400, detail="type query parameter is required")
    items = [
        ContentListItem(id=item["id"], type=item["type"], title=item["title"])
        for item in _vault.values()
        if item["type"] == item_type
        ...
    ]
```

---

### IN-02: Duplicate `FACEBOOK_APP_SECRET` Warning at Module Load and Per-Request

**File:** `messenger-bot/src/index.ts:12-14,25`

**Issue:** When `FACEBOOK_APP_SECRET` is not set, a `console.warn` fires once at module load (lines 12-14) and then again on every POST request inside `verifySignature` (line 25). In a long-running process this produces repeated log noise with no additional information.

**Fix:** Remove the per-request warn at line 25 since the module-load warn already covers it, or remove the module-load warn and keep only the per-request one.

---

### IN-03: Persistent Menu Postbacks for `MENU_PRODUCT_HELP` and `MENU_MAIN` Are No-Ops

**File:** `messenger-bot/src/index.ts:264-268,319-334`

**Issue:** The persistent menu is configured with three postback actions: `MENU_PRODUCT_HELP`, `MENU_CONTACT_HUMAN`, and `MENU_MAIN` (lines 331-333). The postback handler at lines 264-268 only handles `GET_STARTED` — all other postbacks just log and return without sending any response to the user. Users tapping "Product Help" or "Main Menu" from the persistent menu get a silent non-response. This is distinct from CR-01: it is not a security issue, but it is a broken UX path that exists in shipped code today. `MENU_CONTACT_HUMAN` is already flagged as WR-01.

**Fix:** Extend the postback handler to dispatch the same payloads as the quick reply handler:

```typescript
if (event.postback) {
  const p = event.postback.payload as string | undefined ?? "";
  if (p === "MENU_PRODUCT_HELP") { await sendCategoryMenu(senderId); return; }
  if (p === "MENU_MAIN")        { await sendWelcomeMessage(senderId); return; }
  if (p === "MENU_CONTACT_HUMAN") { /* WR-01 placeholder */ return; }
  console.log("Unhandled postback:", p);
  return;
}
```

---

_Reviewed: 2026-05-15T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
