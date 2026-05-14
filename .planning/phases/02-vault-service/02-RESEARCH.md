# Phase 2: Vault Service - Research

**Researched:** 2026-05-14
**Domain:** FastAPI file loading, YAML frontmatter parsing, in-memory caching, hot-reload
**Confidence:** HIGH

---

## Summary

Phase 2 adds a vault loading subsystem to the existing FastAPI backend. The service reads `.md` files from a local directory at startup, parses YAML frontmatter via `python-frontmatter`, caches enabled entries in a module-level dict keyed by `id`, and exposes two new endpoints: `GET /content/{id}` and `POST /content/reload`. The existing `GET /health` endpoint is extended with vault stats.

The stack is simple: one new library (`python-frontmatter 1.1.0`), one new router (`app/routers/content.py`), a lifespan hook on the existing `app` object, and module-level state shared between the content router and the lifespan function. No database, no queue, no external process — purely in-process file I/O at startup and on-demand reload.

The critical design choice is where the vault cache lives: a module-level dict in `app/routers/content.py` is the idiomatic pattern for this scale. FastAPI's `app.state` is the alternative but requires passing `request.app.state` through every handler. The lifespan pattern (`asynccontextmanager`) is the current recommended approach; `@app.on_event` is deprecated in FastAPI 0.95+.

**Primary recommendation:** Module-level `_vault: dict[str, dict]` in `app/routers/content.py`, loaded in `app/main.py` lifespan, replaced atomically in `POST /content/reload`. No asyncio.Lock needed — Python's GIL and single-threaded async event loop make dict reassignment safe for this workload.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** VAULT_PATH points to a single flat directory — all `.md` content files live at the top level of that folder. No nested category subfolders.
- **D-02:** Only `.md` files directly inside VAULT_PATH are loaded — subdirectory traversal is disabled. Anything in subfolders is automatically ignored.
- **D-03:** If VAULT_PATH is not set or the directory does not exist at startup, the server starts normally, logs a warning, and serves zero content files. Content endpoints return 404. The service does not refuse to start.

### Claude's Discretion
- In-memory dict keyed by frontmatter `id` for the content cache
- `python-frontmatter` library for parsing
- New `app/routers/content.py` following the existing `APIRouter(prefix="/content", tags=["content"])` pattern
- Extend `app/config.py` Settings with `vault_path: str = ""`
- Extend `GET /health` to include `vault_loaded: bool` and `content_count: int`
- `POST /content/reload` hot-reload endpoint included in this phase
- Frontmatter schema: `id` (str), `type` (str), `title` (str), `enabled` (bool) — files without `enabled: true` excluded

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VAULT-01 | FastAPI loads Q&A content from Obsidian vault at startup via VAULT_PATH env var | lifespan hook + frontmatter.load() + os.scandir() |
| VAULT-02 | FastAPI serves content by stable frontmatter ID via GET /content/{id} | APIRouter pattern, in-memory dict lookup, HTTPException 404 |
| VAULT-03 | Vault file format uses frontmatter schema (id, type, title, enabled); files without enabled: true ignored | post.get() with type checks, filter by enabled bool |
| QA-04 | Admin can reload vault content without restarting (POST /content/reload) | atomic dict reassignment, same load function reuse |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Vault loading at startup | API / Backend | — | File I/O is server-side; lifespan runs in FastAPI process |
| In-memory content cache | API / Backend | — | Dict lives in FastAPI process memory |
| Content serving by ID | API / Backend | — | REST endpoint, no client-side involvement |
| Health stats (vault_loaded, content_count) | API / Backend | — | Extension of existing /health router |
| Hot-reload trigger | API / Backend | — | POST endpoint that re-runs load function |
| Env config (VAULT_PATH) | API / Backend | — | pydantic-settings loads from .env |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python-frontmatter | 1.1.0 | Parse YAML frontmatter from .md files | Purpose-built for Jekyll/Obsidian-style frontmatter; no alternative needed |
| PyYAML | 6.0.3 | YAML parsing (pulled as python-frontmatter dependency) | Auto-installed; do not add separately |
| fastapi | >=0.115.0 | Already in requirements.txt | No change |
| pytest | 9.0.3 | Test runner | Standard Python test framework |
| httpx | 0.28.1 | TestClient transport (already in requirements.txt as transitive dep) | Required by FastAPI TestClient |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| contextlib.asynccontextmanager | stdlib | Lifespan decorator | Always — it's the current FastAPI pattern |
| os | stdlib | scandir, path checks | File system traversal |
| logging | stdlib | Warning on missing VAULT_PATH | Replaces print() for production-appropriate output |

