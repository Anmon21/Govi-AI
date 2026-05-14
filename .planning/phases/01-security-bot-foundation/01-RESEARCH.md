# Phase 1: Security + Bot Foundation - Research

**Researched:** 2026-05-14
**Domain:** Facebook Messenger Platform webhook security, Messenger Profile API, Express.js HMAC middleware
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** Fallback tone — friendly and helpful, acknowledges the user and redirects without friction (e.g., "I work best with the buttons below — here's what I can help with:")

**D-02:** Fallback quick replies mirror the top-level persistent menu items — consistent navigation, no dead end

**D-03:** HMAC-SHA256 verification code is written now (SEC-01), but gated: when `FACEBOOK_APP_SECRET` is not set in env, skip verification and log a warning — bot remains functional for local development without Facebook setup

**D-04:** `FACEBOOK_APP_SECRET` is not yet obtained — planner must document where to find it (Facebook Developer Dashboard → App Settings → Basic → App Secret) and add it to `messenger-bot/.env.example`

**D-05:** Welcome message text and persistent menu labels are Claude's discretion — sensible defaults for an e-commerce support bot; warm and brief welcome, menu items reflecting the 2 main capabilities (Product Help and Contact Human) plus optional third; labels must be ≤20 characters; treated as placeholder copy

**D-06:** SEC-01 (HMAC) — requires `express.raw()` middleware mounted BEFORE `express.json()` so the raw body is available for signature computation

**D-07:** SEC-02 (Graph API error detection) — after every `axios.post` to Graph API, check `response.data.error` and log it; do not rely on HTTP status alone

**D-08:** SEC-03 (token leak in logs) — log only `err.message` and `err.response?.data` in catch blocks, never the full axios error object

**D-09:** Fix `node_modules` committed to git as part of Phase 1 repo cleanup — add `node_modules/` and `messenger-bot/node_modules/` to `.gitignore`, then `git rm -r --cached`

### Claude's Discretion

- Welcome message text (warm, brief, e-commerce tone)
- Persistent menu item labels (≤20 chars, must be placeholder copy)
- Third menu item selection if appropriate (beyond Product Help and Contact Human)
- node_modules gitignore cleanup (D-09)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SEC-01 | Webhook verifies X-Hub-Signature-256 HMAC before processing any incoming event | HMAC-SHA256 using Node.js built-in `crypto` module; `express.raw()` captures the raw body; `crypto.timingSafeEqual` for constant-time comparison; gated on `FACEBOOK_APP_SECRET` presence |
| SEC-02 | Bot detects and logs Graph API errors returned inside HTTP 200 responses | Facebook Graph API returns `{ "error": {...} }` inside HTTP 200; check `response.data.error` after every `axios.post` to Graph API |
| SEC-03 | Application logs never contain PAGE_ACCESS_TOKEN or other secrets | Full axios error object includes `config.url` which contains the token as a query param; log only `err.message` and `err.response?.data` |
| CORE-01 | User sees a welcome message with navigation options when they first message the Page (Get Started postback handler) | `get_started` is set via `POST /me/messenger_profile`; generates a `messaging_postbacks` event with payload `"GET_STARTED"` or custom string; handled in webhook |
| CORE-02 | User can access a persistent hamburger menu at any time with top-level navigation options | `persistent_menu` set via `POST /me/messenger_profile`; max 3 top-level items; type `postback`; one-time API call at startup or via a setup script |
| CORE-03 | User navigates all flows via quick reply buttons — no free-text input required | Quick replies attached to every response message; `quick_replies` array on the message object; max 13 per message, title ≤20 chars, 1000-char payload limit |
| CORE-04 | User sees a helpful re-anchor message with menu options when they type free text (fallback handler — never silent) | Separate code path for `event.message?.text` that is NOT a quick_reply press; returns fallback message with quick replies mirroring persistent menu |
</phase_requirements>

---

## Summary

Phase 1 is a targeted hardening and skeleton pass on the single existing file `messenger-bot/src/index.ts`. All seven requirements are achievable with zero new npm dependencies — Node.js built-in `crypto` handles HMAC, and the existing `axios` + `express` stack handles all Facebook API calls.

The three security fixes (SEC-01, SEC-02, SEC-03) address real vulnerabilities in the current code: the webhook accepts forged events, Graph API send failures are swallowed silently, and the full axios error object leaks `PAGE_ACCESS_TOKEN` through the request URL. These must be fixed before any feature work is layered on top.

The four CORE requirements add structural bot behaviors using the Facebook Messenger Profile API (a one-time configuration call) and new event handlers in the webhook POST handler. The `get_started` button and `persistent_menu` are configured via a single `POST /me/messenger_profile` call using the already-available `PAGE_ACCESS_TOKEN`. The welcome message, persistent menu rendering, and fallback handler are all new code paths inside the existing Express webhook.

