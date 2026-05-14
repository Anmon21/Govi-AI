---
phase: 02-vault-service
plan: "02"
subsystem: vault-content-api
tags:
  - python
  - fastapi
  - vault
  - obsidian
dependency_graph:
  requires:
    - 02-01  # failing test stubs from Plan 01
  provides:
    - content-router  # GET /content/{id}, POST /content/reload
    - health-vault-stats  # vault_loaded + content_count in /health
    - vault-loader  # load_vault() + _vault cache
  affects:
    - app/main.py
    - app/routers/health.py
tech_stack:
  added: []
  patterns:
    - asynccontextmanager lifespan for startup initialization
    - module-level dict cache with clear()+update() pattern for safe mutation across scopes
    - strict isinstance bool check for YAML-parsed enabled field
key_files:
  created:
    - app/routers/content.py
  modified:
    - app/routers/health.py
    - app/main.py
    - .env.example
decisions:
  - "Used clear()+update() in lifespan (not reassignment) per RESEARCH Pitfall 1 — prevents local binding that leaves routes reading stale empty dict"
  - "vault_loaded reflects directory reachability (path set AND isdir), not cache non-emptiness — gives operators actionable signal"
  - "Strict isinstance(enabled, bool) check rejects YAML string 'true' per VAULT-03 contract"
  - "yaml.YAMLError included in except tuple to satisfy T-2-02 threat mitigation (malformed YAML does not crash load loop)"
metrics:
  duration: "~12 minutes"
  completed: "2026-05-14T14:49:28Z"
  tasks_completed: 3
  files_modified: 4
---

# Phase 02 Plan 02: Vault Content API Implementation Summary

Implemented the vault loader, content router, extended health endpoint, and lifespan registration. All 10 tests written in Plan 01 turned GREEN.

## pytest Output

```
============================= test session starts ==============================
platform darwin -- Python 3.9.6, pytest-8.4.2, pluggy-1.6.0
rootdir: /Users/anmon/Desktop/Govi-AI

tests/test_content.py::test_vault_loads_at_startup PASSED                [ 10%]
tests/test_content.py::test_get_content_by_id PASSED                     [ 20%]
tests/test_content.py::test_get_content_missing_returns_404 PASSED       [ 30%]
tests/test_content.py::test_missing_vault_soft_fails PASSED              [ 40%]
tests/test_content.py::test_disabled_files_excluded PASSED               [ 50%]
tests/test_content.py::test_malformed_frontmatter_skipped PASSED         [ 60%]
tests/test_content.py::test_enabled_string_true_rejected PASSED          [ 70%]
tests/test_content.py::test_reload_endpoint PASSED                       [ 80%]
tests/test_health.py::test_health_includes_vault_stats PASSED            [ 90%]
tests/test_health.py::test_health_vault_loaded_true_when_vault_reachable PASSED [100%]

============================== 10 passed in 0.04s ==============================
```

**Result: 10/10 tests GREEN.**

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create app/routers/content.py | fa810fd | app/routers/content.py (new, 81 lines) |
| 2 | Extend app/routers/health.py | 212a601 | app/routers/health.py |
| 3 | Wire lifespan + content router | 9bf7290 | app/main.py, .env.example |

## What Was Built

**app/routers/content.py** (81 lines): Module-level `_vault: dict[str, dict] = {}` cache. `load_vault()` reads `settings.vault_path` via `os.scandir` (top-level only, no recursion per D-02), parses frontmatter with strict `isinstance(enabled, bool)` check, validates id/type/title as non-empty strings, handles ID collisions (first wins), and soft-fails on missing VAULT_PATH (D-03). `GET /content/{id}` returns `ContentResponse` or 404. `POST /content/reload` uses `global _vault` to rebind the module-level dict atomically.

**app/routers/health.py** (24 lines): Extended with `HealthResponse(BaseModel)` — status, vault_loaded (bool), content_count (int). `vault_loaded` reflects `bool(settings.vault_path) and os.path.isdir(settings.vault_path)` — directory reachability, not cache non-emptiness.

**app/main.py** (27 lines): Added `asynccontextmanager` lifespan that calls `content._vault.clear(); content._vault.update(content.load_vault())` at startup. Content router registered after health and ai routers. `lifespan=lifespan` passed to `FastAPI()`.

**.env.example**: Appended `VAULT_PATH=/path/to/your/obsidian/vault/govi-content`.

## Deviations from Plan

### Auto-added: non-empty string check for type/title fields

**Found during:** Task 1 implementation
**Issue:** The plan specified `isinstance(meta.get(k), str)` but an empty string `""` would pass isinstance while being semantically invalid. The `bad.md` test file has `enabled: true` with no id/type/title — but a file with `type: ""` would silently pass the isinstance check and produce a useless entry.
**Fix:** Changed the validation condition to `not all(isinstance(meta.get(k), str) and meta.get(k) for k in ("type", "title"))` — requiring non-empty strings. This matches the stricter intent of "required string fields" in the plan's warning message.
**Files modified:** app/routers/content.py
**Commit:** fa810fd

No other deviations — plan executed as written.

## Known Stubs

None. All endpoints return live data from `_vault` and `settings`.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: unauthenticated-write | app/routers/content.py | POST /content/reload is unauthenticated — anyone with HTTP access can trigger a filesystem re-read. Accepted for v1 per T-2-04; flagged for Phase 5 hardening. |

## Self-Check

- [x] app/routers/content.py exists (81 lines)
- [x] app/routers/health.py modified (24 lines)
- [x] app/main.py modified (27 lines)
- [x] .env.example updated with VAULT_PATH
- [x] Commits fa810fd, 212a601, 9bf7290 exist
- [x] All 10 pytest tests GREEN
