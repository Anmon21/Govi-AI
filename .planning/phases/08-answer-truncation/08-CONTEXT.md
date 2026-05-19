# Phase 8: Answer Truncation - Context

**Gathered:** 2026-05-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Modify `sendAnswer` in `messenger-bot/src/index.ts` so answers longer than ~200 characters are sent as a truncated preview ending with "..." and a "Read more" quick reply. Tapping "Read more" delivers the full answer text as a follow-up message. Answers at or under the threshold are delivered unchanged. No backend changes — pure bot-side logic in the existing TypeScript file.

</domain>

<decisions>
## Implementation Decisions

### Pre-decided (from prior phases / project planning)

- **D-01 [informational]:** "Read more" sends the full answer as a follow-up message — not an external URL. Vault entries have no URL field; follow-up message is simpler.
- **D-02 [informational]:** Threshold is ~200 characters. Answers at or under the threshold are delivered as-is with no truncation and no "Read more" button.

### Claude's Discretion

User skipped discussion — the following implementation decisions are delegated to the planner/executor, guided by the established codebase patterns:

- **Exact char threshold:** 200 chars is the target. Claude may use 200 exactly or a nearby value to land on a word boundary, as long as the preview reads naturally.
- **Truncation boundary:** Prefer cutting at the last word boundary before the threshold to avoid mid-word splits. Append "..." immediately after the last included word.
- **Quick reply composition:**
  - **Preview message:** Should carry `[Read more]` only. Asking "Was this helpful?" on a truncated message the user hasn't fully read yet is premature and confusing. The feedback prompt is deferred to after the full answer.
  - **Full answer follow-up:** Should carry `FEEDBACK_QUICK_REPLIES` ("Was it helpful? Yes / No") — consistent with the pattern for short answers (Phase 7). This ensures the helpfulness feedback is always offered, regardless of answer length.
- **Full answer delivery mechanism:** Recommend re-fetching from the vault using the `questionId` embedded in a `READ_MORE:<questionId>` payload (analogous to `QUESTION:<questionId>`). This avoids introducing new in-memory state and keeps the bot stateless for this feature. If re-fetch fails, fall back to `sendApologyWithMenu`.
- **Payload constant name:** Follow the existing `PAYLOAD_PREFIX_*` naming convention — e.g., `PAYLOAD_PREFIX_READ_MORE = "READ_MORE:"`.
- **"Read more" button title:** Must be ≤ 20 chars (Facebook limit). `"Read more"` = 9 chars — well within limit.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary Implementation Target

- `messenger-bot/src/index.ts` — the single file all Phase 8 changes land in; `sendAnswer` (line 302) is the primary function to modify

### Requirements and Acceptance Criteria

- `.planning/REQUIREMENTS.md` §UX-04, UX-05 — exact acceptance criteria for this phase
- `.planning/ROADMAP.md` §Phase 8 — success criteria and phase goal

### Quick Reply Patterns (Phase 7 established conventions)

- `.planning/phases/07-helpfulness-feedback/07-UI-SPEC.md` — button title ≤ 20 chars constraint, `FEEDBACK_QUICK_REPLIES` constant, payload naming conventions, sequencing rules; Phase 8 builds directly on top of Phase 7's answer flow

### Error Handling Pattern

- `.planning/phases/06-bug-fixes-hardening/06-CONTEXT.md` §D-07 — non-Axios error log sanitization pattern; any new try/catch in Phase 8 must follow the same `err instanceof Error ? err.message : String(err)` convention

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `sendAnswer` (`index.ts:302`): the function to modify — currently sends `body` with `FEEDBACK_QUICK_REPLIES`; Phase 8 adds truncation logic and a conditional "Read more" quick reply before that send
- `sendMessage` (`index.ts:121`): accepts `quickReplies?: QuickReply[]` — already supports sending with or without quick replies; no change needed
- `FEEDBACK_QUICK_REPLIES` (`index.ts:221`): Phase 7 constant for "Was it helpful? Yes/No" — attach to the full-answer follow-up message
- `PAYLOAD_PREFIX_QUESTION = "QUESTION:"` (`index.ts:230`): the existing pattern for question-ID payloads; `READ_MORE:<questionId>` follows the same convention

### Established Patterns

- Payload dispatch: all quick reply payloads are dispatched in `handleWebhookEvent` (`index.ts:370`) via an if-chain. New `READ_MORE:` case slots in after the existing `QUESTION:` case.
- Error logging: non-Axios errors use `err instanceof Error ? err.message : String(err)` — any new catch block must follow this pattern (DEBT-04 convention from Phase 6).
- Silent error recovery: helper functions log + call `sendApologyWithMenu` on failure; Phase 8 should do the same if the re-fetch for "Read more" fails.
- Typing indicator: `sendAnswer` wraps its content fetch with `typing_on` / `typing_off`. If the "Read more" handler re-fetches from the vault, it should also use `sendTypingIndicator` for consistency.

### Integration Points

- `sendAnswer` (`index.ts:302`): insert truncation check between body fetch and `sendMessage` call
- Quick reply dispatch block (`index.ts:370`): add new `if (payload.startsWith(PAYLOAD_PREFIX_READ_MORE))` case
- Constants section (`index.ts:~226`): add `PAYLOAD_PREFIX_READ_MORE` near the other prefix constants

</code_context>

<specifics>
## Specific Ideas

No specific UI references — standard Messenger truncation with a "Read more" quick reply is the established pattern for this type of feature.

</specifics>

<deferred>
## Deferred Ideas

None — user skipped discussion and all ideas stayed within phase scope.

</deferred>

---

*Phase: 8-Answer Truncation*
*Context gathered: 2026-05-19*
