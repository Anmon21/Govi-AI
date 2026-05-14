# Phase 1: Security + Bot Foundation - Pattern Map

**Mapped:** 2026-05-14
**Files analyzed:** 3 (1 modified + 2 config files)
**Analogs found:** 3 / 3

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `messenger-bot/src/index.ts` | middleware + controller | request-response + event-driven | itself (existing file, being modified) | exact |
| `messenger-bot/.env.example` | config | — | `messenger-bot/.env.example` (existing, add one line) | exact |
| `.gitignore` | config | — | `.gitignore` (existing, add two lines) | exact |

**Note:** All Phase 1 work is concentrated in the single existing file `messenger-bot/src/index.ts`. No new source files are created. The pattern map below is organized by logical change group (security fixes, then core features) rather than by file, since they all land in the same file.

---

## Pattern Assignments

### Change Group A: SEC-01 — HMAC Webhook Signature Verification

**Analog:** `messenger-bot/src/index.ts` (the file itself — this change restructures its middleware setup)

**Existing import pattern** (`messenger-bot/src/index.ts` lines 1-3):
```typescript
import "dotenv/config";
import express, { Request, Response } from "express";
import axios from "axios";
```

**New import additions** — add `crypto` and `NextFunction` following the existing import block style:
```typescript
import "dotenv/config";
import express, { Request, Response, NextFunction } from "express";
import axios from "axios";
import crypto from "crypto";
```

**Existing module-level constants pattern** (`messenger-bot/src/index.ts` lines 8-10):
```typescript
const VERIFY_TOKEN = process.env.FACEBOOK_VERIFY_TOKEN!;
const PAGE_ACCESS_TOKEN = process.env.FACEBOOK_PAGE_ACCESS_TOKEN!;
const GOVI_AI_URL = process.env.GOVI_AI_URL ?? "http://localhost:8000";
```

**New constant** — add `APP_SECRET` WITHOUT the `!` assertion (it is optional per D-03):
```typescript
const APP_SECRET = process.env.FACEBOOK_APP_SECRET; // optional — skip verification if absent
```

**Existing global middleware** (`messenger-bot/src/index.ts` line 6):
```typescript
app.use(express.json());
```
This line MUST be removed. It consumes the raw body before HMAC verification can read it.

**HMAC middleware pattern** — new `verifySignature` function to insert after constants, before route definitions:
```typescript
function verifySignature(req: Request, res: Response, next: NextFunction): void {
  if (!APP_SECRET) {
    console.warn("FACEBOOK_APP_SECRET not set — skipping webhook signature verification");
    (req as any).parsedBody = JSON.parse((req.body as Buffer).toString("utf8"));
    next();
    return;
  }

  const signature = req.headers["x-hub-signature-256"] as string | undefined;
  if (!signature) {
    console.warn("Webhook signature mismatch — check FACEBOOK_APP_SECRET");
    res.sendStatus(403);
    return;
  }

  const rawBody = req.body as Buffer;
  const expected = `sha256=${crypto.createHmac("sha256", APP_SECRET).update(rawBody).digest("hex")}`;
  const expectedBuf = Buffer.from(expected, "utf8");
  const signatureBuf = Buffer.from(signature, "utf8");

  if (
    expectedBuf.length !== signatureBuf.length ||
    !crypto.timingSafeEqual(expectedBuf, signatureBuf)
  ) {
    console.warn("Webhook signature mismatch — check FACEBOOK_APP_SECRET");
    res.sendStatus(403);
    return;
  }

  (req as any).parsedBody = JSON.parse(rawBody.toString("utf8"));
  next();
}
```

**Route mounting pattern** — replace `app.post("/webhook", async (req, res) => {` with route-level middleware chain:
```typescript
app.post(
  "/webhook",
  express.raw({ type: "*/*" }),
  verifySignature,
  async (req: Request, res: Response) => {
    const body = (req as any).parsedBody;
    // ... rest of handler unchanged except body reference
  }
);
```

---

### Change Group B: SEC-02 — Graph API Error Detection

**Analog:** `messenger-bot/src/index.ts` lines 61-72 (existing `sendMessage` function)

**Existing `sendMessage` pattern** (`messenger-bot/src/index.ts` lines 61-72):
```typescript
async function sendMessage(recipientId: string, text: string): Promise<void> {
  await axios.post(
    `https://graph.facebook.com/v19.0/me/messages`,
    {
      recipient: { id: recipientId },
      message: { text },
    },
    {
      params: { access_token: PAGE_ACCESS_TOKEN },
    }
  );
}
```

**Modified `sendMessage` pattern** — adds `QuickReply` type, `quickReplies` parameter, SEC-02 error check, SEC-03 safe logging, and v21.0 bump:
```typescript
interface QuickReply {
  content_type: "text";
  title: string;   // ≤20 characters
  payload: string; // ≤1000 characters
}

