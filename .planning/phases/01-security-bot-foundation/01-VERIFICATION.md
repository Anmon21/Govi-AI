---
phase: 01-security-bot-foundation
verified: 2026-05-14T00:00:00Z
status: human_needed
score: 5/5
overrides_applied: 0
human_verification:
  - test: "Send a POST to /webhook with an invalid X-Hub-Signature-256 header from outside the process"
    expected: "HTTP 403 is returned and the body is not processed"
    why_human: "The unit tests verify verifySignature logic in-process. A live curl against the running bot with a real forged payload is the only end-to-end confirmation that express.raw + verifySignature chain returns 403 over the network."
  - test: "Open Messenger as a new user, click Get Started on the bot Page"
    expected: "Welcome message received with at least one quick-reply navigation button visible"
    why_human: "Requires a live Facebook App bound to the Page, ngrok or equivalent tunnel, and a Messenger client. Cannot verify the Facebook-side rendering of quick replies programmatically."
  - test: "Tap the hamburger (persistent menu) icon in Messenger"
    expected: "Three top-level options appear: Product Help, Contact Human, Main Menu"
    why_human: "Persistent menu is configured via setupMessengerProfile() posting to Facebook's servers at startup. Whether Facebook accepted the configuration and is rendering it requires a live Page and Messenger client."
  - test: "Type free text into the bot (e.g., 'hello')"
    expected: "A re-anchor message appears with quick-reply buttons; the bot does not go silent"
    why_human: "Requires live Messenger session. Verifiable in-process by unit test, but the actual message rendering in Messenger needs human eye-check."
  - test: "Trigger a Graph API send failure (e.g., temporarily use an invalid PAGE_ACCESS_TOKEN) and inspect process stdout/stderr"
    expected: "The log shows 'sendMessage failed: <error message>' with no occurrence of the PAGE_ACCESS_TOKEN value"
    why_human: "Unit test SEC-03 verifies this programmatically. Human confirmation with a real token in a real failure is best practice before sign-off on the PAGE_ACCESS_TOKEN does not appear in log output criterion."
---

# Phase 1: Security + Bot Foundation — Verification Report

**Phase Goal:** The bot skeleton is secure and structurally complete — customers can open the bot, see a welcome message, navigate the persistent menu, and never get a silent dead end.
**Verified:** 2026-05-14
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Sending a forged POST to /webhook returns 403 — the bot does not process it | VERIFIED | `verifySignature` at line 23 uses `crypto.timingSafeEqual` (line 46); returns `res.sendStatus(403)` on mismatch or missing header (lines 35, 49); unit test "verifySignature: invalid signature returns 403" passes (npm test: 10/10 green) |
| 2 | A new user who clicks Get Started receives a welcome message with navigation quick replies | VERIFIED | `handleWebhookEvent` (line 147) dispatches `GET_STARTED` postback to `sendWelcomeMessage` (line 152); `sendWelcomeMessage` calls `sendMessage` with `MAIN_MENU_QUICK_REPLIES` (lines 131-136); 2 quick-reply entries confirmed at lines 127-129; unit tests "GET_STARTED postback invokes sendWelcomeMessage" and "sendWelcomeMessage call includes quick_replies" both pass |
| 3 | A user who types free text receives a re-anchor message — the bot never goes silent | VERIFIED | `handleWebhookEvent` dispatches `event.message?.text` to `sendFallbackMessage` (lines 168-172); fallback text is exact D-01 copy "I work best with the buttons below — here's what I can help with:" (line 142); unit test "free text triggers sendFallbackMessage" passes; quick_reply branch at line 162 is checked before text branch at line 168 (PITFALL-6 guard confirmed by awk check: lines 162 vs 168) |
| 4 | A user can open the persistent hamburger menu and see top-level navigation options at any time | VERIFIED | `setupMessengerProfile` (line 177) posts 3 call_to_actions to Graph API: "Product Help" (12 chars), "Contact Human" (13 chars), "Main Menu" (9 chars) — all ≤20 chars; `get_started.payload = "GET_STARTED"`; `composer_input_disabled: false` (line 192); called fire-and-forget from `app.listen` callback at line 213; unit test "setupMessengerProfile posts get_started + persistent_menu" passes |
| 5 | A Graph API send failure is logged with message and response data — PAGE_ACCESS_TOKEN does not appear in any log output | VERIFIED | All three catch blocks in index.ts log only `axiosErr.message` and `axiosErr.response?.data` — never the full AxiosError object (lines 122, 206); SEC-03 unit test asserts token "secret123" is absent from logs while `err.message` is present; grep for `console.error(..., err)` bare patterns returns 0 matches |

