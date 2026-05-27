---
phase: 10
slug: db-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-27
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.2 |
| **Config file** | None — run from project root |
| **Quick run command** | `python3 -m pytest tests/test_db_foundation.py -q` |
| **Full suite command** | `python3 -m pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/ -q`
- **After every plan wave:** Run `python3 -m pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | DB-01 | T-10-SQL | Parameterized queries only — no f-string SQL | unit | `python3 -m pytest tests/test_db_foundation.py::test_schema_creates_all_tables -x` | ❌ W0 | ⬜ pending |
| 10-01-02 | 01 | 1 | DB-01 | — | N/A | unit | `python3 -m pytest tests/test_db_foundation.py::test_wal_mode_enabled -x` | ❌ W0 | ⬜ pending |
| 10-01-03 | 01 | 1 | DB-01 | — | N/A | unit | `python3 -m pytest tests/test_db_foundation.py::test_busy_timeout -x` | ❌ W0 | ⬜ pending |
| 10-02-01 | 02 | 1 | DB-01 | T-10-KEY | Key from env only — never written to DB | unit | `python3 -m pytest tests/test_db_foundation.py::test_fernet_round_trip -x` | ❌ W0 | ⬜ pending |
| 10-03-01 | 03 | 2 | DB-01 | — | N/A (regression) | unit | `python3 -m pytest tests/test_content.py tests/test_health.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_db_foundation.py` — 4 test functions covering all DB-01 success criteria (~20 lines, uses `tmp_path` fixture for file-based DB)
- [ ] No new `conftest.py` needed — existing fixtures are vault-focused; DB tests use `tmp_path` directly

*Existing infrastructure (`tests/test_content.py`, `tests/test_health.py`) covers no-regression criterion.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `init_db.py` standalone script runs end-to-end | DB-01 | Script output verification | Run `python3 scripts/init_db.py` — confirm exit 0 and `govi.db` created |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