**Primary recommendation:** Fix SEC-01 first (it changes middleware order, which affects all other handlers), then fix SEC-02 and SEC-03 (isolated to `sendMessage`), then add CORE features (new event handlers and a one-time setup call). Node_modules git cleanup is independent and can be done first.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Webhook signature verification | Messenger Bot (Node.js) | — | Verification must happen at the entry point before any processing; Express middleware layer owns it |
| Graph API error detection | Messenger Bot (Node.js) | — | The bot makes all Graph API calls via axios; error checking belongs in the call site |
| Token leak prevention in logs | Messenger Bot (Node.js) | — | Logging is in the bot's catch blocks; fix is in the catch clauses |
| Get Started postback handler | Messenger Bot (Node.js) | — | Messenger sends postback events to the webhook; the bot handles them |
| Persistent menu configuration | Messenger Bot (Node.js) setup call | Facebook Platform (stored) | One-time `POST /me/messenger_profile` call; Facebook stores and serves the menu |
| Welcome message sending | Messenger Bot (Node.js) | — | Response to Get Started postback sent via Send API |
| Fallback free-text handler | Messenger Bot (Node.js) | — | Catch-all event dispatch for unrecognized text messages |
| Quick reply rendering | Messenger Bot (Node.js) | — | `quick_replies` field attached to outgoing message payloads |

---

## Standard Stack

### Core (No New Packages Needed)

| Library | Installed Version | Purpose | Why Standard |
|---------|----------|---------|--------------|
| Node.js `crypto` | Built-in (Node 26.0.0) | HMAC-SHA256 computation for webhook verification | Zero-dependency; `createHmac`, `timingSafeEqual` cover all needs |
| Express | 4.22.2 (installed) | HTTP server, middleware routing | Already the web layer; `express.raw()` is built-in |
| axios | 1.16.1 (installed) | Graph API and Govi AI API calls | Already used; no changes to the client itself |
| dotenv | 16.6.1 (installed) | Env var loading | Already used; just add `FACEBOOK_APP_SECRET` |

**No new npm packages are required for Phase 1.** [VERIFIED: `ls messenger-bot/node_modules`, version check via `node -e`]

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `crypto.createHmac` (built-in) | `x-hub-signature-middleware` npm package | npm package adds a dependency for 10 lines of crypto code; built-in is preferable |
| `express.raw()` (built-in) | `body-parser` raw middleware | `express.raw()` is Express 4.x built-in; body-parser is redundant |

---

## Architecture Patterns

### System Architecture Diagram

```
Facebook Platform
      |
      | POST /webhook (X-Hub-Signature-256 header + raw body)
      v
[Express: express.raw({ type: '*/*' })]  ← captures raw body bytes
      |
      | HMAC-SHA256(rawBody, APP_SECRET) vs header value
      v
[verifySignature middleware]
      | 403 if invalid / missing APP_SECRET → warn + continue
      v
[JSON.parse(req.body)]  ← manual parse after verification
      |
      +--[event.postback.payload === 'GET_STARTED'] → sendWelcome(senderId)
      |
      +--[event.message.quick_reply] → handle quick reply payload (Phase 2+)
      |
      +--[event.message.text] → sendFallback(senderId)  ← fallback catch-all
      |
      v
[sendMessage(recipientId, text, quickReplies?)]
      |
      | POST https://graph.facebook.com/v21.0/me/messages
      | check response.data.error  ← SEC-02
      | catch: log err.message + err.response?.data only  ← SEC-03
      v
Facebook Graph API (delivers message to user)

Setup (one-time, at startup or via script):
POST /me/messenger_profile → sets get_started + persistent_menu
```

### Recommended File Structure (No New Files Required)

All Phase 1 changes are in a single file:

```
messenger-bot/
├── src/
│   └── index.ts        # All changes: SEC-01/02/03 fixes + CORE-01/02/03/04 handlers
├── .env.example        # Add FACEBOOK_APP_SECRET entry
└── (no new files)
```

The persistent menu setup call can live in `index.ts` as an IIFE or startup function that runs once when the bot starts. This keeps the single-file structure intact for Phase 1.

### Pattern 1: HMAC Webhook Verification (SEC-01)

**What:** Replace `express.json()` global middleware with `express.raw({ type: '*/*' })` on the webhook route, then verify the `X-Hub-Signature-256` header before JSON-parsing the body.

**When to use:** On every POST to `/webhook`. Must run before any body processing.

**Critical detail:** `express.raw()` delivers `req.body` as a `Buffer`. The HMAC is computed over the raw Buffer bytes — NOT over `JSON.stringify(parsedBody)`. The comparison uses `crypto.timingSafeEqual` to prevent timing attacks.

