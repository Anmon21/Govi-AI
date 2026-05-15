---
phase: 01-security-bot-foundation
plan: "02"
subsystem: messenger-bot
tags: [security, hmac, webhook, express, typescript]
dependency_graph:
  requires: ["01-01"]
  provides: ["verifySignature", "sendMessage", "QuickReply"]
  affects: ["messenger-bot/src/index.ts"]
tech_stack:
  added: ["node:crypto (built-in, HMAC-SHA256)"]
  patterns:
    - "express.raw({ type: '*/*' }) route-level middleware for raw body capture"
    - "crypto.timingSafeEqual for constant-time HMAC comparison"
    - "Safe axios error logging via destructured AxiosError fields only"
key_files:
  modified:
    - messenger-bot/src/index.ts
decisions:
  - "verifySignature reads process.env.FACEBOOK_APP_SECRET at call time (not module load time) so unit tests can manipulate the env var without re-importing the module"
  - "Module-level APP_SECRET constant retained for startup-guard warning only; verifySignature re-reads env var at every invocation for testability"
  - "Both tasks (SEC-01 and SEC-02/03) committed in a single commit since the implementation is one atomic file change making both sets of tests green"
metrics:
  duration_minutes: 15
  completed_date: "2026-05-14"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 1
---

# Phase 01 Plan 02: Security Hardening (SEC-01/02/03) Summary

**One-liner:** HMAC-SHA256 webhook verification with timingSafeEqual, Graph API error detection in 200 responses, and token-safe catch logging — all in `messenger-bot/src/index.ts`, zero new dependencies.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add HMAC verifySignature middleware + rewire /webhook route (SEC-01) | 3c47e55 | messenger-bot/src/index.ts |
| 2 | Extend sendMessage with quickReplies + SEC-02 error check + SEC-03 safe catch + v21.0 bump | 3c47e55 | messenger-bot/src/index.ts |

## What Was Built

### SEC-01: HMAC Webhook Signature Verification

- Removed `app.use(express.json())` global middleware
- Mounted `express.raw({ type: "*/*" })` + `verifySignature` as route-level middleware on `POST /webhook`
- `verifySignature` computes `sha256=<hmac>` using `crypto.createHmac("sha256", appSecret).update(rawBody).digest("hex")`
- Compares with `crypto.timingSafeEqual` (constant-time, prevents timing attacks)
- Guards against `ERR_CRYPTO_TIMINGSAFEEQUAL_ARRAY_BUFFER_LENGTH` by checking buffer lengths before calling `timingSafeEqual`
- Gracefully degrades when `FACEBOOK_APP_SECRET` is unset: logs warning, parses body normally, calls `next()` (D-03)
- Handler reads `(req as any).parsedBody` (set by `verifySignature`) instead of `req.body` (which is now a Buffer)
- `verifySignature` is exported for unit test access

### SEC-02: Graph API Error Detection

- `sendMessage` wraps `axios.post` in try/catch
- After successful response: checks `response.data?.error` and logs `"Graph API error:"` with error message and full error object
- Facebook returns HTTP 200 with `{ error: {...} }` on send failures — this was previously swallowed silently

### SEC-03: Token-Safe Error Logging

- Both catch blocks in `index.ts` now type `err as unknown`, cast to `AxiosError`, and log only `axiosErr.message` and `axiosErr.response?.data`
- The full `AxiosError` object (which includes `config.url` containing `PAGE_ACCESS_TOKEN` as a query param) is never passed to `console.error`
- Applied to: `sendMessage` catch block and the existing Govi AI call catch block in the POST handler

### Graph API Version Bump

- `sendMessage` now targets `https://graph.facebook.com/v21.0/me/messages` (was v19.0)

### QuickReply Interface + sendMessage Extension

- `export interface QuickReply { content_type: "text"; title: string; payload: string; }` added
- `sendMessage` signature extended to `(recipientId: string, text: string, quickReplies?: QuickReply[]): Promise<void>`
- Empty `quickReplies` array suppressed — Facebook rejects empty `quick_replies` arrays
- Both `verifySignature` and `sendMessage` are exported for testability

## Test Results

```
ℹ pass 5    (3 HMAC + 2 sendMessage)
ℹ fail 0
ℹ skipped 5 (handler/setup tests — pending Plan 03)
```

All SEC-01/02/03 tests GREEN. TypeScript strict build (`npm run build`) exits 0.

## Deviations from Plan

### Design Deviation: verifySignature reads env var at call time

- **Found during:** Task 1 implementation
- **Issue:** The plan specifies `const APP_SECRET = process.env.FACEBOOK_APP_SECRET` as a module-level constant. However, the test scaffolds (from Plan 01) manipulate `process.env.FACEBOOK_APP_SECRET` between test cases after the module is already `require`d. If `verifySignature` read the module-level `APP_SECRET` constant, the env var changes would have no effect and the "missing APP_SECRET" test would fail.
- **Fix:** `verifySignature` reads `process.env.FACEBOOK_APP_SECRET` directly at invocation time. The module-level `APP_SECRET` constant is retained for the startup-guard `console.warn` only.
- **Impact:** Same runtime behavior; improved testability. No behavioral difference in production (env vars don't change at runtime).
- **Rule:** Rule 1 (Bug fix — test would have failed with the verbatim plan approach)

## Known Stubs

None — all exported functions are fully implemented.

## Threat Flags

No new threat surface introduced. All STRIDE threats T-1-01 through T-1-09 from the plan's threat model are mitigated by this implementation.

## Self-Check: PASSED

- `messenger-bot/src/index.ts` exists and contains all required patterns
- Commit 3c47e55 exists in git log
- `npm test` exits 0 with 5 passing, 5 skipped
- `npm run build` exits 0 (strict TypeScript)