**Installation (additions only):**
```bash
pip install python-frontmatter==1.1.0 pytest>=9.0.3
```

Add to `requirements.txt`:
```
python-frontmatter>=1.1.0
pytest>=9.0.3
```

Note: `httpx` is already in `requirements.txt` (>=0.27.0) as a transitive FastAPI dependency and is what `TestClient` uses internally. No change needed.

**Version verification:** `python-frontmatter 1.1.0` confirmed via PyPI JSON API on 2026-05-14. `pytest 9.0.3` and `httpx 0.28.1` confirmed via PyPI JSON API on 2026-05-14. [VERIFIED: pypi.org]

---

## Architecture Patterns

### System Architecture Diagram

```
Startup (lifespan)
    |
    v
os.scandir(VAULT_PATH) --> filter *.md at top level
    |
    v
for each .md file:
    frontmatter.load(path) --> Post object
    validate required keys (id, type, title, enabled)
    skip if enabled != True
    check id collision
    store in _vault dict
    |
    v
_vault: dict[str, dict] populated in content.py module scope

Request: GET /content/{id}
    |
    v
content.py router --> _vault.get(id) --> 404 if missing --> ContentResponse

Request: POST /content/reload
    |
    v
content.py router --> load_vault() --> new_vault dict --> _vault = new_vault (atomic)

Request: GET /health
    |
    v
health.py router --> HealthResponse(status, vault_loaded, content_count)
    (reads _vault from content module)

VAULT_PATH missing/empty:
    |
    v
lifespan logs warning --> _vault remains {} --> server starts normally
```

### Recommended Project Structure
```
app/
├── config.py          # add vault_path: str = ""
├── main.py            # add lifespan + content router
├── routers/
│   ├── ai.py          # unchanged
│   ├── content.py     # NEW — vault cache + endpoints
│   └── health.py      # extend with vault stats
tests/
├── conftest.py        # tmp_path fixtures, TestClient setup
└── test_content.py    # vault load, content serve, reload tests
```

### Pattern 1: Module-Level Vault Dict (Shared State)

**What:** A module-level dict in `app/routers/content.py` holds the vault cache. The lifespan in `app/main.py` calls a `load_vault()` function that populates it.

**When to use:** Single-process FastAPI apps where all state lives in one Python process. Simpler than `app.state` because routers import the dict directly without needing `request`.

```python
# Source: FastAPI docs (fastapi.tiangolo.com/advanced/events) + official lifespan pattern
# app/routers/content.py

import logging
import os
from typing import Optional
import frontmatter
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content", tags=["content"])

_vault: dict[str, dict] = {}


class ContentResponse(BaseModel):
    id: str
    type: str
    title: str
    body: str


def load_vault() -> dict[str, dict]:
    """Load enabled .md files from VAULT_PATH into a fresh dict."""
    vault_path = settings.vault_path
    if not vault_path or not os.path.isdir(vault_path):
        logger.warning("VAULT_PATH not set or directory missing — starting with empty content")
        return {}

    result: dict[str, dict] = {}
    for entry in os.scandir(vault_path):
        if not entry.is_file() or not entry.name.endswith(".md"):
            continue
        try:
            with open(entry.path, encoding="utf-8") as f:
                post = frontmatter.load(f)
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Skipping %s: %s", entry.name, e)
            continue

        meta = post.metadata
        if not isinstance(meta.get("enabled"), bool) or not meta["enabled"]:
            continue
        content_id = meta.get("id")
        if not isinstance(content_id, str) or not content_id:
            logger.warning("Skipping %s: missing or non-string 'id'", entry.name)
            continue
        if content_id in result:
            logger.warning("ID collision: '%s' from %s (skipping duplicate)", content_id, entry.name)
            continue
        if not all(isinstance(meta.get(k), str) for k in ("type", "title")):
            logger.warning("Skipping %s: missing required string fields (type, title)", entry.name)
            continue

        result[content_id] = {
            "id": content_id,
            "type": meta["type"],
            "title": meta["title"],
            "body": post.content,
        }

    return result
```

