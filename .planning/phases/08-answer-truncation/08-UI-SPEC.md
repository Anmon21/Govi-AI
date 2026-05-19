---
phase: 8
slug: answer-truncation
status: draft
platform: facebook-messenger
design_system: not-applicable
created: 2026-05-19
---

# Phase 8 — UI Design Contract: Answer Truncation

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

## Spacing Scale

Not applicable — Messenger controls all rendering. No CSS, layout tokens, or spacing values are defined by this contract.

---

## Typography

Not applicable — Messenger controls all text rendering. No font sizes, weights, or line heights are defined by this contract.

---

## Color

Not applicable — Messenger controls all visual styling. No color tokens are defined by this contract.

---

## Interaction Flow

### Path A: Short answer (≤ 200 chars) — unchanged behavior

```
User taps a question quick reply

Bot:  [vault answer body — full text, ≤200 chars]
      Quick replies: [Was it helpful? Yes] [Was it helpful? No]
```

No truncation, no "Read more" button. Feedback quick replies are attached directly, identical to Phase 7 short-answer behavior.

### Path B: Long answer (> 200 chars) — new behavior

```
User taps a question quick reply

Bot:  [truncated preview — up to last word boundary before 200 chars, ending "..."]
      Quick replies: [Read more]

User taps: "Read more"

Bot:  [full untruncated vault answer text]
      Quick replies: [Was it helpful? Yes] [Was it helpful? No]
```

The preview message carries only `[Read more]`. Feedback quick replies are NOT on the preview — asking "Was this helpful?" before the user has read the full answer is premature. Feedback is deferred to the full-answer message.

### Path C: "Read more" re-fetch fails

```
User taps: "Read more"

Bot:  "Something went wrong fetching that — back to the main menu:"
      Quick replies: [Product Help] [Contact Human]
```

Same `sendApologyWithMenu` pattern used throughout the codebase. No feedback prompt is shown on error.

### Path D: User ignores "Read more" and sends free text

```
Bot:  [truncated preview]
      Quick replies: [Read more]

User types: free text (e.g. "ok", "what about shipping?")

Bot:  "I work best with the buttons below — here's what I can help with:"
      Quick replies: [Product Help] [Contact Human]
```

Existing `sendFallbackMessage` fires via the `event.message.text` branch. No special handling needed.

### Path E: User ignores "Read more" and taps persistent menu

```
Bot:  [truncated preview]
      Quick replies: [Read more]

User taps persistent menu: "Product Help" or "Contact Human" or "Main Menu"

Bot:  (existing postback handler fires — no change)
```

Postback dispatch in `handleWebhookEvent` fires before quick reply handlers. No new behavior.

### Path F: "Was it helpful? Yes" after full answer (Phase 7 — unchanged)

```
Bot:  [full answer text]
      Quick replies: [Was it helpful? Yes] [Was it helpful? No]

User taps: "Was it helpful? Yes"

Bot:  "Glad that helped! Let me know if you need anything else."
      Quick replies: [Product Help] [Contact Human]
```

### Path G: "Was it helpful? No" after full answer (Phase 7 — unchanged)

```
Bot:  [full answer text]
      Quick replies: [Was it helpful? Yes] [Was it helpful? No]

User taps: "Was it helpful? No"

Bot:  (handleEscalation — identical to tapping "Contact Human")
```

---

## Message Copy

Every string that appears in chat is specified exactly here.

### Preview message (UX-04) — new behavior in sendAnswer

The preview text is the vault answer body truncated at the last word boundary at or before 200 characters, with "..." appended immediately after the last included word. No space before "...".

```
[truncated answer body ending "..."]
Quick replies: [Read more]
```

The "..." is appended to the last complete word — not inserted mid-word. The total preview string (including "...") may be up to 203 characters.

### Full-answer follow-up message (UX-05) — new sendReadMoreAnswer function

```
[full vault answer body — no modification]
Quick replies: [Was it helpful? Yes] [Was it helpful? No]
```

