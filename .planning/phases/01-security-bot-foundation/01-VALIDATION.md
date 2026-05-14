---
phase: 1
slug: security-bot-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-14
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Node.js built-in `node:test` (Node 26.0.0 — zero new dependencies) |
| **Config file** | none — Wave 0 adds test script to `messenger-bot/package.json` |
| **Quick run command** | `node --test src/tests/` |
| **Full suite command** | `node --test src/tests/` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `node --test src/tests/`
- **After every plan wave:** Run `node --test src/tests/`
- **Before `/gsd-verify-work`:** Full suite must be green + manual Success Criteria verified
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | SEC-01 | T-1-01 | Valid HMAC → passes through | Unit | `node --test src/tests/hmac.test.ts` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 0 | SEC-01 | T-1-01 | Invalid HMAC → 403 | Unit | `node --test src/tests/hmac.test.ts` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 0 | SEC-01 | T-1-01 | Missing APP_SECRET → skip + warn | Unit | `node --test src/tests/hmac.test.ts` | ❌ W0 | ⬜ pending |
| 1-02-01 | 01 | 0 | SEC-02 | T-1-02 | `response.data.error` present → logged | Unit | `node --test src/tests/sendMessage.test.ts` | ❌ W0 | ⬜ pending |
| 1-02-02 | 01 | 0 | SEC-03 | T-1-03 | catch block does not log full error | Unit | `node --test src/tests/sendMessage.test.ts` | ❌ W0 | ⬜ pending |
| 1-03-01 | 02 | 1 | CORE-01 | — | GET_STARTED postback → welcome message sent | Unit (mock axios) | `node --test src/tests/handlers.test.ts` | ❌ W0 | ⬜ pending |
| 1-03-02 | 02 | 1 | CORE-02 | — | Messenger profile setup call has correct structure | Unit (mock axios) | `node --test src/tests/setup.test.ts` | ❌ W0 | ⬜ pending |
| 1-03-03 | 02 | 1 | CORE-03 | — | Quick reply payloads present in sendMessage calls | Unit | `node --test src/tests/handlers.test.ts` | ❌ W0 | ⬜ pending |
| 1-04-01 | 02 | 1 | CORE-04 | — | Free text event → fallback message with quick replies | Unit (mock axios) | `node --test src/tests/handlers.test.ts` | ❌ W0 | ⬜ pending |
| 1-04-02 | 02 | 1 | CORE-04 | — | Quick reply tap does NOT trigger fallback | Unit | `node --test src/tests/handlers.test.ts` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `messenger-bot/src/tests/hmac.test.ts` — stubs for SEC-01
- [ ] `messenger-bot/src/tests/sendMessage.test.ts` — stubs for SEC-02, SEC-03
- [ ] `messenger-bot/src/tests/handlers.test.ts` — stubs for CORE-01, CORE-03, CORE-04
- [ ] `messenger-bot/src/tests/setup.test.ts` — stubs for CORE-02
- [ ] Add `"test": "node --test src/tests/**/*.test.ts"` to `messenger-bot/package.json` scripts

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Persistent menu visible in Messenger | CORE-02 | Requires live Facebook app + tunnel | Open Messenger → tap hamburger → verify top-level options appear |
| GET_STARTED button fires in Messenger | CORE-01 | Requires live Facebook app + page setup | New user opens bot → verify welcome message received |
| 403 returned to real forged POST | SEC-01 | Requires live webhook endpoint | Send POST with invalid X-Hub-Signature-256 → verify 403 response |
| PAGE_ACCESS_TOKEN absent from log output | SEC-03 | Requires triggering a real Graph API error | Trigger sendMessage failure → inspect logs for token absence |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
