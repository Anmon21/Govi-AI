# Phase 4: Human Escalation — Research

**Researched:** 2026-05-15
**Domain:** Facebook Messenger Handover Protocol, in-process state, admin notification
**Confidence:** MEDIUM — API structure and Page Inbox app ID verified via multiple third-party sources; some Facebook official doc pages returned 404 during this session

---

## Summary

Phase 4 implements a single-click escalation path: the customer taps "Contact Human", the bot (1) records context, (2) sends the admin a Messenger notification, (3) transfers the thread to the Page inbox via the Handover Protocol. The existing `MENU_CONTACT_HUMAN` payload in both MAIN_MENU_QUICK_REPLIES and the persistent menu is already wired and dispatched — Phase 4 fills in the no-op handler stub.

The Facebook Handover Protocol requires the bot's Facebook App to be set as **Primary Receiver** and the Page Inbox to be set as **Secondary Receiver** in the Page's Advanced Messaging settings. This is a one-time manual admin setup step that must be documented. The API call itself is a single `POST` to `/me/pass_thread_control` with `recipient.id` and `target_app_id: 263902037430900` (the canonical Page Inbox app ID). [VERIFIED: multiple platform docs]

The "last message" context for ESC-04 has no database. A module-level `Map<senderId, string>` populated on every free-text event is the correct v1 approach. This is in-process only — it resets on server restart, which is acceptable because the admin notification is sent immediately during the same event loop. The Map entry is only needed for the duration of the escalation request.

**Primary recommendation:** Implement `handleEscalation(senderId, lastMessage)` as a standalone exported async function in `index.ts` that: updates the last-message Map, calls `sendMessage` to admin, calls `passThreadControl`, and sends confirmation to the customer. Guard on `ADMIN_PSID` with soft-fail matching the codebase's existing pattern.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Detect escalation trigger | Messenger Bot (Node.js) | — | Quick reply and postback payloads arrive at the webhook handler |
| Last-message tracking | Messenger Bot (Node.js) | — | Must intercept all inbound text events; no backend involvement needed |
| Admin notification (Messenger message) | Messenger Bot (Node.js) | — | Sends to admin PSID via Graph API — same sendMessage helper already in use |
| Thread handover (Handover Protocol) | Messenger Bot (Node.js) | — | pass_thread_control is a Graph API call from the bot's PAGE_ACCESS_TOKEN |
| Customer confirmation message | Messenger Bot (Node.js) | — | Sent before or alongside pass_thread_control so bot delivers it while it still owns the thread |
| ADMIN_PSID configuration | Environment / .env | — | New env var, same pattern as PAGE_ACCESS_TOKEN |

All ESC-01 through ESC-04 work lives entirely in the Node.js bot (`messenger-bot/src/index.ts`). The FastAPI backend has no role in this phase.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ESC-01 | "Contact Human" option available from main menu AND from any Q&A screen — tapping always triggers escalation | Payload `MENU_CONTACT_HUMAN` already dispatched in handleWebhookEvent stub (line 282–285 index.ts); postback path (persistent menu) handled at line 264–267; both need the new `handleEscalation` function wired in |
| ESC-02 | Admin receives Messenger notification via their Page-Scoped PSID (ADMIN_PSID env var) | Use existing `sendMessage(ADMIN_PSID, text)` helper — no new Graph API call type needed |
| ESC-03 | Thread control transfers to Page inbox via Facebook Handover Protocol | POST `/me/pass_thread_control` with `target_app_id: 263902037430900`; requires Primary Receiver setup |
| ESC-04 | Admin notification includes customer's last message | Module-level `Map<string, string>` populated on every text event; last entry read at escalation time |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| axios | ^1.16.1 (already installed) | POST to `/me/pass_thread_control` Graph API endpoint | Already used for all Graph API calls in the codebase |
| node:test + assert | built-in (Node.js 26) | Test framework | Already used for all existing tests |

No new npm packages are needed for this phase. [VERIFIED: codebase grep of package.json]

### New Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `ADMIN_PSID` | Optional (soft-fail if absent) | Page-Scoped ID of the admin's personal Messenger account |

**Installation:** No new packages. `ADMIN_PSID` added to `messenger-bot/.env.example`.

---

## Architecture Patterns

### System Architecture Diagram