The full answer is the raw `body` string from the vault, delivered without any truncation or modification. `FEEDBACK_QUICK_REPLIES` is attached — identical to how a short answer is sent.

### Error fallback — re-fetch failure (unchanged)

```
"Something went wrong fetching that — back to the main menu:"
Quick replies: [Product Help] [Contact Human]
```

Sourced from `sendApologyWithMenu` — no new copy.

### All other messages — unchanged from Phase 7

| Message | Copy | Quick replies |
|---------|------|---------------|
| Thank-you (HELPFUL_YES) | `Glad that helped! Let me know if you need anything else.` | `[Product Help] [Contact Human]` |
| Escalation confirmation | `Connecting you with a human — we'll be with you shortly!` | none |
| Escalation degraded | `Thanks for reaching out! We'll be in touch as soon as possible.` | `[Product Help] [Contact Human]` |
| Fallback | `I work best with the buttons below — here's what I can help with:` | `[Product Help] [Contact Human]` |

---

## Quick Reply Button Specifications

### "Read more" quick reply (new — Phase 8)

| Title | Payload | Char count |
|-------|---------|------------|
| `Read more` | `READ_MORE:{questionId}` | 9 chars |

"Read more" is 9 characters — well within the 20-character Facebook limit.

The payload embeds the `questionId` so the handler can re-fetch without any in-memory state: `READ_MORE:some-question-id`. Total payload length depends on questionId length but is bounded well within the 1000-char limit.

### Feedback quick replies (Phase 7 — unchanged)

| Title | Payload | Char count |
|-------|---------|------------|
| `Was it helpful? Yes` | `HELPFUL_YES` | 20 chars (exactly at limit) |
| `Was it helpful? No` | `HELPFUL_NO` | 19 chars |

### Main menu quick replies (unchanged)

| Title | Payload |
|-------|---------|
| `Product Help` | `MENU_PRODUCT_HELP` |
| `Contact Human` | `MENU_CONTACT_HUMAN` |

---

## Payload Naming

### New payload constant — Phase 8

| Constant name | String value | Pattern |
|---------------|-------------|---------|
| `PAYLOAD_PREFIX_READ_MORE` | `"READ_MORE:"` | `READ_MORE:{questionId}` |

Follows the established `PAYLOAD_PREFIX_*` naming convention, parallel to `PAYLOAD_PREFIX_QUESTION = "QUESTION:"`.

The full payload sent in the "Read more" quick reply is: `"READ_MORE:" + questionId`.

The handler extracts `questionId` with: `payload.slice(PAYLOAD_PREFIX_READ_MORE.length)`.

### Existing payload constants — unchanged

| Constant | Value |
|----------|-------|
| `PAYLOAD_HELPFUL_YES` | `"HELPFUL_YES"` |
| `PAYLOAD_HELPFUL_NO` | `"HELPFUL_NO"` |
| `MENU_PRODUCT_HELP` | `"MENU_PRODUCT_HELP"` |
| `MENU_CONTACT_HUMAN` | `"MENU_CONTACT_HUMAN"` |
| `MENU_MAIN` | `"MENU_MAIN"` |
| `PAYLOAD_PREFIX_CATEGORY` | `"CATEGORY:"` |
| `PAYLOAD_PREFIX_QUESTION` | `"QUESTION:"` |

---

## Truncation Rules

These rules govern how the preview text is computed.

| Rule | Specification |
|------|--------------|
| Threshold | 200 characters |
| Trigger | `body.length > 200` — strictly greater than |
| Boundary | Cut at the last space at or before index 200 to avoid mid-word splits |
| Suffix | Append `"..."` immediately after the last included word (no space before "...") |
| Maximum preview length | Varies — last word boundary before 200, plus 3 chars for "..." |
| No-truncation path | `body.length <= 200` — send body as-is with `FEEDBACK_QUICK_REPLIES` |
| Edge: no space before 200 | If no space is found before index 200, cut hard at 200 and append "..." |

---

## Sequencing Rules

