---
phase: 10-db-foundation
fixed_at: 2026-05-27T16:05:00Z
review_path: .planning/phases/10-db-foundation/10-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 10: Code Review Fix Report

**Fixed at:** 2026-05-27T16:05:00Z
**Source review:** .planning/phases/10-db-foundation/10-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 7 (CR-01, CR-02, WR-01, WR-02, WR-03, WR-04, WR-05)
- Fixed: 7
- Skipped: 0

## Fixed Issues

### CR-01: `decrypt_token` does not catch `InvalidToken`

**Files modified:** `app/crypto.py`
**Commit:** d93275e
**Applied fix:** Wrapped `_fernet().decrypt(...)` in a try/except block. Catches `cryptography.fernet.InvalidToken` and re-raises as `ValueError("Token decryption failed: invalid ciphertext or wrong key")`. This also resolves WR-03 — the previously unused `InvalidToken` import is now wired into the catch block.

---

### CR-02: Empty `fernet_key` default silently accepted

**Files modified:** `app/crypto.py`
**Commit:** 5c190d8
**Applied fix:** Added a guard at the top of `_fernet()` that raises `RuntimeError("FERNET_KEY is not configured. Set it in .env.")` when `settings.fernet_key` is empty. Used Option B (guard in `_fernet()`) rather than Option A (Pydantic `field_validator`) because Option A would break the test suite and server startup: `settings = Settings()` is instantiated at module import time, and the `.env` file has no FERNET_KEY set. The guard fires at first use with a clear message — satisfying the requirement without disrupting existing tests that monkeypatch the value at runtime. This fix requires human verification: logic is correct but the trade-off between startup-time vs first-use detection is worth confirming.

---

### WR-01: `init_schema` leaks connection on exception

**Files modified:** `app/db.py`
**Commit:** 0092976
**Applied fix:** Wrapped `conn.execute("PRAGMA journal_mode=WAL")`, `conn.executescript(...)`, and `conn.commit()` in a `try/finally` block with `conn.close()` in the `finally` clause. Connection is now guaranteed to close even if `executescript` or `commit` raises.

---

### WR-02: `qa_items.category_id` missing type documentation

**Files modified:** `app/db.py`
**Commit:** 0092976
**Applied fix:** Added inline SQL comment above `category_id`: `-- category_id must reference a row where type='category'; enforced at application layer`. This was committed atomically with WR-01 since both changes are in the same function in `app/db.py`.

---

### WR-03: `InvalidToken` imported but unused

**Files modified:** `app/crypto.py`
**Commit:** d93275e
**Applied fix:** Resolved as a side effect of CR-01. The `InvalidToken` import on line 1 is now used in the `except InvalidToken as exc:` catch block added by CR-01. No separate commit needed.

---

### WR-04: No test for `decrypt_token` with invalid ciphertext

**Files modified:** `tests/test_db_foundation.py`
**Commit:** 26c87fd
**Applied fix:** Added two new tests: `test_decrypt_token_invalid_ciphertext` (passes a non-Fernet string, asserts `ValueError` with "decryption failed") and `test_decrypt_token_wrong_key` (encrypts with key1, attempts decrypt with key2, asserts `ValueError` with "decryption failed"). Also added `import pytest` which was missing from the file.

---

### WR-05: No idempotency test for `init_schema`

**Files modified:** `tests/test_db_foundation.py`
**Commit:** 26c87fd
**Applied fix:** Added `test_schema_idempotent` which calls `init_schema` twice on the same DB path and asserts no exception is raised. Committed atomically with WR-04 since both changes are in `tests/test_db_foundation.py`.

---

## Test Results

All 21 tests pass after fixes:

```
21 passed in 0.09s
```

---

_Fixed: 2026-05-27T16:05:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
