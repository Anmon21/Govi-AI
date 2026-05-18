# Phase 7: Helpfulness Feedback — Research

**Researched:** 2026-05-18
**Domain:** Facebook Messenger quick reply dispatch — TypeScript/Node.js
**Confidence:** HIGH

---

## Summary

Phase 7 is a surgical two-touch change to `messenger-bot/src/index.ts`. The entire feature lives in one file and touches exactly two functions: `sendAnswer` (swap its trailing quick replies from `MAIN_MENU_QUICK_REPLIES` to a new `FEEDBACK_QUICK_REPLIES` constant) and `handleWebhookEvent` (add two new cases in the existing quick reply dispatch block). No new files, no new dependencies, no new services.

The UI design contract in `07-UI-SPEC.md` is fully specified and implementation-ready: exact message copy, payload names, button titles, sequencing rules, edge cases, and which lines change. The executor can follow the spec verbatim.

The primary technical risk is the event routing distinction: feedback taps arrive as `event.message.quick_reply.payload` (NOT `event.postback.payload`). The existing `handleWebhookEvent` already has a dedicated quick reply dispatch block at line 362, and the two new cases (`HELPFUL_YES`, `HELPFUL_NO`) must be inserted inside that block — before the unknown-payload fallback at line 393. This ordering is already enforced by the existing code structure (PITFALL 6 comment in the file).

**Primary recommendation:** One plan, three tasks — (1) add the `FEEDBACK_QUICK_REPLIES` constant and swap it into `sendAnswer`, (2) add the two quick reply handlers in `handleWebhookEvent`, (3) write a `feedback.test.ts` covering the five cases listed in the UI spec test surface.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Attach feedback prompt to answer | Messenger bot (Node.js) | — | `sendAnswer` already owns the answer send; quick replies attach at the same call site |
| Handle HELPFUL_YES tap | Messenger bot (Node.js) | — | Quick reply event is received and dispatched entirely in the bot's webhook handler |
| Handle HELPFUL_NO tap | Messenger bot (Node.js) | — | Delegates to the existing `handleEscalation` — no backend involvement |
| Escalation on "No" | Messenger bot (Node.js) → Facebook Graph API | — | `handleEscalation` already handles admin notification + `passThreadControl` |
| Thank-you message on "Yes" | Messenger bot (Node.js) | — | Simple `sendMessage` call — no backend, no vault fetch |

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UX-01 | User sees "Was this helpful?" quick reply (Yes / No) after every answer | `sendAnswer` at line 303 sends the answer with `MAIN_MENU_QUICK_REPLIES`; swap to `FEEDBACK_QUICK_REPLIES` to attach the feedback buttons to the answer message |
| UX-02 | User tapping "Yes" receives a short acknowledgment message and is shown the main menu | Add `HELPFUL_YES` case in the quick reply block: one `sendMessage` call with the thank-you copy and `MAIN_MENU_QUICK_REPLIES` |
| UX-03 | User tapping "No" is routed to the escalation flow | Add `HELPFUL_NO` case in the quick reply block: call `handleEscalation(senderId)` directly |
</phase_requirements>

---

## Standard Stack

### Core

No new dependencies. Phase 7 uses only what already exists.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Node.js built-in test runner | Node 26 (project runtime) | Unit tests | Already used across all test files in the project (`node:test`, `node:assert/strict`) |
| axios (monkey-patched in tests) | ^1.16.1 (locked) | HTTP stubs in tests | Existing test pattern — replace `axios.get` / `axios.post` inline, restore in `finally` |

**No installation step required.** [VERIFIED: package.json]

---

## Architecture Patterns

### System Architecture Diagram

```
Facebook Messenger
      |
      | POST /webhook (event.message.quick_reply.payload = "HELPFUL_YES" or "HELPFUL_NO")
      v
handleWebhookEvent()
      |
      +-- event.message.quick_reply? YES
      |         |
      |         +-- payload === "HELPFUL_YES"
      |         |       → sendMessage(sender, thank-you, MAIN_MENU_QUICK_REPLIES)
      |         |
      |         +-- payload === "HELPFUL_NO"
      |         |       → handleEscalation(sender)
      |         |             → sendMessage(adminPsid, notification)
      |         |             → sendMessage(sender, "Connecting you...")
      |         |             → passThreadControl(sender) → Facebook Graph API
      |         |
      |         +-- payload.startsWith("QUESTION:")
      |                 → sendAnswer(sender, questionId)
      |                       → GET /content/:id  (Govi AI API)
      |                       → sendMessage(sender, body, FEEDBACK_QUICK_REPLIES)  ← CHANGED
      |
      +-- event.postback? (persistent menu taps — unchanged path)
      |
      +-- event.message.text? (free text — sendFallbackMessage — unchanged)
```

