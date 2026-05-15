---
phase: 04-human-escalation
verified: 2026-05-15T03:30:00Z
status: human_needed
score: 7/7 must-haves verified (automated); 3/3 manual items pending human sign-off
overrides_applied: 0
re_verification: false
human_verification:
  - test: "Thread control transfers to Page inbox (ESC-03 live)"
    expected: "After tapping Contact Human, the customer thread appears in the Facebook Page inbox and the admin can type a reply that the customer receives in Messenger"
    why_human: "Requires live Facebook Page configured with Primary/Secondary Receiver Handover Protocol and a real ADMIN_PSID; cannot be validated by grep or unit tests"
  - test: "Admin receives Messenger notification with last-message context (ESC-02 / ESC-04 live)"
    expected: "Admin's personal Messenger receives a message containing the customer's last free-text message substring (e.g. 'Last message: \"what colour is the medium tote\"')"
    why_human: "Requires live ADMIN_PSID set in .env, live bot running, and a real Messenger account to observe the notification"
  - test: "Soft-fail verified live with ADMIN_PSID unset (SC-4 live)"
    expected: "Bot logs 'ADMIN_PSID not configured — escalation degraded'; customer receives 'We'll be in touch' message; thread stays bot-owned (no Page inbox transfer)"
    why_human: "Live server restart with .env change needed to confirm no crash and no passThreadControl call in a real webhook context"
---

# Phase 4: Human Escalation Verification Report

**Phase Goal:** A customer who wants human help can request it from any screen; the admin receives a Messenger notification with context and the thread transfers to the Page inbox
**Verified:** 2026-05-15T03:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | "Contact Human" is available from main menu and any Q&A screen; tapping it triggers escalation | VERIFIED | `MAIN_MENU_QUICK_REPLIES` array contains `MENU_CONTACT_HUMAN` quick reply (line 186). `handleWebhookEvent` wires `MENU_CONTACT_HUMAN` in the quick_reply branch (line 329) AND the postback branch (line 306). Both call `await handleEscalation(senderId)`. ESC-01 tests (2 tests) pass. |
| 2 | After escalation, admin receives a Messenger message that includes the customer's last message as context | VERIFIED (automated) / PENDING (live) | `handleEscalation` reads `lastMessageCache.get(senderId)` and builds `contextLine = \`\nLast message: "${lastMessage}"\`` (line 177). Admin message sent via `sendMessage(adminPsid, ...)` (line 178). ESC-02 and ESC-04 unit tests pass. Live Messenger delivery requires human confirmation. |
| 3 | After escalation, customer's thread appears in Page inbox and accepts admin replies | PENDING (human only) | `passThreadControl` posts `{ recipient: { id }, target_app_id: "263902037430900" }` to `https://graph.facebook.com/v21.0/me/pass_thread_control` (lines 144-165). ESC-03 unit test passes. Thread-appearing-in-Page-inbox and admin-can-reply cannot be automated. |
| 4 | If ADMIN_PSID not configured, escalation fails gracefully with "we'll be in touch" and no crash | VERIFIED | `handleEscalation` reads `process.env.ADMIN_PSID` dynamically (line 169); `if (!adminPsid)` guard (line 171) emits `console.warn("ADMIN_PSID not configured — escalation degraded")`, sends customer "Thanks for reaching out! We'll be in touch as soon as possible." (line 173), and returns without calling `passThreadControl`. Soft-fail unit test passes with `assert.strictEqual(passThreadCalls.length, 0)`. |

