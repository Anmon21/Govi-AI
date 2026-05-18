---
phase: 7
slug: helpfulness-feedback
status: draft
platform: facebook-messenger
design_system: not-applicable
created: 2026-05-18
---

# Phase 7 — UI Design Contract: Helpfulness Feedback

> This is a Facebook Messenger chatbot. There is no web UI. The "UI" is message copy, quick reply buttons, and message sequencing. All visual rendering is done by Messenger; this contract governs only what the bot sends.

---

## Design System

| Property | Value |
|----------|-------|
| Platform | Facebook Messenger |
| Rendering | Messenger client (iOS / Android / Web) |
| Component library | Not applicable |
| Spacing / typography | Not applicable — Messenger controls all rendering |
| Quick reply constraints | Title ≤ 20 chars, payload ≤ 1000 chars, max 13 per message |

---

## Interaction Flow

### Path A: Answer → Yes (satisfied)

```
Bot:  [answer body text]
      Quick replies: [Was it helpful? Yes] [Was it helpful? No]

User taps: "Was it helpful? Yes"

Bot:  "Glad that helped! Let me know if you need anything else."
      Quick replies: [Product Help] [Contact Human]
```

No additional message between thank-you and the main menu — the quick replies on the thank-you message serve as the menu.

### Path B: Answer → No (not satisfied)

```
Bot:  [answer body text]
      Quick replies: [Was it helpful? Yes] [Was it helpful? No]

User taps: "Was it helpful? No"

Bot:  (enters handleEscalation — identical to tapping "Contact Human")
      → sends admin notification
      → sends "Connecting you with a human — we'll be with you shortly!"
      → calls passThreadControl
```

No new message is inserted before escalation. The "No" tap is a direct alias for `MENU_CONTACT_HUMAN`.

### Path C: User ignores feedback and sends free text

```
Bot:  [answer body text]
      Quick replies: [Was it helpful? Yes] [Was it helpful? No]

User types: free text (e.g. "ok thanks" / "what about shipping?")

Bot:  (existing sendFallbackMessage — no change)
      "I work best with the buttons below — here's what I can help with:"
      Quick replies: [Product Help] [Contact Human]
```

Free text after an answer is handled by the existing `event.message.text` branch in `handleWebhookEvent`. No special handling needed.

### Path D: Escalation fails (ADMIN_PSID not configured)

```
User taps: "Was it helpful? No"

handleEscalation degrades as-is:
  Bot:  "Thanks for reaching out! We'll be in touch as soon as possible."
        Quick replies: [Product Help] [Contact Human]
```

No new behavior — `handleEscalation` already handles missing `ADMIN_PSID` gracefully.

---

## Message Copy

Every string that appears in chat is specified exactly here.

### Answer message (UX-01) — sendAnswer change

The answer body is sourced from the vault (`response.data.body`). The feedback quick replies replace the current `MAIN_MENU_QUICK_REPLIES` that `sendAnswer` attaches:

```
[vault answer body text]
Quick replies: [Was it helpful? Yes] [Was it helpful? No]
```

The answer message carries the feedback quick replies. No separate "Was this helpful?" message is sent — the quick replies on the answer message are the prompt.

### Thank-you message (UX-02) — new copy

```
"Glad that helped! Let me know if you need anything else."
Quick replies: [Product Help] [Contact Human]
```

Character counts: "Glad that helped! Let me know if you need anything else." = 55 chars (well within Messenger message limits).

### No path (UX-03) — no new copy

`handleEscalation` copy is unchanged:
- Admin notification: `"A customer ({senderId}) requested human support.\nLast message: \"{lastMessage}\"\nPlease reply from the Page Inbox."`
- User confirmation: `"Connecting you with a human — we'll be with you shortly!"`

---

## Quick Reply Button Specifications

### Feedback quick replies (new)

| Title | Payload | Char count |
|-------|---------|------------|
| `Was it helpful? Yes` | `HELPFUL_YES` | 20 chars (exactly at limit) |
| `Was it helpful? No` | `HELPFUL_NO` | 19 chars |

Both titles are at or under the 20-character Facebook limit.

Note: The titles include "Was it helpful?" inline because Messenger does not display the message text when a user taps a quick reply — the button title must be self-explanatory in isolation for the log/history view.

### Main menu quick replies (unchanged)

| Title | Payload |
|-------|---------|
| `Product Help` | `MENU_PRODUCT_HELP` |
| `Contact Human` | `MENU_CONTACT_HUMAN` |

---

## Payload Naming

### New payload constants — Phase 7

| Constant name | String value | Handler |
|---------------|-------------|---------|
| `PAYLOAD_HELPFUL_YES` | `"HELPFUL_YES"` | Send thank-you message + main menu quick replies |
| `PAYLOAD_HELPFUL_NO` | `"HELPFUL_NO"` | Call `handleEscalation(senderId)` |

### Existing payload constants — unchanged

| Constant | Value |
|----------|-------|
| `MENU_PRODUCT_HELP` | `"MENU_PRODUCT_HELP"` |
| `MENU_CONTACT_HUMAN` | `"MENU_CONTACT_HUMAN"` |
| `MENU_MAIN` | `"MENU_MAIN"` |
| `PAYLOAD_PREFIX_CATEGORY` | `"CATEGORY:"` |
| `PAYLOAD_PREFIX_QUESTION` | `"QUESTION:"` |

---

## Sequencing Rules

1. The answer message (from `sendAnswer`) is the message that carries `HELPFUL_YES` / `HELPFUL_NO` quick replies. No separate message is sent before or after asking for feedback.