**Score:** 5/5 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `messenger-bot/src/index.ts` | Full bot skeleton: HMAC, Graph API error detection, welcome/fallback/setup handlers | VERIFIED | 215 lines; all 9 required exports present; no stubs or placeholder returns |
| `messenger-bot/src/tests/hmac.test.ts` | SEC-01 unit tests — valid HMAC, invalid HMAC, missing APP_SECRET | VERIFIED | 3 tests, all passing |
| `messenger-bot/src/tests/sendMessage.test.ts` | SEC-02 + SEC-03 unit tests | VERIFIED | 2 tests, all passing |
| `messenger-bot/src/tests/handlers.test.ts` | CORE-01, CORE-03, CORE-04 unit tests | VERIFIED | 4 tests, all passing |
| `messenger-bot/src/tests/setup.test.ts` | CORE-02 unit test | VERIFIED | 1 test, passing |
| `messenger-bot/.env.example` | Documents FACEBOOK_APP_SECRET | VERIFIED | Line 4: `FACEBOOK_APP_SECRET=your_app_secret_here` with comment on line 3 |
| `.gitignore` | node_modules/ and messenger-bot/node_modules/ excluded | VERIFIED | Lines 13-14; `git ls-files messenger-bot/node_modules` returns 0 rows |
| `messenger-bot/package.json` | `test` script invoking node --test with ts-node loader | VERIFIED | `"node --test-force-exit --test --require ts-node/register src/tests/*.test.ts"` |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app.post("/webhook", ...)` | `verifySignature` middleware | `express.raw({ type: "*/*" }), verifySignature` route-level middleware chain | WIRED | Lines 73-75: `express.raw({ type: "*/*" })` + `verifySignature` both in the middleware array before the handler |
| `verifySignature` | `crypto.timingSafeEqual` | Node.js built-in HMAC comparison | WIRED | Line 46: `crypto.timingSafeEqual(expectedBuf, signatureBuf)` with length pre-check at line 45 |
| `sendMessage` catch block | `console.error(message, response?.data)` | Destructured AxiosError fields only | WIRED | Line 122: `console.error("sendMessage failed:", axiosErr.message, axiosErr.response?.data)` |
| `sendMessage` axios.post target | `https://graph.facebook.com/v21.0/me/messages` | Template literal via `GRAPH_API_VERSION` constant | WIRED | Line 105: template literal using `GRAPH_API_VERSION = "v21.0"` (line 95); no v19.0 reference remains |
| `app.listen` callback | `setupMessengerProfile()` | Fire-and-forget call after Express binds | WIRED | Line 213: `setupMessengerProfile()` inside the `app.listen` callback (line 211) |
| `setupMessengerProfile` | `POST /me/messenger_profile` | axios.post with PAGE_ACCESS_TOKEN query param | WIRED | Line 179-201: `axios.post` with full payload including `get_started`, `greeting`, `persistent_menu` |
| `event dispatcher` | `sendWelcomeMessage` / `sendFallbackMessage` | `GET_STARTED` postback OR `message.text` (with quick_reply guard) | WIRED | Lines 151-173: postback dispatch at 151, quick_reply guard at 162, text fallback at 168 — correct order |
| `sendWelcomeMessage` / `sendFallbackMessage` | `sendMessage(recipient, text, MAIN_MENU_QUICK_REPLIES)` | Shared quick-reply constant | WIRED | Lines 132-136 and 140-144: both functions pass `MAIN_MENU_QUICK_REPLIES` as third arg |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `sendMessage` | `quickReplies` | Caller-provided `MAIN_MENU_QUICK_REPLIES` constant | Yes — 2-item array defined at lines 126-129 | FLOWING |
| `setupMessengerProfile` | Persistent menu payload | Hardcoded literal in function body (lines 191-197) | Yes — 3 postback actions, titles checked ≤20 chars | FLOWING |
| `verifySignature` | `parsedBody` | `JSON.parse(rawBody.toString("utf8"))` at lines 27 and 53 | Yes — raw Buffer from `express.raw` is parsed | FLOWING |
| POST handler | `body` | `(req as any).parsedBody` at line 77 | Yes — populated by `verifySignature` after HMAC check | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 10 unit tests pass | `cd messenger-bot && npm test` | exit 0; 10 pass, 0 fail, 0 skip, 0 cancelled | PASS |
| TypeScript strict build compiles | `cd messenger-bot && npm run build` | exit 0 (tsc; no output = clean) | PASS |
| quick_reply branch before text branch | `awk` order check | quick_reply line 162, text line 168; order_correct: 1 | PASS |
| No bare err in console.error calls | `grep -E "console\.error\([^,]*,\s*err\s*\)"` | 0 matches | PASS |
| No /ai/chat in index.ts | `grep -c "/ai/chat"` | 0 | PASS |
| No v19.0 Graph API URL | `grep -c "graph.facebook.com/v19"` | 0 | PASS |

---

## Probe Execution

