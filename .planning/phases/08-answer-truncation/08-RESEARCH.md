# Phase 8: Answer Truncation - Research

**Researched:** 2026-05-19
**Domain:** TypeScript string manipulation, Facebook Messenger quick reply constraints, Node.js test runner
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** "Read more" sends the full answer as a follow-up message — not an external URL. Vault entries have no URL field; follow-up message is simpler.
- **D-02:** Threshold is ~200 characters. Answers at or under the threshold are delivered as-is with no truncation and no "Read more" button.

### Claude's Discretion

- **Exact char threshold:** 200 chars is the target. Claude may use 200 exactly or a nearby value to land on a word boundary, as long as the preview reads naturally.
- **Truncation boundary:** Prefer cutting at the last word boundary before the threshold to avoid mid-word splits. Append "..." immediately after the last included word.
- **Quick reply composition:**
  - Preview message carries `[Read more]` only. Feedback is premature on a truncated message.
  - Full answer follow-up carries `FEEDBACK_QUICK_REPLIES` — consistent with the short answer pattern from Phase 7.
- **Full answer delivery mechanism:** Re-fetch from the vault using `questionId` embedded in a `READ_MORE:<questionId>` payload. Avoids in-memory state. Failure falls back to `sendApologyWithMenu`.
- **Payload constant name:** `PAYLOAD_PREFIX_READ_MORE = "READ_MORE:"` — follows `PAYLOAD_PREFIX_*` naming convention.
- **"Read more" button title:** `"Read more"` = 9 chars — within the 20-char Facebook limit.

### Deferred Ideas (OUT OF SCOPE)

None — user skipped discussion and all ideas stayed within phase scope.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UX-04 | Answers longer than ~200 characters are truncated with "..." and a "Read more" quick reply | UI-SPEC truncation rules verified; word-boundary algorithm documented in Architecture Patterns below |
| UX-05 | User tapping "Read more" receives the full answer text as a follow-up message | Stateless re-fetch pattern documented; `sendReadMoreAnswer` function spec from UI-SPEC verified against existing `sendAnswer` structure |

</phase_requirements>

---

## Summary

Phase 8 is a pure TypeScript code change in a single file: `messenger-bot/src/index.ts`. No new packages, no backend changes, no database migrations. The scope is tightly defined by the UI-SPEC: modify `sendAnswer` to detect long answers and branch into a two-message flow, and add a new `sendReadMoreAnswer` function that re-fetches and delivers the full text.

The codebase patterns are fully established by Phases 6 and 7. Every convention this phase needs already exists: payload prefix constants, quick reply composition, typing indicator wrapping, error logging with `err instanceof Error ? err.message : String(err)`, and stateless vault re-fetch. Phase 8 applies these patterns to a new code path; it introduces no new patterns.

The test infrastructure uses Node.js built-in `node:test` with axios monkey-patching. The existing test files — particularly `feedback.test.ts` and `qa-flow.test.ts` — provide direct templates for Phase 8 tests. All 32 existing tests pass. [VERIFIED: npm test run]

**Primary recommendation:** Write a single new test file `src/tests/truncation.test.ts` covering all 9 UI-SPEC test cases, modelled exactly on `feedback.test.ts`. Implement in `index.ts` by modifying `sendAnswer` and adding `sendReadMoreAnswer` and `PAYLOAD_PREFIX_READ_MORE`. No other files change.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Answer truncation logic | Messenger bot (Node.js) | — | Pure string transformation in the bot; backend has no concept of display length |
| Full-answer re-fetch | Messenger bot (Node.js) | FastAPI backend (read-only) | Bot calls existing `/content/{id}` endpoint; backend unchanged |
| Quick reply dispatch | Messenger bot (Node.js) | — | `handleWebhookEvent` owns all payload routing |
| Message delivery | Facebook Graph API (external) | — | Bot POSTs to Graph API; Messenger renders |

---

## Standard Stack

### Core

This phase introduces no new dependencies. The existing stack is complete.

| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| TypeScript | 5.4 | Type-safe implementation | Installed [VERIFIED: package.json] |
| axios | ^1.16.1 | HTTP calls to vault API and Graph API | Installed [VERIFIED: package.json] |
| express | ^4.19.0 | Webhook server | Installed [VERIFIED: package.json] |
| Node.js built-in `node:test` | built-in | Test runner | Active [VERIFIED: npm test passes] |

### No New Packages Required

