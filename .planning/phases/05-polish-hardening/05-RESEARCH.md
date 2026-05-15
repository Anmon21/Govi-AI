# Phase 5: Polish + Hardening - Research

**Researched:** 2026-05-15
**Domain:** Facebook Messenger Sender Actions API + Node.js/TypeScript bot hardening
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| POLISH-01 | Bot shows a typing indicator (typing_on action) while fetching answers from the FastAPI content API | UI-SPEC confirms endpoint, call ordering, error path (finally block), and SEC-03 compliance. Existing `sendMessage` and `passThreadControl` functions provide the exact implementation template. |
</phase_requirements>

---

## Summary

Phase 5 has two deliverables: (1) a typing indicator that fires in `sendAnswer` only, implemented
via a new `sendTypingIndicator` helper using the existing `axios` + SEC-03 pattern; and (2) a
verified, complete `messenger-bot/.env.example` that matches the current runtime environment.

The UI-SPEC (05-UI-SPEC.md) is the authoritative design contract for this phase and has already
resolved all ambiguous design decisions — endpoint shape, call ordering, error path (finally
block), minimum display duration (none), scope (sendAnswer only), and SEC-03 compliance. The
research below confirms the implementation against the existing codebase and identifies the exact
test changes required.

The dominant risk is a test breakage: the `qa-flow: QUESTION:<id> triggers sendAnswer` test
asserts `postCalls.length === 1` (exactly one axios.post). After adding typing_on + typing_off,
`sendAnswer` will fire 3 POSTs. This single assertion must be updated. The other three qa-flow
tests involve `sendCategoryMenu` or `sendQuestionMenu` (not `sendAnswer`) and are unaffected.

**Primary recommendation:** Implement `sendTypingIndicator` in one task. Update `.env.example`
and the single broken test assertion in a second task. No new dependencies needed.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Typing indicator API call | Messenger bot (Node.js) | — | sendAnswer lives in index.ts; typing_on/off are Graph API calls, same tier as sendMessage |
| Error-safe logging | Messenger bot (Node.js) | — | SEC-03 is a bot-tier concern; FastAPI side is unchanged |
| Env var documentation | Messenger bot config | Root config | Only messenger-bot/.env.example needs updating; root .env.example covers FastAPI vars which are unchanged |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| axios | ^1.7.0 | HTTP client for Graph API and FastAPI calls | Already in package.json; all existing API calls use it |
| dotenv | ^16.4.0 | Env var loading | Already in package.json |

**No new dependencies required.** [VERIFIED: messenger-bot/package.json via codebase read]

The typing indicator uses the same `axios.post` call shape as `sendMessage`. There is no
additional library, SDK, or Graph API client to install.

---

## Architecture Patterns

### System Architecture Diagram

```
Customer taps question button
        |
        v
handleWebhookEvent (QUESTION:<id> payload)
        |
        v
sendAnswer(recipientId, questionId)
        |
        +--> sendTypingIndicator(recipientId, "typing_on")  [new — POST /me/messages]
        |
        +--> axios.get /content/{id}                         [existing FastAPI call]
        |         |
        |    success: sendMessage(recipientId, body, quickReplies)  [POST /me/messages]
        |    failure: sendApologyWithMenu(recipientId)               [POST /me/messages]
        |
        +--> sendTypingIndicator(recipientId, "typing_off")  [new — POST /me/messages, in finally]
```

All other handlers (`sendCategoryMenu`, `sendQuestionMenu`, `sendWelcomeMessage`,
`sendFallbackMessage`, `handleEscalation`) are untouched.

### Recommended Project Structure

No structural changes. `sendTypingIndicator` is added to the existing single-file entry point:

```
messenger-bot/src/
└── index.ts     # add sendTypingIndicator (exported), modify sendAnswer
```

### Pattern 1: sendTypingIndicator — modeled on sendMessage and passThreadControl

**What:** A `Promise<void>` helper that POSTs `sender_action` to the Graph API using the same
`axios.post` pattern already established for `sendMessage` and `passThreadControl`.

**When to use:** Called by `sendAnswer` only — typing_on before the fetch, typing_off in finally.

