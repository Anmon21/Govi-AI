# Phase 6: Bug Fixes & Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-16
**Phase:** 6-Bug Fixes & Hardening
**Areas discussed:** Postback routing fix, Startup validation scope, Async failure handling, Error log sanitization

---

## Postback Routing Fix (DEBT-01)

*(Discussed in prior session — captured from checkpoint)*

| Option | Description | Selected |
|--------|-------------|----------|
| Surgical patch | Add MENU_PRODUCT_HELP and MENU_MAIN if-checks before the existing catch-all | ✓ |
| Unified dispatch function | Refactor postback handling into a single dispatch map | |

**User's choice:** Surgical patch

---

| Option | Description | Selected |
|--------|-------------|----------|
| Keep current behavior | Log "Postback received: [payload]" and silently drop | ✓ |
| Send fallback message | Send a user-facing "I didn't understand that" message | |
| You decide | Defer to Claude | |

**User's choice:** Keep current behavior — log + silent drop for unknown postback payloads

---

## Startup Validation Scope (DEBT-03)

*(Discussed in prior session — captured from checkpoint)*

| Option | Description | Selected |
|--------|-------------|----------|
| VERIFY_TOKEN only | Exact DEBT-03 scope | ✓ |
| VERIFY_TOKEN + PAGE_ACCESS_TOKEN | Broader startup guard | |

**User's choice:** VERIFY_TOKEN only

---

| Option | Description | Selected |
|--------|-------------|----------|
| process.exit(1) with console.error | Clear message before app.listen | ✓ |
| throw new Error at module level | Module-level throw | |

**User's choice:** process.exit(1) with console.error

---

| Option | Description | Selected |
|--------|-------------|----------|
| After dotenv/config import | Before any app setup | ✓ |
| Just before app.listen | Late validation | |

**User's choice:** After dotenv/config import — before any app setup

---

## Async Failure Handling (DEBT-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Wrap each handleWebhookEvent call | Per-event try/catch in inner loop — one event failure can't block later events | — |
| Wrap the entire entry/messaging loops | Single try/catch around both for loops — simpler but drops remaining batch on failure | — |
| You decide | Defer to Claude | ✓ |

**User's choice:** You decide — Claude chose per-event try/catch (inner loop)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Log and continue | console.error with safe message, no user notification | ✓ |
| Log and send fallback to user | Attempt fallback message — could cause cascading failure | |
| Log only, no fallback | Same as first option | |

**User's choice:** Log and continue

---

## Error Log Sanitization (DEBT-04)

| Option | Description | Selected |
|--------|-------------|----------|
| err.message only | `err instanceof Error ? err.message : String(err)` | ✓ |
| String(err) | Always coerce to string — simpler but loses structure | |
| "Unknown error" only | Most conservative — nothing useful for debugging | |

**User's choice:** err.message only — `err instanceof Error ? err.message : String(err)`

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — consistent safe logging everywhere | DEBT-02 catch also uses err.message pattern | ✓ |
| No — webhook catch can log raw err | Different rule for webhook catch | |

**User's choice:** Yes — same safe-logging pattern applies to the new DEBT-02 catch block too

---

## Claude's Discretion

- **DEBT-02 catch scope:** User deferred to Claude. Claude chose per-event try/catch inside the inner `for` loop — rationale: Facebook batches can contain multiple events, and per-event isolation prevents one bad event from dropping the rest of the batch.

## Deferred Ideas

None — discussion stayed within phase scope.
