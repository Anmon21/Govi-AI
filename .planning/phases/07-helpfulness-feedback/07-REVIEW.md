---
phase: 07-helpfulness-feedback
reviewed: 2026-05-18T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - messenger-bot/src/index.ts
  - messenger-bot/src/tests/feedback.test.ts
  - messenger-bot/src/tests/qa-flow.test.ts
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 07: Code Review Report

**Reviewed:** 2026-05-18
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Phase 7 adds feedback quick replies (thumbs-up/down via `HELPFUL_YES`/`HELPFUL_NO` payloads) after every Q&A answer, a thank-you re-anchor path, and HELPFUL_NO escalation. It also adds missing postback handlers for `MENU_PRODUCT_HELP` and `MENU_MAIN`, hardens all `catch` blocks to use `err.message` instead of the raw error object, adds a `FACEBOOK_VERIFY_TOKEN` startup guard, and wraps the event-dispatch loop in a top-level try/catch.

The core feature logic is correct: `sendAnswer` now attaches `FEEDBACK_QUICK_REPLIES`, the `HELPFUL_YES`/`HELPFUL_NO` dispatcher works, and test coverage for both paths is present. Three warnings were found — two are quality gaps introduced by this phase, one is a stale test name. Three info items are pre-existing noise that the phase did not create but left unaddressed.

No security vulnerabilities or correctness blockers were found in the new code.

---

## Warnings

### WR-01: `FACEBOOK_PAGE_ACCESS_TOKEN` has no startup guard — inconsistent with the `VERIFY_TOKEN` guard added this phase

**File:** `messenger-bot/src/index.ts:6-14`

**Issue:** This phase added a hard startup guard for `FACEBOOK_VERIFY_TOKEN` (lines 6-9, `process.exit(1)` if absent). `FACEBOOK_PAGE_ACCESS_TOKEN` is declared on line 14 with a TypeScript non-null assertion (`!`) but receives no equivalent runtime guard. If `FACEBOOK_PAGE_ACCESS_TOKEN` is absent at startup, all Graph API calls silently emit `?access_token=undefined` in the URL. The first `sendMessage` call will receive a 400/403 from the Graph API, which is caught and swallowed, leaving the user with no response and the operator with no startup error. The two required tokens are now inconsistently guarded.

**Fix:**
```typescript
if (!process.env.FACEBOOK_VERIFY_TOKEN) {
  console.error("FACEBOOK_VERIFY_TOKEN is not set — refusing to start. Configure it in messenger-bot/.env and restart.");
  process.exit(1);
}
if (!process.env.FACEBOOK_PAGE_ACCESS_TOKEN) {
  console.error("FACEBOOK_PAGE_ACCESS_TOKEN is not set — refusing to start. Configure it in messenger-bot/.env and restart.");
  process.exit(1);
}
```

---

### WR-02: `PAYLOAD_HELPFUL_YES` and `PAYLOAD_HELPFUL_NO` constants are exported but never referenced

**File:** `messenger-bot/src/index.ts:226-227`

**Issue:** The two named constants are exported but the `handleWebhookEvent` dispatcher (lines 400 and 408) uses bare string literals `"HELPFUL_YES"` and `"HELPFUL_NO"` for comparison. The constants and the literals can silently diverge if one is changed without updating the other. Neither the tests nor any other file imports these constants.

**Fix:** Either use the constants in the dispatcher:
```typescript
if (payload === PAYLOAD_HELPFUL_YES) {
if (payload === PAYLOAD_HELPFUL_NO) {
```
Or remove the constants entirely since nothing consumes them.

---

### WR-03: Stale test name in `qa-flow.test.ts` says "main menu re-anchor" after being updated to assert `FEEDBACK_QUICK_REPLIES`

**File:** `messenger-bot/src/tests/qa-flow.test.ts:121`

**Issue:** The test was originally named `"qa-flow: QUESTION:<id> triggers sendAnswer with body text and main menu re-anchor"`. This phase updated the assertion on line 145 to check `FEEDBACK_QUICK_REPLIES` instead of `MAIN_MENU_QUICK_REPLIES`, which is correct — but the test name still says "main menu re-anchor". When this test fails in future, the name will point engineers toward the wrong behavior.

**Fix:**
```typescript
test("qa-flow: QUESTION:<id> triggers sendAnswer with body text and FEEDBACK_QUICK_REPLIES", async (t) => {
```

---

## Info

### IN-01: `verifySignature` emits the "not set" warning on every incoming request, not just at startup

**File:** `messenger-bot/src/index.ts:17-18, 30`

**Issue:** Lines 17-18 emit one warn at module load time. Lines 30-31 emit the identical message again inside `verifySignature`, which runs on every `POST /webhook`. Production deployments without `FACEBOOK_APP_SECRET` will flood logs with this message at request rate.

**Fix:** Remove the per-request warn (lines 30-31) and rely solely on the startup warn, or promote the startup warn to `process.exit(1)` like the other token guards.

---

### IN-02: Misleading log label when webhook signature header is absent

**File:** `messenger-bot/src/index.ts:45`

**Issue:** When the `x-hub-signature-256` header is entirely missing, the log says `"Webhook signature mismatch"`. A missing header is not a mismatch — it is a missing header. This makes it harder to distinguish replay/tamper attacks (actual mismatch) from misconfigured clients or load-balancer stripping.

**Fix:**
```typescript
if (!signature) {
  console.warn("Webhook signature header absent — request rejected");
  res.sendStatus(403);
  return;
}
```

---

### IN-03: `sendCategoryMenu` truncates to 13 items with no navigation escape hatch

**File:** `messenger-bot/src/index.ts:252`

**Issue:** `sendQuestionMenu` defensively slices to 12 and appends a "Main menu" quick reply when items exceed 12, so total never exceeds 13 and the user always has an exit. `sendCategoryMenu` slices directly to 13 with no escape hatch. If there are 13 or more categories, the user cannot navigate away — the 13th slot that could carry "Main Menu" is consumed by a category entry. This is an asymmetric UX trap. (Pre-existing issue, not introduced by Phase 7, but noted for completeness.)

**Fix:** Mirror `sendQuestionMenu`'s pattern:
```typescript
const quickReplies: QuickReply[] = items.slice(0, 12).map((item) => ({
  content_type: "text",
  title: item.title,
  payload: `${PAYLOAD_PREFIX_CATEGORY}${item.id}`,
}));
if (items.length > 12) {
  quickReplies.push({ content_type: "text", title: "Main menu", payload: "MENU_MAIN" });
}
```

---

_Reviewed: 2026-05-18_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