**Why `express.raw()` and not the `verify` callback on `express.json()`:**
The CONTEXT.md (D-06) explicitly mandates `express.raw()` before `express.json()`. Both approaches work, but mounting `express.raw()` first on the webhook route and then manually parsing the JSON is cleaner and avoids global middleware conflicts.

```typescript
// Source: [VERIFIED: Node.js crypto docs + Express docs + community HMAC patterns]
import crypto from "crypto";

const APP_SECRET = process.env.FACEBOOK_APP_SECRET;

function verifySignature(req: Request, res: Response, next: Function): void {
  if (!APP_SECRET) {
    console.warn("FACEBOOK_APP_SECRET not set — skipping webhook signature verification");
    // Still need to parse the body for downstream handlers
    const body = req.body as Buffer;
    (req as any).parsedBody = JSON.parse(body.toString("utf8"));
    next();
    return;
  }

  const signature = req.headers["x-hub-signature-256"] as string | undefined;
  if (!signature) {
    res.sendStatus(403);
    return;
  }

  const rawBody = req.body as Buffer;
  const expected = `sha256=${crypto
    .createHmac("sha256", APP_SECRET)
    .update(rawBody)
    .digest("hex")}`;

  const expectedBuf = Buffer.from(expected, "utf8");
  const signatureBuf = Buffer.from(signature, "utf8");

  if (
    expectedBuf.length !== signatureBuf.length ||
    !crypto.timingSafeEqual(expectedBuf, signatureBuf)
  ) {
    res.sendStatus(403);
    return;
  }

  (req as any).parsedBody = JSON.parse(rawBody.toString("utf8"));
  next();
}

// Mount BEFORE express.json() — use express.raw() on this specific route:
app.post(
  "/webhook",
  express.raw({ type: "*/*" }),
  verifySignature,
  async (req: Request, res: Response) => {
    const body = (req as any).parsedBody;
    // ... rest of handler
  }
);
```

**Note on global `express.json()`:** The current code has `app.use(express.json())` globally. This MUST be removed or scoped away from `/webhook`, otherwise `req.body` will be a parsed object (not a Buffer) when the HMAC middleware runs. The GET `/webhook` route does not need body parsing, so removing global `express.json()` is safe.

### Pattern 2: Graph API Error Detection (SEC-02)

**What:** After every `axios.post` to the Facebook Graph API, check `response.data.error`. Facebook returns HTTP 200 with an error body on send failures (rate limits, policy violations, window expiry).

```typescript
// Source: [VERIFIED: PITFALLS.md, Facebook Platform behavior documentation]
async function sendMessage(
  recipientId: string,
  text: string,
  quickReplies?: QuickReply[]
): Promise<void> {
  const messagePayload: Record<string, unknown> = { text };
  if (quickReplies && quickReplies.length > 0) {
    messagePayload.quick_replies = quickReplies;
  }

  const response = await axios.post(
    `https://graph.facebook.com/v21.0/me/messages`,
    {
      recipient: { id: recipientId },
      message: messagePayload,
    },
    {
      params: { access_token: PAGE_ACCESS_TOKEN },
    }
  );

  // SEC-02: Facebook returns errors inside HTTP 200
  if (response.data?.error) {
    console.error("Graph API error:", response.data.error.message, response.data.error);
  }
}
```

### Pattern 3: Token-Safe Error Logging (SEC-03)

**What:** In catch blocks, log only `err.message` and `err.response?.data`. Never log the full axios error — it includes `config.url` which contains `PAGE_ACCESS_TOKEN` as a query parameter.

```typescript
// Source: [VERIFIED: CONCERNS.md, PITFALLS.md]
} catch (err: unknown) {
  const axiosErr = err as import("axios").AxiosError;
  // SEC-03: Never log the full axios error object (contains PAGE_ACCESS_TOKEN in config.url)
  console.error("Graph API call failed:", axiosErr.message, axiosErr.response?.data);
  // Do NOT: console.error("Error:", err)  ← leaks PAGE_ACCESS_TOKEN
}
```

### Pattern 4: Messenger Profile Setup (CORE-01 + CORE-02)

**What:** One-time `POST /me/messenger_profile` to configure `get_started` button and `persistent_menu`. This should run at bot startup as an async setup function.

**API endpoint:** `POST https://graph.facebook.com/v21.0/me/messenger_profile`

**`get_started` behavior:** When set, a "Get Started" button appears for first-time users on the conversation welcome screen. Clicking it sends a `messaging_postbacks` event to the webhook with the configured payload string (e.g., `"GET_STARTED"`). The greeting text shown above the Get Started button is separate (the `greeting` property).

