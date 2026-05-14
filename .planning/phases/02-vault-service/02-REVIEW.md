---
phase: 02-vault-service
reviewed: 2026-05-14T14:54:22Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - app/routers/content.py
  - app/routers/health.py
  - app/main.py
  - app/config.py
  - tests/conftest.py
  - tests/test_content.py
  - tests/test_health.py
findings:
  critical: 2
  warning: 4
  info: 2
  total: 8
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-05-14T14:54:22Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Reviewed the vault service implementation: `load_vault()`, `/content/{id}`, `POST /content/reload`, health endpoint vault stats, lifespan wiring, and the test suite. The core read path is sound — frontmatter parsing, enabled-filter, required-field validation, and dict-key-only content addressing all work correctly. Two blockers require fixing before this ships: an unguarded `os.scandir()` call that crashes the process on permission-denied, and an unauthenticated `/content/reload` endpoint that any external caller can trigger. Four warnings cover a misleading health field, non-deterministic ID collision resolution, inconsistent reload strategy between lifespan and the reload handler, and an untested crash path. Two info items cover test duplication and a missing test scenario.

---

## Critical Issues

### CR-01: `os.scandir()` PermissionError crashes the process

**File:** `app/routers/content.py:31`

**Issue:** `load_vault()` wraps per-file I/O errors (lines 34-39) but does not wrap the `os.scandir()` call itself. If the vault directory exists and passes the `os.path.isdir()` check on line 26 but has mode `000` (or is otherwise unreadable by the process), `os.scandir()` raises `PermissionError` (a subclass of `OSError`). This exception is unhandled and propagates through `lifespan()` in `app/main.py`, crashing the application at startup. The same crash occurs when `reload_vault()` calls `load_vault()` at runtime. Verified empirically: `os.path.isdir()` returns `True` for a `chmod 000` directory on macOS/Linux, making the guard on line 26 insufficient.

**Fix:**
```python
def load_vault() -> dict[str, dict]:
    vault_path = settings.vault_path
    if not vault_path or not os.path.isdir(vault_path):
        logger.warning("VAULT_PATH not set or directory missing — starting with empty content")
        return {}

    result: dict[str, dict] = {}
    try:
        entries = list(os.scandir(vault_path))
    except OSError as e:
        logger.warning("Cannot read vault directory %s: %s — starting with empty content", vault_path, e)
        return {}

    for entry in entries:
        if not entry.is_file() or not entry.name.endswith(".md"):
            continue
        # ... rest unchanged
```

---

### CR-02: `POST /content/reload` is unauthenticated and callable by any origin

**File:** `app/routers/content.py:76-81`

**Issue:** The reload endpoint carries no authentication, no API key check, and no rate limiting. Combined with `allow_origins=["*"]` in `app/main.py:19`, any webpage a user visits can issue a cross-origin `fetch('POST /content/reload')` and trigger a full filesystem scan. Non-browser clients (curl, scripts) require no credentials at all. In production, this endpoint causes the server to re-read its entire vault directory on demand from any caller — a low-effort trigger for repeated I/O that also lets an attacker confirm the vault directory layout via timing or error responses. At minimum this is an unauthorized privileged operation.

**Fix:** Add a shared-secret check before the reload logic. The simplest approach consistent with the existing env-var config pattern:

```python
# app/config.py — add:
reload_secret: str = ""

# app/routers/content.py — update reload handler:
from fastapi import APIRouter, HTTPException, Header
from typing import Annotated

@router.post("/reload")
async def reload_vault(x_reload_secret: Annotated[str | None, Header()] = None):
    if settings.reload_secret and x_reload_secret != settings.reload_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")
    global _vault
    new_vault = load_vault()
    _vault = new_vault
    return {"reloaded": True, "content_count": len(_vault)}
```

---

## Warnings

### WR-01: `vault_loaded` in health response does not reflect actual load success

**File:** `app/routers/health.py:22`

**Issue:** `vault_loaded` is computed as `bool(settings.vault_path) and os.path.isdir(settings.vault_path)` — it checks only whether the path is configured and exists as a directory. It does not reflect whether `load_vault()` actually populated the cache. If the vault directory exists but is unreadable (permission denied, or all files are disabled/invalid), `vault_loaded` returns `True` while `content_count` is `0`. This misleads operators: the health check appears green while no content is being served.

**Fix:** Drive `vault_loaded` from the actual cache state rather than re-checking the filesystem at request time:

```python
@router.get("", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="ok",
        vault_loaded=len(content._vault) > 0,
        content_count=len(content._vault),
    )
```

If a distinction between "vault configured" and "vault has content" is needed, add a separate `vault_configured` field rather than overloading `vault_loaded`.

---

### WR-02: ID collision winner is non-deterministic

**File:** `app/routers/content.py:50-52`