1. `sendAnswer` is the entry point for both short and long answers. It fetches the body, applies the truncation check, and branches:
   - Body ≤ 200 chars: send body with `FEEDBACK_QUICK_REPLIES` (no change from Phase 7).
   - Body > 200 chars: send preview with `[Read more]` quick reply only.

2. The preview message carries `[Read more]` as its only quick reply. No feedback buttons appear on the preview message.

3. Tapping "Read more" triggers a `READ_MORE:{questionId}` quick reply payload. The handler re-fetches the full answer from the vault and sends it with `FEEDBACK_QUICK_REPLIES` attached.

4. The full-answer follow-up is sent with `FEEDBACK_QUICK_REPLIES` — same as the short-answer path. This ensures feedback is always offered once the user has the complete answer, regardless of answer length.

5. Typing indicators: the "Read more" handler re-fetches from the vault and must wrap the fetch with `sendTypingIndicator(recipientId, "typing_on")` before and `sendTypingIndicator(recipientId, "typing_off")` after (in `finally`), consistent with `sendAnswer`.

6. Quick reply tap events arrive as `event.message.quick_reply`. The new `READ_MORE:` case is inserted after the existing `QUESTION:` case and before the `HELPFUL_YES` case in the quick reply dispatch block.

7. Message ordering per user session for long answers:
   ```
   Message 1: preview + [Read more]
   Message 2: full answer + [Was it helpful? Yes] [Was it helpful? No]
   Message 3 (optional): thank-you + [Product Help] [Contact Human]
   ```

---

## Implementation Hooks

### Functions that change

**`sendAnswer` (messenger-bot/src/index.ts:302)**

Current behavior: sends `body` with `FEEDBACK_QUICK_REPLIES`.

New behavior: after fetching `body`, apply truncation check:
- If `body.length <= 200`: send body with `FEEDBACK_QUICK_REPLIES` (unchanged).
- If `body.length > 200`: compute preview (truncate at last word boundary before 200, append "..."), send preview with a single `[Read more]` quick reply carrying payload `READ_MORE:{questionId}`.

**`handleWebhookEvent` (messenger-bot/src/index.ts:370)**

New case in the quick reply dispatch block, inserted after the `QUESTION:` case and before the `HELPFUL_YES` case:

```typescript
if (payload.startsWith(PAYLOAD_PREFIX_READ_MORE)) {
  const questionId = payload.slice(PAYLOAD_PREFIX_READ_MORE.length);
  if (questionId) {
    await sendReadMoreAnswer(senderId, questionId);
    return;
  }
}
```

### New function to add

**`sendReadMoreAnswer(recipientId: string, questionId: string): Promise<void>`**

Re-fetches the vault answer for `questionId`, sends the full body with `FEEDBACK_QUICK_REPLIES`. Wraps with `sendTypingIndicator`. On fetch failure, calls `sendApologyWithMenu`. Error logging follows the `err instanceof Error ? err.message : String(err)` pattern (DEBT-04 convention).

### New constant to add

```typescript
export const PAYLOAD_PREFIX_READ_MORE = "READ_MORE:";
```

Place near `PAYLOAD_PREFIX_QUESTION` (around line 230) so prefix constants are visually grouped.

### Functions that do NOT change

- `sendMessage` — no change
- `sendTypingIndicator` — no change
- `sendApologyWithMenu` — no change
- `sendCategoryMenu` — no change
- `sendQuestionMenu` — no change
- `sendWelcomeMessage` — no change
- `sendFallbackMessage` — no change
- `handleEscalation` — no change
- `passThreadControl` — no change
- `setupMessengerProfile` — no change
- `FEEDBACK_QUICK_REPLIES` — no change
- `MAIN_MENU_QUICK_REPLIES` — no change

---

## Copywriting Contract