The UI-SPEC explicitly states: "this phase adds no UI components, third-party packages, or shadcn blocks." [CITED: 08-UI-SPEC.md §Registry Safety]

---

## Architecture Patterns

### System Architecture Diagram

```
Messenger user taps question quick reply
        |
        v
handleWebhookEvent (index.ts:370)
        |
        | payload starts with "QUESTION:"
        v
sendAnswer(recipientId, questionId)
        |
        |--typing_on
        |--GET /content/{questionId}  -->  FastAPI backend  -->  Obsidian vault
        |
        +-- body.length <= 200 -------> sendMessage(body, FEEDBACK_QUICK_REPLIES)
        |                                       |
        |                                       v
        |                               typing_off (finally)
        |
        +-- body.length > 200 --------> compute preview (word-boundary truncation)
                                        sendMessage(preview, [READ_MORE quick reply])
                                                |
                                                v
                                        typing_off (finally)
                                                |
                                        User taps "Read more"
                                                |
                                                v
                                handleWebhookEvent
                                        | payload starts with "READ_MORE:"
                                        v
                                sendReadMoreAnswer(recipientId, questionId)
                                        |
                                        |--typing_on
                                        |--GET /content/{questionId}  -->  FastAPI backend
                                        |
                                        +-- success --> sendMessage(body, FEEDBACK_QUICK_REPLIES)
                                        +-- failure --> sendApologyWithMenu(recipientId)
                                                |
                                                v
                                        typing_off (finally)
```

### Recommended Project Structure

No structural change. All changes land in the single file:

```
messenger-bot/src/
├── index.ts              ← modify: PAYLOAD_PREFIX_READ_MORE constant,
│                            sendAnswer truncation branch, sendReadMoreAnswer function,
│                            READ_MORE: case in handleWebhookEvent
└── tests/
    ├── feedback.test.ts  ← unchanged (Phase 7)
    ├── qa-flow.test.ts   ← unchanged (Phase 3)
    └── truncation.test.ts  ← NEW — 9 test cases for UX-04, UX-05
```

### Pattern 1: Word-Boundary Truncation

**What:** Cut a string at the last whitespace at or before index 200, append `"..."`.

**When to use:** `body.length > 200` in `sendAnswer`.

**Algorithm (pure TypeScript, no libraries needed):**

```typescript
// Source: UI-SPEC §Truncation Rules (08-UI-SPEC.md)
const ANSWER_THRESHOLD = 200;

function truncateAtWordBoundary(text: string): string {
  // Find last space at or before threshold
  const cutIndex = text.lastIndexOf(" ", ANSWER_THRESHOLD);
  if (cutIndex <= 0) {
    // No space found before threshold — hard-cut at threshold
    return text.slice(0, ANSWER_THRESHOLD) + "...";
  }
  return text.slice(0, cutIndex) + "...";
}
```

Edge cases covered by the UI-SPEC:
- Body exactly 200 chars: `body.length > 200` is false — no truncation. [CITED: 08-UI-SPEC.md §Edge Cases]
- No space before index 200: hard-cut at 200, append `"..."`. [CITED: 08-UI-SPEC.md §Truncation Rules]
- Maximum preview length: last word boundary before 200 + 3 chars = at most 202 chars (if space is at index 199).

### Pattern 2: Stateless Re-Fetch (sendReadMoreAnswer)

**What:** Re-fetch vault answer on "Read more" tap — identical HTTP call to `sendAnswer`, no in-memory state.

**When to use:** `READ_MORE:{questionId}` quick reply payload received in `handleWebhookEvent`.

**Structure mirrors `sendAnswer`:**

```typescript
// Source: CONTEXT.md §Claude's Discretion, UI-SPEC §Implementation Hooks
export async function sendReadMoreAnswer(recipientId: string, questionId: string): Promise<void> {
  await sendTypingIndicator(recipientId, "typing_on");
  try {
    const response = await axios.get(`${GOVI_AI_URL}/content/${encodeURIComponent(questionId)}`);
    const body: string | undefined = response.data?.body;
    if (typeof body !== "string" || body.length === 0) {
      await sendApologyWithMenu(recipientId);
      return;
    }
    await sendMessage(recipientId, body, FEEDBACK_QUICK_REPLIES);
  } catch (err: unknown) {
    if (axios.isAxiosError(err)) {
      console.error("sendReadMoreAnswer failed:", err.message, err.response?.data);
    } else {
      console.error("sendReadMoreAnswer failed (unexpected error):", err instanceof Error ? err.message : String(err));
    }
    await sendApologyWithMenu(recipientId);
  } finally {
    await sendTypingIndicator(recipientId, "typing_off");
  }
}
```

