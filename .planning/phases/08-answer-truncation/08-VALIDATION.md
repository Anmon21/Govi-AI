---
phase: 8
slug: answer-truncation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-19
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Node.js built-in `node:test` |
| **Config file** | none — runner called directly via `npm test` |
| **Quick run command** | `npm --prefix messenger-bot test` |
| **Full suite command** | `npm --prefix messenger-bot test` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `npm --prefix messenger-bot test`
- **After every plan wave:** Run `npm --prefix messenger-bot test`
- **Before `/gsd-verify-work`:** Full suite (32 existing + 9 new truncation tests) must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 0 | UX-04, UX-05 | — | N/A | unit | `npm --prefix messenger-bot test` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 1 | UX-04 | T-08-01 / — | `encodeURIComponent` on questionId prevents URL injection | unit | `npm --prefix messenger-bot test` | ✅ after W0 | ⬜ pending |
| 08-01-03 | 01 | 1 | UX-05 | T-08-01 / — | `encodeURIComponent` on questionId prevents URL injection | unit | `npm --prefix messenger-bot test` | ✅ after W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `messenger-bot/src/tests/truncation.test.ts` — 9 test case stubs covering UX-04 and UX-05 (per 08-UI-SPEC.md §Test Surface)

No framework install needed — `node:test` is built into Node 26.

*Existing infrastructure covers test runner and stub helpers.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Preview message displays cleanly truncated text in Messenger app | UX-04 | Requires deployed Facebook bot + live Messenger client | Send a question whose answer exceeds 200 chars; verify preview ends with "..." and shows "Read more" button |
| Full answer follow-up received after tapping "Read more" | UX-05 | Requires deployed Facebook bot + live Messenger client | Tap "Read more" on a truncated answer; verify full text arrives and "Was it helpful?" buttons appear |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