```typescript
// Source: UI-SPEC 05-UI-SPEC.md + existing sendMessage/passThreadControl in index.ts
export async function sendTypingIndicator(
  recipientId: string,
  action: "typing_on" | "typing_off"
): Promise<void> {
  try {
    await axios.post(
      `https://graph.facebook.com/${GRAPH_API_VERSION}/me/messages`,
      {
        recipient: { id: recipientId },
        sender_action: action,
      },
      { params: { access_token: PAGE_ACCESS_TOKEN } }
    );
  } catch (err: unknown) {
    // SEC-03: Never log the full axios error (config.url contains PAGE_ACCESS_TOKEN)
    if (axios.isAxiosError(err)) {
      console.error("sendTypingIndicator failed:", err.message, err.response?.data);
    } else {
      console.error("sendTypingIndicator failed (unexpected error):", err);
    }
  }
}
```

**Key details:**
- Endpoint: `POST https://graph.facebook.com/v21.0/me/messages` [VERIFIED: UI-SPEC, consistent with existing sendMessage URL]
- Body has `sender_action`, NOT `message` — these are mutually exclusive fields per the Graph API [CITED: developers.facebook.com/docs/messenger-platform/send-messages/sender-actions]
- `access_token` is a query param (same as sendMessage) [VERIFIED: existing index.ts]
- Errors are swallowed after logging — typing indicator failure must not prevent answer delivery [VERIFIED: UI-SPEC Implementation Constraints §6]
- Must be exported for unit testability [VERIFIED: UI-SPEC Implementation Constraints §5]

### Pattern 2: finally block in sendAnswer

**What:** Restructure `sendAnswer` to wrap the existing try/catch in a try/finally, with typing_on before and typing_off in finally.

**When to use:** Guarantees typing_off fires on both success and error paths.

```typescript
// Source: UI-SPEC 05-UI-SPEC.md §Call Ordering + Error Case Ordering
export async function sendAnswer(recipientId: string, questionId: string): Promise<void> {
  await sendTypingIndicator(recipientId, "typing_on");
  try {
    const response = await axios.get(`${GOVI_AI_URL}/content/${encodeURIComponent(questionId)}`);
    const body: string | undefined = response.data?.body;
    if (typeof body !== "string" || body.length === 0) {
      await sendApologyWithMenu(recipientId);
      return;
    }
    await sendMessage(recipientId, body, MAIN_MENU_QUICK_REPLIES);
  } catch (err: unknown) {
    if (axios.isAxiosError(err)) {
      console.error("sendAnswer failed:", err.message, err.response?.data);
    } else {
      console.error("sendAnswer failed (unexpected error):", err);
    }
    await sendApologyWithMenu(recipientId);
  } finally {
    await sendTypingIndicator(recipientId, "typing_off");
  }
}
```

**Note on early return:** The `return` inside the `if (!body)` branch is inside the `try` block.
TypeScript/JS `finally` runs after a `return` in `try`, so `typing_off` still fires correctly
even when the early return path is taken. [VERIFIED: JavaScript language semantics — finally
executes before the return value is delivered]

### Anti-Patterns to Avoid

- **Adding typing indicators to sendCategoryMenu or sendQuestionMenu:** Out of scope. POLISH-01
  says "while fetching answers" — navigation menus are not answers. CLAUDE.md: no features beyond
  what was asked.
- **Adding artificial delay between typing_on and the fetch:** Do not add `setTimeout`. The HTTP
  round-trip latency to FastAPI is the natural delay. UI-SPEC explicitly prohibits added delays.
- **Propagating sendTypingIndicator errors:** Errors must be swallowed (logged, not thrown). A
  typing indicator failure must not prevent the answer or apology from reaching the customer.
- **Sending typing_off before sendMessage resolves:** Causes visible indicator flicker. UI-SPEC
  mandates `typing_off` after `sendMessage` completes, which the `finally` pattern enforces
  correctly (finally runs after the await chain completes, including sendMessage).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Typing indicator | Custom animation or delay loop | Facebook's sender_action=typing_on/off | Messenger renders animated dots natively; no client-side code possible |
| Token-safe logging | Custom redaction logic | Existing SEC-03 pattern (axios.isAxiosError guard) | Already established in sendMessage and passThreadControl — copy it exactly |
| Test stubbing | New mock framework | Existing withAxiosStubs pattern in qa-flow.test.ts | Pattern is already proven and consistent across all test files |

