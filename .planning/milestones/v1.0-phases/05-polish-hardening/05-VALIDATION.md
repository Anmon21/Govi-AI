---
phase: "05"
slug: polish-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-15
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Node.js built-in test runner (`node:test`) |
| **Config file** | `messenger-bot/package.json` → `"test": "node --test-force-exit --test --require ts-node/register src/tests/*.test.ts"` |
| **Quick run command** | `cd messenger-bot && npm test` |
| **Full suite command** | `cd messenger-bot && npm test` (same — all tests in one suite) |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd messenger-bot && npm test`
- **After every plan wave:** Run `cd messenger-bot && npm test`
- **Before `/gsd-verify-work`:** Full suite must be green (21 existing + 2 new POLISH-01 tests)
- **Max feedback latency:** ~2 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 0 | POLISH-01 | T-5-01 | typing_off sent even when API throws (finally block) | unit | `cd messenger-bot && npm test` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 0 | POLISH-01 | — | postCalls count updated for typing_on/off surrounding sendMessage | unit | `cd messenger-bot && npm test` | ❌ W0 (update existing) | ⬜ pending |
| 05-01-03 | 01 | 1 | POLISH-01 | T-5-01 | sendTypingIndicator uses SEC-03 error pattern (no PAGE_ACCESS_TOKEN in log) | unit | `cd messenger-bot && npm test` | ✅ (via existing SEC-03 grep pattern) | ⬜ pending |
| 05-02-01 | 02 | 1 | POLISH-01 | — | .env.example has comment blocks on all 6 vars | manual | inspect file | ❌ — manual | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Update `messenger-bot/src/tests/qa-flow.test.ts` — change `postCalls.length === 1` to `=== 3` and `postCalls[0]` to `postCalls[1]` for the QUESTION answer assertion; add new test `qa-flow: sendAnswer typing_off fires even when API fetch fails`

*Note: Python tests (`python3 -m pytest tests/ -q`) are unchanged by this phase — no FastAPI modifications.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Typing indicator visible in Messenger before answer arrives | POLISH-01 | Requires live Facebook Page + ngrok tunnel | Start both services, tap a question in Messenger, observe animated dots before answer text appears |
| Bot starts cleanly from fresh clone | POLISH-01 | Requires a fresh environment + npm install | Clone repo, copy .env.example → .env, fill real values, `cd messenger-bot && npm start` — no errors at startup |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
