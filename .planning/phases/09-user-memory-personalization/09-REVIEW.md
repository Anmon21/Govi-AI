---
phase: 09-user-memory-personalization
reviewed: 2026-05-20T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - messenger-bot/src/index.ts
  - messenger-bot/src/tests/personalization.test.ts
  - messenger-bot/src/tests/debt-fixes.test.ts
findings:
  critical: 2
  warning: 5
  info: 2
  total: 9
status: issues_found
---

# Phase 09: Code Review Report

**Reviewed:** 2026-05-20T00:00:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

This phase adds UX-06 (in-memory name cache populated from Graph API) and UX-07 (personalized welcome greeting) to `index.ts`, plus two test files covering the new behavior and prior tech-debt fixes. The implementation logic in `index.ts` is structurally sound, but there are two critical issues: a real token value that could surface in logged error responses, and test isolation failures that mean the test suite can produce false positives or false negatives depending on execution order. Five warnings cover weaker test assertions, a missing response-error check, a fire-and-forget Promise, and an unnecessary import.

---

## Critical Issues

### CR-01: Graph API error response body logged — may contain PAGE_ACCESS_TOKEN

**File:** `messenger-bot/src/index.ts:133`
**Issue:** The comments at lines 131, 163, 187, and 210 correctly explain that the full Axios error must not be logged because `config.url` contains the `PAGE_ACCESS_TOKEN` query parameter. However, all four catch blocks log `err.response?.data` verbatim. Facebook's Graph API error responses include the request URL (or fields from it) in `error.fbtrace_id` contexts, and more critically the Graph API documentation states that error objects can echo back request parameters. Even if that does not occur in practice today, logging the raw response body from any authenticated Graph API call defeats the stated intent of SEC-03. The token is also sent as a query parameter (`access_token=...`), which some edge-case error responses (e.g., OAuth-level 401s) include in their body.

**Fix:**
```typescript
// Replace all four instances of:
console.error("fetchUserName failed:", err.message, err.response?.data);
// With:
console.error("fetchUserName failed:", err.message, err.response?.status);
```
Log only the HTTP status code from the response, not the full response body. Apply the same fix to `sendMessage` (line 166), `passThreadControl` (line 189), and `sendTypingIndicator` (line 212).

---

### CR-02: DEBT-02 test does not stub `axios.get` — `fetchUserName` hits unstubbed network path, making test unreliable

**File:** `messenger-bot/src/tests/debt-fixes.test.ts:116-168`
**Issue:** The DEBT-02 test exercises `handleWebhookEvent` for two GET_STARTED events. Since Phase 9, `handleWebhookEvent` calls `fetchUserName` (which uses `axios.get`) for any PSID not already in `userNameCache`. The test stubs `axios.post` but never stubs `axios.get`. If `USR_D1` and `USR_D2` are not already in the module-singleton `userNameCache` (which is not cleared in this test), the real `axios.get` fires against `graph.facebook.com`. In CI or any environment without a valid `PAGE_ACCESS_TOKEN`, this network call throws, causing `handleWebhookEvent` to reject before `axios.post` is ever reached. The assertion `callCount === 2` then fails — not because the isolation logic is broken, but because the test setup is broken. The `PAGE_ACCESS_TOKEN` captured at module load (line 14 of `index.ts`) would be `"test-token"` (set by line 10 of `debt-fixes.test.ts`), which is invalid for a real Graph API call, making the `axios.get` call throw every time for a fresh `userNameCache` entry.

**Fix:**
```typescript
// Add before the callCount/recordedErrors declarations:
const mod = require("../index");
const cache: Map<string, string> = mod.userNameCache;
cache.set("USR_D1", "");
cache.set("USR_D2", "");

// OR: stub axios.get in this test alongside axios.post:
const originalGet = axios.get;
axios.get = async (_url: string) => ({ data: {} });
// ... and restore in finally:
axios.get = originalGet;
```
Prepopulating the cache or stubbing `axios.get` prevents the unstubbed network call.

---

## Warnings

### WR-01: DEBT-01b (MENU_MAIN) test does not stub `axios.get` — fetchUserName fires against live network

**File:** `messenger-bot/src/tests/debt-fixes.test.ts:61-84`
**Issue:** The MENU_MAIN test uses sender ID `USR_B` and stubs only `axios.post`. After Phase 9, routing `MENU_MAIN` through `handleWebhookEvent` triggers `fetchUserName` first (for unknown PSIDs) via `axios.get`. If `USR_B` is not already in `userNameCache`, the unstubbed `axios.get` issues a live request to `graph.facebook.com/v21.0/USR_B` with `PAGE_ACCESS_TOKEN=test-token`, which will either throw a network error or return a 400. The `fetchUserName` catch silently stores `""` in the cache on error, so the test may not fail outright — but it makes an unintended external call during testing and is one network-availability incident away from a flaky failure.

**Fix:**
```typescript
// Add before the postBodies declaration:
const originalGet = axios.get;
axios.get = async (_url: string) => ({ data: {} });

// In the finally block, add:
axios.get = originalGet;
```

---

### WR-02: `personalization.test.ts` does not set `FACEBOOK_PAGE_ACCESS_TOKEN` — token captured as `undefined` if this file loads first