---

## ENV VAR Documentation: Current State vs Target State

### Current `messenger-bot/.env.example` State

[VERIFIED: codebase read of messenger-bot/.env.example]

```
FACEBOOK_VERIFY_TOKEN=your_verify_token_here
FACEBOOK_PAGE_ACCESS_TOKEN=your_page_access_token_here
# FACEBOOK_APP_SECRET — Facebook Developer Dashboard → App Settings → Basic → App Secret
FACEBOOK_APP_SECRET=your_app_secret_here
# ADMIN_PSID — Page-Scoped ID of the admin's Messenger account; have the admin message the Page once and read the [senderId] from the bot log
ADMIN_PSID=your_admin_psid_here
GOVI_AI_URL=http://localhost:8000
PORT=3000
```

**All 6 runtime vars are present.** Phase 5 adds no new vars. [VERIFIED: index.ts reads exactly
these 6 vars: FACEBOOK_VERIFY_TOKEN, FACEBOOK_PAGE_ACCESS_TOKEN, FACEBOOK_APP_SECRET,
ADMIN_PSID, GOVI_AI_URL, PORT]

### Gap between current .env.example and UI-SPEC target

The UI-SPEC specifies a richer comment format with multi-line comments and a PAGE_INBOX_APP_ID
reference entry. The current .env.example has minimal single-line comments for FACEBOOK_APP_SECRET
and ADMIN_PSID, and no comments at all for FACEBOOK_VERIFY_TOKEN, FACEBOOK_PAGE_ACCESS_TOKEN,
GOVI_AI_URL, or PORT.

**Changes needed:** Expand comments to match UI-SPEC target — every var gets a descriptive comment
line explaining what it is and where to get the value, plus a commented-out PAGE_INBOX_APP_ID
reference entry. This is a documentation-only change; no runtime behavior changes.

### Root `.env.example` (FastAPI side)

[VERIFIED: codebase read of root .env.example]

Current content covers `ANTHROPIC_API_KEY`, `APP_ENV`, `APP_PORT`, `VAULT_PATH`. Phase 5 does
not modify the FastAPI side. Root .env.example does not need updating.

---

## Test Implications

### Which tests break when typing indicators are added

`sendAnswer` gains 2 new `axios.post` calls (typing_on before, typing_off after).
All axios.post calls go through the shared `withAxiosStubs` interceptor in qa-flow.test.ts.

| Test | Handler Invoked | Currently Asserts | After Change | Breaks? |
|------|----------------|-------------------|--------------|---------|
| MENU_PRODUCT_HELP triggers categories | sendCategoryMenu | postCalls.length === 1 | 1 (unchanged — no typing on category menus) | NO |
| CATEGORY:<id> triggers questions | sendQuestionMenu | postCalls.length === 1 | 1 (unchanged) | NO |
| QUESTION:<id> triggers sendAnswer (success) | sendAnswer | postCalls.length === 1 | 3 (typing_on + message + typing_off) | **YES** |
| API error sends apology (MENU_PRODUCT_HELP) | sendCategoryMenu | postCalls.length === 1 | 1 (unchanged) | NO |

[VERIFIED: qa-flow.test.ts line 135 asserts postCalls.length === 1 for the sendAnswer success
path. The payload used is QUESTION:q-shipping-01, which routes to sendAnswer.]

**Only one assertion must change:** line 135 in qa-flow.test.ts.

### Updated assertion for sendAnswer test

```typescript
// Before:
assert.strictEqual(stubs.postCalls.length, 1, "single sendMessage delivers answer + re-anchor");
const msg = stubs.postCalls[0].body?.message;

// After:
assert.strictEqual(stubs.postCalls.length, 3, "typing_on + sendMessage + typing_off for answer delivery");
// typing_on is postCalls[0], sendMessage is postCalls[1], typing_off is postCalls[2]
const msg = stubs.postCalls[1].body?.message;
```

The additional assertions verifying `msg.text` and `msg.quick_replies` remain valid — only
the index and the count change.

### New test: typing indicator error path

The UI-SPEC requires that `typing_off` fires even when the API fetch fails. A dedicated test
should verify this: stub `axios.get` to throw, assert that `postCalls` contains exactly 2
typing-indicator POSTs (typing_on + typing_off) in addition to the apology sendMessage.

