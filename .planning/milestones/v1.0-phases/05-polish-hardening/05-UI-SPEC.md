---
phase: 5
slug: polish-hardening
status: draft
shadcn_initialized: false
preset: none
created: 2026-05-15
---

# Phase 5 — UI Design Contract: Polish + Hardening

> This is a Facebook Messenger bot, NOT a web app. There is no HTML, CSS, or React.
> "UI" in this phase means: (1) Messenger interaction design — typing indicators, message timing, and
> API call ordering; (2) Developer experience — environment variable documentation and fresh-clone setup.
>
> Sections from the standard template that are not applicable (Spacing, Typography, Color, Registry)
> are marked NOT APPLICABLE with a rationale.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none — Messenger bot, not a web app |
| Preset | not applicable |
| Component library | not applicable |
| Icon library | not applicable |
| Font | not applicable — Messenger controls all rendering |

Source: `important_context` block; confirmed by absence of `components.json`, `tailwind.config.*`, or
any web framework in `messenger-bot/`.

---

## Spacing Scale

NOT APPLICABLE. The bot sends text strings and quick reply payloads to the Facebook Graph API.
Messenger controls all visual spacing. No spacing tokens are authored by this codebase.

---

## Typography

NOT APPLICABLE. Messenger controls all font rendering. The bot authors message text only.

---

## Color

NOT APPLICABLE. Messenger controls all color. The bot does not render any UI surface.

---

## Interaction Contract: Typing Indicator

This is the primary design contract for Phase 5.

### Facebook Graph API Endpoint

```
POST https://graph.facebook.com/v21.0/me/messages
Authorization: access_token query param (same pattern as sendMessage)
Body:
  {
    "recipient": { "id": "<senderId>" },
    "sender_action": "typing_on"   // or "typing_off"
  }
```

### Scope — Which handlers receive typing indicators

| Handler | Calls FastAPI? | Typing indicator? | Rationale |
|---------|---------------|-------------------|-----------|
| `sendAnswer` | Yes — `GET /content/{id}` | YES | POLISH-01 target: "while fetching answers" |
| `sendCategoryMenu` | Yes — `GET /content?type=category` | NO | Navigation menu build, not answer delivery; indicator not required by POLISH-01 |
| `sendQuestionMenu` | Yes — `GET /content?type=question&category=` | NO | Navigation menu build, not answer delivery; indicator not required by POLISH-01 |
| `sendWelcomeMessage` | No | NO | No async I/O before reply |
| `sendFallbackMessage` | No | NO | No async I/O before reply |
| `handleEscalation` | No (Graph API only) | NO | Escalation uses passThreadControl, not content API; already has its own ordering constraint (customer confirm before passThreadControl — Pitfall 1) |

Decision source: REQUIREMENTS.md POLISH-01 says "while fetching answers from the FastAPI content API".
`sendAnswer` is the only handler whose sole purpose is fetching and delivering an answer.
Extending to `sendCategoryMenu` and `sendQuestionMenu` is out of scope for POLISH-01 and should not
be added in this phase (CLAUDE.md: no features beyond what was asked).

### Call Ordering within `sendAnswer`

```
1. POST /me/messages  { sender_action: "typing_on" }   ← new
2. GET  /content/{id}                                  ← existing axios call
3. POST /me/messages  { text: body, quick_replies: … } ← existing sendMessage call
4. POST /me/messages  { sender_action: "typing_off" }  ← new
```

`typing_off` MUST be sent after `sendMessage` resolves — not after the axios fetch completes.
Rationale: If `typing_off` is sent before `sendMessage`, the indicator may reappear briefly while
the message is in-flight, causing a visible flicker.

### Error Case Ordering

If the axios fetch fails (network error, non-2xx, empty body), the sequence is:

```
1. POST /me/messages  { sender_action: "typing_on" }   ← already sent
2. GET  /content/{id}                                  ← throws or returns bad body
3. sendApologyWithMenu(recipientId)                    ← existing error path
4. POST /me/messages  { sender_action: "typing_off" }  ← new, MUST still execute
```

`typing_off` MUST be sent even when the fetch fails. The indicator must be dismissed regardless
of outcome. Use a `finally` block to guarantee this.

Pattern (TypeScript):
```typescript
await sendTypingIndicator(recipientId, "typing_on");
try {
  // existing fetch + sendMessage logic
} finally {
  await sendTypingIndicator(recipientId, "typing_off");
}
```

### Minimum Display Duration

No artificial minimum delay. Do not add `setTimeout` or sleep between `typing_on` and the fetch.
The natural latency of the HTTP round-trip to FastAPI is sufficient. Adding a forced delay would
make the bot feel slower, not more polished (CLAUDE.md: no features beyond what was asked).

### New Helper: `sendTypingIndicator`

A single exported helper encapsulates the Graph API call. It must:
- Accept `recipientId: string` and `action: "typing_on" | "typing_off"`
- POST to `/me/messages` with `sender_action`
- Apply the SEC-03 error-narrowing pattern (axios.isAxiosError check, no full error object logged)
- Return `Promise<void>`
- Be exported so it can be independently unit-tested

Signature:
```typescript
export async function sendTypingIndicator(
  recipientId: string,
  action: "typing_on" | "typing_off"
): Promise<void>
```

### SEC-03 Compliance

The typing indicator POST uses `PAGE_ACCESS_TOKEN` in the query param (same as `sendMessage`).
The error handler MUST follow the existing SEC-03 pattern — log `err.message` and
`err.response?.data` only, never the full axios error object.