**Automated Score:** 7/7 truths verified (4 truths, all automated-verifiable aspects confirmed; 3 live-Messenger aspects pend human)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `messenger-bot/src/index.ts` | PAGE_INBOX_APP_ID, lastMessageCache, passThreadControl, handleEscalation; wired MENU_CONTACT_HUMAN | VERIFIED | All 4 exports present. `export const PAGE_INBOX_APP_ID = "263902037430900"` (line 109). `export const lastMessageCache = new Map<string, string>()` (line 110). `export async function passThreadControl` (line 144). `export async function handleEscalation` (line 167). MENU_CONTACT_HUMAN wired at lines 306-309 (postback) and 329-332 (quick_reply). |
| `messenger-bot/src/tests/escalation.test.ts` | 7 test cases for ESC-01/02/03/04 and soft-fail | VERIFIED | File exists with 7 tests, all passing (21 total, 0 skipped, 0 failed as of npm test run). |
| `messenger-bot/.env.example` | ADMIN_PSID documented with discovery-instructions comment | VERIFIED | Line 5-6: comment `# ADMIN_PSID — Page-Scoped ID of the admin's Messenger account; have the admin message the Page once and read the [senderId] from the bot log`. Line 6: `ADMIN_PSID=your_admin_psid_here`. All 5 pre-existing keys intact. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `handleWebhookEvent` quick_reply branch (`MENU_CONTACT_HUMAN`) | `handleEscalation(senderId)` | `await handleEscalation(senderId)` at line 330 | WIRED | Quick_reply branch checks `payload === "MENU_CONTACT_HUMAN"` and calls `await handleEscalation(senderId); return;` |
| `handleWebhookEvent` postback branch (`MENU_CONTACT_HUMAN`) | `handleEscalation(senderId)` | `event.postback?.payload === "MENU_CONTACT_HUMAN"` at line 306 | WIRED | New postback branch at line 306-309, before the catch-all generic postback log at line 311-314 — correct ordering confirmed |
| `handleWebhookEvent` free-text branch | `lastMessageCache.set(senderId, ...)` | single `set()` call at line 354, inside `if (event.message?.text)` block | WIRED | `lastMessageCache.set` appears exactly once (line 354), inside the free-text branch AFTER the quick_reply branch exits with `return;`. Quick_reply labels never corrupt the cache. |
| `handleEscalation` | admin notification + customer confirm + `passThreadControl` | ordered awaits: admin notify (line 178) → customer confirm (line 180) → passThreadControl (line 181) | WIRED + ORDERED | Customer confirmation on line 180 precedes `passThreadControl(senderId)` on line 181 — Pitfall 1 ordering satisfied. |
| `passThreadControl` | `https://graph.facebook.com/v21.0/me/pass_thread_control` | `axios.post` with `target_app_id: PAGE_INBOX_APP_ID` | WIRED | URL at line 147. Body at lines 148-151: `{ recipient: { id: recipientId }, target_app_id: PAGE_INBOX_APP_ID }`. |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `handleEscalation` — admin notification body | `lastMessage` from `lastMessageCache.get(senderId)` | `lastMessageCache.set(senderId, event.message.text)` in free-text branch (line 354) | Yes — set from actual Messenger event text before escalation is triggered | FLOWING |
| `passThreadControl` | `PAGE_INBOX_APP_ID` | Hardcoded constant `"263902037430900"` (canonical Page Inbox app ID, not dynamic) | N/A — intentionally static per Facebook Handover Protocol spec | FLOWING (by design) |
| `handleEscalation` — soft-fail guard | `adminPsid = process.env.ADMIN_PSID` | Read dynamically inside function body (not captured at module load) — correct for test env-mutation compatibility | Yes — reads live env at call time | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| ESC-01: MENU_CONTACT_HUMAN quick_reply routes to handleEscalation | `npm test` (ESC-01 quick_reply test) | PASS — admin ADM_1 and customer USR_ESC_1 both appear in axios.post calls; no fallback text | PASS |
| ESC-01: MENU_CONTACT_HUMAN postback routes to handleEscalation | `npm test` (ESC-01 postback test) | PASS — admin ADM_1 and customer USR_ESC_2 both appear in axios.post calls | PASS |
| ESC-02: admin notification posted to ADMIN_PSID | `npm test` (ESC-02 test) | PASS — at least one axios.post to ADM_2, message.text >= 10 chars | PASS |
| ESC-03: passThreadControl POSTs correct body | `npm test` (ESC-03 test) | PASS — URL contains `/me/pass_thread_control` and `v21.0`; body deepStrictEqual to spec | PASS |
| ESC-04: admin notification includes last message | `npm test` (ESC-04 admin body test) | PASS — admin message text contains `"where is my order"` | PASS |
| ESC-04: lastMessageCache updated on free text, not quick_reply | `npm test` (ESC-04 cache test) | PASS — free text sets cache; quick_reply does not set cache | PASS |
| Soft-fail: ADMIN_PSID absent → customer fallback, no passThreadControl | `npm test` (Soft-fail test) | PASS — exactly 1 axios.post to USR_ESC_8, text includes "be in touch", 0 pass_thread_control calls | PASS |
| Full test suite: 21 pass, 0 fail, 0 skip | `cd messenger-bot && npm test` | `ℹ pass 21 ℹ fail 0 ℹ skipped 0` | PASS |

---

### Probe Execution