```typescript
// Verify typing_off fires even when API fetch fails
test("qa-flow: sendAnswer typing_off fires even when API fetch fails", async (t) => {
  // ...stub axios.get to throw, count typing calls in postCalls...
  // postCalls should be: [typing_on, apology_sendMessage, typing_off]
  // typing_off appears in postCalls even though fetch threw
});
```

This test covers the `finally` block semantic — it is the primary correctness guarantee for
the error path behavior specified in the UI-SPEC.

### Escalation tests (escalation.test.ts)

The escalation tests count `axios.post` calls but only for `handleEscalation` and
`passThreadControl`, which are not modified. No changes needed. [VERIFIED: escalation.test.ts
does not invoke sendAnswer]

---

## Common Pitfalls

### Pitfall 1: Early return inside try does not prevent finally

**What goes wrong:** Developer worries that `return` inside the empty-body guard skips `finally`.
**Why it happens:** Confusion about JavaScript finally semantics.
**How to avoid:** In JavaScript/TypeScript, `finally` always executes before a `return` from the
`try` block delivers its value. The typing_off call is guaranteed.
**Warning signs:** TypeScript compiler will not warn about this — it is a runtime semantic.

### Pitfall 2: Test count assertion off-by-one

**What goes wrong:** Test asserts `postCalls.length === 2` instead of 3.
**Why it happens:** Forgetting that both typing_on and typing_off are separate POSTs, each going
through the axios.post stub.
**How to avoid:** Count explicitly: typing_on (index 0) + sendMessage (index 1) + typing_off
(index 2) = 3 total.

### Pitfall 3: typing_off before sendMessage

**What goes wrong:** `typing_off` sent immediately after the GET fetch completes, before
`sendMessage` resolves, causing the indicator to reappear briefly while the message is in-flight.
**Why it happens:** Developer puts `typing_off` after `await axios.get(...)` instead of after
`await sendMessage(...)`.
**How to avoid:** Use the `finally` pattern — it runs after the entire `try` block completes,
which includes the `await sendMessage(...)` call.

### Pitfall 4: Logging the full axios error in sendTypingIndicator

**What goes wrong:** `console.error("error:", err)` logs the full AxiosError, which includes
`config.url` containing `PAGE_ACCESS_TOKEN`.
**Why it happens:** Forgetting to apply the SEC-03 isAxiosError narrowing pattern.
**How to avoid:** Copy the exact error handler from `sendMessage` or `passThreadControl` —
`if (axios.isAxiosError(err)) { console.error(..., err.message, err.response?.data); }`.

### Pitfall 5: Typing indicator on sendCategoryMenu or sendQuestionMenu

**What goes wrong:** Developer adds typing indicators to navigation menu fetches "for consistency."
**Why it happens:** It seems logical — they also call FastAPI.
**How to avoid:** POLISH-01 is explicit: "while fetching answers." CLAUDE.md: no features beyond
what was asked. Scope is sendAnswer only.

---

## Code Examples

### Full sendTypingIndicator implementation