```
Customer taps "Contact Human"
        │
        ▼
handleWebhookEvent (index.ts)
  quick_reply payload == "MENU_CONTACT_HUMAN"
  OR postback payload == "MENU_CONTACT_HUMAN"
        │
        ▼
handleEscalation(senderId, lastMessage)
  ├─ Read lastMessageCache.get(senderId)  (may be undefined)
  ├─ sendMessage(ADMIN_PSID, notification)  ─────────────────► Admin's Messenger
  ├─ passThreadControl(senderId)  ───────────────────────────► Graph API /me/pass_thread_control
  └─ sendMessage(senderId, confirmation)  ───────────────────► Customer's Messenger
        │
        ▼ (bot loses thread ownership)
  Page Inbox owns the conversation
  Admin replies manually from Page Inbox
```

### Recommended Project Structure

No new directories. All changes to `messenger-bot/src/index.ts`:

```
messenger-bot/src/
├── index.ts          # Add: lastMessageCache, passThreadControl, handleEscalation
└── tests/
    └── escalation.test.ts  # New: Wave 0 tests for ESC-01 through ESC-04
```

### Pattern 1: pass_thread_control Graph API Call

**What:** POST to Graph API endpoint to transfer thread ownership to Page Inbox.
**When to use:** Immediately after sending the admin notification, before sending the customer confirmation (so the bot still owns the thread for the customer message).

```typescript
// Source: [CITED: docs.druidai.com/fb-handover, doc.woztell.com/fb-pass-thread-control]
// Page Inbox app ID — fixed constant for all Facebook Pages
export const PAGE_INBOX_APP_ID = "263902037430900";

export async function passThreadControl(recipientId: string): Promise<void> {
  try {
    const response = await axios.post(
      `https://graph.facebook.com/${GRAPH_API_VERSION}/me/pass_thread_control`,
      {
        recipient: { id: recipientId },
        target_app_id: PAGE_INBOX_APP_ID,
      },
      { params: { access_token: PAGE_ACCESS_TOKEN } }
    );
    // Graph API can return errors inside HTTP 200 (same pattern as sendMessage)
    if (response.data?.error) {
      console.error("pass_thread_control Graph API error:", response.data.error.message, response.data.error);
    }
  } catch (err: unknown) {
    // SEC-03: never log full axios error (contains PAGE_ACCESS_TOKEN)
    if (axios.isAxiosError(err)) {
      console.error("passThreadControl failed:", err.message, err.response?.data);
    } else {
      console.error("passThreadControl failed (unexpected):", err);
    }
  }
}
```

### Pattern 2: Last-Message Cache (Module-Level Map)

**What:** A module-level `Map<string, string>` that stores the most recent text message per senderId.
**When to use:** Updated on every inbound `event.message.text` event. Read when escalation is triggered.

```typescript
// Source: [ASSUMED] — standard in-process cache pattern; no library needed
// Acceptable for v1 because: (a) escalation is same-request, (b) no persistence requirement
export const lastMessageCache = new Map<string, string>();

// In handleWebhookEvent, before the fallback message call:
if (event.message?.text) {
  lastMessageCache.set(senderId, event.message.text);
  // ... existing fallback logic
}

// Quick reply taps that carry text also set event.message.text — but those are
// menu labels ("Product Help"), not meaningful user context. Guard: only cache
// messages that are NOT quick_reply events (quick replies are already handled above).
```

**Important:** The cache update must only happen for genuine free-text events, not for quick reply taps (which also populate `event.message.text` with the button label). The existing dispatcher checks `event.message?.quick_reply` before `event.message?.text`, so the text branch is only reached for genuine free-text input. The cache update goes inside the `event.message?.text` branch, which is correct.

### Pattern 3: handleEscalation with Soft-Fail

**What:** Orchestrates the three-step escalation sequence with graceful degradation if ADMIN_PSID is absent.
**When to use:** Called from the `MENU_CONTACT_HUMAN` handler for both quick reply and postback paths.

```typescript
// Source: [ASSUMED] — pattern matches existing codebase soft-fail style (e.g., FACEBOOK_APP_SECRET)
const ADMIN_PSID = process.env.ADMIN_PSID;