```python
# app/main.py — lifespan pattern (replaces deprecated @app.on_event)
# Source: fastapi.tiangolo.com/advanced/events

from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.routers import content

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.routers.content import _vault, load_vault
    _vault.update(load_vault())     # populate in-place on startup
    yield

app = FastAPI(title="Govi AI", version="0.1.0", lifespan=lifespan)
app.include_router(content.router)
```

**Important:** Because `_vault` is declared as a module-level `dict` in `content.py`, `_vault.update(new)` mutates the same object. Reassigning `_vault = new_dict` inside lifespan would rebind a local name and NOT affect the module-level reference. Use `_vault.clear(); _vault.update(new)` for the startup case.

For `POST /content/reload`, the endpoint is inside `content.py` and CAN reassign `_vault` as a module global using `global _vault`.

### Pattern 2: Hot-Reload via Global Reassignment

**What:** POST /content/reload calls `load_vault()`, builds a new dict, and replaces the module-level `_vault`. Dict reassignment in Python is atomic from the GIL's perspective — no partial reads during replacement.

**When to use:** Single-process, single-worker deployments (which this project uses — no containerization, no gunicorn workers).

```python
# app/routers/content.py (continued)

@router.post("/reload")
async def reload_vault():
    global _vault
    new_vault = load_vault()
    _vault = new_vault          # atomic replacement
    return {"reloaded": True, "content_count": len(_vault)}


@router.get("/{content_id}", response_model=ContentResponse)
async def get_content(content_id: str):
    item = _vault.get(content_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Content not found")
    return ContentResponse(**item)
```

**Concurrency note:** Python dict replacement is safe under the GIL for single-process deployments. If the project ever moves to multiple workers (gunicorn with multiple processes), this pattern breaks — each process has its own `_vault`. For v1 scope this is not a concern. [ASSUMED — based on CLAUDE.md "no containerization" constraint, single worker assumed]

### Pattern 3: Extended Health Response

**What:** The health router imports the `_vault` reference from `content` module to read its current count.

```python
# app/routers/health.py
from fastapi import APIRouter
from pydantic import BaseModel
from app.routers import content

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    vault_loaded: bool
    content_count: int


@router.get("", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="ok",
        vault_loaded=len(content._vault) > 0,
        content_count=len(content._vault),
    )
```

**Circular import check:** `health.py` imports from `content.py`; `content.py` does not import from `health.py`. No circular import. `main.py` imports both routers, so this is safe.

### Anti-Patterns to Avoid

- **`@app.on_event("startup")`:** Deprecated since FastAPI 0.95.0. Use `lifespan` instead. [VERIFIED: fastapi.tiangolo.com/advanced/events]
- **`asyncio.Lock` for dict replacement:** Unnecessary overhead for single-process, read-heavy, single-writer workload. The GIL makes `_vault = new_dict` safe.
- **`app.state` for vault cache:** Requires `request.app.state.vault` threading through every route signature. Module-level dict is cleaner for this scale.
- **Recursive `os.walk`:** D-02 locks scanning to top-level only. Use `os.scandir` + `entry.is_file()` check.
- **`frontmatter.load("path/file.md")` without explicit encoding:** Obsidian files may have BOM. Use `open(..., encoding="utf-8")` then pass file object to `frontmatter.load()`.
- **Catching bare `Exception` in load loop:** Catch specific exceptions (`OSError`, `UnicodeDecodeError`, `yaml.YAMLError`) — log and continue rather than crashing the entire load.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML frontmatter parsing | Custom regex/split on `---` | `python-frontmatter` | Edge cases: TOML/JSON frontmatter, CRLF line endings, BOM, empty blocks, multi-doc YAML |
| File encoding detection | Custom BOM detector | `open(path, encoding="utf-8")` + `UnicodeDecodeError` catch | BOM handled by `utf-8-sig` if needed; bare `utf-8` is sufficient for Obsidian |