No probes declared in PLAN files. Step 7c: no conventional probe scripts found under `scripts/*/tests/`. Phase does not declare probe-based verification — skipped.

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SEC-01 | 01-02-PLAN | Webhook verifies X-Hub-Signature-256 HMAC before processing any incoming event | SATISFIED | `verifySignature` function with `crypto.createHmac` + `crypto.timingSafeEqual`; express.raw + middleware chain wired; 3 unit tests green |
| SEC-02 | 01-02-PLAN | Bot detects and logs Graph API errors returned inside HTTP 200 responses | SATISFIED | `response.data?.error` check at line 116; `console.error("Graph API error:", ...)` at line 117; unit test green |
| SEC-03 | 01-02-PLAN | Application logs never contain PAGE_ACCESS_TOKEN or other secrets | SATISFIED | All 3 catch blocks use `axiosErr.message` + `axiosErr.response?.data` only (lines 122, 206); unit test verifies token absent from logs |
| CORE-01 | 01-03-PLAN | User sees welcome message with navigation options on Get Started postback | SATISFIED | `handleWebhookEvent` dispatches `GET_STARTED` to `sendWelcomeMessage`; unit test green |
| CORE-02 | 01-03-PLAN | User can access persistent hamburger menu at any time (max 3 items) | SATISFIED | `setupMessengerProfile` posts 3-item `call_to_actions`; called at startup; unit test verifies structure; NEEDS HUMAN for live Messenger verification |
| CORE-03 | 01-03-PLAN | User navigates all flows via quick reply buttons — no free-text input required | SATISFIED | Both `sendWelcomeMessage` and `sendFallbackMessage` pass `MAIN_MENU_QUICK_REPLIES` (2 items); unit tests verify presence and `content_type: "text"` |
| CORE-04 | 01-03-PLAN | User sees helpful re-anchor message with menu options when typing free text | SATISFIED | `handleWebhookEvent` dispatches `message.text` to `sendFallbackMessage` with quick-reply guard; PITFALL-6 dispatch order verified; unit tests green |

All 7 Phase 1 requirement IDs accounted for. No orphaned requirements.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `messenger-bot/src/index.ts` | 176 | Comment: "placeholders per D-05 — user may adjust before go-live" | Info | Not a stub — the setupMessengerProfile function is fully implemented with real axios.post calls and correct payload. The comment refers to copy/text content (welcome message text and menu labels) being placeholder copy, not to the code being incomplete. The D-05 decision explicitly authorizes this. No remediation needed. |

No TBD, FIXME, or XXX markers found in any modified file. No debt markers without issue references.

---

## Human Verification Required

### 1. Live Forged POST Returns 403

**Test:** With the bot running locally (`npm run dev`) and exposed via ngrok or equivalent, send: `curl -X POST https://<tunnel>/webhook -H "X-Hub-Signature-256: sha256=invalidsignaturehere" -H "Content-Type: application/json" -d '{"object":"page"}'`
**Expected:** HTTP 403 response; nothing processed; no message sent
**Why human:** Unit test verifies the verifySignature function in-process. Network-level 403 through the Express stack requires a running server.

### 2. Get Started Welcome in Messenger

**Test:** As a new user (or one who has reset conversation), open the bot's Messenger conversation and click "Get Started"
**Expected:** A welcome message arrives with at least 2 quick-reply buttons (Product Help, Contact Human) visible in the Messenger interface
**Why human:** Facebook-side button rendering cannot be verified without a live Messenger session with a properly configured Page.

### 3. Persistent Menu Visible in Messenger

**Test:** Open an active Messenger conversation with the bot and tap the hamburger/plus icon
**Expected:** Three menu items appear: "Product Help", "Contact Human", "Main Menu"
**Why human:** Menu visibility depends on whether Facebook's servers accepted the `setupMessengerProfile` call. The bot must have started with a valid `PAGE_ACCESS_TOKEN` for the call to succeed. The unit test verifies payload structure only.

### 4. Free Text Fallback in Live Messenger

**Test:** In an active Messenger conversation, type any free-form message (e.g., "what products do you have?")
**Expected:** The bot replies with "I work best with the buttons below — here's what I can help with:" and shows the quick-reply buttons. No silent no-response.
**Why human:** Requires live Messenger session to verify end-to-end message delivery.

### 5. PAGE_ACCESS_TOKEN Absent From Logs on Send Failure

**Test:** Temporarily replace `FACEBOOK_PAGE_ACCESS_TOKEN` in `messenger-bot/.env` with an invalid value, start the bot, trigger a message send (e.g., via a real Get Started postback), and inspect stdout/stderr
**Expected:** Log line contains "sendMessage failed: <error description>" with no occurrence of the invalid token value
**Why human:** The unit test verifies this pattern with a mocked axios. Real Graph API rejection with an actual token in the URL is the strongest evidence for SEC-03.

---

## Gaps Summary

No gaps found. All 5 phase success criteria are verified in the codebase with substantive, wired, and data-flowing implementations. The npm test suite runs 10 tests, all passing (0 skipped, 0 failed). TypeScript strict build is clean.

The 5 human verification items above are standard live-environment checks that cannot be automated without a Facebook app and tunnel. They do not indicate code defects — they confirm the code works end-to-end in the production environment.

---

_Verified: 2026-05-14_
_Verifier: Claude (gsd-verifier)_