---

## Developer Experience Contract: Environment Variables

### What to Document

Every env var that the bot reads at runtime must appear in `messenger-bot/.env.example` with:
1. A comment line explaining what it is and where to get the value
2. A placeholder value that is clearly a placeholder (not a real token)
3. Default value noted in the comment if one exists

### Current State

`messenger-bot/.env.example` already documents all six vars in use. Phase 5 adds no new env vars.
The Phase 5 task is to verify the existing docs are complete, accurate, and match the current
codebase — then confirm the bot starts cleanly from a fresh clone.

### Complete `.env.example` Contract

This is the target state after Phase 5. Each entry is the authoritative documented form:

```dotenv
# FACEBOOK_VERIFY_TOKEN — arbitrary string you choose; must match what you enter in the
# Facebook Developer Dashboard when registering the webhook
FACEBOOK_VERIFY_TOKEN=your_verify_token_here

# FACEBOOK_PAGE_ACCESS_TOKEN — Facebook Developer Dashboard → your App → Messenger →
# Settings → Generate Token (select your Page)
FACEBOOK_PAGE_ACCESS_TOKEN=your_page_access_token_here

# FACEBOOK_APP_SECRET — Facebook Developer Dashboard → your App → Settings → Basic → App Secret
# Required for HMAC webhook signature verification (SEC-01). If unset, the bot warns and skips
# signature verification — acceptable for local dev, must be set in production.
FACEBOOK_APP_SECRET=your_app_secret_here

# ADMIN_PSID — Page-Scoped ID of the admin's Messenger account.
# How to get it: have the admin send any message to the Page, then read the [senderId] printed
# in the bot console log. If unset, escalation degrades gracefully (customer gets a fallback
# message, no crash).
ADMIN_PSID=your_admin_psid_here

# PAGE_INBOX_APP_ID — hardcoded to Facebook's canonical Page Inbox app ID (263902037430900).
# This value does not change — it is not an env var. Documented here for reference only.
# PAGE_INBOX_APP_ID=263902037430900

# GOVI_AI_URL — base URL of the FastAPI backend. Default: http://localhost:8000
GOVI_AI_URL=http://localhost:8000

# PORT — port the Express webhook server listens on. Default: 3000
PORT=3000
```

### Fresh-Clone Verification Checklist

The following sequence must succeed with only `.env` configuration (no code changes):

1. `git clone <repo>` + `cd messenger-bot` + `cp .env.example .env` (fill real values)
2. `npm install`
3. `npm run dev` — server starts, logs `Messenger bot listening on port 3000`
4. `npm test` — all tests pass (no failures, no skips)
5. Webhook registration in Facebook Developer Dashboard succeeds (GET /webhook returns challenge)

This checklist is the acceptance gate for the POLISH-01 success criterion 2: "bot starts cleanly
from a fresh clone with only .env configuration."

---

## Copywriting Contract

The typing indicator introduces no new user-visible copy. No new Messenger messages are sent.
`typing_on` and `typing_off` are silent Graph API actions — customers see the animated dots,
not text.

The `.env.example` comment strings are the only new "copy" in this phase. They are defined in
the Developer Experience Contract section above.

| Element | Copy |
|---------|------|
| Typing indicator (user-visible) | None — animated dots rendered by Messenger, no text authored |
| Error: typing_off skipped | NOT VISIBLE — error logged to console only, no user-facing message |
| .env comment: FACEBOOK_VERIFY_TOKEN | "arbitrary string you choose; must match what you enter in the Facebook Developer Dashboard when registering the webhook" |
| .env comment: FACEBOOK_PAGE_ACCESS_TOKEN | "Facebook Developer Dashboard → your App → Messenger → Settings → Generate Token (select your Page)" |
| .env comment: FACEBOOK_APP_SECRET | "Required for HMAC webhook signature verification (SEC-01). If unset, the bot warns and skips signature verification — acceptable for local dev, must be set in production." |
| .env comment: ADMIN_PSID | "have the admin send any message to the Page, then read the [senderId] printed in the bot console log. If unset, escalation degrades gracefully (customer gets a fallback message, no crash)." |

---

## Registry Safety

NOT APPLICABLE. This phase adds no npm dependencies and uses no third-party component registries.
The typing indicator is implemented with the existing `axios` client (already in `package.json`).

---

## Implementation Constraints

These constraints must be observed by the executor and planner:

1. `sendTypingIndicator` is the ONLY new function. Do not add any other abstractions.
2. Only `sendAnswer` is modified to call `sendTypingIndicator`. `sendCategoryMenu` and
   `sendQuestionMenu` are NOT touched.
3. The `finally` block pattern is mandatory — `typing_off` must execute on both success and
   error paths.
4. No `setTimeout` / artificial delays anywhere in this phase.
5. `sendTypingIndicator` must be exported for testability — consistent with the established
   pattern (all handler functions are exported in `index.ts`).
6. SEC-03 error-narrowing pattern (axios.isAxiosError guard) applies to `sendTypingIndicator`
   errors — same as `sendMessage` and `passThreadControl`.
7. The `.env.example` update is a documentation-only change — it must not alter any runtime
   behavior.

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS (not applicable — Messenger bot)
- [ ] Dimension 3 Color: PASS (not applicable — Messenger bot)
- [ ] Dimension 4 Typography: PASS (not applicable — Messenger bot)
- [ ] Dimension 5 Spacing: PASS (not applicable — Messenger bot)
- [ ] Dimension 6 Registry Safety: PASS (no new dependencies)

**Approval:** pending