**Key insight:** Frontmatter parsing looks simple but has many edge cases (CRLF, BOM, empty `---` blocks, indented YAML, multiline strings). The library handles all of these.

---

## Common Pitfalls

### Pitfall 1: Lifespan Startup Dict Mutation vs Reassignment
**What goes wrong:** Assigning `_vault = load_vault()` inside lifespan does not update the module-level `_vault` — it creates a new local binding. Routes still see the empty original dict.
**Why it happens:** Python variable scoping — lifespan callback has its own local scope.
**How to avoid:** Use `_vault.clear(); _vault.update(load_vault())` in lifespan. In the reload endpoint (which is in `content.py`), `global _vault; _vault = new_dict` works correctly because you're in the same module.
**Warning signs:** `/health` returns `content_count: 0` even after vault files exist.

### Pitfall 2: Missing Frontmatter Returns Empty Metadata, Not Error
**What goes wrong:** `frontmatter.load()` on a file with no `---` block returns a Post with empty `metadata = {}`. Code accessing `post["id"]` raises `KeyError`.
**Why it happens:** The library treats missing frontmatter as valid — empty metadata is intentional for plain Markdown files. [VERIFIED: Context7/eyeseast/python-frontmatter]
**How to avoid:** Use `meta.get("id")` and validate each required field before inserting into `_vault`. Skip files that fail validation with a warning log.
**Warning signs:** `KeyError` on file load, service crashes on startup.

### Pitfall 3: `enabled` Field Type Coercion
**What goes wrong:** YAML `enabled: true` parses as Python `True` (bool). But `enabled: "true"` (with quotes) parses as the string `"true"`, which is truthy but `is not True`. Code checking `if meta["enabled"]` accepts both; code checking `meta["enabled"] is True` rejects the string.
**Why it happens:** Obsidian users sometimes quote boolean values.
**How to avoid:** Check `isinstance(meta.get("enabled"), bool) and meta["enabled"]`. This strictly requires an unquoted YAML boolean.
**Warning signs:** Files with `enabled: "true"` silently excluded from vault.

### Pitfall 4: ID Collision Across Files
**What goes wrong:** Two `.md` files with the same `id` frontmatter value — last one loaded silently wins, first is lost.
**Why it happens:** `os.scandir` order is OS-dependent (not alphabetical, not insertion-order).
**How to avoid:** Before inserting, check `if content_id in result:` and log a warning with both filenames. Skip the duplicate. This makes the scan order irrelevant.
**Warning signs:** `content_count` is lower than expected; specific IDs intermittently missing.

### Pitfall 5: UnicodeDecodeError on Non-UTF-8 Files
**What goes wrong:** Some editors (Windows Notepad) save `.md` files in Latin-1 or UTF-16. `frontmatter.load(f)` with `encoding="utf-8"` raises `UnicodeDecodeError`.
**Why it happens:** No encoding enforcement in Obsidian.
**How to avoid:** Wrap file open in `try/except UnicodeDecodeError`, log and skip the file. Do not crash the load loop.
**Warning signs:** Startup log shows skip warnings; expected content not served.

### Pitfall 6: Circular Import Between health.py and content.py
**What goes wrong:** If `content.py` imports from `health.py` (even indirectly), Python raises `ImportError: cannot import name X`.
**Why it happens:** Circular module dependencies.
**How to avoid:** Only `health.py` imports from `content.py` (for `_vault` access). `content.py` imports from `config.py` only. Keep the dependency graph acyclic.
**Warning signs:** `ImportError` on startup before any request is handled.

---

## Code Examples

### Loading Vault at Startup (lifespan)
```python
# Source: fastapi.tiangolo.com/advanced/events
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.routers import content
    content._vault.clear()
    content._vault.update(content.load_vault())
    yield
    # no cleanup needed — process exit releases memory

app = FastAPI(lifespan=lifespan)
```