| Element | Exact copy |
|---------|-----------|
| Preview suffix | `...` (appended to last complete word — no space before) |
| "Read more" button title | `Read more` |
| Full answer | [raw vault body — no modification] |
| Feedback button — positive (unchanged) | `Was it helpful? Yes` |
| Feedback button — negative (unchanged) | `Was it helpful? No` |
| Thank-you message (unchanged) | `Glad that helped! Let me know if you need anything else.` |
| Re-fetch error | `Something went wrong fetching that — back to the main menu:` |
| Escalation confirmation (unchanged) | `Connecting you with a human — we'll be with you shortly!` |

No empty-state copy is specific to this phase. The re-fetch-fail case reuses the existing `sendApologyWithMenu` copy.

---

## Edge Cases

| Scenario | Behavior | Source |
|----------|----------|--------|
| Answer body exactly 200 chars | Send as-is with `FEEDBACK_QUICK_REPLIES` — threshold is strictly `> 200` | UX-04: "longer than ~200 characters" |
| Answer body 201+ chars, no space before index 200 | Hard-cut at 200, append "..." | Truncation rule — edge case |
| Re-fetch on "Read more" tap returns empty body | `sendApologyWithMenu` fires — no feedback prompt | Consistent with `sendAnswer` empty-body handling |
| Re-fetch on "Read more" tap fails (network/API error) | Log error (`err instanceof Error ? err.message : String(err)`), call `sendApologyWithMenu` | DEBT-04 convention from Phase 6 |
| User ignores "Read more" and types free text | `sendFallbackMessage` fires — existing handler, no change | PITFALL 6 order preserved |
| User ignores "Read more" and taps persistent menu | Existing postback handler fires — no change | Postback dispatched before quick reply |
| Short answer (≤ 200 chars) | No truncation, no "Read more", `FEEDBACK_QUICK_REPLIES` attached — Phase 7 behavior unchanged | UX-04 condition |
| Answer body is empty or fetch fails in `sendAnswer` | `sendApologyWithMenu` fires — no truncation logic reached, no "Read more" shown | Short-circuit before truncation check |
| `READ_MORE:` payload with empty questionId | Skip the handler, fall through to `sendFallbackMessage` | Guard: `if (questionId)` |

---

## Test Surface

The executor must cover these cases in the Phase 8 test file:

1. `sendAnswer` with body ≤ 200 chars sends body text with `FEEDBACK_QUICK_REPLIES` (no truncation, no "Read more")
2. `sendAnswer` with body > 200 chars sends truncated preview ending "..." with a single `[Read more]` quick reply (payload `READ_MORE:{questionId}`)
3. Preview text cuts at last word boundary before 200 chars (not mid-word)
4. `READ_MORE:{questionId}` quick reply tap calls `sendReadMoreAnswer` and sends full body with `FEEDBACK_QUICK_REPLIES`
5. `sendReadMoreAnswer` re-fetch failure calls `sendApologyWithMenu`
6. `sendAnswer` with empty body still calls `sendApologyWithMenu` — no truncation path reached (regression)
7. `sendAnswer` fetch failure still calls `sendApologyWithMenu` — no truncation path reached (regression)
8. Unknown quick reply payload after "Read more" is shown still routes to `sendFallbackMessage` (regression)
9. Body exactly 200 chars sends as-is with `FEEDBACK_QUICK_REPLIES` — no "Read more"

---

## Registry Safety

Not applicable — this phase adds no UI components, third-party packages, or shadcn blocks. The only change is string constants and control flow in `messenger-bot/src/index.ts`.

---

## Checker Sign-Off

- [ ] Interaction flows: all paths specified with exact message sequences
- [ ] Copy: every user-visible string written out exactly
- [ ] Button titles: all within 20-char Facebook limit
- [ ] Payload naming: new constants named, existing constants confirmed unchanged
- [ ] Truncation rules: threshold, boundary, suffix, and edge cases declared
- [ ] Sequencing rules: message order and quick reply attachment points declared
- [ ] Edge cases: all failure and boundary scenarios covered
- [ ] Implementation hooks: changed functions identified, new function specified
- [ ] Test surface: 9 cases listed for executor

**Approval:** pending
