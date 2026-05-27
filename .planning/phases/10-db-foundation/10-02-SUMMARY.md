---
phase: 10
plan: "02"
subsystem: backend-config-crypto
tags: [fernet, encryption, config, settings, tdd]
dependency_graph:
  requires: [10-01]
  provides: [app/crypto.py, settings.db_path, settings.fernet_key]
  affects: [Phase 12 token encryption, Plan 03 DB path config]
tech_stack:
  added: [cryptography>=41.0.0]
  patterns: [lazy-key-validation, Fernet AES-128-CBC+HMAC-SHA256]
key_files:
  created: [app/crypto.py]
  modified: [app/config.py, requirements.txt, .env.example, tests/test_db_foundation.py]
decisions:
  - "Lazy key loading: _fernet() reads settings.fernet_key at call time (not import time) so monkeypatch works in tests without module reload"
  - "No try/except in crypto.py: matches app/routers/ai.py propagation style — errors surface naturally"
  - "InvalidToken re-exported from app.crypto: Phase 12 can catch decrypt failures with a single import"
metrics:
  duration: "2m"
  completed: "2026-05-27"
  tasks_completed: 2
  files_changed: 5
---

# Phase 10 Plan 02: Fernet Encryption Helpers Summary

Fernet encrypt/decrypt helpers for Page Access Tokens using cryptography library, with Settings extended for DB_PATH and FERNET_KEY env vars.

## What Was Built

### Task 1: Settings extension, requirements, env docs
- Added `db_path: str = "govi.db"` and `fernet_key: str = ""` to `Settings` class in `app/config.py`
- Appended `cryptography>=41.0.0` to `requirements.txt`
- Documented `DB_PATH` and `FERNET_KEY` in `.env.example` with generation hint — no real key material (T-10-KEY compliant)

### Task 2: app/crypto.py (TDD RED/GREEN)
- Created `app/crypto.py` with three functions:
  - `_fernet() -> Fernet`: lazy key loader from `settings.fernet_key`
  - `encrypt_token(plain: str) -> str`: Fernet encrypt to base64 string
  - `decrypt_token(enc: str) -> str`: Fernet decrypt from base64 string
- `InvalidToken` re-exported for Phase 12 callers
- Appended `test_fernet_round_trip(monkeypatch)` to `tests/test_db_foundation.py`

## Verification Results

- `python3 -m pytest tests/test_db_foundation.py -q` → 4 passed (3 DB + 1 Fernet round-trip)
- `python3 -m pytest tests/ -q` → 18 passed (full suite green)
- `from app.crypto import InvalidToken` → `InvalidToken` (re-export confirmed)
- `from app.config import settings; print(settings.db_path)` → `govi.db`
- T-10-KEY grep gates: no hardcoded key material, no sqlite3/file-writes/prints in crypto.py

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | f158fa8 | feat(10-02): extend Settings with db_path and fernet_key; add cryptography dep |
| Task 2 (RED) | c6829c5 | test(10-02): add failing test_fernet_round_trip for encrypt/decrypt round-trip |
| Task 2 (GREEN) | 442f377 | feat(10-02): create app/crypto.py Fernet encrypt/decrypt helpers |

## TDD Gate Compliance

- RED gate: commit c6829c5 (`test(10-02)`) — test failed with ModuleNotFoundError as expected
- GREEN gate: commit 442f377 (`feat(10-02)`) — all 4 tests pass

## Deviations from Plan

None - plan executed exactly as written.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced beyond what the plan's threat model covers. The `app/crypto.py` module is pure in-memory encryption/decryption — no I/O side effects. T-10-KEY and T-10-CRYPTO-ROLL mitigations applied as specified.

## Known Stubs

None — all functions are fully implemented. Phase 12 is the first consumer of `encrypt_token`/`decrypt_token`; the helpers are complete and ready.

## Self-Check: PASSED

- app/crypto.py exists: FOUND
- app/config.py has db_path and fernet_key: FOUND
- requirements.txt has cryptography>=41.0.0: FOUND
- .env.example has DB_PATH and FERNET_KEY: FOUND
- tests/test_db_foundation.py has test_fernet_round_trip: FOUND
- Commit f158fa8 exists: FOUND
- Commit c6829c5 exists: FOUND
- Commit 442f377 exists: FOUND