**Issue:** When two `.md` files carry the same `id` in their frontmatter, the first file encountered by `os.scandir()` wins. `os.scandir()` returns entries in filesystem order, which varies by OS, filesystem type, and whether files were added in the same directory-entry block. The same vault directory can produce different collision winners across deployments or after an `fsck`. The log message says "skipping duplicate" but does not name the winning file, making it difficult to diagnose which content is actually being served.

**Fix:** Log both the winner (already in `result` at collision time) and the loser so the operator knows exactly which file is active:

```python
if content_id in result:
    logger.warning(
        "ID collision: '%s' already loaded; skipping %s (kept earlier entry)",
        content_id,
        entry.name,
    )
    continue
```

For deterministic behavior, sort entries before iterating:

```python
for entry in sorted(os.scandir(vault_path), key=lambda e: e.name):
```

---

### WR-03: Inconsistent vault update strategy between lifespan and reload handler

**File:** `app/main.py:11-12` and `app/routers/content.py:77-80`

**Issue:** The lifespan handler uses in-place mutation (`_vault.clear()` + `_vault.update()`), while `reload_vault()` uses a full rebind (`global _vault; _vault = new_vault`). These are semantically equivalent in CPython because `health.py` re-reads `content._vault` as a module attribute on every request (so it always sees the current binding). However, the inconsistency creates a correctness trap: if any other code were to hold a direct reference to `_vault` (e.g., `my_ref = content._vault`), the rebind in `reload_vault()` would silently diverge from that reference. Additionally, the `clear()` + `update()` pattern in lifespan creates a window where `_vault` is empty, causing concurrent GETs to return 404 during that window. While startup concurrency is unlikely, the pattern is wrong by construction.

**Fix:** Use the same atomic-rebind approach everywhere:

```python
# app/main.py lifespan — replace clear+update with rebind:
@asynccontextmanager
async def lifespan(app: FastAPI):
    content._vault = content.load_vault()
    yield
```

This removes the empty-window race and makes both update paths identical.

---

### WR-04: Tests manually pre-populate `_vault` before entering `TestClient` context, but lifespan overwrites it

**File:** `tests/test_content.py:17-19`, `tests/test_health.py:30-31`, `tests/conftest.py:18-19`

**Issue:** Multiple tests follow this pattern:

```python
monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
content_module._vault.clear()
content_module._vault.update(content_module.load_vault())
with TestClient(app) as client:
    ...
```

`TestClient` used as a context manager triggers the FastAPI lifespan, which calls `content._vault.clear()` + `content._vault.update(content.load_vault())`. This overwrites the manual pre-population. The tests pass only because `monkeypatch.setattr` is applied before `TestClient` enters, so the lifespan re-reads the correct `vault_path` and gets the same result. The manual pre-population is dead code — it is fully redundant and creates a false impression that tests control vault state independently of the lifespan. If the lifespan logic ever changes (e.g., adding async loading), these tests will silently break in a confusing way.

**Fix:** Remove the manual `_vault` manipulation before `TestClient` entry. Rely solely on `monkeypatch.setattr` to control `vault_path` before the lifespan fires:

```python
def test_get_content_by_id(tmp_path, monkeypatch):
    write_md(tmp_path / "q1.md", "id: q1\ntype: faq\ntitle: Test Title\nenabled: true", "Answer body")
    monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
    with TestClient(app) as client:
        resp = client.get("/content/q1")
        assert resp.status_code == 200
```

---

## Info

### IN-01: `write_md` helper is duplicated between `conftest.py` and `test_content.py`

**File:** `tests/conftest.py:9-11` and `tests/test_content.py:7-9`

**Issue:** Both files define an identical `write_md(path, frontmatter_block, body)` helper with the same implementation and only a trivially different default body string (`"Body"` vs `"Body text"`). The `conftest.py` version is not imported or used by `test_content.py`.

**Fix:** Remove `write_md` from `test_content.py` and import it from `conftest.py`, or declare it only in `conftest.py` (pytest auto-imports conftest fixtures and helpers are available if exposed as fixtures or imported explicitly).

---

### IN-02: No test for `os.scandir()` permission error path in `load_vault()`

**File:** `tests/test_content.py` (absent)

**Issue:** After fixing CR-01, the new `OSError` handler around `os.scandir()` will have no test coverage. The existing `test_missing_vault_soft_fails` only covers the case where `vault_path` does not exist at all (handled by the `os.path.isdir()` guard), not the case where the directory exists but is unreadable.

**Fix:** Add a test that creates a `tmp_path` subdirectory, `chmod`s it to `0o000`, sets it as `vault_path`, and asserts that `load_vault()` returns `{}` without raising:

```python
def test_unreadable_vault_soft_fails(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    vault.chmod(0o000)
    monkeypatch.setattr(config_module.settings, "vault_path", str(vault))
    try:
        result = content_module.load_vault()
        assert result == {}
    finally:
        vault.chmod(0o755)  # restore so tmp_path cleanup succeeds
```

---

_Reviewed: 2026-05-14T14:54:22Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
