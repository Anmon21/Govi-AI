---
phase: 06-bug-fixes-hardening
verified: 2026-05-16T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 06 Plan 01: DEBT Fixes & Hardening Verification Report

**Phase Goal:** Apply four surgical patches to messenger-bot/src/index.ts that eliminate tech debt items DEBT-01 through DEBT-04. No new features — only precise edits. Add a focused test file proving the routing fix, per-event catch isolation, and sanitized non-Axios log shape.
**Verified:** 2026-05-16
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Tapping the Messenger persistent menu 'Product Help' button (postback MENU_PRODUCT_HELP) shows the category quick-reply menu | VERIFIED | `index.ts` line 346: `if (event.postback?.payload === "MENU_PRODUCT_HELP") { await sendCategoryMenu(senderId); return; }`. Confirmed in correct ordering position (after MENU_CONTACT_HUMAN at line 341, before catch-all at line 356). Test A passes. |
| 2 | Tapping the Messenger persistent menu 'Main Menu' button (postback MENU_MAIN) shows the welcome message | VERIFIED | `index.ts` line 351: `if (event.postback?.payload === "MENU_MAIN") { await sendWelcomeMessage(senderId); return; }`. Confirmed in correct ordering position. Test B passes. |
| 3 | An exception thrown inside handleWebhookEvent for one event is caught — the bot process keeps running and the next event in the same batch is still processed | VERIFIED | `index.ts` lines 107–111: `try { await handleWebhookEvent(event); } catch (err: unknown) { console.error("handleWebhookEvent failed (unexpected):", err instanceof Error ? err.message : String(err)); }` wraps only the inner loop per-event call. `res.sendStatus(200)` at line 103 is before the outer loop at line 105. Test D passes: callCount === 2 after first event throws. |
| 4 | Starting the bot with FACEBOOK_VERIFY_TOKEN unset causes process exit code 1 before app.listen runs, with a readable stderr message | VERIFIED | `index.ts` lines 6–9: guard after `import "dotenv/config"` (line 1) and before `const app = express()` (line 11). Guard message: "FACEBOOK_VERIFY_TOKEN is not set — refusing to start. Configure it in messenger-bot/.env and restart." `process.exit(1)` at line 8. No PAGE_ACCESS_TOKEN guard present (per D-06 scope). `npx tsc --noEmit` exits 0. |
| 5 | Every non-Axios error branch in messenger-bot/src/index.ts logs a string (err.message or String(err)) — never the raw err object | VERIFIED | 8 occurrences of `err instanceof Error ? err.message : String(err)` confirmed (7 function else-branches + 1 in the DEBT-02 catch block). `grep -nE 'console.error\("[^"]*unexpected[^"]*", err\)'` returns zero non-override matches. Axios branches still log `err.message, err.response?.data` (7 instances confirmed). Test E passes: non-Error throw "plain-string-error" is logged as the string "plain-string-error". |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `messenger-bot/src/index.ts` | All four DEBT fixes; contains MENU_PRODUCT_HELP | VERIFIED | File exists, substantive (448 lines), all four patches present and wired to correct dispatch paths |
| `messenger-bot/src/tests/debt-fixes.test.ts` | Automated tests for DEBT-01, DEBT-02, DEBT-04; contains "DEBT-01" | VERIFIED | File exists (204 lines), 5 test() calls at top level, DEBT IDs present in comments and test names |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| handleWebhookEvent postback dispatcher | sendCategoryMenu / sendWelcomeMessage | `if (event.postback?.payload === 'MENU_PRODUCT_HELP')` and `'MENU_MAIN'` | WIRED | Lines 346–354 confirmed; ordering correct: after MENU_CONTACT_HUMAN (341), before catch-all (356) |
| POST /webhook inner for-loop | handleWebhookEvent | `try { await handleWebhookEvent(event) } catch { console.error(...sanitized...) }` | WIRED | Lines 107–111 confirmed; outer loop unwrapped; res.sendStatus(200) at line 103 precedes loop at line 105 |
| module top-level (after dotenv/config) | process.exit(1) | `if (!process.env.FACEBOOK_VERIFY_TOKEN) { console.error(...); process.exit(1); }` | WIRED | Lines 6–9 confirmed; appears after import at line 1 and before `const app = express()` at line 11 |

---

### Data-Flow Trace (Level 4)

Not applicable — this phase patches control-flow and error-handling behavior in an existing file. No new data-rendering artifacts were introduced.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 27 tests pass (5 new + 22 prior) | `cd messenger-bot && npm test` | 27 pass, 0 fail, 0 skip | PASS |
| TypeScript compiles clean | `cd messenger-bot && npx tsc --noEmit` | exit 0, no output | PASS |
| DEBT-01 routing: MENU_PRODUCT_HELP dispatches to sendCategoryMenu | Test A in npm test output | `DEBT-01: MENU_PRODUCT_HELP postback routes to sendCategoryMenu` — pass | PASS |
| DEBT-01 routing: MENU_MAIN dispatches to sendWelcomeMessage | Test B in npm test output | `DEBT-01: MENU_MAIN postback routes to sendWelcomeMessage` — pass | PASS |
| DEBT-02 isolation: Event 1 throw does not block Event 2 | Test D in npm test output | `DEBT-02: per-event catch isolation` — callCount === 2 asserted and pass | PASS |
| DEBT-04 sanitization: non-Error throw logged as string | Test E in npm test output | `DEBT-04: non-Error throw in sendMessage logs string` — pass | PASS |

---

### Probe Execution

No probes defined for this phase (`scripts/*/tests/probe-*.sh` not present). Skipped.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DEBT-01 | 06-01-PLAN.md | User persistent menu taps (MENU_PRODUCT_HELP, MENU_MAIN) are handled correctly by the postback dispatcher | SATISFIED | Lines 346–354 in index.ts; Tests A, B, C pass |
| DEBT-02 | 06-01-PLAN.md | Unhandled promise rejections from the webhook processing loop are caught and logged without crashing the bot | SATISFIED | Lines 107–111 in index.ts; Test D passes |
| DEBT-03 | 06-01-PLAN.md | Bot fails at startup with a clear error message if VERIFY_TOKEN is not set in the environment | SATISFIED | Lines 6–9 in index.ts; process.exit(1) before app.listen at line 444 |
| DEBT-04 | 06-01-PLAN.md | Error logging for non-Axios errors omits raw error objects to prevent accidental token leak | SATISFIED | 8 occurrences of sanitization pattern confirmed; Test E passes |

No orphaned requirements: REQUIREMENTS.md maps DEBT-01 through DEBT-04 exclusively to Phase 6. All four are accounted for.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | — |

No TBD, FIXME, or XXX markers found in either modified file. No placeholder return values detected. No raw error object logging remaining in non-Axios branches.

---

### Human Verification Required

None. All must-have truths are verifiable from source analysis and automated test execution. Persistent menu behavior on live Messenger (optional smoke test noted in the plan) is not a blocker for phase verification — the routing logic is proven by Tests A and B.

---

## Gaps Summary

No gaps. All five must-have truths are verified, all four DEBT requirement IDs are satisfied, both artifacts exist and are substantive and wired, all key links confirmed, 27/27 tests pass, TypeScript compiles clean, no debt markers remain.

---

_Verified: 2026-05-16_
_Verifier: Claude (gsd-verifier)_
