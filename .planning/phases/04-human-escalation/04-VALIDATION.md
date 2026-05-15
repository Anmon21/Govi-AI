---
phase: 04
slug: human-escalation
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-15
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Node built-in node:test + ts-node (bot); pytest + TestClient (FastAPI) |
| **Config file** | messenger-bot/package.json test script |
| **Quick run command** | `cd messenger-bot && npm test` |
| **Full suite command** | `cd messenger-bot && npm test` + `python3 -m pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd messenger-bot && npm test`
- **After every plan wave:** Run full suite (bot + Python)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 0 | ESC-01 | — | N/A | unit | `grep -q 'handleEscalation' messenger-bot/src/tests/escalation.test.ts && echo OK` | ❌ W0 | ⬜ pending |
| 4-01-02 | 01 | 0 | ESC-02 | — | N/A | unit | `cd messenger-bot && npm test 2>&1 | grep -E "pass|skip"` | ❌ W0 | ⬜ pending |
| 4-01-03 | 01 | 0 | ESC-03 | — | N/A | unit | `grep -q 'pass_thread_control' messenger-bot/src/tests/escalation.test.ts && echo OK` | ❌ W0 | ⬜ pending |
| 4-01-04 | 01 | 0 | ESC-04 | — | N/A | unit | `grep -q 'lastMessage' messenger-bot/src/tests/escalation.test.ts && echo OK` | ❌ W0 | ⬜ pending |
| 4-02-01 | 02 | 1 | ESC-01,ESC-02,ESC-03,ESC-04 | T-4-01,T-4-02 | ADMIN_PSID absent → no crash | unit | `cd messenger-bot && npm test 2>&1 | grep -E "^ℹ pass"` | ❌ W1 | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `messenger-bot/src/tests/escalation.test.ts` — test stubs for ESC-01/02/03/04 (skip state until Wave 1)
- [ ] Tests import `handleEscalation` from `"../index"` — will skip/fail RED until Wave 1 exports it

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Thread control transfers to Page inbox | ESC-03 | Requires live Facebook Page + Messenger | Send "Contact Human" in live Messenger; confirm thread appears in Page inbox |
| Admin receives Messenger notification | ESC-02 | Requires live ADMIN_PSID | Verify admin account receives message with customer's last message text |
| Primary Receiver configured correctly | ESC-03 | Facebook Page Settings UI | Go to Page Settings → Advanced Messaging → Handover Protocol; verify app listed as Primary Receiver |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-15
