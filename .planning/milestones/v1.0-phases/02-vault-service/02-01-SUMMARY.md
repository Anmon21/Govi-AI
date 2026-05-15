---
phase: 02-vault-service
plan: 01
subsystem: backend/testing
tags:
  - python
  - fastapi
  - pytest
  - vault
dependency_graph:
  requires:
    - "01-03: walking skeleton (FastAPI app)"
  provides:
    - "pytest test suite skeleton (RED state)"
    - "vault_path config field"
    - "python-frontmatter dependency"
  affects:
    - "app/config.py (Settings class)"
    - "requirements.txt"
tech_stack:
  added:
    - "python-frontmatter==1.1.0"
    - "pytest==8.4.2"
  patterns:
    - "pytest fixtures with monkeypatch + TestClient for FastAPI integration tests"
    - "tmp_path-based vault isolation per test"
key_files:
  created:
    - "tests/__init__.py"
    - "tests/conftest.py"
    - "tests/test_content.py"
    - "tests/test_health.py"
  modified:
    - "requirements.txt"
    - "app/config.py"
decisions:
  - "Downgraded pytest pin from >=9.0.3 to >=8.0.0: pytest 9.x requires Python>=3.10; system has Python 3.9.6. pytest 8.4.2 installed — all fixture/collection features needed are identical."
  - "Used write_md helper in both conftest.py and test_content.py (duplicate) — conftest version is a fixture helper, test_content version is a local helper used directly. Both serve distinct call sites."
metrics:
  duration: "~10 minutes"
  completed: "2026-05-14"
  tasks_completed: 3
  files_changed: 6
---

# Phase 2 Plan 1: Test Scaffolding and Dependency Setup Summary

Test scaffolding for vault service with python-frontmatter 1.1.0 and pytest 8.4.2, locking the executable contract via 10 failing tests before Plan 02 implements the content router.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add Phase 2 dependencies and vault_path config | d143ff7 | requirements.txt, app/config.py |
| 2 | Create tests/ package with conftest fixtures | 8d6c18a | tests/__init__.py, tests/conftest.py |
| 3 | Write failing test stubs | 857f3ad | tests/test_content.py, tests/test_health.py |

## Installed Package Versions

| Package | Version Installed |
|---------|-------------------|
| python-frontmatter | 1.1.0 |
| pytest | 8.4.2 |

Both installed via `pip install --user` into system Python 3.9.6 user site-packages.

## Test Functions Created

### tests/test_content.py (8 functions)

| Function | Requirement | What It Tests |
|----------|-------------|---------------|
| `test_vault_loads_at_startup` | VAULT-01 | health shows content_count=1 after startup load |
| `test_get_content_by_id` | VAULT-02 | GET /content/q1 returns 200 with id, title, body |
| `test_get_content_missing_returns_404` | VAULT-02 | GET /content/nonexistent returns 404 |
| `test_missing_vault_soft_fails` | VAULT-01 D-03 | missing path -> 200 health, content_count=0, vault_loaded=False |
| `test_disabled_files_excluded` | VAULT-03 | enabled:true served, enabled:false returns 404 |
| `test_malformed_frontmatter_skipped` | VAULT-03 | missing required fields silently skipped |
| `test_enabled_string_true_rejected` | VAULT-03 Pitfall 3 | quoted "true" string is NOT served (strict bool) |
| `test_reload_endpoint` | QA-04 | POST /content/reload returns reloaded:True and new content is accessible |

### tests/test_health.py (2 functions)

| Function | Requirement | What It Tests |
|----------|-------------|---------------|
| `test_health_includes_vault_stats` | VAULT-01 | /health has status, vault_loaded, content_count keys |
| `test_health_vault_loaded_true_when_vault_reachable` | VAULT-01 | vault_loaded=True and content_count=1 after loading a valid file |

## RED State Confirmation

`python -m pytest tests/ --collect-only -q` produces:

```
ImportError while loading conftest '.../tests/conftest.py'.
conftest.py imports `app.routers.content` which does not exist.
ModuleNotFoundError: No module named 'app.routers.content'
```

This is the expected RED state. Plan 02 creates `app/routers/content.py`, turning all 10 tests GREEN with no test modifications.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pytest 9.x not installable on Python 3.9**

- **Found during:** Task 1 -- `pip install pytest>=9.0.3` failed
- **Issue:** pytest>=9.0.0 requires Python>=3.10; system has CPython 3.9.6
- **Fix:** Changed requirements.txt pin from `pytest>=9.0.3` to `pytest>=8.0.0`; pytest 8.4.2 installed successfully. The 8.x series provides all fixture and collection features the tests need.
- **Files modified:** requirements.txt
- **Commit:** d143ff7

## Threat Flags

None. Wave 0 ships only test scaffolding and a config field -- no new network endpoints, auth paths, or file access at trust boundaries.

## Known Stubs

None. This plan creates test stubs (which are intentionally failing because the module they test does not exist yet), not implementation stubs. The failing-test state is the correct RED outcome. Plan 02 resolves it.

## Self-Check: PASSED

- tests/__init__.py exists and is empty
- tests/conftest.py exists with `client`, `vault_dir` fixtures and `write_md` helper
- tests/test_content.py has 8 named test functions
- tests/test_health.py has 2 named test functions
- requirements.txt contains python-frontmatter>=1.1.0 and pytest>=8.0.0
- app/config.py has `vault_path: str = ""`
- python -m pytest --collect-only produces ImportError (RED state)
- No modifications to app/routers/, app/main.py, or any other production code
- Commits d143ff7, 8d6c18a, 857f3ad all exist in git log