### Recommended Project Structure

No structural changes. All changes are inside the existing single-file bot:

```
messenger-bot/src/
├── index.ts              # two-point change: FEEDBACK_QUICK_REPLIES constant + handler cases
└── tests/
    └── feedback.test.ts  # new — covers the 5 cases from UI spec test surface
```

### Pattern 1: Quick Reply Dispatch Block

**What:** The existing `handleWebhookEvent` checks `event.message?.quick_reply` before `event.message?.text`. Inside that block, each known payload is an `if (payload === "X")` guard with `return` after handling. New cases follow the identical pattern.

**When to use:** Any new quick reply payload must be added here, not in the postback block.

**Example (existing pattern, verified in codebase):**
```typescript
// Source: messenger-bot/src/index.ts:362-395
if (event.message?.quick_reply) {
  const payload: string = event.message.quick_reply.payload ?? "";
  if (payload === "MENU_PRODUCT_HELP") {
    await sendCategoryMenu(senderId);
    return;
  }
  if (payload === "MENU_CONTACT_HUMAN") {
    await handleEscalation(senderId);
    return;
  }
  // ... more cases ...
  // New cases for Phase 7 inserted HERE, before the fallback below:
  if (payload === "HELPFUL_YES") {
    await sendMessage(senderId, "Glad that helped! Let me know if you need anything else.", MAIN_MENU_QUICK_REPLIES);
    return;
  }
  if (payload === "HELPFUL_NO") {
    await handleEscalation(senderId);
    return;
  }
  // Unknown / malformed payload — re-anchor instead of going silent
  await sendFallbackMessage(senderId);
  return;
}
```
[VERIFIED: codebase grep]

### Pattern 2: Exporting Constants for Testability

**What:** All stable string payloads and quick reply arrays are exported module-level constants. Tests import them directly to assert exact values without hardcoding strings.

**Example (existing):**
```typescript
// Source: messenger-bot/src/index.ts:216-219
export const MAIN_MENU_QUICK_REPLIES: QuickReply[] = [
  { content_type: "text", title: "Product Help", payload: "MENU_PRODUCT_HELP" },
  { content_type: "text", title: "Contact Human", payload: "MENU_CONTACT_HUMAN" },
];
```

New constants follow the same pattern:
```typescript
export const FEEDBACK_QUICK_REPLIES: QuickReply[] = [
  { content_type: "text", title: "Was it helpful? Yes", payload: "HELPFUL_YES" },
  { content_type: "text", title: "Was it helpful? No",  payload: "HELPFUL_NO" },
];
export const PAYLOAD_HELPFUL_YES = "HELPFUL_YES";
export const PAYLOAD_HELPFUL_NO  = "HELPFUL_NO";
```
[VERIFIED: UI-SPEC.md + codebase grep]

### Pattern 3: Axios Stub Test Pattern

**What:** Tests monkey-patch `axios.get` / `axios.post` inline, collect calls into arrays, then restore originals in `finally`. No Jest mocking library — uses Node's built-in test runner.

**Example (from `qa-flow.test.ts`):**
```typescript
// Source: messenger-bot/src/tests/qa-flow.test.ts:33-55
function withAxiosStubs(opts: { onGet?: ...; onPost?: ... }) {
  const axios = require("axios");
  const originalPost = axios.post;
  const originalGet = axios.get;
  const postCalls: { url: string; body: any }[] = [];
  axios.post = async (url: string, body: any) => { postCalls.push({ url, body }); ... };
  return { postCalls, restore() { axios.post = originalPost; axios.get = originalGet; } };
}
```
[VERIFIED: codebase read]

### Anti-Patterns to Avoid