**`persistent_menu` constraints:**
- Max 3 top-level `call_to_actions` items [MEDIUM: cross-verified via SUMMARY.md + multiple community sources]
- Title ≤30 characters per item [MEDIUM: search results; official docs say 30, not 20 — note discrepancy]
- Type must be `postback`, `web_url`, or `nested`
- `composer_input_disabled: false` keeps the text input visible (recommended — disabling it locks out accessibility users)

```typescript
// Source: [VERIFIED: official Meta developer docs endpoint structure + CONTEXT.md code context]
async function setupMessengerProfile(): Promise<void> {
  try {
    await axios.post(
      `https://graph.facebook.com/v21.0/me/messenger_profile`,
      {
        get_started: { payload: "GET_STARTED" },
        greeting: [
          {
            locale: "default",
            text: "Hi! I'm the Govi support bot. I can help with product questions or connect you with a human.",
          },
        ],
        persistent_menu: [
          {
            locale: "default",
            composer_input_disabled: false,
            call_to_actions: [
              { type: "postback", title: "Product Help", payload: "MENU_PRODUCT_HELP" },
              { type: "postback", title: "Contact Human", payload: "MENU_CONTACT_HUMAN" },
              { type: "postback", title: "Main Menu", payload: "MENU_MAIN" },
            ],
          },
        ],
      },
      { params: { access_token: PAGE_ACCESS_TOKEN } }
    );
    console.log("Messenger profile configured");
  } catch (err: unknown) {
    const axiosErr = err as import("axios").AxiosError;
    console.error("Messenger profile setup failed:", axiosErr.message, axiosErr.response?.data);
  }
}
```

**When to call:** On startup, after the Express server binds. The profile persists on Facebook's side — re-calling on every restart is idempotent and harmless.

### Pattern 5: Get Started Postback Handler (CORE-01)

**What:** Detect the `messaging_postbacks` event type in the webhook loop and handle the `GET_STARTED` payload.

```typescript
// Source: [VERIFIED: codebase inspection of index.ts + CONTEXT.md]
for (const event of entry.messaging ?? []) {
  const senderId: string = event.sender.id;

  if (event.postback) {
    // Postback from button press (including Get Started)
    const payload: string = event.postback.payload;
    if (payload === "GET_STARTED") {
      await sendWelcomeMessage(senderId);
    }
    // Additional postback payloads handled in later phases
    continue;
  }

  if (event.message?.quick_reply) {
    // Quick reply tap — use payload, not message.text
    const qrPayload: string = event.message.quick_reply.payload;
    // Phase 2+ handles navigation payloads
    continue;
  }

  if (event.message?.text) {
    // CORE-04: Free text fallback
    await sendFallbackMessage(senderId);
    continue;
  }
}
```

### Pattern 6: Quick Replies on Messages (CORE-03 + CORE-04)

**What:** Attach `quick_replies` array to outgoing messages. The Messenger Platform renders these as tappable chips below the message bubble.

**Constraints (VERIFIED via official Meta docs):**
- Maximum 13 quick replies per message
- `title`: max 20 characters, required for `content_type: "text"`
- `payload`: max 1000 characters, required for `content_type: "text"`
- `content_type`: `"text"` (navigation), `"user_phone_number"`, or `"user_email"`

```typescript
// Source: [VERIFIED: developers.facebook.com/docs/messenger-platform/send-messages/quick-replies]
interface QuickReply {
  content_type: "text";
  title: string;      // ≤20 characters
  payload: string;    // ≤1000 characters
}

const MAIN_MENU_QUICK_REPLIES: QuickReply[] = [
  { content_type: "text", title: "Product Help", payload: "MENU_PRODUCT_HELP" },
  { content_type: "text", title: "Contact Human", payload: "MENU_CONTACT_HUMAN" },
];

async function sendFallbackMessage(recipientId: string): Promise<void> {
  await sendMessage(
    recipientId,
    "I work best with the buttons below — here's what I can help with:",
    MAIN_MENU_QUICK_REPLIES
  );
}