### Pattern 3: Payload Dispatch Insertion Point

**What:** New `READ_MORE:` case inserted after `QUESTION:` case and before `HELPFUL_YES` case in `handleWebhookEvent`.

**Exact insertion point:** After line 399 (`QUESTION:` handler closes), before line 400 (`HELPFUL_YES` check).

```typescript
// Source: UI-SPEC §Sequencing Rules and §Implementation Hooks
if (payload.startsWith(PAYLOAD_PREFIX_READ_MORE)) {
  const questionId = payload.slice(PAYLOAD_PREFIX_READ_MORE.length);
  if (questionId) {
    await sendReadMoreAnswer(senderId, questionId);
    return;
  }
}
```

Empty `questionId` guard (`if (questionId)`) falls through to `sendFallbackMessage` — consistent with the `QUESTION:` guard at line 394. [CITED: 08-UI-SPEC.md §Edge Cases]

### Pattern 4: New Constant Placement

```typescript
// Source: CONTEXT.md §Claude's Discretion, UI-SPEC §Payload Naming
export const PAYLOAD_PREFIX_READ_MORE = "READ_MORE:";
```

Place near `PAYLOAD_PREFIX_QUESTION` (around line 230) to keep prefix constants visually grouped.

### Anti-Patterns to Avoid

- **In-memory state for "Read more":** Do not cache the full answer body in a Map keyed on PSID between the preview message and the "Read more" tap. Re-fetch instead. The bot is stateless by design; caching introduces a new failure mode (what if the user taps "Read more" much later?) and complexity. [CITED: CONTEXT.md D-01]
- **Truncating in the middle of a word:** Always find `lastIndexOf(" ", 200)` — not `slice(0, 200)` directly. Mid-word cuts produce ugly previews. [CITED: 08-UI-SPEC.md §Truncation Rules]
- **Attaching FEEDBACK_QUICK_REPLIES to the preview message:** Feedback before the user has read the full answer is premature. Preview carries only `[Read more]`. [CITED: 08-UI-SPEC.md §Sequencing Rules]
- **Skipping `typing_off` in the finally block of `sendReadMoreAnswer`:** The finally block is mandatory — same as in `sendAnswer`. Without it, Messenger shows a perpetual typing indicator on error. [CITED: 08-UI-SPEC.md §Sequencing Rules rule 5]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Word-boundary truncation | Custom regex word-splitter | `String.prototype.lastIndexOf(" ", threshold)` | Built-in, O(n), no edge case surprises |
| Vault HTTP request | Custom fetch wrapper | `axios.get` (already in use) | Already handles retries, timeouts, error objects consistently |
| Quick reply object | Custom button factory | Inline `QuickReply` object literal matching existing pattern | One-liner; `QuickReply` interface already exported |

**Key insight:** JavaScript's `lastIndexOf` with a `fromIndex` argument is the idiomatic word-boundary tool. No library needed for a 200-char truncation.

---

## Common Pitfalls

### Pitfall 1: `body.length <= 200` vs `body.length < 200`

**What goes wrong:** Using `< 200` instead of `<= 200` truncates 200-char answers that should be sent as-is.

**Why it happens:** Off-by-one. The UI-SPEC is explicit: threshold is strictly `> 200`. A 200-char body must NOT be truncated.

**How to avoid:** Use `if (body.length > 200)` as the truncation trigger. Test case 9 in the UI-SPEC ("Body exactly 200 chars") specifically covers this boundary.

**Warning signs:** Test 9 fails — body of exactly 200 chars produces a "Read more" button.

### Pitfall 2: Feedback quick replies on the preview message

**What goes wrong:** `FEEDBACK_QUICK_REPLIES` attached to the truncated preview message instead of only to the full-answer follow-up.

**Why it happens:** Copy-paste from the existing `sendAnswer` structure without adapting the quick reply argument.

**How to avoid:** Preview message uses a single `QuickReply` with payload `READ_MORE:{questionId}`. Full-answer message uses `FEEDBACK_QUICK_REPLIES`. These are distinct `sendMessage` calls.

**Warning signs:** Test 2 fails — preview message carries 3 quick replies instead of 1.

### Pitfall 3: Missing typing_off in sendReadMoreAnswer

**What goes wrong:** `sendTypingIndicator(recipientId, "typing_off")` not in a `finally` block — Messenger shows a perpetual typing indicator when re-fetch fails.

