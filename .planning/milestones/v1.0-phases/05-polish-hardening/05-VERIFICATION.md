---
phase: 05-polish-hardening
verified: 2026-05-15T00:00:00Z
status: human_needed
score: 2/2 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Trigger a QUESTION quick reply from a real Messenger conversation on the live Page"
    expected: "A typing indicator (three animated dots) appears in the Messenger thread immediately after tapping the question button, then disappears when the answer text arrives"
    why_human: "Typing indicator visibility is a real-time Messenger UI behavior that cannot be observed from automated tests or code inspection — postCalls assertions verify the API calls fire in the correct order but cannot confirm the Facebook Graph API renders the indicator in the thread"
---

# Phase 05: Polish + Hardening Verification Report

**Phase Goal:** The bot feels responsive and the deployment is verified clean — ready to go live
**Verified:** 2026-05-15
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | When a customer selects a question, a typing indicator appears in the Messenger thread before the answer arrives — the bot does not appear frozen during the API fetch | VERIFIED (automated) | `sendTypingIndicator` exported at line 167 of `messenger-bot/src/index.ts`; `sendAnswer` calls `typing_on` as its first line (line 286) and `typing_off` in a `finally` block (line 303); all 22 tests pass including both POLISH-01 tests; `npm test` exits 0 |
| 2 | All environment variables are documented with example values and the bot starts cleanly from a fresh clone with only .env configuration | VERIFIED | `messenger-bot/.env.example` documents all 6 runtime vars with descriptive comment blocks; `PAGE_INBOX_APP_ID` appears as commented reference; `npx tsc --noEmit` exits 0; all 22 tests load and pass with env stubbed to PORT=0 |

**Score:** 2/2 truths verified (automated)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `messenger-bot/src/index.ts` | Exported `sendTypingIndicator` helper + `sendAnswer` wrapped with `typing_on` / try / finally `typing_off` | VERIFIED | `export async function sendTypingIndicator` present (line 167); `sender_action: action` in body (line 177); `typing_on` call at start of `sendAnswer` body (line 286); `finally` block with `typing_off` (lines 302-304) |
| `messenger-bot/src/tests/qa-flow.test.ts` | Updated QUESTION test assertion (`postCalls.length` 1 to 3, body at index 1) + new error-path test | VERIFIED | `postCalls.length, 3` appears twice (success path + error path); `postCalls[1].body?.message` referenced at lines 138, 184, 187; `sender_action === "typing_on"` and `sender_action === "typing_off"` assertions present; test `"qa-flow: sendAnswer typing_off fires even when API fetch fails"` at line 169 |
| `messenger-bot/.env.example` | 6 runtime vars with descriptive comments; `PAGE_INBOX_APP_ID` as commented reference | VERIFIED | All 6 vars present as uncommented live vars; `# PAGE_INBOX_APP_ID=263902037430900` comment present; HMAC mention in `FACEBOOK_APP_SECRET` comment; "degrade" mention in `ADMIN_PSID` comment; `http://localhost:8000` appears twice |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `sendAnswer` | `sendTypingIndicator` | `await sendTypingIndicator(recipientId, "typing_on")` before `axios.get`; `await sendTypingIndicator(recipientId, "typing_off")` in `finally` | WIRED | Confirmed at lines 286 and 303 of `index.ts`; `awk` on sendAnswer scope finds exactly 1 `finally` block |
| `sendTypingIndicator` | Facebook Graph API `/me/messages` | `axios.post` with `{ recipient: { id: recipientId }, sender_action: action }` body | WIRED | `sender_action: action` at line 177; same URL template as `sendMessage` |
| `sendTypingIndicator` error handler | SEC-03 logging pattern | `axios.isAxiosError` guard; logs only `err.message` and `err.response?.data` in Axios branch | WIRED | `axios.isAxiosError` present in `sendTypingIndicator` scope; `else` branch logs raw `err` only for non-Axios unknowns (identical pattern to `sendMessage` and `passThreadControl` — non-Axios errors cannot contain `config.url` with `PAGE_ACCESS_TOKEN`) |
| `qa-flow.test.ts` QUESTION test | `sendAnswer` typing behavior | `withAxiosStubs` captures all `axios.post` calls; ordering asserted via `postCalls[0].body?.sender_action === "typing_on"` and `postCalls[2].body?.sender_action === "typing_off"` | WIRED | `postCalls` captures both typing indicator POSTs and the answer sendMessage POST; assertions at lines 136-137 of test file |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `sendTypingIndicator` | `action` param | TypeScript narrowed literal union `"typing_on" \| "typing_off"` — passed by caller | Yes — compiler-enforced, no user input reaches the Graph API body | FLOWING |
| `sendAnswer` | `body` from vault response | `axios.get(\`${GOVI_AI_URL}/content/${questionId}\`)` → `response.data?.body` | Yes — live FastAPI vault fetch; empty-body guard triggers apology path | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 22 tests pass (including both POLISH-01 tests) | `cd messenger-bot && npm test` | `ℹ tests 22 · ℹ pass 22 · ℹ fail 0 · ℹ skipped 0` | PASS |
| TypeScript strict compile clean | `cd messenger-bot && npx tsc --noEmit` | exit 0 | PASS |
| `sendTypingIndicator` exported | `grep -c 'export async function sendTypingIndicator' messenger-bot/src/index.ts` | 1 | PASS |
| `typing_on` is first call in `sendAnswer` body | `grep -A1 'async function sendAnswer' index.ts \| grep -c sendTypingIndicator` | 1 | PASS |
| No artificial delays | `grep -c 'setTimeout' messenger-bot/src/index.ts` | 0 | PASS |
| `sendCategoryMenu` and `sendQuestionMenu` not modified | `awk` scope grep for `sendTypingIndicator` in each | 0 each | PASS |
| `PAGE_INBOX_APP_ID` commented reference present | `grep -c '^# PAGE_INBOX_APP_ID=263902037430900' messenger-bot/.env.example` | 1 | PASS |
| `PAGE_INBOX_APP_ID` is not a live env var | `grep -v '^#' .env.example \| grep -c '^PAGE_INBOX_APP_ID='` | 0 | PASS |