async function sendMessage(
  recipientId: string,
  text: string,
  quickReplies?: QuickReply[]
): Promise<void> {
  const messagePayload: Record<string, unknown> = { text };
  if (quickReplies && quickReplies.length > 0) {
    messagePayload.quick_replies = quickReplies;
  }

  try {
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
  } catch (err: unknown) {
    const axiosErr = err as import("axios").AxiosError;
    // SEC-03: Never log the full axios error object (contains PAGE_ACCESS_TOKEN in config.url)
    console.error("sendMessage failed:", axiosErr.message, axiosErr.response?.data);
  }
}
```

---

### Change Group C: SEC-03 — Token-Safe Error Logging in Existing Catch Block

**Analog:** `messenger-bot/src/index.ts` lines 53-56 (existing catch block in the POST handler)

**Existing unsafe pattern** (`messenger-bot/src/index.ts` lines 53-56):
```typescript
} catch (err) {
  console.error("Error calling Govi AI:", err);  // leaks token if err is AxiosError
  await sendMessage(senderId, "Sorry, something went wrong. Please try again.");
}
```

**Replacement safe pattern** — log only message and response data, matching the style in Change Group B:
```typescript
} catch (err: unknown) {
  const axiosErr = err as import("axios").AxiosError;
  // SEC-03: Never log the full axios error object
  console.error("Error calling Govi AI:", axiosErr.message, axiosErr.response?.data);
  await sendMessage(senderId, "Sorry, something went wrong. Please try again.");
}
```

---

### Change Group D: CORE-01 + CORE-02 — Messenger Profile Setup

**Analog:** `messenger-bot/src/index.ts` lines 61-72 (existing axios POST pattern for Graph API)

**New `setupMessengerProfile` function** — follows same axios.post structure as `sendMessage`, same catch style:
```typescript
async function setupMessengerProfile(): Promise<void> {
  try {
    await axios.post(
      `https://graph.facebook.com/v21.0/me/messenger_profile`,
      {
        get_started: { payload: "GET_STARTED" },
        greeting: [
          {
            locale: "default",
            text: "Hi! I'm the Govi support bot. Ask me about products or talk to a human.",
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

**Call site** — inside the `app.listen` callback, following the existing `console.log` call:
```typescript
const port = process.env.PORT ?? 3000;
app.listen(port, () => {
  console.log(`Messenger bot listening on port ${port}`);
  setupMessengerProfile();
});
```

---

### Change Group E: CORE-01 + CORE-03 + CORE-04 — Event Dispatcher + Handlers

**Analog:** `messenger-bot/src/index.ts` lines 38-58 (existing event loop inside POST handler)

**Existing event loop pattern** (`messenger-bot/src/index.ts` lines 38-58):
```typescript
for (const entry of body.entry ?? []) {
  for (const event of entry.messaging ?? []) {
    if (!event.message?.text) continue;

    const senderId: string = event.sender.id;
    const userText: string = event.message.text;

    console.log(`[${senderId}] ${userText}`);

    try {
      const { data } = await axios.post(`${GOVI_AI_URL}/ai/chat`, {
        message: userText,
      });
      await sendMessage(senderId, data.reply);
    } catch (err) {
      console.error("Error calling Govi AI:", err);
      await sendMessage(senderId, "Sorry, something went wrong. Please try again.");
    }
  }
}
```

**Quick reply constants** — add before the route definitions, after constants block:
```typescript
const MAIN_MENU_QUICK_REPLIES: QuickReply[] = [
  { content_type: "text", title: "Product Help", payload: "MENU_PRODUCT_HELP" },
  { content_type: "text", title: "Contact Human", payload: "MENU_CONTACT_HUMAN" },
];
```

**New helper functions** — add after `sendMessage`, before `setupMessengerProfile`:
```typescript
async function sendWelcomeMessage(recipientId: string): Promise<void> {
  await sendMessage(
    recipientId,
    "Welcome to Govi! I can help with product questions or connect you with a human.",
    MAIN_MENU_QUICK_REPLIES
  );
}

async function sendFallbackMessage(recipientId: string): Promise<void> {
  await sendMessage(
    recipientId,
    "I work best with the buttons below — here's what I can help with:",
    MAIN_MENU_QUICK_REPLIES
  );
}
```

**Replacement event loop** — dispatch order is postback → quick_reply → free text (critical: quick_reply BEFORE text per PITFALLS.md):
```typescript
for (const entry of body.entry ?? []) {
  for (const event of entry.messaging ?? []) {
    const senderId: string = event.sender.id;

    if (event.postback) {
      const payload: string = event.postback.payload;
      if (payload === "GET_STARTED") {
        await sendWelcomeMessage(senderId);
      }
      // Additional postback payloads handled in Phase 2+
      continue;
    }

    if (event.message?.quick_reply) {
      // Quick reply tap — use payload, not message.text
      // Phase 2+ handles navigation payloads
      continue;
    }

    if (event.message?.text) {
      console.log(`[${senderId}] ${event.message.text}`);
      // CORE-04: Free text fallback — never a silent dead end
      await sendFallbackMessage(senderId);
      continue;
    }
  }
}
```

---

### Change Group F: .env.example — Add FACEBOOK_APP_SECRET

**Analog:** `messenger-bot/.env.example` lines 1-4 (existing file)

**Existing file** (`messenger-bot/.env.example` lines 1-4):
```
FACEBOOK_VERIFY_TOKEN=your_verify_token_here
FACEBOOK_PAGE_ACCESS_TOKEN=your_page_access_token_here
GOVI_AI_URL=http://localhost:8000
PORT=3000
```

**Add one line** after `FACEBOOK_PAGE_ACCESS_TOKEN`, following the same `KEY=description_here` style:
```
FACEBOOK_APP_SECRET=your_app_secret_here
```

**Where to find it:** Facebook Developer Dashboard → Your App → App Settings → Basic → App Secret.

---

### Change Group G: .gitignore — node_modules Cleanup (D-09)

**Analog:** `.gitignore` lines 1-13 (existing file)

**Existing file** (`.gitignore` lines 1-13):
```
.env
__pycache__/
*.py[cod]
*.pyo
.venv/
venv/
.idea/
.vscode/
*.egg-info/
dist/
build/
.DS_Store
```

**Add two lines** at the end, following the same trailing-slash directory style:
```
node_modules/
messenger-bot/node_modules/
```

After updating `.gitignore`, run `git rm -r --cached messenger-bot/node_modules` to stop tracking the already-committed directory. No source files are touched by this operation.

---

## Shared Patterns

### Error Handling — Safe Axios Error Logging
**Source:** `messenger-bot/src/index.ts` lines 53-56 (existing pattern, being fixed)
**Apply to:** Every `catch` block in `index.ts` that catches an axios error (Govi AI call, Graph API call, profile setup call)

Pattern — always type the caught error and destructure only safe fields:
```typescript
} catch (err: unknown) {
  const axiosErr = err as import("axios").AxiosError;
  console.error("<context>:", axiosErr.message, axiosErr.response?.data);
}
```

Never use `console.error("...", err)` directly — the full `AxiosError` includes `config.url` which contains `PAGE_ACCESS_TOKEN`.

### Graph API Call Pattern
**Source:** `messenger-bot/src/index.ts` lines 61-72 (existing `sendMessage`)
**Apply to:** `sendMessage` (modified), `setupMessengerProfile` (new)

All Graph API calls use the same structure:
```typescript
await axios.post(
  `https://graph.facebook.com/v21.0/me/<endpoint>`,
  { /* body */ },
  { params: { access_token: PAGE_ACCESS_TOKEN } }
);
```

Access token always goes in `params` (appended as query string), not in the Authorization header — this is how the Facebook Graph API requires it.

### Env Var Constants Pattern
**Source:** `messenger-bot/src/index.ts` lines 8-10 (existing)
**Apply to:** New `APP_SECRET` constant

Required vars use non-null assertion (`!`). Optional vars use `??` fallback or no assertion. `APP_SECRET` is optional — do NOT use `!`.

```typescript
// Required — must be present
const VERIFY_TOKEN = process.env.FACEBOOK_VERIFY_TOKEN!;
const PAGE_ACCESS_TOKEN = process.env.FACEBOOK_PAGE_ACCESS_TOKEN!;
// Optional — absent is valid; behavior degrades gracefully
const APP_SECRET = process.env.FACEBOOK_APP_SECRET;
```

### Facebook Webhook Acknowledge Pattern
**Source:** `messenger-bot/src/index.ts` line 36 (existing)
**Apply to:** Must be preserved in modified POST handler

`res.sendStatus(200)` MUST fire before the async event processing loop — Facebook requires acknowledgement within 20 seconds. Do not move or defer it.

```typescript
// Acknowledge receipt immediately — Facebook requires this within 20s
res.sendStatus(200);

for (const entry of body.entry ?? []) { ... }
```

---

## No Analog Found

No files in this phase are without an analog. All patterns are derived from `messenger-bot/src/index.ts` (the only bot file). The HMAC verification pattern uses Node.js built-in `crypto` — no codebase analog exists, but the RESEARCH.md code examples provide the verified implementation.

---

## Metadata

**Analog search scope:** `messenger-bot/src/`, `app/`, root config files
**Files scanned:** 5 (`messenger-bot/src/index.ts`, `messenger-bot/.env.example`, `messenger-bot/package.json`, `.gitignore`, `app/routers/ai.py`)
**Pattern extraction date:** 2026-05-14
