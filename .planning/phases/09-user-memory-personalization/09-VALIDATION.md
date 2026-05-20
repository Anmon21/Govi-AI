---
phase: 09
slug: user-memory-personalization
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-20
---

# Phase 09 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | node:test (built-in) |
| **Config file** | messenger-bot/package.json (`"test": "node --test src/tests/"`) |
| **Quick run command** | `npm --prefix messenger-bot test` |
| **Full suite command** | `npm --prefix messenger-bot test` |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run `npm --prefix messenger-bot test`
- **After every plan wave:** Run `npm --prefix messenger-bot test`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | UX-06 | T-09-01 | Graph API PSID not logged | unit | `npm --prefix messenger-bot test` | ❌ W0 | ⬜ pending |
| 09-01-02 | 01 | 1 | UX-06, UX-07 | T-09-01 | sentinel stored on failure | unit | `npm --prefix messenger-bot test` | ❌ W0 | ⬜ pending |
| 09-01-03 | 01 | 1 | UX-07 | — | returning greeting includes first name | unit | `npm --prefix messenger-bot test` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `messenger-bot/src/tests/personalization.test.ts` — stubs for UX-06 (name fetch, sentinel) and UX-07 (returning greeting)

*Existing test infrastructure (node:test + withAxiosStubs pattern) covers all phase requirements — no framework install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Returning user sees first name in greeting on real Messenger | UX-07 | Requires Business Asset User Profile Access on live Facebook app; cannot be stubbed in unit tests | Send GET_STARTED from a previously-seen PSID via Messenger; verify greeting contains first name |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