### Probe Execution

Step 7c: SKIPPED — no `scripts/*/tests/probe-*.sh` files exist in this project; phase is a Messenger bot feature addition, not a migration/tooling phase.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| POLISH-01 | 05-01-PLAN.md, 05-02-PLAN.md | Bot shows a typing indicator (typing_on action) while fetching answers from the FastAPI content API | SATISFIED | `sendTypingIndicator` implemented and wired into `sendAnswer`; marked `[x]` in REQUIREMENTS.md; both TDD RED tests turned GREEN; 22/22 pass |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | — | — | — |

Scanned: `messenger-bot/src/index.ts`, `messenger-bot/src/tests/qa-flow.test.ts`, `messenger-bot/.env.example`. No TBD, FIXME, XXX, placeholder stubs, hardcoded empty returns in functional paths, or bare-err logging in Axios error branches.

Note: The `else` branch in `sendTypingIndicator`'s catch block logs `err` directly (`console.error("sendTypingIndicator failed (unexpected error):", err)`). This is the established SEC-03 pattern used identically in `sendMessage` (line 139) and `passThreadControl` (line 162). Non-Axios errors cannot carry `config.url` containing `PAGE_ACCESS_TOKEN`, so this is not a token leak.

### Human Verification Required

#### 1. Typing Indicator Visible in Live Messenger Thread

**Test:** With the bot deployed and connected to a real Facebook Page, trigger any question flow. Tap "Product Help" → pick a category → tap a question.

**Expected:** A typing indicator (the three animated dots) appears in the customer's Messenger thread immediately after the question is tapped. The indicator remains visible while the bot fetches the answer from the FastAPI backend. When the answer message arrives, the indicator disappears automatically.

**Why human:** The typing indicator is a real-time Messenger UI element rendered by the Facebook client upon receiving a `sender_action: typing_on` POST to the Graph API. Automated tests (via `withAxiosStubs`) confirm the three POSTs fire in the correct order (`typing_on` → `sendMessage` → `typing_off`), but cannot verify that the Facebook Graph API accepts the requests and that the Messenger mobile/web client renders the indicator visually. This requires a live Facebook Page with real credentials and a real device or web client.

### Gaps Summary

No gaps. All must-haves are VERIFIED in the codebase. The single outstanding item is a human test to confirm the typing indicator renders in a live Messenger thread — this cannot be verified programmatically and was explicitly called out in the PLAN's `<verification>` section and in `05-VALIDATION.md` as a follow-up checkpoint.

---

_Verified: 2026-05-15_
_Verifier: Claude (gsd-verifier)_
