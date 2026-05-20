---
phase: 09-user-memory-personalization
verified: 2026-05-20T00:00:00Z
status: human_needed
score: 10/10 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Send GET_STARTED from a real Messenger account with a known first name"
    expected: "Greeting message reads: Welcome back, {first_name}! How can I help you today?"
    why_human: "Requires Facebook App with Business Asset User Profile Access granted, a deployed bot instance, and a live Messenger session — cannot verify Graph API permission grant or live message delivery programmatically"
---

# Phase 9: User Memory & Personalization Verification Report

**Phase Goal:** Returning users are greeted by name, making the bot feel aware of who they are without requiring any persistent storage
**Verified:** 2026-05-20
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | First event from an unknown PSID triggers a Graph API GET for first_name before any handler runs | VERIFIED | `handleWebhookEvent` lines 399-401: `if (!userNameCache.has(senderId)) { await fetchUserName(senderId); }` — guard appears before all routing branches |
| 2  | Graph API success stores the first name string in userNameCache keyed by PSID | VERIFIED | `fetchUserName` line 129: `userNameCache.set(psid, firstName)` in try block; test "UX-06: fetchUserName with valid first_name..." passes |
| 3  | Graph API returning empty object stores empty-string sentinel so no retry occurs | VERIFIED | `fetchUserName` line 128: `response.data?.first_name ?? ""` — nullish coalescing produces empty string; test "UX-06: fetchUserName with empty object response..." passes |
| 4  | Graph API throwing (network, 4xx) stores empty-string sentinel so no retry occurs | VERIFIED | `fetchUserName` lines 130-138: catch block calls `userNameCache.set(psid, "")` after logging; test "UX-06: fetchUserName with network error..." passes |
| 5  | Second event from same PSID skips the Graph API call entirely (cache hit) | VERIFIED | Guard uses `Map.has()` not truthiness — empty-string sentinel triggers has()=true; test "UX-06: handleWebhookEvent fired twice..." asserts exactly 1 Graph call and passes |
| 6  | sendWelcomeMessage sends the personalized greeting when cache contains a non-empty name | VERIFIED | Lines 380-384: `firstName ? \`Welcome back, ${firstName}!...\` : ...`; test "UX-07: sendWelcomeMessage sends personalized greeting..." passes |
| 7  | sendWelcomeMessage sends the generic greeting when cache contains empty-string sentinel | VERIFIED | `userNameCache.get()` returns `""` which is falsy — ternary takes generic branch; test "UX-07: sendWelcomeMessage sends generic greeting when cache has empty-string sentinel..." passes |
| 8  | sendWelcomeMessage sends the generic greeting when PSID is absent from cache | VERIFIED | `userNameCache.get()` returns `undefined` which is falsy; test "UX-07: sendWelcomeMessage sends generic greeting when PSID absent from cache..." passes |
| 9  | PAGE_ACCESS_TOKEN never appears in any error log emitted by fetchUserName | VERIFIED | Lines 132-136: catch logs only `err.message` and `err.response?.data` (Axios branch) or `err.message`/`String(err)` (non-Axios branch) — raw error object never logged; no reference to `PAGE_ACCESS_TOKEN` in any console.error call |
| 10 | handleWebhookEvent called with GET_STARTED for unknown PSID, Graph API returns a name, greeting sent to Messenger contains the name | VERIFIED | End-to-end test "UX-06+UX-07 end-to-end: GET_STARTED for unknown PSID with name fetched sends personalized greeting" passes — asserts postCalls contains `"Welcome back, Alice! How can I help you today?"` |

**Score:** 10/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `messenger-bot/src/tests/personalization.test.ts` | 9 automated test cases covering UX-06 and UX-07, min 210 lines | VERIFIED | File exists, 202 lines (8 lines short of 210 threshold; see note), 9 test blocks present, all 9 pass |
| `messenger-bot/src/index.ts` | userNameCache Map, fetchUserName helper, handleWebhookEvent guard, updated sendWelcomeMessage | VERIFIED | All four insertions confirmed at lines 120, 122-139, 399-401, 379-385 |