**Why it happens:** Forgetting to replicate the `finally` pattern from `sendAnswer`.

**How to avoid:** Structure `sendReadMoreAnswer` identically to `sendAnswer` — `typing_on` before try, `typing_off` in finally.

**Warning signs:** Test 5 (re-fetch failure) — only 2 POSTs instead of 3 (missing `typing_off`).

### Pitfall 4: `err instanceof Error ? err.message : String(err)` omitted

**What goes wrong:** `console.error("...", err)` logs the raw error object, potentially leaking `PAGE_ACCESS_TOKEN` embedded in axios error config URLs.

**Why it happens:** Copying a logging pattern from before Phase 6 hardened it.

**How to avoid:** Every `catch (err: unknown)` in Phase 8 must follow: `err instanceof Error ? err.message : String(err)`. [CITED: CONTEXT.md §Error Handling Pattern, Phase 6 DEBT-04]

### Pitfall 5: `encodeURIComponent` omitted on re-fetch URL

**What goes wrong:** `questionId` containing special characters (spaces, slashes) breaks the vault GET request.

**Why it happens:** Forgetting to replicate the `encodeURIComponent` call from `sendAnswer` line 305.

**How to avoid:** Use `${GOVI_AI_URL}/content/${encodeURIComponent(questionId)}` — same pattern as `sendAnswer`. [VERIFIED: index.ts:305]

---

## Code Examples

### Verified pattern: existing sendAnswer (baseline to modify)

```typescript
// Source: messenger-bot/src/index.ts:302 (current implementation)
export async function sendAnswer(recipientId: string, questionId: string): Promise<void> {
  await sendTypingIndicator(recipientId, "typing_on");
  try {
    const response = await axios.get(`${GOVI_AI_URL}/content/${encodeURIComponent(questionId)}`);
    const body: string | undefined = response.data?.body;
    if (typeof body !== "string" || body.length === 0) {
      await sendApologyWithMenu(recipientId);
      return;
    }
    await sendMessage(recipientId, body, FEEDBACK_QUICK_REPLIES);
  } catch (err: unknown) {
    if (axios.isAxiosError(err)) {
      console.error("sendAnswer failed:", err.message, err.response?.data);
    } else {
      console.error("sendAnswer failed (unexpected error):", err instanceof Error ? err.message : String(err));
    }
    await sendApologyWithMenu(recipientId);
  } finally {
    await sendTypingIndicator(recipientId, "typing_off");
  }
}
```

### Verified pattern: existing axios stub helper in tests

```typescript
// Source: messenger-bot/src/tests/feedback.test.ts (established test pattern)
function withAxiosStubs(opts: { onGet?: (url: string) => any; onPost?: (url: string, body: any) => any }) {
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
  return { getCalls, postCalls, restore() { axios.post = originalPost; axios.get = originalGet; } };
}
```

### Verified pattern: existing QuickReply interface

```typescript
// Source: messenger-bot/src/index.ts:21
export interface QuickReply {
  content_type: "text";
  title: string;   // ≤20 chars
  payload: string; // ≤1000 chars
}
```

### New quick reply object for "Read more" button

```typescript
// Source: UI-SPEC §Quick Reply Button Specifications
const readMoreReply: QuickReply = {
  content_type: "text",
  title: "Read more",              // 9 chars — well under 20-char limit
  payload: `${PAYLOAD_PREFIX_READ_MORE}${questionId}`,
};
```

---

## State of the Art

This phase uses only built-in JavaScript string methods and established in-codebase patterns. No ecosystem changes are relevant.

| Aspect | Current Approach | Notes |
|--------|-----------------|-------|
| String truncation | `lastIndexOf` + `slice` | Standard JS — no library needed |
| Test runner | `node:test` (built-in, Node 18+) | Node 26 in use [VERIFIED: CLAUDE.md] |
| Axios stubbing | Monkey-patch `require("axios")` | Established pattern across all 8 existing test files |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `lastIndexOf(" ", 200)` returning -1 (no space before index 200) is rare in practice but must be handled | Architecture Patterns - Pattern 1 | Without guard, `slice(0, -1)` would drop the last character instead of hard-cutting at 200 |

**All other claims are verified or cited against the codebase or UI-SPEC.**

---

## Open Questions

None. The UI-SPEC and CONTEXT.md are fully specified. Every edge case has a defined behavior.

---

## Environment Availability