async function sendWelcomeMessage(recipientId: string): Promise<void> {
  await sendMessage(
    recipientId,
    "Welcome to Govi support! How can I help you today?",
    MAIN_MENU_QUICK_REPLIES
  );
}
```

### Anti-Patterns to Avoid

- **Global `express.json()` when doing HMAC verification:** The raw body bytes are consumed by `express.json()` before the HMAC middleware can read them. Remove the global `app.use(express.json())` call.
- **Logging the full axios error:** `console.error("Error:", err)` dumps the full `AxiosError` which includes `config.url` containing `PAGE_ACCESS_TOKEN`. Always destructure: `axiosErr.message` and `axiosErr.response?.data`.
- **Relying on HTTP status for Graph API errors:** Facebook returns `{ "error": {...} }` inside HTTP 200. Must check `response.data?.error` explicitly.
- **Using `event.message.text` for quick reply taps:** When a user taps a quick reply, `event.message.text` contains the button title, but `event.message.quick_reply.payload` contains the structured payload. Always check for `event.message.quick_reply` first.
- **Hardcoding the Graph API version everywhere:** The existing code uses `v19.0`. Change it to `v21.0` in `sendMessage`. If this is set in multiple places later, extract to a constant (`GRAPH_API_VERSION`).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HMAC constant-time comparison | Custom comparison loop | `crypto.timingSafeEqual` | Timing attacks are real; custom byte-by-byte comparisons are vulnerable |
| Webhook signature parsing | Manual `X-Hub-Signature-256` header parsing | `header.replace('sha256=', '')` + `crypto.createHmac` | Only 2 lines; no library needed, but don't implement timing-unsafe string comparison |
| Quick reply character truncation | Custom string slicer | Validate at definition time with TypeScript type assertions or a helper | Silent truncation in UI is confusing; fail fast at startup or test time |

**Key insight:** All Phase 1 security and feature work uses Node.js built-ins and the existing installed packages. No new dependencies are needed.

---

## Common Pitfalls

### Pitfall 1: Body Already Parsed When HMAC Middleware Runs

**What goes wrong:** `app.use(express.json())` is called globally before the route-level HMAC middleware. By the time the HMAC middleware runs, `req.body` is an object, not a `Buffer`. `crypto.createHmac(...).update(req.body)` hashes the object's `[object Object]` string representation, which never matches the header.

**Why it happens:** Express processes global middleware before route-level middleware. The global `app.use(express.json())` on line 6 of the current `index.ts` runs first.

**How to avoid:** Remove `app.use(express.json())` entirely. Mount `express.raw({ type: '*/*' })` as the FIRST route-level middleware specifically on the `POST /webhook` route. Manually parse with `JSON.parse(rawBody.toString())` AFTER signature verification succeeds.

**Warning signs:** HMAC verification always returns 403, even for valid Facebook requests; unit tests with valid signatures fail.

### Pitfall 2: Token Buffer Length Mismatch in timingSafeEqual

**What goes wrong:** `crypto.timingSafeEqual` throws `ERR_CRYPTO_TIMINGSAFEEQUAL_ARRAY_BUFFER_LENGTH` if the two Buffers are different lengths. A missing or malformed `X-Hub-Signature-256` header (e.g., missing `sha256=` prefix, or a hash of different length) causes the process to throw rather than returning 403.

**Why it happens:** `timingSafeEqual` requires both buffers to be the same length — it cannot safely compare buffers of different lengths without leaking timing information.

**How to avoid:** Guard with `expectedBuf.length !== signatureBuf.length` before calling `timingSafeEqual`, and return 403 immediately if lengths differ.

**Warning signs:** Unhandled exception crash on malformed signature header instead of clean 403.

### Pitfall 3: `APP_SECRET` Present But Wrong — Always Returns 403

**What goes wrong:** Developer sets `FACEBOOK_APP_SECRET` to the wrong value (copy-paste error, wrong App in Facebook Developer Console). Every incoming webhook event returns 403 — the bot stops working entirely with no useful log message.

**Why it happens:** HMAC is sensitive to the exact secret. A wrong App Secret produces a completely different hash.

**How to avoid:** Log a clear message when returning 403: `console.warn("Webhook signature mismatch — check FACEBOOK_APP_SECRET")`. This distinguishes a forged request from a misconfigured secret.

**Warning signs:** All webhook events return 403, even when tested from the Facebook Developer Console webhook test tool.

### Pitfall 4: Get Started Postback Not Firing

**What goes wrong:** The `get_started` property is set via `POST /me/messenger_profile`, but existing users who have already opened a conversation see no Get Started button. The postback only fires for new conversations.

**Why it happens:** Facebook only shows the Get Started button on the conversation welcome screen — it appears once, for users who have never messaged the Page before. Existing conversations don't have a welcome screen.

**How to avoid:** This is expected platform behavior. For testing, use a Facebook account that has never messaged the Page, or delete the conversation from the Messenger app and start fresh. Document this in the test plan.

**Warning signs:** Developer tests with the same account that was used to set up the bot, never sees the Get Started button.

### Pitfall 5: Persistent Menu Setup Call Fails Silently at Startup

**What goes wrong:** The `setupMessengerProfile()` call fails (invalid token, wrong API version, network error) at startup, but the bot continues running. The persistent menu never appears. No obvious error in the console.

**Why it happens:** If the setup function swallows errors or is not awaited properly, failures are invisible.

**How to avoid:** Always log the error in the catch block of the setup function. Include `axiosErr.response?.data` to get Facebook's error body. Consider logging success explicitly (`console.log("Messenger profile configured")`).

**Warning signs:** Bot starts with no error but the hamburger menu does not appear in Messenger.

### Pitfall 6: Quick Reply Tap Not Handled, Falls Through to Fallback

**What goes wrong:** A user taps a quick reply button. The event has BOTH `event.message.text` (the button label) AND `event.message.quick_reply.payload`. If the event dispatcher checks `event.message?.text` before checking for `event.message?.quick_reply`, the quick reply tap is processed as free text and triggers the fallback message instead of navigation.

**Why it happens:** Event dispatch order in the webhook handler — `message.text` check runs before `message.quick_reply` check.

**How to avoid:** Always check `event.message?.quick_reply` BEFORE `event.message?.text`. The dispatch order must be: postback → quick_reply → free text.

**Warning signs:** Tapping a quick reply button shows the fallback message; double messages to users.

---

## Code Examples

### Complete Middleware Order (SEC-01)

```typescript
// Source: [VERIFIED: Node.js crypto built-in + Express 4.x docs + CONTEXT.md D-06]
import "dotenv/config";
import express, { Request, Response, NextFunction } from "express";
import axios, { AxiosError } from "axios";
import crypto from "crypto";