2. When the user taps `HELPFUL_YES`: send exactly one message — the thank-you — with `MAIN_MENU_QUICK_REPLIES` attached. Do not send the thank-you and then a second "Here's the menu" message.

3. When the user taps `HELPFUL_NO`: call `handleEscalation` directly. Do not send any intermediate message like "OK, let me get a human." The escalation function already sends the right confirmation.

4. Typing indicators: `sendAnswer` already wraps its API call with `typing_on` / `typing_off`. The thank-you message for `HELPFUL_YES` does not need a typing indicator — it is a simple text send with no async fetch.

5. Quick reply tap events arrive as `event.message.quick_reply` — they must be handled before `event.message.text` (PITFALL 6 in existing code). The new `HELPFUL_YES` / `HELPFUL_NO` cases are added inside the existing quick reply dispatch block.

---

## Implementation Hooks

### Functions that change

**`sendAnswer` (messenger-bot/src/index.ts:294)**

Current behavior: sends answer body with `MAIN_MENU_QUICK_REPLIES`.

New behavior: sends answer body with `FEEDBACK_QUICK_REPLIES` (the new constant defined below) instead of `MAIN_MENU_QUICK_REPLIES`.

```typescript
// Replace line 303:
// was: await sendMessage(recipientId, body, MAIN_MENU_QUICK_REPLIES);
// becomes:
await sendMessage(recipientId, body, FEEDBACK_QUICK_REPLIES);
```

**`handleWebhookEvent` (messenger-bot/src/index.ts:332)**

Two new cases in the quick reply dispatch block, inserted before the "unknown payload" fallback at line 392:

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

### New exports to add

```typescript
export const FEEDBACK_QUICK_REPLIES: QuickReply[] = [
  { content_type: "text", title: "Was it helpful? Yes", payload: "HELPFUL_YES" },
  { content_type: "text", title: "Was it helpful? No",  payload: "HELPFUL_NO" },
];

export const PAYLOAD_HELPFUL_YES = "HELPFUL_YES";
export const PAYLOAD_HELPFUL_NO  = "HELPFUL_NO";
```

Place `FEEDBACK_QUICK_REPLIES` near `MAIN_MENU_QUICK_REPLIES` (around line 216) so the two constants are visually grouped.

### Functions that do NOT change

- `handleEscalation` — called as-is; no modifications
- `sendWelcomeMessage` — no change
- `sendFallbackMessage` — no change
- `sendCategoryMenu` — no change
- `sendQuestionMenu` — no change
- `passThreadControl` — no change
- `sendTypingIndicator` — no change
- `setupMessengerProfile` — no change

---

## Edge Cases

| Scenario | Behavior | Source |
|----------|----------|--------|
| User ignores feedback and types free text | `sendFallbackMessage` fires — existing handler, no change | PITFALL 6 order preserved |
| User ignores feedback and taps persistent menu "Product Help" | Existing postback handler fires — no change | Postback dispatched before quick reply |
| User ignores feedback and taps persistent menu "Contact Human" | Existing postback handler fires — no change | Postback dispatched before quick reply |
| `ADMIN_PSID` not set and user taps "No" | `handleEscalation` sends degraded response — existing behavior | No new code needed |
| Answer body is empty or fetch fails | `sendApologyWithMenu` fires (no feedback prompt shown) — existing behavior | Short-circuit before feedback |
| User taps "No" when thread control already passed | `passThreadControl` may log a Graph API error — acceptable, existing behavior | Not in scope |

---

## Copywriting Contract

| Element | Exact copy |
|---------|-----------|
| Feedback button — positive | `Was it helpful? Yes` |
| Feedback button — negative | `Was it helpful? No` |
| Thank-you message | `Glad that helped! Let me know if you need anything else.` |
| Escalation confirmation (unchanged) | `Connecting you with a human — we'll be with you shortly!` |
| Escalation degraded (unchanged) | `Thanks for reaching out! We'll be in touch as soon as possible.` |
| Admin notification template (unchanged) | `A customer ({senderId}) requested human support.\nLast message: "{lastMessage}"\nPlease reply from the Page Inbox.` |

No empty-state copy is needed for this phase — the feedback prompt only appears after a successful answer delivery.

---

## Test Surface

The executor must cover these cases in the test file:

1. `sendAnswer` attaches `FEEDBACK_QUICK_REPLIES` (not `MAIN_MENU_QUICK_REPLIES`) on successful answer fetch
2. `HELPFUL_YES` quick reply tap calls `sendMessage` with the exact thank-you string and `MAIN_MENU_QUICK_REPLIES`
3. `HELPFUL_NO` quick reply tap calls `handleEscalation`
4. Unknown quick reply payload after feedback is shown still routes to `sendFallbackMessage` (regression)
5. `sendAnswer` on fetch error still calls `sendApologyWithMenu` (regression — no feedback prompt on error)

---

## Registry Safety

Not applicable — this phase adds no UI components, third-party packages, or shadcn blocks. The only change is string constants and control flow in `messenger-bot/src/index.ts`.

---

## Checker Sign-Off

- [ ] Interaction flows: all paths specified with exact message sequences
- [ ] Copy: every user-visible string written out exactly
- [ ] Button titles: all within 20-char Facebook limit
- [ ] Payload naming: new constants named, existing constants confirmed unchanged
- [ ] Sequencing rules: message order and quick reply attachment points declared
- [ ] Edge cases: free text, persistent menu, missing ADMIN_PSID, empty answer all covered
- [ ] Implementation hooks: changed functions identified with line references
- [ ] Test surface: cases listed for executor

**Approval:** pending