No probe scripts declared or present (`scripts/*/tests/probe-*.sh` — none found). Step 7c: SKIPPED (no probe scripts).

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ESC-01 | 04-01, 04-02 | User can tap "Contact Human" from the menu or any screen to trigger escalation | SATISFIED | MENU_CONTACT_HUMAN wired in both quick_reply and postback dispatchers in handleWebhookEvent. MAIN_MENU_QUICK_REPLIES attached to every response function (welcome, fallback, answers). Both ESC-01 tests pass. |
| ESC-02 | 04-01, 04-02 | Admin receives a Messenger notification via their Page-Scoped PSID when user requests escalation | SATISFIED (automated) / NEEDS HUMAN (live) | handleEscalation sends to adminPsid when set. ESC-02 unit test passes. Live delivery requires human confirmation. |
| ESC-03 | 04-01, 04-02 | Thread control transfers to Page inbox via Facebook Handover Protocol | SATISFIED (automated) / NEEDS HUMAN (live) | passThreadControl POSTs correct body/URL. ESC-03 unit test passes. Actual Page inbox transfer requires live verification. |
| ESC-04 | 04-01, 04-02 | Admin notification includes the customer's last message | SATISFIED (automated) / NEEDS HUMAN (live) | lastMessageCache stores free-text only; handleEscalation reads it and builds `Last message: "${lastMessage}"` substring. Both ESC-04 tests pass. Live admin message content requires human confirmation. |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `messenger-bot/src/index.ts` | 110 | `export const lastMessageCache = new Map<string, string>()` — unbounded in-process Map | Info | T-4-03: memory growth risk for large user bases; explicitly deferred to v2 per 04-02-SUMMARY.md. Not a blocker for v1 scope. |

No `TBD`, `FIXME`, or `XXX` markers found in modified files. No placeholder stubs. No unreferenced debt markers.

---

### Human Verification Required

The automated test suite is completely green (21/21 pass). The three items below require a live Facebook Messenger environment and cannot be verified programmatically.

**Note from instructions:** The user has confirmed that live Messenger verification (thread appearing in Page inbox) was completed manually and approved. These items are marked accordingly.

#### 1. Thread Appears in Page Inbox (ESC-03 live)

**Test:** With bot running and Handover Protocol configured (Govi app = Primary Receiver, Page Inbox id 263902037430900 = Secondary Receiver), send a message from a customer Messenger account, then tap "Contact Human." Open the Facebook Page Inbox.
**Expected:** The customer's conversation thread appears in the Page Inbox. The admin can type a reply from the Page Inbox and the customer receives it in Messenger.
**Why human:** Requires live Page setup (Advanced Messaging → Handover Protocol), a real ADMIN_PSID, and two real Messenger accounts.

**User-approved:** Yes (per verification instructions — manual live test completed)

#### 2. Admin Receives Notification with Last-Message Context (ESC-02 / ESC-04 live)

**Test:** From a customer account, send a free-text message (e.g. "what colour is the medium tote"), then tap "Contact Human." Check the admin's personal Messenger.
**Expected:** Admin receives a message containing `Last message: "what colour is the medium tote"` and a prompt to reply from the Page Inbox.
**Why human:** Requires live ADMIN_PSID in .env, a real second Messenger account (admin), and the bot running with the actual Facebook Graph API.

**User-approved:** Yes (per verification instructions — manual live test completed)

#### 3. Soft-Fail Verified Live with ADMIN_PSID Unset (SC-4 live)

**Test:** Stop the bot, comment out ADMIN_PSID in messenger-bot/.env, restart. From a customer account tap "Contact Human."
**Expected:** Bot log shows `ADMIN_PSID not configured — escalation degraded`. Customer receives "Thanks for reaching out! We'll be in touch as soon as possible." with main-menu quick replies. No Page Inbox transfer occurs.
**Why human:** Requires restarting the live bot with a modified .env and observing server log output alongside Messenger behavior.

**User-approved:** Yes (per verification instructions — manual live test completed)

---

### Gaps Summary

No automated gaps. All 7 observable truths are verified in the codebase with passing tests:

- ESC-01: Both quick_reply and postback dispatchers are wired to handleEscalation (two call sites confirmed, 2 passing tests)
- ESC-02: handleEscalation sends to adminPsid when set (1 passing test)
- ESC-03: passThreadControl POSTs correct URL and body structure (1 passing test, PAGE_INBOX_APP_ID constant verified)
- ESC-04: lastMessageCache writes only in free-text branch; admin notification embeds last-message context (2 passing tests)
- Soft-fail: ADMIN_PSID absent path emits warning, sends customer fallback, does not call passThreadControl (1 passing test)
- Message ordering: customer confirmation (line 180) precedes passThreadControl (line 181) in handleEscalation — Pitfall 1 satisfied
- Security: ADMIN_PSID never interpolated into any log statement (grep confirmed empty)

The three human verification items are live-Messenger behaviors that cannot be automated. Per the user's instructions, these were completed manually and approved.

---

_Verified: 2026-05-15T03:30:00Z_
_Verifier: Claude (gsd-verifier)_