const app = express();
// REMOVED: app.use(express.json())  ← would consume raw body before HMAC check

const VERIFY_TOKEN = process.env.FACEBOOK_VERIFY_TOKEN!;
const PAGE_ACCESS_TOKEN = process.env.FACEBOOK_PAGE_ACCESS_TOKEN!;
const APP_SECRET = process.env.FACEBOOK_APP_SECRET; // optional — no ! assertion
```

### Env Guard Pattern (from CONCERNS.md)

```typescript
// Source: [VERIFIED: CONCERNS.md — non-null assertions on required env vars are fragile]
// Required vars — throw early with a descriptive message
if (!VERIFY_TOKEN) throw new Error("FACEBOOK_VERIFY_TOKEN is required");
if (!PAGE_ACCESS_TOKEN) throw new Error("FACEBOOK_PAGE_ACCESS_TOKEN is required");
// Optional vars — warn if absent
if (!APP_SECRET) {
  console.warn("FACEBOOK_APP_SECRET not set — skipping webhook signature verification");
}
```

### node_modules Git Cleanup (D-09)

```bash
# Source: [VERIFIED: CONCERNS.md + git documentation]
# 1. Add to .gitignore (both root and messenger-bot scopes)
echo "node_modules/" >> .gitignore
# 2. Remove from git tracking without deleting from disk
git rm -r --cached messenger-bot/node_modules
git commit -m "chore: remove node_modules from git tracking"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Graph API v19.0 (existing code) | v21.0 (recommended bump) | v20+ available as of late 2023 | v19.0 still works; v21.0 is stable and less likely to deprecate soon |
| Graph API v21.0 (research SUMMARY.md recommendation) | v21.0 confirmed reasonable; v25.0 is latest | v25.0 released Feb 2026 | v21.0 is safe to ship; v25.0 is newest but overkill for a bump from v19.0 |

**On Graph API version:** The latest stable version is v25.0 (released February 18, 2026). The existing code uses v19.0. The prior SUMMARY.md research recommended v21.0. Given v25.0 is now current, bumping to v21.0 is a safe conservative choice. Bumping to v25.0 is also fine — there are no Messenger-breaking changes in the Messenger Send API between v21 and v25. [CITED: developers.facebook.com/docs/graph-api/changelog/versions/]

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Persistent menu `call_to_actions` is limited to 3 top-level items max | Standard Stack, Code Examples | Could be 5 per level per some sources; planning uses 3 (conservative, matches SUMMARY.md and phase constraints) |
| A2 | Persistent menu item title limit is 30 characters | Code Examples note | One source says 30; SUMMARY.md says 20; quick_reply titles are definitely 20. Use 20 as safe conservative limit for both |
| A3 | Graph API v21.0 is suitable for all Phase 1 calls | Code Examples | v25.0 is latest; v21.0 is not deprecated; safe to use either |
| A4 | Re-calling `POST /me/messenger_profile` on every startup is idempotent | Architecture Patterns | [ASSUMED] If Facebook rate-limits profile setup calls, startup will fail; mitigation: wrap in try/catch, log don't throw |

**Note on A2:** Sources conflict on persistent menu title length (20 vs 30 chars). Quick reply title limit is definitively 20 chars per official Meta docs. For safety, use ≤20 chars for ALL interactive element titles in Phase 1. This is the more restrictive safe default.

---

## Open Questions