**File:** `messenger-bot/src/tests/personalization.test.ts:8-9`
**Issue:** `index.ts` line 14 captures `PAGE_ACCESS_TOKEN = process.env.FACEBOOK_PAGE_ACCESS_TOKEN!` at module load time. `personalization.test.ts` sets `FACEBOOK_VERIFY_TOKEN` and `PORT` but not `FACEBOOK_PAGE_ACCESS_TOKEN`. Because `debt-fixes.test.ts` does set it (line 10), the token is defined if `debt-fixes.test.ts` is loaded first. The test runner runs files in glob order (`src/tests/*.test.ts`); `debt-fixes.test.ts` sorts before `personalization.test.ts` alphabetically, which currently saves this. However, this is an ordering dependency, not a guarantee. If any test isolation or ordering changes, `PAGE_ACCESS_TOKEN` becomes the literal string `"undefined"` in all Graph API calls from the personalization tests.

**Fix:**
```typescript
// Add to personalization.test.ts lines 8-9 block:
process.env.FACEBOOK_PAGE_ACCESS_TOKEN = "test-token";
```

---

### WR-03: `debt-fixes.test.ts` never clears `userNameCache` — test results are order-dependent

**File:** `messenger-bot/src/tests/debt-fixes.test.ts` (all tests)
**Issue:** `userNameCache` is a module-level `Map` singleton exported from `index.ts`. The personalization tests (which run before debt-fixes alphabetically) call `userNameCache.clear()` at the start of most tests, but those clearing calls use PSIDs like `PSID_A`–`PSID_I`. The debt-fixes tests use PSIDs `USR_A`–`USR_E`. If personalization tests have already populated the cache with entries that happen to share a PSID, or if a prior test suite run left entries, the `fetchUserName` call is skipped. Conversely, since debt-fixes tests never clear the cache, PSIDs from DEBT-01a (`USR_A`) will still be in the cache when DEBT-02 runs `USR_D1`/`USR_D2`, meaning `fetchUserName` may or may not fire depending on what has been set. This makes DEBT-02's unverified assumption about `callCount` order-dependent.

**Fix:** Add a `userNameCache.clear()` call at the start of each test in `debt-fixes.test.ts` that calls `handleWebhookEvent`:
```typescript
const mod = require("../index");
mod.userNameCache.clear();
```

---

### WR-04: `sendTypingIndicator` does not check `response.data?.error` for Graph API errors inside HTTP 200

**File:** `messenger-bot/src/index.ts:196-217`
**Issue:** `sendMessage` (line 160) and `passThreadControl` (line 183) both check `response.data?.error` after a successful HTTP response, because the Graph API can return errors inside a 200. `sendTypingIndicator` has no such check. A failed typing indicator will be silently swallowed. This is inconsistent and can obscure misconfiguration (e.g., wrong `PAGE_ACCESS_TOKEN`, wrong thread ownership).

**Fix:**
```typescript
// After the await axios.post call in sendTypingIndicator, add:
if (response.data?.error) {
  console.error("sendTypingIndicator Graph API error:", response.data.error.message, response.data.error);
}
```
Note: the current `await axios.post(...)` result is not captured. Assign it first:
```typescript
const response = await axios.post(...);
if (response.data?.error) { ... }
```

---

### WR-05: `setupMessengerProfile()` called without `void` operator — unawaited Promise not acknowledged

**File:** `messenger-bot/src/index.ts:532`
**Issue:** `setupMessengerProfile()` is called in the `app.listen` callback without `await` (the callback is not `async`) and without the `void` operator. Under `strict: true`, TypeScript does not flag floating Promises by default (that requires `@typescript-eslint/no-floating-promises`), but the pattern is inconsistent with the codebase's intent. More importantly, if `setupMessengerProfile` throws synchronously before its first `await`, the exception will be an unhandled Promise rejection. The function has an internal `try/catch`, so this is unlikely in practice, but the pattern is fragile.

**Fix:**
```typescript
// Line 532 — acknowledge the floating Promise explicitly:
void setupMessengerProfile();
```

---

## Info

### IN-01: `import type {} from "../index"` is a no-op

**File:** `messenger-bot/src/tests/personalization.test.ts:6`
**Issue:** `import type {} from "../index"` imports zero named types. This statement has no effect — it does not cause the module to load (type imports are erased at compile time) and imports nothing useful. It appears to be a leftover placeholder.

**Fix:** Remove line 6 entirely.

---

### IN-02: `PAGE_INBOX_APP_ID` hardcoded as a numeric string literal

**File:** `messenger-bot/src/index.ts:119`
**Issue:** The App ID `"263902037430900"` is hardcoded in source. While this is not a secret, it couples the codebase to a specific Facebook App deployment and must be changed by code edit (not configuration) to support a different App ID. The project convention is that all deployment-specific values come from environment variables.

**Fix:**
```typescript
export const PAGE_INBOX_APP_ID = process.env.FACEBOOK_PAGE_INBOX_APP_ID ?? "263902037430900";
```
Add `FACEBOOK_PAGE_INBOX_APP_ID` (optional, with current value as default) to `messenger-bot/.env.example`.

---

_Reviewed: 2026-05-20T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