```typescript
// Source: UI-SPEC 05-UI-SPEC.md + modeled on sendMessage (index.ts lines 112-142)
export async function sendTypingIndicator(
  recipientId: string,
  action: "typing_on" | "typing_off"
): Promise<void> {
  try {
    await axios.post(
      `https://graph.facebook.com/${GRAPH_API_VERSION}/me/messages`,
      {
        recipient: { id: recipientId },
        sender_action: action,
      },
      { params: { access_token: PAGE_ACCESS_TOKEN } }
    );
  } catch (err: unknown) {
    if (axios.isAxiosError(err)) {
      console.error("sendTypingIndicator failed:", err.message, err.response?.data);
    } else {
      console.error("sendTypingIndicator failed (unexpected error):", err);
    }
  }
}
```

### sendAnswer with typing indicator wired in

```typescript
// Source: UI-SPEC 05-UI-SPEC.md §Call Ordering within sendAnswer
export async function sendAnswer(recipientId: string, questionId: string): Promise<void> {
  await sendTypingIndicator(recipientId, "typing_on");
  try {
    const response = await axios.get(`${GOVI_AI_URL}/content/${encodeURIComponent(questionId)}`);
    const body: string | undefined = response.data?.body;
    if (typeof body !== "string" || body.length === 0) {
      await sendApologyWithMenu(recipientId);
      return;
    }
    await sendMessage(recipientId, body, MAIN_MENU_QUICK_REPLIES);
  } catch (err: unknown) {
    if (axios.isAxiosError(err)) {
      console.error("sendAnswer failed:", err.message, err.response?.data);
    } else {
      console.error("sendAnswer failed (unexpected error):", err);
    }
    await sendApologyWithMenu(recipientId);
  } finally {
    await sendTypingIndicator(recipientId, "typing_off");
  }
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No typing indicator (Phase 1-4 baseline) | typing_on/off wrapping sendAnswer | Phase 5 | Bot no longer appears frozen during FastAPI fetch |

**No deprecated approaches in this phase.** The `sender_action` API has been stable in the
Facebook Graph API for years. The project already runs on v21.0 of the Graph API for all other
sends. [CITED: developers.facebook.com/docs/messenger-platform/send-messages/sender-actions]

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Facebook automatically times out typing_on after ~20 seconds if typing_off is not received | Common Pitfalls (implicit) | If false and timeout is shorter, the indicator may disappear before the answer arrives for slow connections. The finally block sends explicit typing_off regardless, so this is informational only — no plan impact. |
| A2 | `sender_action` and `message` fields are mutually exclusive in the Send API request body | Standard Stack / Code Examples | If wrong, the typing indicator post would need a different body shape. The UI-SPEC confirms the body shape; this assumption only affects why `message` is absent from the body. Extremely low risk. |

**All implementation claims are VERIFIED or CITED.** The two assumptions above do not affect
the plan — the implementation is fully specified by the UI-SPEC and confirmed by the codebase.

---

## Open Questions

None. The UI-SPEC and existing codebase provide complete implementation guidance. All research
questions posed in the phase brief are answered below for reference:

1. **Endpoint shape:** `POST https://graph.facebook.com/v21.0/me/messages` with
   `{ recipient: { id }, sender_action: "typing_on" }` — same URL pattern as `sendMessage`.
   [VERIFIED: existing sendMessage in index.ts + UI-SPEC]

2. **Call ordering:** typing_on BEFORE axios.get; typing_off in `finally` after `sendMessage`
   resolves. [VERIFIED: UI-SPEC §Call Ordering]

3. **sendTypingIndicator reuses axios.post:** Yes — identical pattern to sendMessage and
   passThreadControl. [VERIFIED: index.ts]

4. **Facebook auto-timeout for typing_on:** The official docs do not document a specific
   timeout; best practice is to always send explicit typing_off. The `finally` block ensures
   this regardless. [CITED: developers.facebook.com/docs/messenger-platform/send-messages/sender-actions]

5. **typing_off when fetch fails:** Yes — `finally` block guarantees it regardless of
   success or failure. [VERIFIED: UI-SPEC §Error Case Ordering]

6. **sendTypingIndicator errors propagation:** Swallowed after SEC-03-compliant logging.
   [VERIFIED: UI-SPEC Implementation Constraints §6]

7. **Test updates needed:** One assertion in qa-flow.test.ts (line 135) changes from
   `postCalls.length === 1` to `postCalls.length === 3`, and `postCalls[0]` becomes
   `postCalls[1]` for the message body check. Plus one new test for the error-path typing_off.
   [VERIFIED: qa-flow.test.ts analysis]

8. **Scope guard confirmed:** sendAnswer only. sendCategoryMenu and sendQuestionMenu are
   untouched. No Python/FastAPI changes. No changes to verifySignature or sendMessage.
   [VERIFIED: UI-SPEC §Scope]

---

## Environment Availability

Step 2.6: SKIPPED. Phase 5 is code/config changes only. No new external tools, services, CLIs,
or runtimes are required. The existing Node.js + axios environment already supports all
Graph API calls needed.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Node.js built-in test runner (`node:test`) |
| Config file | `messenger-bot/package.json` → `"test": "node --test --require ts-node/register 'src/tests/*.test.ts'"` |
| Quick run command | `npm --prefix messenger-bot test` |
| Full suite command | `npm --prefix messenger-bot test` (same — no separate suite split) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| POLISH-01 (success path) | sendAnswer fires typing_on before fetch and typing_off after sendMessage | unit | `npm --prefix messenger-bot test` | ❌ Wave 0 — update existing test + add new test in qa-flow.test.ts |
| POLISH-01 (error path) | typing_off fires even when API fetch throws | unit | `npm --prefix messenger-bot test` | ❌ Wave 0 — new test in qa-flow.test.ts |

### Sampling Rate

- **Per task commit:** `npm --prefix messenger-bot test`
- **Per wave merge:** `npm --prefix messenger-bot test`
- **Phase gate:** All 21 existing tests still pass + 2 new POLISH-01 tests green

### Wave 0 Gaps

- [ ] Update `messenger-bot/src/tests/qa-flow.test.ts` line 135: change `postCalls.length` assertion from 1 to 3, update `postCalls[0]` to `postCalls[1]` for message body check — covers POLISH-01 success path
- [ ] Add new test `qa-flow: sendAnswer typing_off fires even when API fetch fails` in `qa-flow.test.ts` — covers POLISH-01 error path

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | n/a |
| V3 Session Management | no | n/a |
| V4 Access Control | no | n/a |
| V5 Input Validation | no | recipientId and action are internal values, not user-supplied strings |
| V6 Cryptography | no | typing indicator uses same token-in-params pattern as existing sendMessage |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| PAGE_ACCESS_TOKEN in axios error log | Information Disclosure | SEC-03: axios.isAxiosError guard, log err.message + err.response?.data only (never full error object). Already established — sendTypingIndicator must replicate the exact same pattern. |

No new threat surface introduced. `sendTypingIndicator` is a Graph API call using the same token
and the same SEC-03 logging pattern already in production for `sendMessage` and `passThreadControl`.

---

## Project Constraints (from CLAUDE.md)

| Constraint | Impact on Phase 5 |
|------------|------------------|
| Node.js/TypeScript for Messenger bot — maintain existing split | sendTypingIndicator goes in index.ts; no Python changes |
| Facebook Messenger only — no other channels | Typing indicator is a Messenger-specific Graph API action — correct scope |
| No containerization — same manual deploy pattern | No deployment changes needed |
| Scope: standalone system | No integration with external systems beyond existing Graph API |
| No features beyond what was asked (CLAUDE.md §2) | typing indicator on sendAnswer only — NOT sendCategoryMenu/sendQuestionMenu |
| Touch only what you must (CLAUDE.md §3) | Two changes: (1) add sendTypingIndicator + modify sendAnswer; (2) update .env.example comments |
| Strict TypeScript (tsconfig.json strict: true) | sendTypingIndicator must be fully typed; `action: "typing_on" | "typing_off"` union type ensures compile-time safety |

---

## Sources

### Primary (HIGH confidence)
- `messenger-bot/src/index.ts` — existing sendMessage, passThreadControl patterns; confirmed sendAnswer structure; confirmed 21/21 tests pass at baseline
- `.planning/phases/05-polish-hardening/05-UI-SPEC.md` — authoritative design contract; endpoint, call ordering, error path, scope, SEC-03 requirements all resolved
- `messenger-bot/src/tests/qa-flow.test.ts` — confirmed exact assertion at line 135 that breaks; confirmed withAxiosStubs intercepts both get and post
- `messenger-bot/.env.example` — confirmed all 6 vars present; confirmed comment gap vs UI-SPEC target

### Secondary (MEDIUM confidence)
- [Facebook Sender Actions docs](https://developers.facebook.com/docs/messenger-platform/send-messages/sender-actions) — confirmed typing_on/typing_off are the correct sender_action values; confirmed POST to /me/messages; confirmed body shape with recipient + sender_action

### Tertiary (LOW confidence)
- None — all implementation claims verified from codebase or official docs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; confirmed from package.json
- Architecture: HIGH — fully specified by UI-SPEC; confirmed from codebase
- Pitfalls: HIGH — derived from codebase analysis and TypeScript language semantics
- Test implications: HIGH — derived from line-by-line qa-flow.test.ts analysis

**Research date:** 2026-05-15
**Valid until:** 2026-06-15 (Graph API sender_action is stable; Facebook API versioning is slow-moving)