1. **Persistent menu title character limit — 20 or 30?**
   - What we know: Quick reply titles are definitively 20 chars (verified from official docs). Search results for persistent menu say 30, but the research prior (SUMMARY.md) used 20.
   - What's unclear: Official Meta docs were inaccessible during this research session.
   - Recommendation: Use 20 characters as the safe limit for all Phase 1 button labels. Adjust in Phase 2 if confirmed otherwise.

2. **Should the persistent menu setup call run every startup or only once?**
   - What we know: The call is idempotent — same configuration sent again replaces the current setting silently.
   - What's unclear: Whether there is a rate limit on `POST /me/messenger_profile` calls.
   - Recommendation: Run at startup for simplicity. If rate limits become an issue, move to a standalone setup script.

3. **Graph API version — v21.0 or v25.0?**
   - What we know: Both are valid. v25.0 is the most recent (Feb 2026). v21.0 is what SUMMARY.md recommended.
   - Recommendation: Use v21.0 as planned. Extract to a constant for easy future updates.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | All bot code | Yes | v26.0.0 | — |
| npm | Package management | Yes | v11.12.1 | — |
| `crypto` (Node built-in) | SEC-01 HMAC | Yes | Built-in | — |
| `express` | Web server | Yes | 4.22.2 (installed) | — |
| `axios` | Graph API calls | Yes | 1.16.1 (installed) | — |
| `dotenv` | Env var loading | Yes | 16.6.1 (installed) | — |
| `typescript` | Build | Yes | 5.9.3 (installed) | — |
| Facebook Developer Account | Persistent menu setup, testing | Unknown | — | Local dev skips with D-03 guard |
| Facebook App Secret | SEC-01 verification | Not yet obtained | — | D-03: skip + warn when absent |
| ngrok or tunnel | Real webhook testing | Unknown | — | Test security fixes with unit tests; postback flows require tunnel |

**Missing dependencies with no fallback:** None that block coding. `FACEBOOK_APP_SECRET` is required for real webhook verification but Phase 1 code is gated to skip gracefully when absent (D-03).

**Missing dependencies with fallback:** Facebook App Secret — skip verification and warn (D-03). Tunnel service — test locally with unit tests, integration testing requires a real tunnel.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | None detected — no test runner installed |
| Config file | None — Wave 0 must create |
| Quick run command | `npm test` (to be configured) |
| Full suite command | `npm test` |

**Note:** `nyquist_validation` is enabled. No test framework is currently installed in `messenger-bot/`. Wave 0 must add a test runner. Given the TypeScript environment, **Jest with `ts-jest`** is the standard choice. However, since CLAUDE.md mandates no new dependencies beyond what's needed, and `ts-node` is already installed, a lightweight option is `node:test` (Node 18+ built-in test runner) with no npm install required.

**Recommendation:** Use Node.js built-in `node:test` runner (available in Node 26.0.0 — confirmed installed). Zero new dependencies. Run with `node --test` or add to `package.json` scripts. [VERIFIED: Node 26 ships with `node:test`]

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SEC-01 | Valid HMAC signature → passes through | Unit | `node --test src/tests/hmac.test.ts` | No — Wave 0 |
| SEC-01 | Invalid HMAC signature → 403 | Unit | `node --test src/tests/hmac.test.ts` | No — Wave 0 |
| SEC-01 | Missing APP_SECRET → skip + warn | Unit | `node --test src/tests/hmac.test.ts` | No — Wave 0 |
| SEC-02 | `response.data.error` present → logged | Unit | `node --test src/tests/sendMessage.test.ts` | No — Wave 0 |
| SEC-03 | catch block does not log full error | Unit | `node --test src/tests/sendMessage.test.ts` | No — Wave 0 |
| CORE-01 | GET_STARTED postback → welcome message sent | Unit (mock axios) | `node --test src/tests/handlers.test.ts` | No — Wave 0 |
| CORE-02 | Messenger profile setup call has correct structure | Unit (mock axios) | `node --test src/tests/setup.test.ts` | No — Wave 0 |
| CORE-03 | Quick reply payloads present in sendMessage calls | Unit | `node --test src/tests/handlers.test.ts` | No — Wave 0 |
| CORE-04 | Free text event → fallback message with quick replies | Unit (mock axios) | `node --test src/tests/handlers.test.ts` | No — Wave 0 |
| CORE-04 | Quick reply tap does NOT trigger fallback | Unit | `node --test src/tests/handlers.test.ts` | No — Wave 0 |

**Integration tests (require live Facebook setup):** Persistent menu visible in Messenger, Get Started button fires, 403 on forged POST — these are manual verification steps described in Success Criteria.

### Sampling Rate

