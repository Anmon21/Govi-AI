---
phase: 01-security-bot-foundation
reviewed: 2026-05-14T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - messenger-bot/src/index.ts
  - messenger-bot/src/tests/hmac.test.ts
  - messenger-bot/src/tests/sendMessage.test.ts
  - messenger-bot/src/tests/handlers.test.ts
  - messenger-bot/src/tests/setup.test.ts
  - messenger-bot/package.json
  - .gitignore
  - messenger-bot/.env.example
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-05-14T00:00:00Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

The phase 1 implementation covers HMAC signature verification, Graph API error detection, safe error logging, welcome/fallback message flows, and Messenger Profile setup. The security controls are structurally correct — `timingSafeEqual` is used with proper length-guard, the token is passed via query param (not logged via `config.url`), and the quick-reply dispatch order correctly guards against pitfall 6. However, one blocker was found: unguarded `JSON.parse` calls inside `verifySignature` will crash the request handler on any malformed body. Four warnings cover a duplicate startup warning, a dead module-level variable, missing startup validation for required env vars, and an unsafe type cast pattern repeated in two catch blocks.

## Critical Issues

### CR-01: Unguarded `JSON.parse` crashes on malformed request body

**File:** `messenger-bot/src/index.ts:27` and `messenger-bot/src/index.ts:53`

**Issue:** `verifySignature` calls `JSON.parse(rawBody.toString("utf8"))` in two code paths — the no-secret bypass path (line 27) and the valid-signature path (line 53) — with no surrounding `try/catch`. Any POST to `/webhook` with a non-JSON body (binary data, truncated payload, malformed UTF-8 after signature check passes) will throw a `SyntaxError` that propagates out of Express middleware uncaught. Express will return a 500 and log a stack trace. Facebook's retry mechanism will re-deliver the event repeatedly, causing cascading 500s. Since Facebook uses this endpoint for all events (messages, postbacks, echoes), a single malformed delivery can block processing.

**Fix:**
```typescript
// In verifySignature, replace both bare JSON.parse calls with:
let parsed: unknown;
try {
  parsed = JSON.parse(rawBody.toString("utf8"));
} catch {
  res.sendStatus(400);
  return;
}
(req as any).parsedBody = parsed;
next();
```

## Warnings

### WR-01: `console.warn` fires twice per request when `FACEBOOK_APP_SECRET` is absent

**File:** `messenger-bot/src/index.ts:13-15` and `messenger-bot/src/index.ts:26`

**Issue:** The same "skipping webhook signature verification" warning is emitted at module load (line 14) and then again inside `verifySignature` on every incoming POST request (line 26). In a production deployment without `FACEBOOK_APP_SECRET` set, every single message from every user generates a spurious warn line in the log, making the warning effectively meaningless as an alert signal and polluting log aggregation.

**Fix:** Remove the per-request warn inside `verifySignature`. The module-load warn (line 14) is sufficient — it fires once at startup and serves as an operator alert. The `verifySignature` function should silently fall through to `next()` when no secret is configured.

```typescript
// Line 25-29: remove console.warn inside verifySignature when appSecret is absent
if (!appSecret) {
  (req as any).parsedBody = JSON.parse((req.body as Buffer).toString("utf8"));
  next();
  return;
}
```

### WR-02: Module-level `APP_SECRET` variable is dead code

**File:** `messenger-bot/src/index.ts:11`

**Issue:** `const APP_SECRET = process.env.FACEBOOK_APP_SECRET;` is read at startup and used only to drive the startup warning (lines 13-15). `verifySignature` does not use this variable — it re-reads `process.env.FACEBOOK_APP_SECRET` directly on line 24. The module-level `APP_SECRET` is therefore never used after the startup warning block, making it dead code that misleads readers into thinking it is authoritative. It also means the startup warning and the per-request behavior can theoretically diverge if the env var were mutated between module load and the first request (not realistic, but an inconsistency).

**Fix:** Remove the module-level `APP_SECRET` variable and inline the env check in the startup block:

