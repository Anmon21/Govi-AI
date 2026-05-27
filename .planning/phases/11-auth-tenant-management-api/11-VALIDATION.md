---
phase: 11
slug: auth-tenant-management-api
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-27
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (>=8.0.0, already installed) |
| **Config file** | none — pytest discovers `tests/` by convention |
| **Quick run command** | `python3 -m pytest tests/test_auth.py -x -q` |
| **Full suite command** | `python3 -m pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds (21 existing + ~10 new auth tests) |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/test_auth.py -x -q`
- **After every plan wave:** Run `python3 -m pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 11-W0-01 | 01 | 0 | TENANT-01,02,03 | — | Wave 0 test stubs exist | infra | `python3 -m pytest tests/test_auth.py --collect-only -q` | ❌ Wave 0 | ⬜ pending |
| 11-01-01 | 01 | 1 | SC-1 | T-login | `POST /auth/login` valid → signed JWT | unit | `pytest tests/test_auth.py -k "login_success" -x` | ❌ Wave 0 | ⬜ pending |
| 11-01-02 | 01 | 1 | SC-1 | T-login | Invalid credentials → 401 | unit | `pytest tests/test_auth.py -k "login_invalid" -x` | ❌ Wave 0 | ⬜ pending |
| 11-01-03 | 01 | 1 | SC-4 | T-deactivated | Deactivated tenant → 401 | unit | `pytest tests/test_auth.py -k "inactive_tenant" -x` | ❌ Wave 0 | ⬜ pending |
| 11-02-01 | 02 | 2 | TENANT-01 | T-create | `POST /admin/tenants` creates tenant with bcrypt hash | unit+int | `pytest tests/test_auth.py -k "create_tenant" -x` | ❌ Wave 0 | ⬜ pending |
| 11-02-02 | 02 | 2 | TENANT-01 | T-dup | Duplicate email → 409 | unit | `pytest tests/test_auth.py -k "duplicate_email" -x` | ❌ Wave 0 | ⬜ pending |
| 11-02-03 | 02 | 2 | TENANT-02 | T-list | `GET /admin/tenants` lists only non-super-admin tenants with page_count | integration | `pytest tests/test_auth.py -k "list_tenants" -x` | ❌ Wave 0 | ⬜ pending |
| 11-02-04 | 02 | 2 | TENANT-03 | T-delete | `DELETE /admin/tenants/{id}` soft-deletes tenant + pages | integration | `pytest tests/test_auth.py -k "soft_delete" -x` | ❌ Wave 0 | ⬜ pending |
| 11-03-01 | 03 | 3 | SC-5 | T-isolation | `GET /tenants/me` returns own record only | integration | `pytest tests/test_auth.py -k "tenant_isolation" -x` | ❌ Wave 0 | ⬜ pending |
| 11-03-02 | 03 | 3 | SC-5 | T-403 | Non-super-admin token → 403 on `/admin/tenants` | unit | `pytest tests/test_auth.py -k "forbidden" -x` | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_auth.py` — stubs for SC-1 through SC-5 and TENANT-01 through TENANT-03 (9 test functions)
- [ ] `pip install "PyJWT>=2.8.0" "passlib[bcrypt]>=1.7.4"` + update `requirements.txt`
- [ ] `tests/conftest.py` — extend with `db_client` fixture: `TestClient` wired to tmp-path SQLite DB with seeded super-admin row (pattern: `test_db_foundation.py` monkeypatch approach)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| JWT decode in external client (e.g. Postman) | SC-1 | Verify token is valid JWT format | Decode `access_token` at jwt.io — confirm `sub`, `role`, `exp` claims |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