- **Adding feedback handling to the postback block:** `HELPFUL_YES` / `HELPFUL_NO` arrive via quick reply events (`event.message.quick_reply.payload`), not postback events. The postback block is for persistent menu taps only.
- **Sending two messages for the "Yes" path:** The UI spec is explicit — the thank-you message carries `MAIN_MENU_QUICK_REPLIES` as its quick replies. No separate "here's the menu" message follows.
- **Adding a new message before escalation on "No":** The `handleEscalation` function already sends the confirmation. Inserting an intermediate message would cause two user-facing messages.
- **Modifying `handleEscalation`:** The function is called as-is. No changes needed inside it.
- **Changing the order of quick reply / text check in `handleWebhookEvent`:** PITFALL 6 (noted in existing code comments) — quick reply events also set `event.message.text`. Reversing the order would break all quick reply handling.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Quick reply button rendering | Custom Messenger template | Facebook Graph API message format with `quick_replies` array | Messenger handles all rendering; bot only sends JSON |
| Test spy/mock library | Jest / Sinon / vitest | Node built-in test runner (`node:test`) | Already in use across all test files; no new devDependencies |
| Feedback state tracking | Server-side session, cookie, or in-memory flag | None needed | The bot is stateless — quick reply payloads carry all the intent; no server-side state required to know what the user responded to |

**Key insight:** Facebook quick replies are self-describing — the payload tells the handler everything it needs to know. There is no need to track "this user was shown a feedback prompt" because the only way a `HELPFUL_YES` / `HELPFUL_NO` payload arrives is if the user tapped a feedback button that the bot sent. Stateless dispatch is correct here.

---

## Common Pitfalls

### Pitfall 1: Wrong Event Path for Quick Replies

**What goes wrong:** Handler is placed in the `postback` block — quick reply taps are never routed to it.

**Why it happens:** Quick replies look like buttons; it's natural to assume they fire `postback.payload` like persistent menu buttons.

**How to avoid:** Quick reply taps set `event.message.quick_reply.payload`, not `event.postback.payload`. The dispatch check is `event.message?.quick_reply` (line 362 in `handleWebhookEvent`). New `HELPFUL_YES` / `HELPFUL_NO` cases go inside that block.

**Warning signs:** The quick reply tap produces no response; logs show `event.message.text` matches the button title but no handler fires.

### Pitfall 2: Insertion Point Within the Quick Reply Block

**What goes wrong:** New cases are inserted after the `sendFallbackMessage` fallback — they are unreachable because the fallback `return`s first.

**Why it happens:** Appending to the end of the block looks natural.

**How to avoid:** Insert the two new `if` cases before the final `await sendFallbackMessage(senderId); return;` at line 393.

**Warning signs:** Tapping Yes or No always shows the fallback message instead of the expected response.

### Pitfall 3: `sendAnswer` Still Sends `MAIN_MENU_QUICK_REPLIES`

**What goes wrong:** The constant swap in `sendAnswer` is forgotten; users see Product Help / Contact Human buttons after an answer instead of the feedback prompt.

**Why it happens:** Two separate edits are needed — the constant definition and the call site in `sendAnswer`. Missing one leaves behavior unchanged.

**How to avoid:** `sendAnswer` line 303: `await sendMessage(recipientId, body, MAIN_MENU_QUICK_REPLIES)` must become `await sendMessage(recipientId, body, FEEDBACK_QUICK_REPLIES)`. The test for UX-01 (sendAnswer attaches FEEDBACK_QUICK_REPLIES) will catch this.

**Warning signs:** `qa-flow.test.ts` test "QUESTION:<id> triggers sendAnswer with body text and main menu re-anchor" will need updating — it currently asserts `MAIN_MENU_QUICK_REPLIES`. That test must be updated to assert `FEEDBACK_QUICK_REPLIES` as part of this phase.

### Pitfall 4: Button Title Exceeds 20-Character Facebook Limit

**What goes wrong:** Facebook silently truncates or rejects the quick reply if the title exceeds 20 chars.

**Why it happens:** The title "Was it helpful? Yes" is exactly 20 chars — one character over and it fails.

**How to avoid:** "Was it helpful? Yes" = 20 chars (at limit, valid). "Was it helpful? No" = 19 chars (under limit, valid). These are specified exactly in the UI spec and must not be changed.

**Warning signs:** Quick replies do not appear in Messenger; Graph API returns an error about button title length.

### Pitfall 5: Existing `qa-flow.test.ts` Test Breakage

**What goes wrong:** The test at `qa-flow.test.ts:118` asserts `deepStrictEqual(msg?.quick_replies, MAIN_MENU_QUICK_REPLIES)` after a `QUESTION:` tap. After this phase, `sendAnswer` sends `FEEDBACK_QUICK_REPLIES` instead — this test will fail.

**Why it happens:** The existing test was written against pre-Phase-7 behavior.

**How to avoid:** Update the test assertion in `qa-flow.test.ts:141` to assert `FEEDBACK_QUICK_REPLIES` instead of `MAIN_MENU_QUICK_REPLIES`. This is an intentional regression update, not a bug.

---