export async function handleEscalation(senderId: string): Promise<void> {
  const lastMessage = lastMessageCache.get(senderId);

  if (!ADMIN_PSID) {
    console.warn("ADMIN_PSID not configured — escalation degraded");
    await sendMessage(
      senderId,
      "Thanks for reaching out! We'll get back to you as soon as possible."
    );
    return;
  }

  // Notify admin with context
  const contextLine = lastMessage
    ? `\nLast message: "${lastMessage}"`
    : "";
  await sendMessage(
    ADMIN_PSID,
    `A customer has requested human support.${contextLine}\nPlease reply in the Page Inbox.`
  );

  // (1) Send customer confirmation BEFORE passThreadControl — bot must own
  //     the thread at send time or Facebook returns error 551 (Pitfall 1)
  await sendMessage(
    senderId,
    "Connecting you with a human — we'll be with you shortly!"
  );

  // (2) Transfer thread — bot is done sending after this call
  await passThreadControl(senderId);
}
```

**Ordering note:** The Graph API is asynchronous — there is no guarantee that `passThreadControl` completes before `sendMessage` for the customer. In practice, send the customer confirmation message first, then call `passThreadControl`. If the bot sends after the handover is acknowledged by Facebook, the send will be rejected (error code 551). See the Pitfalls section.

### Pattern 4: ESC-01 — Wiring MENU_CONTACT_HUMAN

The stub already exists at line 282 (`handleWebhookEvent`). The postback handler at line 264 also receives `MENU_CONTACT_HUMAN` from the persistent menu but currently only logs. Both need to call `handleEscalation`.

```typescript
// Quick reply path (existing stub, replace the no-op):
if (payload === "MENU_CONTACT_HUMAN") {
  await handleEscalation(senderId);
  return;
}

// Postback path (add after GET_STARTED check):
if (event.postback?.payload === "MENU_CONTACT_HUMAN") {
  await handleEscalation(senderId);
  return;
}
```

For ESC-01's "from any Q&A screen" requirement: `MAIN_MENU_QUICK_REPLIES` already contains the "Contact Human" entry and is attached to every `sendAnswer`, `sendCategoryMenu` (empty case), `sendQuestionMenu` (empty case), and fallback response. No structural changes to those functions are needed — the quick reply payload is already `MENU_CONTACT_HUMAN` and the handler will be wired. [VERIFIED: codebase grep of MAIN_MENU_QUICK_REPLIES usage in index.ts]

### Anti-Patterns to Avoid

- **Sending customer confirmation AFTER passThreadControl:** If the bot attempts to send a message after the Page Inbox owns the thread, Facebook returns error code 551. Always send the customer-facing confirmation message before or synchronously with `passThreadControl`. [CITED: Graph API error code 551 — "This person isn't available right now" returned when bot is not thread owner]
- **Caching quick reply labels as last messages:** Quick reply taps set `event.message.text` to the button label (e.g., "Contact Human"). The `event.message.text` branch in `handleWebhookEvent` is only reached for genuine free-text input — the dispatcher short-circuits on `event.message.quick_reply` first. The cache update in the text branch is safe.
- **Not configuring Primary/Secondary Receiver:** If the app is not configured as Primary Receiver in Page Settings → Advanced Messaging, `pass_thread_control` will fail silently or return an error. This is a required manual setup step.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Thread handover | Custom session-state tracking, polling loop | Facebook Handover Protocol (`pass_thread_control` API) | Facebook handles all thread ownership state; bot just calls one endpoint |
| Admin notification delivery | Custom notification service, email | `sendMessage(ADMIN_PSID, ...)` via existing helper | Admin receives the notification in Messenger — same channel they'll use to reply |
| Persistent last-message storage | SQLite, Redis, file-based cache | Module-level `Map<string, string>` | Escalation is same-request; the context only needs to survive the duration of the event handler |

---

## Runtime State Inventory

This phase adds no stored state beyond the in-process `Map`. No rename, no migration.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None — no database, no persistent state | — |
| Live service config | Facebook Page Advanced Messaging settings (Primary/Secondary Receiver) — manual one-time setup | Admin configures Page Inbox as Secondary Receiver in Page Settings |
| OS-registered state | None | — |
| Secrets/env vars | `ADMIN_PSID` — new optional env var added to `messenger-bot/.env` | Add to .env.example, add to .env, document how to find it |
| Build artifacts | None | — |

---

## Common Pitfalls

### Pitfall 1: Sending Customer Message After Thread Is Handed Over
**What goes wrong:** The bot calls `passThreadControl`, and then tries to `sendMessage` to the customer. Facebook returns HTTP 200 with `error.code: 551` ("This person isn't available right now"). The customer sees nothing.
**Why it happens:** Once the Page Inbox owns the thread, the bot is no longer the thread owner and cannot send messages.
**How to avoid:** Send the customer-facing confirmation message first (before `passThreadControl`), or handle the 551 error in `sendMessage` — which already checks `response.data?.error` (SEC-02). Ordering: (1) send admin notification, (2) send customer confirmation, (3) call passThreadControl.
**Warning signs:** `console.error("sendMessage failed:")` or `console.error("Graph API error:")` immediately after escalation, with code 551.

### Pitfall 2: Primary Receiver Not Configured
**What goes wrong:** `passThreadControl` call returns an error (likely error code 100 — "Invalid parameter" or an authorization error). Thread is never transferred. The bot continues to own the thread.
**Why it happens:** The Handover Protocol requires the bot's app to be configured as Primary Receiver in Page Settings → Advanced Messaging. Without this, Facebook rejects the `pass_thread_control` call.
**How to avoid:** Document the one-time setup step explicitly. The plan must include a `user_setup` section for this.
**Warning signs:** `passThreadControl failed:` log with a 400/403 response, or a Graph API error body.

### Pitfall 3: ADMIN_PSID Is the Facebook User ID, Not the PSID
**What goes wrong:** Admin supplies their Facebook profile ID (visible in profile URLs). `sendMessage` to this ID fails with a Graph API error because the Page Inbox uses Page-Scoped IDs, not Facebook user IDs.
**Why it happens:** PSIDs are per-page identifiers, distinct from Facebook user IDs. They are only obtainable by having the admin send a message to the Page — at which point the webhook receives `event.sender.id` which IS the PSID.
**How to avoid:** Document the PSID discovery procedure: admin must message the Page from their personal Messenger account, then look at the server log for the `console.log("[senderId] ...")` output, which logs the sender ID on every inbound message.
**Warning signs:** `sendMessage failed:` with "not a valid user" or similar error when trying to notify admin.

### Pitfall 4: last message cache contains quick reply label, not real user text
**What goes wrong:** Admin notification reads: `Last message: "Contact Human"` — meaningless context.
**Why it happens:** Quick reply taps set both `event.message.quick_reply` and `event.message.text` (the button label). If the cache update happens without checking for quick_reply first, the label gets stored.
**How to avoid:** The cache update must occur only in the `event.message?.text` branch of `handleWebhookEvent`, which is only reached after the quick_reply check short-circuits. Do not update the cache in the quick_reply branch.
**Warning signs:** Admin consistently sees button labels as "last message" in escalation notifications.

### Pitfall 5: Bot receives messages after handover (standby channel)
**What goes wrong:** After `passThreadControl`, Facebook still delivers webhook events to the bot (in the "standby" channel). If `handleWebhookEvent` processes these, the bot may respond to messages it shouldn't own.
**Why it happens:** When the bot is not the thread owner, Facebook delivers events to subscribed apps via a "standby" webhook. The current event handler does not check for standby events.
**How to avoid:** Add a guard in the webhook POST handler: check for `body.entry[].standby` events and skip them (do not route to `handleWebhookEvent`). [ASSUMED: standby channel behavior — verified that standby events exist conceptually; specific field name needs verification against Facebook docs]
**Warning signs:** Bot sends messages to a customer who is supposed to be in the Page Inbox handover state.

---

## Code Examples

### passThreadControl (complete implementation)

```typescript
// Source: [CITED: Graph API reference page/pass_thread_control; druidai.com handover docs]
export const PAGE_INBOX_APP_ID = "263902037430900";