- **Per task commit:** `node --test src/tests/` (all unit tests, ~seconds)
- **Per wave merge:** Same — all unit tests
- **Phase gate:** All unit tests green + manual Success Criteria verification before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `messenger-bot/src/tests/hmac.test.ts` — covers SEC-01
- [ ] `messenger-bot/src/tests/sendMessage.test.ts` — covers SEC-02, SEC-03
- [ ] `messenger-bot/src/tests/handlers.test.ts` — covers CORE-01, CORE-03, CORE-04
- [ ] `messenger-bot/src/tests/setup.test.ts` — covers CORE-02
- [ ] Add `"test": "node --test src/tests/**/*.test.ts"` to `messenger-bot/package.json` scripts (requires ts-node or compiled output)
- [ ] Alternatively: `"test": "ts-node --test src/tests/**"` using already-installed `ts-node`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Bot-to-Facebook is token-based (PAGE_ACCESS_TOKEN); no user auth in this phase |
| V3 Session Management | No | Stateless in Phase 1; no session state introduced |
| V4 Access Control | Partial | Webhook access controlled by HMAC verification (SEC-01) |
| V5 Input Validation | Yes | Event structure validated with existence checks before accessing nested fields; no user input processed directly |
| V6 Cryptography | Yes | HMAC-SHA256 via `crypto.createHmac` (Node built-in, not hand-rolled); `crypto.timingSafeEqual` for timing-safe comparison |

### Known Threat Patterns for Messenger Webhook + Express

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Forged webhook POST from non-Facebook actor | Spoofing | HMAC-SHA256 verification (SEC-01) — return 403 on mismatch |
| PAGE_ACCESS_TOKEN exfiltration via logs | Information Disclosure | Log only `err.message` + `err.response?.data` (SEC-03) |
| Silent message send failure | Denial of Service (availability) | Check `response.data.error` after every Graph API call (SEC-02) |
| Timing attack on HMAC comparison | Spoofing | `crypto.timingSafeEqual` constant-time comparison |
| Env var absent → silent undefined behavior | Tampering | Startup guards throwing on missing required vars; warn on optional vars |

---

## Sources

### Primary (HIGH confidence)

- **Codebase direct inspection** — `messenger-bot/src/index.ts` (lines 1-78), `.planning/codebase/CONCERNS.md`, `.planning/codebase/STACK.md`, `.planning/research/PITFALLS.md`, `.planning/research/SUMMARY.md` — [VERIFIED: Read tool]
- **Node.js built-in `crypto`** — `crypto.createHmac`, `crypto.timingSafeEqual` available in Node 26.0.0 — [VERIFIED: `node -e "const c = require('crypto'); console.log(c.getHashes().includes('sha256'))"`]
- **Installed package versions** — axios 1.16.1, express 4.22.2, typescript 5.9.3, dotenv 16.6.1 — [VERIFIED: `node -e "require('./messenger-bot/node_modules/X/package.json').version"`]
- **Quick replies constraints (13 max, 20-char title)** — [CITED: developers.facebook.com/docs/messenger-platform/send-messages/quick-replies via WebFetch]
- **Graph API version history** — v25.0 released Feb 18, 2026; v21.0 stable — [CITED: developers.facebook.com/docs/graph-api/changelog/versions/]

### Secondary (MEDIUM confidence)

- **Persistent menu structure** — locale, call_to_actions, postback/web_url types, composer_input_disabled — [CITED: gist.github.com/enablo-dev/5d4d8bc355863b118544277093c05960 + multiple community sources]
- **HMAC with express.raw() pattern** — middleware order, raw body requirement, timingSafeEqual usage — [CITED: multiple community webhook verification guides; consistent across hookdeck.com, dev.to, medium.com]
- **Persistent menu max 3 items** — [MEDIUM: SUMMARY.md (cross-referenced with platform research) + community sources; official docs inaccessible during session]

### Tertiary (LOW confidence)

- **Persistent menu title character limit** — 20 vs 30 conflict — [LOW: search results say 30; SUMMARY.md says 20; using 20 as conservative safe limit until official docs confirm]

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all packages verified via installed node_modules; Node.js crypto built-in confirmed
- Security patterns (SEC-01/02/03): HIGH — HMAC pattern is well-documented across multiple authoritative sources; existing code bugs confirmed via direct inspection
- Messenger Profile API (CORE-01/02): MEDIUM — endpoint structure confirmed from multiple sources; exact field limits (title chars, max items) have one conflicting data point
- Quick reply constraints (CORE-03/04): HIGH — confirmed from official Meta documentation via WebFetch
- Graph API version: HIGH — version history confirmed from official Meta versioning page

**Research date:** 2026-05-14
**Valid until:** 2026-06-14 (Facebook platform constraints are stable; API version shelf life is ~2 years)