```typescript
if (!process.env.FACEBOOK_APP_SECRET) {
  console.warn("FACEBOOK_APP_SECRET not set — skipping webhook signature verification");
}
```

### WR-03: No startup validation for required environment variables

**File:** `messenger-bot/src/index.ts:8-9`

**Issue:** `VERIFY_TOKEN` and `PAGE_ACCESS_TOKEN` are declared with the non-null assertion operator (`!`) but are never validated at startup. If either env var is missing from `.env`, the process starts without error. Missing `FACEBOOK_VERIFY_TOKEN` causes every webhook verification request from Facebook to return 403, silently breaking the initial webhook registration. Missing `FACEBOOK_PAGE_ACCESS_TOKEN` causes all outbound messages to fail with a Facebook OAuthException — users receive no response and no operator alert is raised at startup.

**Fix:** Add explicit guards before `app.listen`:

```typescript
if (!process.env.FACEBOOK_VERIFY_TOKEN) {
  console.error("FATAL: FACEBOOK_VERIFY_TOKEN is required");
  process.exit(1);
}
if (!process.env.FACEBOOK_PAGE_ACCESS_TOKEN) {
  console.error("FATAL: FACEBOOK_PAGE_ACCESS_TOKEN is required");
  process.exit(1);
}
```

### WR-04: Unsafe `err as AxiosError` cast in two catch blocks

**File:** `messenger-bot/src/index.ts:120` and `messenger-bot/src/index.ts:205`

**Issue:** Both catch blocks cast the thrown value with `err as import("axios").AxiosError` and then immediately access `axiosErr.message` and `axiosErr.response?.data`. If anything other than an axios error is thrown (e.g., a synchronous programming error inside the try block, or a non-Error rejection), `axiosErr.message` could be `undefined` and the cast is structurally wrong. TypeScript's `strict` mode requires `unknown` in catch, so the cast is necessary — but it should be validated rather than asserted blindly.

**Fix:** Use `axios.isAxiosError()` to narrow the type safely, falling back to generic `Error` handling:

```typescript
} catch (err: unknown) {
  if (axios.isAxiosError(err)) {
    console.error("sendMessage failed:", err.message, err.response?.data);
  } else {
    console.error("sendMessage failed (unexpected error):", err);
  }
}
```

## Info

### IN-01: `(req as any).parsedBody` bypasses the type system at two sites

**File:** `messenger-bot/src/index.ts:27`, `messenger-bot/src/index.ts:53`, `messenger-bot/src/index.ts:77`

**Issue:** Attaching `parsedBody` to the Express `Request` via `(req as any)` loses all type safety. The route handler at line 77 also reads it with `(req as any).parsedBody`, meaning the shape of the parsed body is `any` throughout the handler. This is an existing pattern acknowledged in CLAUDE.md but worth flagging as a quality gap — a missed assertion on `body.object` type (e.g., `body.object !== "page"`) is already present, but deeper accesses like `body.entry ?? []` and `entry.messaging ?? []` are entirely unguarded.

**Fix:** Use Express request interface augmentation to add a typed property:

```typescript
// In a types.d.ts or inline:
declare global {
  namespace Express {
    interface Request {
      parsedBody?: unknown;
    }
  }
}
```

Then narrow `parsedBody` to a known shape before accessing fields.

### IN-02: `handleWebhookEvent` parameter typed as `any`

**File:** `messenger-bot/src/index.ts:147`

**Issue:** `export async function handleWebhookEvent(event: any)` accepts `any`, which disables type checking for all property accesses inside the function (`event.sender?.id`, `event.postback?.payload`, `event.message?.quick_reply`). TypeScript's `strict` mode provides no protection here.

**Fix:** Define a minimal event shape interface:

```typescript
interface MessagingEvent {
  sender?: { id?: string };
  postback?: { payload?: string };
  message?: {
    text?: string;
    quick_reply?: { payload?: string };
  };
}

export async function handleWebhookEvent(event: MessagingEvent): Promise<void> {
```

---

_Reviewed: 2026-05-14T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