export async function passThreadControl(recipientId: string): Promise<void> {
  try {
    const response = await axios.post(
      `https://graph.facebook.com/${GRAPH_API_VERSION}/me/pass_thread_control`,
      {
        recipient: { id: recipientId },
        target_app_id: PAGE_INBOX_APP_ID,
      },
      { params: { access_token: PAGE_ACCESS_TOKEN } }
    );
    if (response.data?.error) {
      console.error("pass_thread_control error:", response.data.error.message, response.data.error);
    }
  } catch (err: unknown) {
    if (axios.isAxiosError(err)) {
      console.error("passThreadControl failed:", err.message, err.response?.data);
    } else {
      console.error("passThreadControl failed (unexpected):", err);
    }
  }
}
```

### Admin PSID Discovery (setup documentation)

The admin must complete this one-time setup:
1. Open Messenger on their personal Facebook account
2. Search for the Govi Page and send any message (e.g., "hi")
3. The bot server will log: `[<PSID>] hi` — the number in brackets is the PSID
4. Copy that number into `ADMIN_PSID` in `messenger-bot/.env`

### Standby Event Guard (add to webhook POST handler)

```typescript
// Source: [ASSUMED] — standby channel is a Facebook Handover Protocol concept
// Guard before the message routing loop:
for (const entry of body.entry ?? []) {
  // Skip standby events — these arrive when another app owns the thread
  if (entry.standby) continue;
  for (const event of entry.messaging ?? []) {
    await handleWebhookEvent(event);
  }
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom "live chat" iframe or email handoff | Facebook Handover Protocol (`pass_thread_control`) | 2017 (Messenger Platform v1.4) | Thread seamlessly moves to Page Inbox — no separate tool for admin |
| Primary receiver required for all handovers | Any connected app can initiate if configured as Primary | Present | Setup step in Page Advanced Messaging is mandatory; without it, calls fail |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `lastMessageCache` Map update in the `event.message?.text` branch is safe from quick reply labels because the dispatcher short-circuits on `quick_reply` first | Architecture Patterns — Pattern 2 | If wrong: admin receives button labels as context. Fix: add explicit `!event.message?.quick_reply` guard to the cache update |
| A2 | Sending the customer confirmation message before calling `passThreadControl` guarantees the message is delivered (bot still owns thread at send time) | Pitfall 1 | If wrong (race condition): customer confirmation is rejected. Fix: handle error 551 in sendMessage gracefully — already done by SEC-02 check |
| A3 | Facebook delivers standby events under `body.entry[].standby` (not `body.entry[].messaging`) | Code Examples — standby guard | If wrong: guard fails; bot may respond during handover. Mitigation: the bot still processes events correctly (just redundant), since the thread is owned by Page Inbox and passThreadControl will fail |
| A4 | `target_app_id` accepts string `"263902037430900"` — the Graph API reference shows it as "numeric string" | Standard Stack | If wrong (requires integer): TypeScript `as unknown as number` cast needed. Low risk — the value is below Number.MAX_SAFE_INTEGER |

**If this table is empty:** Not applicable; all four assumptions are explicit above.

---

## Open Questions (RESOLVED)

1. **Does `pass_thread_control` fail if the app is NOT configured as Primary Receiver?**
   - What we know: The API requires Primary Receiver status. The error code would be 100 (invalid parameter) or an authorization error.
   - RESOLVED: Accept risk and proceed. The `passThreadControl` catch block logs `response.data` on all error responses (already specified in Plan 04-02 Task 1). The live Messenger checkpoint (Task 2) is the safety net — if Primary Receiver is not configured, the manual test will reveal it immediately. A startup warning is added if `ADMIN_PSID` is set.

2. **Does the bot need to subscribe to `messaging_handovers` webhook event for ESC-03 to work?**
   - What we know: `messaging_handovers` is needed to receive notification when control is *returned* to the bot. It is NOT required to *call* `pass_thread_control`.
   - RESOLVED: No webhook subscription change is needed for Phase 4. `pass_thread_control` succeeds based on App Dashboard Primary Receiver configuration, not webhook subscriptions. The live Messenger checkpoint (Task 2) verifies actual thread transfer. Document `messaging_handovers` subscription as an optional v2 setup step (for bot reactivation after human handoff).

3. **Can the admin notification include a deep link to the Page Inbox conversation?**
   - RESOLVED: Out of scope for v1. Facebook Messenger does not support deep links to specific conversations in plain text messages. Plain-text notification with last-message context is sufficient for ESC-04.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Test runner, bot runtime | ✓ | v26.0.0 | — |
| npm (axios, already installed) | Graph API calls | ✓ | ^1.16.1 in package.json | — |
| Facebook PAGE_ACCESS_TOKEN | passThreadControl, sendMessage | ✓ (existing) | — | Bot cannot make any Graph API calls without it |
| ADMIN_PSID | Admin notification | Optional | — | Soft-fail: log + send customer "we'll be in touch" |
| Facebook App configured as Primary Receiver | passThreadControl | ✗ (manual setup required) | — | No programmatic fallback; passThreadControl returns error |

**Missing dependencies with no fallback:**
- Facebook App must be set as Primary Receiver in Page Settings → Advanced Messaging. This is a manual one-time admin action. The plan must include a `user_setup` entry for this.

**Missing dependencies with fallback:**
- `ADMIN_PSID` — if absent, escalation degrades gracefully (customer gets confirmation, admin gets no notification, thread NOT transferred).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | node:test (Node.js built-in) + assert/strict |
| Config file | none — runner invoked via package.json test script |
| Quick run command | `cd messenger-bot && npm test` |
| Full suite command | `cd messenger-bot && npm test` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ESC-01 | `MENU_CONTACT_HUMAN` quick reply calls `handleEscalation` | unit | `cd messenger-bot && npm test` | ❌ Wave 0: `src/tests/escalation.test.ts` |
| ESC-01 | `MENU_CONTACT_HUMAN` postback calls `handleEscalation` | unit | `cd messenger-bot && npm test` | ❌ Wave 0: same file |
| ESC-02 | `handleEscalation` sends message to ADMIN_PSID with customer context | unit (mock axios.post) | `cd messenger-bot && npm test` | ❌ Wave 0: same file |
| ESC-03 | `passThreadControl` POSTs to `/me/pass_thread_control` with correct body | unit (mock axios.post) | `cd messenger-bot && npm test` | ❌ Wave 0: same file |
| ESC-04 | Admin notification message body includes last-message text | unit | `cd messenger-bot && npm test` | ❌ Wave 0: same file |
| ESC-04 | `lastMessageCache` updated on free-text event, NOT on quick reply | unit | `cd messenger-bot && npm test` | ❌ Wave 0: same file |
| ESC-02/SC-4 | ADMIN_PSID absent → no crash, customer gets "we'll be in touch" message | unit | `cd messenger-bot && npm test` | ❌ Wave 0: same file |

### Sampling Rate

- **Per task commit:** `cd messenger-bot && npm test`
- **Per wave merge:** `cd messenger-bot && npm test`
- **Phase gate:** Full suite (14 existing + new escalation tests) green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `messenger-bot/src/tests/escalation.test.ts` — covers ESC-01, ESC-02, ESC-03, ESC-04, soft-fail
- [ ] All tests must skip gracefully if `handleEscalation`/`passThreadControl`/`lastMessageCache` not yet exported (matching existing test pattern)

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | stateless — no session |
| V4 Access Control | yes (limited) | ADMIN_PSID controls who receives notifications; no auth on the Messenger send itself |
| V5 Input Validation | yes | `lastMessage` is user-supplied text included in admin notification — no code injection risk via Messenger text, but must not be rendered as HTML |
| V6 Cryptography | no | — |

### Known Threat Patterns for This Phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Admin PSID leakage in logs | Information Disclosure | SEC-03 already prevents full axios error logging; ADMIN_PSID treated like PAGE_ACCESS_TOKEN — never logged |
| Forged escalation requests | Spoofing | SEC-01 HMAC signature verification already protects all webhook events |
| Admin notification spam (user repeatedly taps Contact Human) | Denial of Service | Accept for v1; no rate limiting in scope |

---

## Sources

### Primary (HIGH confidence)

- [CITED: docs.druidai.com/fb-handover] — Page Inbox app ID `263902037430900` confirmed
- [CITED: doc.woztell.com/fb-pass-thread-control] — Page Inbox app ID `263902037430900` confirmed (second independent source)
- [CITED: fbsamples/messenger-platform-samples GitHub] — `page_inbox_app_id = 263902037430900` in actual sample code
- [CITED: developers.facebook.com/docs/graph-api/reference/page/pass_thread_control/] — endpoint `POST /{page_id}/pass_thread_control`, fields `recipient` + `target_app_id` + `metadata`, error codes 100, 190, 551
- [VERIFIED: codebase grep] — `MAIN_MENU_QUICK_REPLIES` already contains `MENU_CONTACT_HUMAN`; persistent menu also sends `MENU_CONTACT_HUMAN` postback; stub exists at line 282 of index.ts

### Secondary (MEDIUM confidence)

- [bottender.js.org/docs/channel-messenger-handover-protocol/] — handover behavior after pass_thread_control (thread moves to Page Inbox Done folder)
- [blog.messengerdevelopers.com/using-handover-protocol] — Primary/Secondary Receiver configuration path in Page Settings → Advanced Messaging
- [Sprinklr Handover Protocol docs] — configuration steps for Advanced Messaging

### Tertiary (LOW confidence)

- Training knowledge on standby channel field name (`entry.standby`) — not independently verified in this session; marked [ASSUMED]

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — no new libraries; all existing
- API endpoint + Page Inbox app ID: MEDIUM-HIGH — confirmed by three independent sources (druidai, woztell, fbsamples); official Facebook doc pages returned 404 during this session
- Architecture: HIGH — follows established codebase patterns exactly
- Pitfalls: MEDIUM — error codes verified via Graph API reference; standby channel behavior is ASSUMED
- Primary Receiver requirement: MEDIUM — confirmed by multiple third-party docs; Facebook official docs were 404

**Research date:** 2026-05-15
**Valid until:** 2026-06-15 (Graph API versioning is stable; Handover Protocol is not a fast-moving area)
