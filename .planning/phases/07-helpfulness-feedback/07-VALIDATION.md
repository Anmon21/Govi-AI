---
phase: 7
slug: helpfulness-feedback
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-18
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Node.js built-in test runner (`node:test`) |
| **Config file** | None — tests run via npm script |
| **Quick run command** | `cd messenger-bot && npm test` |
| **Full suite command** | `cd messenger-bot && npm test` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd messenger-bot && npm test`
- **After every plan wave:** Run `cd messenger-bot && npm test`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | UX-01 | `sendAnswer` attaches `FEEDBACK_QUICK_REPLIES` on success | unit | `cd messenger-bot && npm test` | ❌ Wave 0 — feedback.test.ts | ⬜ pending |
| 07-01-02 | 01 | 1 | UX-01 | `sendAnswer` error path unchanged (regression) | unit | `cd messenger-bot && npm test` | ❌ Wave 0 | ⬜ pending |
| 07-01-03 | 01 | 1 | UX-02 | `HELPFUL_YES` → thank-you string + `MAIN_MENU_QUICK_REPLIES` | unit | `cd messenger-bot && npm test` | ❌ Wave 0 | ⬜ pending |
| 07-01-04 | 01 | 1 | UX-03 | `HELPFUL_NO` → delegates to `handleEscalation` | unit | `cd messenger-bot && npm test` | ❌ Wave 0 | ⬜ pending |
| 07-01-05 | 01 | 1 | Regression | Unknown payload after feedback → `sendFallbackMessage` | unit | `cd messenger-bot && npm test` | ❌ Wave 0 | ⬜ pending |
| 07-01-06 | 01 | 1 | Regression | `qa-flow.test.ts:141` updated from `MAIN_MENU_QUICK_REPLIES` to `FEEDBACK_QUICK_REPLIES` | unit | `cd messenger-bot && npm test` | ⚠️ Exists — needs update | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `messenger-bot/src/tests/feedback.test.ts` — new file covering UX-01, UX-02, UX-03, and two regression cases
- [ ] `messenger-bot/src/tests/qa-flow.test.ts` line 141 — update assertion from `MAIN_MENU_QUICK_REPLIES` to `FEEDBACK_QUICK_REPLIES` before implementation (so test reflects new contract)

*Existing test infrastructure (Node built-in runner, axios stub pattern) requires no installation. Only the new test file and the updated assertion need to be added in Wave 0.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Quick reply buttons visually appear in Messenger app | UX-01 | Requires live Facebook Messenger environment | Send a message that triggers a Q&A answer; verify two buttons appear: "Was it helpful? Yes" and "Was it helpful? No" |
| "Yes" path: thank-you renders and menu buttons appear | UX-02 | Live Messenger required | Tap "Was it helpful? Yes"; verify thank-you text and Product Help / Contact Human buttons appear |
| "No" path: escalation message delivered | UX-03 | Live Messenger required | Tap "Was it helpful? No"; verify escalation confirmation message is received |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING test file references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