### Scanning Flat Directory (top-level .md only)
```python
# Source: stdlib os.scandir docs — no recursion
import os

for entry in os.scandir(vault_path):
    if entry.is_file() and entry.name.endswith(".md"):
        # process entry.path
```

### Parsing Frontmatter Safely
```python
# Source: Context7 /eyeseast/python-frontmatter
import frontmatter

with open(entry.path, encoding="utf-8") as f:
    post = frontmatter.load(f)

# post.content  -- body text (str)
# post.metadata -- dict of frontmatter fields
# post.get("key", default) -- safe access with default
```

### TestClient with lifespan (pytest)
```python
# Source: fastapi.tiangolo.com/advanced/testing-events
from fastapi.testclient import TestClient
from app.main import app

def test_health_shows_vault_stats(tmp_path):
    # Write a test .md file to tmp_path
    (tmp_path / "item.md").write_text(
        "---\nid: q1\ntype: faq\ntitle: Test\nenabled: true\n---\nBody text"
    )
    import app.config as config_module
    # Override vault_path for this test
    original = config_module.settings.vault_path
    config_module.settings.vault_path = str(tmp_path)
    try:
        with TestClient(app) as client:
            resp = client.get("/health")
            assert resp.status_code == 200
            assert resp.json()["vault_loaded"] is True
            assert resp.json()["content_count"] == 1
    finally:
        config_module.settings.vault_path = original
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` | `lifespan` with `asynccontextmanager` | FastAPI 0.95.0 (2023) | `on_event` still works but raises deprecation warning |

**Deprecated/outdated:**
- `@app.on_event("startup")` / `@app.on_event("shutdown")`: Deprecated. Use `lifespan` parameter on `FastAPI()`. [VERIFIED: fastapi.tiangolo.com/advanced/events]

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Single-process, single-worker deployment — dict reassignment is safe without asyncio.Lock | Pattern 2: Hot-Reload | If gunicorn multi-process is ever used, each worker has its own _vault; reload hits one worker only |
| A2 | No existing test infrastructure — tests/ directory and pytest.ini must be created in Wave 0 | Validation Architecture | If tests exist elsewhere, Wave 0 setup tasks are wasted effort |

---

## Open Questions

1. **Where does `vault_loaded` mean?**
   - What we know: D-03 says if VAULT_PATH is missing, serve zero content. Health should reflect this.
   - What's unclear: Should `vault_loaded: false` mean "no path configured" vs "path configured but empty"? Both result in `content_count: 0`.
   - Recommendation: `vault_loaded = settings.vault_path != "" and os.path.isdir(settings.vault_path)` — reflects whether the vault is reachable, not whether it has content. This gives operators an actionable distinction.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.9.6 | FastAPI backend | Yes | 3.9.6 | — |
| python-frontmatter | Vault loading | No (not installed) | — | Must install — no fallback |
| pytest | Testing | No (not installed) | — | Must install — no fallback |
| httpx | TestClient | No (not installed locally) | — | Already in requirements.txt; install with pip |

**Missing dependencies with no fallback:**
- `python-frontmatter`: Required for Phase 2 core functionality. Wave 0 task must add to requirements.txt and install.
- `pytest`: Required for test suite. Wave 0 task must add to requirements.txt and install.