## Code Examples

### 1. Exact Change to `sendAnswer` (UX-01)

```typescript
// Source: messenger-bot/src/index.ts — current line 303
// BEFORE:
await sendMessage(recipientId, body, MAIN_MENU_QUICK_REPLIES);

// AFTER:
await sendMessage(recipientId, body, FEEDBACK_QUICK_REPLIES);
```
[VERIFIED: codebase read, line 303]

### 2. New Constant Block (place near MAIN_MENU_QUICK_REPLIES, line 216)

```typescript
// Source: 07-UI-SPEC.md Implementation Hooks
export const FEEDBACK_QUICK_REPLIES: QuickReply[] = [
  { content_type: "text", title: "Was it helpful? Yes", payload: "HELPFUL_YES" },
  { content_type: "text", title: "Was it helpful? No",  payload: "HELPFUL_NO" },
];

export const PAYLOAD_HELPFUL_YES = "HELPFUL_YES";
export const PAYLOAD_HELPFUL_NO  = "HELPFUL_NO";
```
[VERIFIED: UI-SPEC.md]

### 3. New Cases in Quick Reply Dispatch (insert before fallback, line 392)

```typescript
// Source: 07-UI-SPEC.md Implementation Hooks
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
[VERIFIED: UI-SPEC.md]

### 4. Test: `sendAnswer` Attaches `FEEDBACK_QUICK_REPLIES` (UX-01)

```typescript
// Pattern from qa-flow.test.ts:withAxiosStubs
test("UX-01: sendAnswer attaches FEEDBACK_QUICK_REPLIES on success", async (t) => {
  // stub axios.get to return a body, collect axios.post calls
  // assert postCalls[1].body.message.quick_replies deep-equals FEEDBACK_QUICK_REPLIES
});
```
[VERIFIED: existing test pattern in qa-flow.test.ts]

### 5. Test: `HELPFUL_YES` Routes to Thank-You Message (UX-02)

```typescript
test("UX-02: HELPFUL_YES quick reply sends thank-you with MAIN_MENU_QUICK_REPLIES", async (t) => {
  // fire handleWebhookEvent({ message: { quick_reply: { payload: "HELPFUL_YES" }, text: "Was it helpful? Yes" }, sender: { id: "USR_X" } })
  // assert one axios.post call
  // assert postCalls[0].body.message.text === "Glad that helped! Let me know if you need anything else."
  // assert postCalls[0].body.message.quick_replies deep-equals MAIN_MENU_QUICK_REPLIES
});
```

### 6. Test: `HELPFUL_NO` Delegates to `handleEscalation` (UX-03)

```typescript
test("UX-03: HELPFUL_NO quick reply calls handleEscalation", async (t) => {
  // set ADMIN_PSID, stub axios.post, fire HELPFUL_NO quick reply event
  // assert postCalls includes admin notification message
  // assert postCalls includes "Connecting you with a human" message to sender
});
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Answers end with `MAIN_MENU_QUICK_REPLIES` | Answers end with `FEEDBACK_QUICK_REPLIES` | Phase 7 | Users see Yes/No instead of Product Help/Contact Human after answers |
| No feedback mechanism | Feedback quick replies on every answer message | Phase 7 | Users can confirm satisfaction or escalate immediately without hunting for a menu option |

**Deprecated/outdated:**
- `MAIN_MENU_QUICK_REPLIES` on `sendAnswer` success path: replaced by `FEEDBACK_QUICK_REPLIES` in Phase 7. `MAIN_MENU_QUICK_REPLIES` still used by `sendWelcomeMessage`, `sendFallbackMessage`, `handleEscalation` (degraded), and the new thank-you message for UX-02.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Phase 6 (`debt-fixes.test.ts`) is fully implemented and passing before Phase 7 begins | Summary | If DEBT-01/02/03/04 patches are not applied, `handleWebhookEvent` may not yet handle quick replies correctly in all paths |

**All other claims in this research are VERIFIED from the codebase or UI-SPEC.md.**

---

## Open Questions

1. **Does the existing `qa-flow.test.ts` answer test need updating?**
   - What we know: Line 141 asserts `deepStrictEqual(msg?.quick_replies, MAIN_MENU_QUICK_REPLIES)` after a `QUESTION:` tap. After Phase 7, `sendAnswer` sends `FEEDBACK_QUICK_REPLIES`.
   - What's unclear: Whether the planner should treat this as a task in the Phase 7 plan or flag it as a regression risk.
   - Recommendation: Include an explicit task to update `qa-flow.test.ts:141` assertion from `MAIN_MENU_QUICK_REPLIES` to `FEEDBACK_QUICK_REPLIES`. This is not optional — if left unupdated, the existing test suite will fail after the Phase 7 code change.