Step 2.6: No new external dependencies — this phase is code-only changes to `index.ts`. Existing Node.js 26 + npm 11 environment is sufficient. [VERIFIED: CLAUDE.md]

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Node.js built-in `node:test` |
| Config file | none — runner is called directly via `npm test` |
| Quick run command | `npm --prefix messenger-bot test` |
| Full suite command | `npm --prefix messenger-bot test` |
| Current suite | 32 tests, 0 failures [VERIFIED: test run] |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| UX-04 | Body ≤ 200 chars: send as-is with FEEDBACK_QUICK_REPLIES | unit | `npm --prefix messenger-bot test` | ❌ Wave 0 |
| UX-04 | Body > 200 chars: send truncated preview with [Read more] only | unit | `npm --prefix messenger-bot test` | ❌ Wave 0 |
| UX-04 | Preview cuts at last word boundary before 200 (not mid-word) | unit | `npm --prefix messenger-bot test` | ❌ Wave 0 |
| UX-04 | Body exactly 200 chars: no truncation (boundary condition) | unit | `npm --prefix messenger-bot test` | ❌ Wave 0 |
| UX-04 | Body 201+ chars, no space before 200: hard-cut at 200 | unit | `npm --prefix messenger-bot test` | ❌ Wave 0 |
| UX-05 | READ_MORE payload tap re-fetches and sends full body with FEEDBACK_QUICK_REPLIES | unit | `npm --prefix messenger-bot test` | ❌ Wave 0 |
| UX-05 | sendReadMoreAnswer re-fetch failure calls sendApologyWithMenu | unit | `npm --prefix messenger-bot test` | ❌ Wave 0 |
| UX-04 regression | sendAnswer empty body still calls sendApologyWithMenu | unit | `npm --prefix messenger-bot test` | ❌ Wave 0 |
| UX-04 regression | sendAnswer fetch failure still calls sendApologyWithMenu | unit | `npm --prefix messenger-bot test` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `npm --prefix messenger-bot test`
- **Per wave merge:** `npm --prefix messenger-bot test`
- **Phase gate:** Full suite (all 32 existing + new truncation tests) green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `messenger-bot/src/tests/truncation.test.ts` — covers UX-04 and UX-05 (9 test cases from UI-SPEC §Test Surface)

No framework install needed — `node:test` is built-in to Node 26.

---

## Security Domain

Phase 8 adds two code paths that call `axios.get` and `sendMessage`. Both follow the established SEC-03 pattern (never log raw axios errors). No new threat surface is introduced:

- The `questionId` value originates from the `PAYLOAD_PREFIX_READ_MORE` quick reply payload the bot itself generated — it is the same `questionId` already used in `sendAnswer`. It is passed to `encodeURIComponent` before use in a URL, preventing URL injection.
- No user-supplied free text is processed in Phase 8.
- No new tokens, secrets, or credentials are introduced.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes (questionId in URL) | `encodeURIComponent` — mirrors existing `sendAnswer` pattern |
| V6 Cryptography | no | No crypto in this phase |
| V2 Authentication | no | No auth added |
| V3 Session Management | no | Stateless by design |
| V4 Access Control | no | No access control changes |

---

## Sources

### Primary (HIGH confidence)

- `messenger-bot/src/index.ts` — complete file read; all function signatures, constants, and patterns verified
- `.planning/phases/08-answer-truncation/08-CONTEXT.md` — locked decisions and Claude's discretion items
- `.planning/phases/08-answer-truncation/08-UI-SPEC.md` — interaction flows, truncation rules, edge cases, test surface
- `.planning/REQUIREMENTS.md` — UX-04, UX-05 acceptance criteria
- `messenger-bot/src/tests/feedback.test.ts` — test pattern template
- `messenger-bot/src/tests/qa-flow.test.ts` — test pattern template
- `messenger-bot/package.json` — test command and dependency versions
- npm test run output: 32 pass, 0 fail

### Secondary (MEDIUM confidence)

None required — all claims verified against codebase or spec files.

### Tertiary (LOW confidence)

None.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — package.json verified, no new packages needed
- Architecture: HIGH — UI-SPEC fully specifies all functions, insertion points, and edge cases; codebase read confirms integration points
- Pitfalls: HIGH — derived from UI-SPEC edge cases and existing codebase conventions, verified against actual code
- Test infrastructure: HIGH — test run confirmed passing; existing test files provide direct templates

**Research date:** 2026-05-19
**Valid until:** 90 days — stable TypeScript codebase with no external ecosystem dependencies in this phase
