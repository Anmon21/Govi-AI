---
phase: 02
slug: vault-service
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-14
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + FastAPI TestClient (httpx) |
| **Config file** | none — Wave 0 installs pytest + httpx + python-frontmatter |
| **Quick run command** | `python -m pytest tests/test_content.py tests/test_health.py -q` |
| **Full suite command** | `python -m pytest tests/ -q --tb=short` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -q --tb=short`
- **After every plan wave:** Run full suite
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 0 | VAULT-01 | — | N/A | unit | `grep -q 'vault_path' app/config.py && echo OK` | ❌ W0 | ⬜ pending |
| 2-01-02 | 01 | 0 | VAULT-01 | — | N/A | integration | `python -m pytest tests/test_content.py -q` | ❌ W0 | ⬜ pending |
| 2-01-03 | 01 | 0 | VAULT-02 | — | N/A | integration | `python -m pytest tests/test_content.py::test_get_content_by_id -q` | ❌ W0 | ⬜ pending |
| 2-01-04 | 01 | 0 | VAULT-03 | — | N/A | integration | `python -m pytest tests/test_content.py::test_disabled_not_served -q` | ❌ W0 | ⬜ pending |
| 2-01-05 | 01 | 0 | VAULT-01 | — | N/A | integration | `python -m pytest tests/test_health.py::test_health_vault_stats -q` | ❌ W0 | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — tmp_path vault fixture with sample .md files (enabled + disabled)
- [ ] `tests/test_content.py` — stubs for VAULT-01, VAULT-02, VAULT-03, reload endpoint
- [ ] `tests/test_health.py` — stub for vault stats in /health response
- [ ] `requirements.txt` updated — add `python-frontmatter>=1.1.0`, `pytest>=9.0.3`, `httpx>=0.27.0`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Soft-fail on missing VAULT_PATH at server start | VAULT-01 | Requires process launch observation | Start server with VAULT_PATH unset, confirm it starts and logs a warning; `curl /health` returns content_count=0 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
