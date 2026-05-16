# Phase 6: Bug Fixes & Hardening - Context

**Gathered:** 2026-05-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Eliminate four v1.0 tech debt items in `messenger-bot/src/index.ts` so the bot handles persistent menu postbacks correctly, survives async failures in the webhook loop, fails loudly at startup if VERIFY_TOKEN is missing, and never leaks auth tokens through raw error objects in logs. No new user-facing features — pure hardening.

</domain>

<decisions>
## Implementation Decisions

### DEBT-01: Postback Routing Fix
- **D-01:** Surgical patch — add `MENU_PRODUCT_HELP` and `MENU_MAIN` if-checks inside `handleWebhookEvent` before the existing catch-all postback block. No refactor to a dispatch function.
- **D-02:** Unknown postback payloads → keep current behavior: log `"Postback received: [payload]"` and silently drop. No fallback message sent.

### DEBT-02: Async Failure Handling
- **D-03:** Wrap each individual `await handleWebhookEvent(event)` call in a try/catch (inner loop, per-event isolation) — one event failure cannot block later events in the same Facebook batch.
- **D-04:** Catch action: log and continue. No user notification — matches the silent-error pattern already established in `sendMessage`/`passThreadControl`.
- **D-05:** The catch block MUST use the same safe-logging pattern as DEBT-04 (see D-07) — no raw error objects in webhook catch either.

### DEBT-03: Startup Validation
- **D-06:** Guard `VERIFY_TOKEN` only (exact DEBT-03 scope — `PAGE_ACCESS_TOKEN` excluded). Placement: after `dotenv/config` import, before any app setup. Failure mode: `process.exit(1)` with `console.error` and a clear human-readable message.

### DEBT-04: Error Log Sanitization
- **D-07:** All non-Axios error branches replace `console.error("...", err)` with `console.error("...", err instanceof Error ? err.message : String(err))`. This covers every existing `else` branch in `sendMessage`, `passThreadControl`, `sendTypingIndicator`, `sendCategoryMenu`, `sendQuestionMenu`, `sendAnswer`, and `setupMessengerProfile` — plus the new DEBT-02 catch block.

### Claude's Discretion
- Catch scope for DEBT-02: Claude chose per-event try/catch (inner loop) over wrapping the full entry/messaging for-loops — rationale: Facebook batches multiple events and per-event isolation is more resilient.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary Source File
- `messenger-bot/src/index.ts` — the single file all four DEBT fixes land in

### Requirements
- `.planning/REQUIREMENTS.md` §DEBT-01 through DEBT-04 — the exact acceptance criteria for each debt item

### Phase Goal
- `.planning/ROADMAP.md` §Phase 6 — success criteria and phase dependencies

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `handleWebhookEvent` (index.ts:~300): the async function that processes each Messenger event — DEBT-01 fix goes inside the `if (event.postback)` block; DEBT-02 catch wraps its call site in the POST handler loop
- `verifySignature` middleware (index.ts:~22): already in place; DEBT fixes don't touch it
- `axios.isAxiosError(err)` guard pattern: already used consistently in `sendMessage`, `passThreadControl`, `sendTypingIndicator`, `sendCategoryMenu`, `sendQuestionMenu`, `sendAnswer`, `setupMessengerProfile` — DEBT-04 modifies the `else` branch of each

### Established Patterns
- Error logging convention: `console.error("functionName failed:", err.message, err.response?.data)` for Axios errors — DEBT-04 makes the non-Axios branch equally safe
- Silent error recovery: failed helper functions log + recover silently (no process crash) — DEBT-02 extends this pattern to the webhook event loop itself

### Integration Points
- POST `/webhook` handler (index.ts): res.sendStatus(200) is sent before the event loop — DEBT-02 catch must not interfere with this already-acknowledged response
- `setupMessengerProfile` (index.ts): also has a non-Axios else branch — DEBT-04 covers it too

</code_context>

<specifics>
## Specific Ideas

No specific references — all four fixes are surgical patches to existing code following established patterns.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 6-Bug Fixes & Hardening*
*Context gathered: 2026-05-16*