**Missing dependencies with fallback:**
- None.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | none — see Wave 0 (create pytest.ini or add [tool.pytest.ini_options] to pyproject.toml) |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VAULT-01 | Vault loads from VAULT_PATH on startup; health shows content_count > 0 | integration | `python -m pytest tests/test_content.py::test_vault_loads_at_startup -x` | No — Wave 0 |
| VAULT-01 | VAULT_PATH missing → server starts, content_count = 0, no crash | integration | `python -m pytest tests/test_content.py::test_missing_vault_soft_fails -x` | No — Wave 0 |
| VAULT-02 | GET /content/{id} returns title and body for loaded item | integration | `python -m pytest tests/test_content.py::test_get_content_by_id -x` | No — Wave 0 |
| VAULT-02 | GET /content/{unknown_id} returns 404 | integration | `python -m pytest tests/test_content.py::test_get_content_missing_returns_404 -x` | No — Wave 0 |
| VAULT-03 | Files without enabled: true are not served | integration | `python -m pytest tests/test_content.py::test_disabled_files_excluded -x` | No — Wave 0 |
| VAULT-03 | Files with missing required fields are skipped, not crash | integration | `python -m pytest tests/test_content.py::test_malformed_frontmatter_skipped -x` | No — Wave 0 |
| QA-04 | POST /content/reload hot-reloads without restart | integration | `python -m pytest tests/test_content.py::test_reload_endpoint -x` | No — Wave 0 |
| VAULT-01 | GET /health includes vault_loaded and content_count | integration | `python -m pytest tests/test_content.py::test_health_includes_vault_stats -x` | No — Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/__init__.py` — marks tests as package
- [ ] `tests/conftest.py` — shared `tmp_path`-based vault fixture, TestClient factory with vault_path override
- [ ] `tests/test_content.py` — covers all 8 requirements above
- [ ] Framework install: `pip install pytest>=9.0.3 python-frontmatter>=1.1.0` — neither detected locally
- [ ] Add to `requirements.txt`: `python-frontmatter>=1.1.0` and `pytest>=9.0.3`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No auth on content endpoints in v1 |
| V3 Session Management | No | Stateless endpoints |
| V4 Access Control | No | No user-scoped content in Phase 2 |
| V5 Input Validation | Yes | content_id path param — FastAPI type validates str; dict lookup is safe |
| V6 Cryptography | No | No secrets involved in vault loading |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via VAULT_PATH | Tampering | VAULT_PATH set via trusted env var only; `os.scandir` + `entry.is_file()` prevents traversal |
| ID injection via frontmatter | Spoofing | IDs are dict keys used only for memory lookup — no SQL, no shell, no eval |
| Large file DoS | Denial of Service | [ASSUMED] No file size limit currently; acceptable for Obsidian vault use case |

---

## Project Constraints (from CLAUDE.md)

- Python: snake_case, 4-space indent, Pydantic BaseModel for all responses — apply to `ContentResponse`, `HealthResponse`
- No comments unless WHY is non-obvious — follow existing inline comment style (em-dash)
- Surgical changes — only touch `config.py`, `main.py`, `health.py`; create new `content.py`; do not refactor unrelated code
- Match existing style: `router = APIRouter(prefix="/content", tags=["content"])` — same pattern as `ai.py`
- TypeScript strict mode — N/A for this phase (Python only)
- No speculative features — no pagination, no search, no TTL; only what's in scope

---

## Sources

### Primary (HIGH confidence)
- Context7 `/eyeseast/python-frontmatter` — Post object API, load(), loads(), metadata access, encoding handling
- Context7 `/websites/fastapi_tiangolo` — lifespan pattern, TestClient lifespan testing, app.state, dependency injection
- PyPI JSON API (`pypi.org/pypi/python-frontmatter/json`) — version 1.1.0, PyYAML dependency
- PyPI JSON API (`pypi.org/pypi/pytest/json`) — version 9.0.3
- PyPI JSON API (`pypi.org/pypi/httpx/json`) — version 0.28.1

### Secondary (MEDIUM confidence)
- [FastAPI Lifespan Docs](https://fastapi.tiangolo.com/advanced/events/) — asynccontextmanager pattern, deprecation of on_event
- [FastAPI Testing Events](https://fastapi.tiangolo.com/advanced/testing-events/) — TestClient with lifespan
- [python-frontmatter Read the Docs](https://python-frontmatter.readthedocs.io/en/latest/api.html) — API reference

### Tertiary (LOW confidence)
- WebSearch results on FastAPI module-level dict vs app.state — corroborates Context7 findings; not independently cited

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions verified via PyPI JSON API
- Architecture: HIGH — patterns verified via Context7 official FastAPI docs
- Pitfalls: HIGH — derived from library behavior verified in Context7 docs + known Python scoping rules
- Security: MEDIUM — basic analysis; no formal ASVS audit performed

**Research date:** 2026-05-14
**Valid until:** 2026-06-14 (stable libraries, 30-day window)