**Note on line count:** PLAN specifies `min_lines: 210` for personalization.test.ts; file is 202 lines. The file contains all 9 required test cases with full assertions — the 8-line shortfall is due to slightly more concise formatting, not missing content. All 9 tests pass. This is not treated as a BLOCKER.

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `handleWebhookEvent` | `fetchUserName` | `await fetchUserName(senderId)` when `!userNameCache.has(senderId)` | WIRED | Line 399: `if (!userNameCache.has(senderId)) {` line 400: `await fetchUserName(senderId);` — pattern `userNameCache\.has\(senderId\)` confirmed |
| `fetchUserName` | `userNameCache` | `userNameCache.set(psid, firstName)` in try; `userNameCache.set(psid, '')` in catch | WIRED | Line 129: try-branch set; line 137: catch-branch sentinel set — both present |
| `sendWelcomeMessage` | `userNameCache` | `userNameCache.get(recipientId)` | WIRED | Line 380: `const firstName = userNameCache.get(recipientId);` — confirmed |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `sendWelcomeMessage` | `firstName` | `userNameCache.get(recipientId)` | Yes — Map populated by `fetchUserName` which GETs Facebook Graph API | FLOWING |
| `fetchUserName` | `firstName` | `axios.get(graph.facebook.com/{psid}?fields=first_name)` | Yes — real HTTP GET to Facebook Graph API (live), sentinel on failure | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 9 personalization tests pass | `npm --prefix messenger-bot test` | 50 tests, 50 pass, 0 fail, 0 skipped | PASS |
| TypeScript strict compilation | `npm --prefix messenger-bot run build` | exits 0, no type errors | PASS |
| userNameCache appears >= 4 times in index.ts | `grep -c "userNameCache" index.ts` | 5 | PASS |
| fetchUserName declaration and call site in handleWebhookEvent | `grep -n "fetchUserName" index.ts` | Declaration line 122, call site line 400 | PASS |
| "Welcome back," appears exactly once | `grep -n "Welcome back," index.ts` | Line 382 — exactly one match | PASS |
| userNameCache.has guard in handleWebhookEvent | `grep -n "userNameCache.has" index.ts` | Line 399 — inside handleWebhookEvent | PASS |

### Probe Execution

No probes defined for this phase. Step 7c: SKIPPED (no probe scripts present).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| UX-06 | 09-01-PLAN.md | Bot fetches user's first name via Graph API on first interaction and stores it per PSID in an in-memory Map | SATISFIED | `fetchUserName` exports the Map-backed fetch; `handleWebhookEvent` guard calls it once per unknown PSID; 5 tests directly cover UX-06 behaviors |
| UX-07 | 09-01-PLAN.md | Returning user is greeted by name in the welcome / Get Started message | SATISFIED | `sendWelcomeMessage` reads from `userNameCache` and branches on name presence; 4 tests directly cover UX-07 behaviors including end-to-end |

Both requirements declared in PLAN frontmatter are accounted for. REQUIREMENTS.md maps exactly UX-06 and UX-07 to Phase 9 — no orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | — | — | — |

Scanned `messenger-bot/src/index.ts` and `messenger-bot/src/tests/personalization.test.ts` for TBD, FIXME, XXX, TODO, HACK, PLACEHOLDER, `return null`, `return {}`, `return []`, and hardcoded empty props. No blockers found.

The SUMMARY also notes modification to `messenger-bot/src/tests/debt-fixes.test.ts` — the DEBT-01c assertion was updated to filter out Graph API calls that Phase 9 legitimately introduces. This is correct behavior, not a stub or anti-pattern.

### Human Verification Required

#### 1. Live Messenger Personalized Greeting

**Test:** Deploy the bot to a Facebook Page with Business Asset User Profile Access enabled. Open Messenger, tap "Get Started" from an account with a known first name.
**Expected:** The bot sends "Welcome back, {first_name}! How can I help you today?" using the actual account's first name.
**Why human:** Requires a deployed bot instance, a Facebook App with `Business Asset User Profile Access` permission granted, and a live Messenger interaction. The Graph API will return 4xx in development (no permission), causing the sentinel fallback. Cannot verify the permission grant or live name resolution programmatically.

### Gaps Summary

No programmatic gaps found. All 10 must-have truths are VERIFIED, all key links are WIRED, the test suite is fully green (50/50), and TypeScript compilation is clean.

The one outstanding item is a live-environment UAT step that requires Facebook app permission grant — this is inherently a human verification step, not a code defect. The code correctly handles the degraded case (generic greeting) when the permission is absent.

---

_Verified: 2026-05-20_
_Verifier: Claude (gsd-verifier)_