---

## Environment Availability

Step 2.6: SKIPPED — Phase 7 is a pure code change in `messenger-bot/src/index.ts`. No external tools, databases, or services beyond what already runs the bot. The only runtime dependency is Node.js 26, which is already present and verified by the project runtime config.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Node.js built-in test runner (`node:test`) |
| Config file | None — tests run via npm script |
| Quick run command | `cd messenger-bot && npm test` |
| Full suite command | `cd messenger-bot && npm test` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UX-01 | `sendAnswer` attaches `FEEDBACK_QUICK_REPLIES` on successful answer fetch | unit | `cd messenger-bot && npm test` (runs all `*.test.ts`) | ❌ Wave 0 — `feedback.test.ts` |
| UX-01 | `sendAnswer` on fetch error still calls `sendApologyWithMenu` (regression) | unit | `cd messenger-bot && npm test` | ❌ Wave 0 |
| UX-02 | `HELPFUL_YES` quick reply tap → sends thank-you string + `MAIN_MENU_QUICK_REPLIES` | unit | `cd messenger-bot && npm test` | ❌ Wave 0 |
| UX-03 | `HELPFUL_NO` quick reply tap → calls `handleEscalation` | unit | `cd messenger-bot && npm test` | ❌ Wave 0 |
| Regression | Unknown quick reply payload after feedback buttons → `sendFallbackMessage` | unit | `cd messenger-bot && npm test` | ❌ Wave 0 |
| Regression | `qa-flow.test.ts:141` answer test updated from `MAIN_MENU_QUICK_REPLIES` to `FEEDBACK_QUICK_REPLIES` | unit | `cd messenger-bot && npm test` | ⚠️ Exists — needs assertion update |

### Sampling Rate

- **Per task commit:** `cd messenger-bot && npm test`
- **Per wave merge:** `cd messenger-bot && npm test`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `messenger-bot/src/tests/feedback.test.ts` — covers UX-01, UX-02, UX-03, and two regression cases
- [ ] `messenger-bot/src/tests/qa-flow.test.ts` line 141 — assertion must be updated from `MAIN_MENU_QUICK_REPLIES` to `FEEDBACK_QUICK_REPLIES` (pre-implementation update so the test reflects the new contract)

*(All other test infrastructure exists — no new framework install needed)*

---

## Security Domain

Phase 7 introduces no new external calls, no user input processing beyond what the existing dispatcher already handles, and no new authentication paths.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Unchanged — postback/quick reply origin validated by existing `verifySignature` middleware |
| V3 Session Management | No | Bot remains stateless — no session introduced |
| V4 Access Control | No | No new admin or privileged paths |
| V5 Input Validation | Minimal | `payload` string is already normalized via `?? ""` guard at line 364; new cases use exact equality checks, no interpolation |
| V6 Cryptography | No | No cryptographic operations |

No new threat surface. The `HELPFUL_NO` path delegates to `handleEscalation`, which already has SEC-03-compliant error logging.

---

## Sources

### Primary (HIGH confidence)

- `messenger-bot/src/index.ts` (full read) — verified all function implementations, event routing logic, export surface, and exact line numbers
- `messenger-bot/src/tests/qa-flow.test.ts` (full read) — verified test pattern, existing assertion at line 141 that must be updated
- `messenger-bot/src/tests/debt-fixes.test.ts` (full read) — verified stub pattern and test structure
- `.planning/phases/07-helpfulness-feedback/07-UI-SPEC.md` (full read) — verified all copy, payloads, sequencing rules, and implementation hooks
- `messenger-bot/package.json` (read) — verified test runner command and no new dependencies required
- `.planning/REQUIREMENTS.md` (read) — verified UX-01, UX-02, UX-03 definitions
- `.planning/config.json` (read) — confirmed `nyquist_validation: true`

### Secondary (MEDIUM confidence)

None required — all findings sourced directly from the codebase.

### Tertiary (LOW confidence)

None.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified from package.json; no new dependencies
- Architecture: HIGH — verified from full codebase read; all call sites and function signatures confirmed
- Pitfalls: HIGH — derived directly from existing code structure, comments, and test assertions; not speculative

**Research date:** 2026-05-18
**Valid until:** Until `messenger-bot/src/index.ts` is structurally changed (stable file — 60-day estimate)
