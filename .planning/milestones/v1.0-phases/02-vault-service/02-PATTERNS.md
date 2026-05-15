# Phase 2: Vault Service - Pattern Map

**Mapped:** 2026-05-14
**Files analyzed:** 8 (3 new source files, 3 existing files modified, 1 config modified, 1 new config)
**Analogs found:** 5 / 8

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/routers/content.py` | router + service | request-response + file-I/O | `app/routers/ai.py` | role-match |
| `app/routers/health.py` | router | request-response | itself (existing, being extended) | exact |
| `app/config.py` | config | — | itself (existing, add one field) | exact |
| `app/main.py` | app factory | — | itself (existing, add lifespan + router) | exact |
| `requirements.txt` | config | — | itself (existing, add two lines) | exact |
| `tests/conftest.py` | test fixture | — | none | none |
| `tests/test_content.py` | test | — | none | none |
| `tests/test_health.py` | test | — | none | none |

---

## Pattern Assignments

### `app/routers/content.py` (router + service, request-response + file-I/O)

**Analog:** `app/routers/ai.py`

**Imports pattern** (`app/routers/ai.py` lines 1-6):
```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import anthropic

from app.config import settings
```

**New file imports** — follow same structure, swap anthropic for stdlib + frontmatter:
```python
import logging
import os
import frontmatter
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
```

**Router declaration pattern** (`app/routers/ai.py` line 7):
```python
router = APIRouter(prefix="/ai", tags=["ai"])
```

**New router declaration** — copy structure exactly, change prefix and tag:
```python
router = APIRouter(prefix="/content", tags=["content"])
```

**Module-level state** — no analog in codebase; new pattern for this phase:
```python
_vault: dict[str, dict] = {}
```

**Pydantic response model pattern** (`app/routers/ai.py` lines 16-20):
```python
class ChatResponse(BaseModel):
    reply: str
    model: str
    input_tokens: int
    output_tokens: int
```

**New response model** — copy structure, change fields:
```python
class ContentResponse(BaseModel):
    id: str
    type: str
    title: str
    body: str
```

**Route handler pattern** (`app/routers/ai.py` lines 23-26):
```python
@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")
```

**GET by-ID handler** — same `response_model` convention, 404 on miss:
```python
@router.get("/{content_id}", response_model=ContentResponse)
async def get_content(content_id: str):
    item = _vault.get(content_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Content not found")
    return ContentResponse(**item)
```

**POST reload handler** — returns plain dict (no response model needed; ai.py shows FastAPI serialises dicts fine):
```python
@router.post("/reload")
async def reload_vault():
    global _vault
    new_vault = load_vault()
    _vault = new_vault
    return {"reloaded": True, "content_count": len(_vault)}
```

**Return pattern** (`app/routers/ai.py` lines 37-42):
```python
return ChatResponse(
    reply=message.content[0].text,
    model=message.model,
    input_tokens=message.usage.input_tokens,
    output_tokens=message.usage.output_tokens,
)
```

**`load_vault()` function** — soft-fail on missing path, logging instead of raising (D-03):
```python
logger = logging.getLogger(__name__)


def load_vault() -> dict[str, dict]:
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

---

### `app/routers/health.py` (router, request-response — existing file, extend)

**Analog:** itself — `app/routers/health.py` lines 1-8

**Existing full file** (`app/routers/health.py` lines 1-8):
```python
from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check():
    return {"status": "ok"}
```

**Extended version** — add `BaseModel` import, import content module, add `HealthResponse`, extend return:
```python
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
        vault_loaded=bool(content.settings.vault_path and __import__("os").path.isdir(content.settings.vault_path)),
        content_count=len(content._vault),
    )
```

**Note on `vault_loaded`:** Per RESEARCH.md open question resolution — `vault_loaded` reflects whether the vault directory is reachable (`settings.vault_path` is set AND directory exists), not just whether `_vault` is non-empty. This gives operators an actionable distinction between "not configured" and "configured but empty".

---

### `app/config.py` (config — existing file, add one field)

**Analog:** itself — `app/config.py` lines 1-12

**Existing full file** (`app/config.py` lines 1-12):
```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    app_env: str = "development"
    app_port: int = 8000

    model_config = {"env_file": ".env"}


settings = Settings()
```

**Addition** — insert `vault_path: str = ""` after `app_port`, following the same `field_name: type = default` style:
```python
class Settings(BaseSettings):
    anthropic_api_key: str = ""
    app_env: str = "development"
    app_port: int = 8000
    vault_path: str = ""

    model_config = {"env_file": ".env"}
```

No other changes to this file.

---

### `app/main.py` (app factory — existing file, add lifespan + router)

**Analog:** itself — `app/main.py` lines 1-17

**Existing full file** (`app/main.py` lines 1-17):
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import health, ai

app = FastAPI(title="Govi AI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(ai.router)
```

**Router registration pattern** (`app/main.py` lines 15-16):
```python
app.include_router(health.router)
app.include_router(ai.router)
```

**Extended version** — add `asynccontextmanager` import, add `content` to router imports, wrap `FastAPI()` with lifespan, add `content` router:
```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import health, ai, content


@asynccontextmanager
async def lifespan(app: FastAPI):
    content._vault.clear()
    content._vault.update(content.load_vault())
    yield


app = FastAPI(title="Govi AI", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(ai.router)
app.include_router(content.router)
```

**Critical:** Use `content._vault.clear(); content._vault.update(...)` in lifespan — NOT `_vault = load_vault()`. The latter creates a local binding and does not affect the module-level dict that routes read. The reload endpoint in `content.py` uses `global _vault; _vault = new_dict` because it lives in the same module (where `global` rebinds the module attribute).

---

### `requirements.txt` (config — existing file, add two lines)

**Existing full file** (`requirements.txt` lines 1-7):
```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
pydantic>=2.7.0
pydantic-settings>=2.3.0
python-dotenv>=1.0.0
httpx>=0.27.0
anthropic>=0.30.0
```

**Add two lines** at the end, following existing `package>=version` style:
```
python-frontmatter>=1.1.0
pytest>=9.0.3
```

`httpx` is already present (line 6) — do not add again.

---

### `tests/conftest.py` (test fixture — no analog)

No conftest.py or any test file exists in the codebase. Use the FastAPI TestClient pattern from RESEARCH.md:

```python
import pytest
from fastapi.testclient import TestClient

import app.routers.content as content_module
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient with vault_path pointing to a controlled tmp directory."""
    import app.config as config_module
    monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
    content_module._vault.clear()
    content_module._vault.update(content_module.load_vault())
    with TestClient(app) as c:
        yield c
    content_module._vault.clear()


@pytest.fixture
def vault_dir(tmp_path):
    """Return tmp_path for tests that need to write vault files directly."""
    return tmp_path
```

**Note:** `monkeypatch` is pytest's built-in fixture — no import needed. It auto-restores the patched value after each test.

---

### `tests/test_content.py` (test — no analog)

No test analog exists. Pattern derived from RESEARCH.md validation architecture (8 required test cases) and FastAPI TestClient conventions:

```python
import app.routers.content as content_module
import app.config as config_module
from fastapi.testclient import TestClient
from app.main import app


def write_md(path, frontmatter: str, body: str = "Body text"):
    """Helper: write a .md file with given frontmatter block."""
    path.write_text(f"---\n{frontmatter}\n---\n{body}", encoding="utf-8")


def test_vault_loads_at_startup(tmp_path, monkeypatch):
    write_md(tmp_path / "q1.md", "id: q1\ntype: faq\ntitle: T\nenabled: true")
    monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
    content_module._vault.clear()
    content_module._vault.update(content_module.load_vault())
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.json()["content_count"] == 1


def test_get_content_by_id(tmp_path, monkeypatch):
    write_md(tmp_path / "q1.md", "id: q1\ntype: faq\ntitle: Test Title\nenabled: true", "Answer body")
    monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
    content_module._vault.clear()
    content_module._vault.update(content_module.load_vault())
    with TestClient(app) as client:
        resp = client.get("/content/q1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "q1"
        assert data["title"] == "Test Title"
        assert data["body"] == "Answer body"


def test_get_content_missing_returns_404(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
    content_module._vault.clear()
    with TestClient(app) as client:
        resp = client.get("/content/nonexistent")
        assert resp.status_code == 404


def test_missing_vault_soft_fails(monkeypatch):
    monkeypatch.setattr(config_module.settings, "vault_path", "/does/not/exist")
    content_module._vault.clear()
    content_module._vault.update(content_module.load_vault())
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["content_count"] == 0


def test_disabled_files_excluded(tmp_path, monkeypatch):
    write_md(tmp_path / "enabled.md", "id: e1\ntype: faq\ntitle: E\nenabled: true")
    write_md(tmp_path / "disabled.md", "id: d1\ntype: faq\ntitle: D\nenabled: false")
    monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
    content_module._vault.clear()
    content_module._vault.update(content_module.load_vault())
    with TestClient(app) as client:
        assert client.get("/content/e1").status_code == 200
        assert client.get("/content/d1").status_code == 404


def test_malformed_frontmatter_skipped(tmp_path, monkeypatch):
    write_md(tmp_path / "ok.md", "id: ok1\ntype: faq\ntitle: OK\nenabled: true")
    write_md(tmp_path / "bad.md", "enabled: true")  # missing id, type, title
    monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
    content_module._vault.clear()
    content_module._vault.update(content_module.load_vault())
    with TestClient(app) as client:
        assert len(content_module._vault) == 1


def test_reload_endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
    content_module._vault.clear()
    with TestClient(app) as client:
        assert client.get("/health").json()["content_count"] == 0
        write_md(tmp_path / "new.md", "id: n1\ntype: faq\ntitle: New\nenabled: true")
        resp = client.post("/content/reload")
        assert resp.status_code == 200
        assert resp.json()["content_count"] == 1
        assert client.get("/content/n1").status_code == 200
```

---

### `tests/test_health.py` (test — no analog)

```python
import app.routers.content as content_module
import app.config as config_module
from fastapi.testclient import TestClient
from app.main import app


def test_health_includes_vault_stats(monkeypatch):
    monkeypatch.setattr(config_module.settings, "vault_path", "")
    content_module._vault.clear()
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "vault_loaded" in data
        assert "content_count" in data
        assert data["status"] == "ok"


def test_health_vault_loaded_true_when_vault_reachable(tmp_path, monkeypatch):
    (tmp_path / "q.md").write_text(
        "---\nid: q1\ntype: faq\ntitle: T\nenabled: true\n---\nBody",
        encoding="utf-8",
    )
    monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
    content_module._vault.clear()
    content_module._vault.update(content_module.load_vault())
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.json()["vault_loaded"] is True
        assert resp.json()["content_count"] == 1
```

---

## Shared Patterns

### Settings Singleton Import
**Source:** `app/config.py` line 12, used in `app/routers/ai.py` line 5
**Apply to:** `app/routers/content.py`

```python
from app.config import settings
```

Access as `settings.vault_path` — same as `settings.anthropic_api_key` in ai.py.

### APIRouter Declaration
**Source:** `app/routers/ai.py` line 7
**Apply to:** `app/routers/content.py`

```python
router = APIRouter(prefix="/content", tags=["content"])
```

Prefix and tag are lowercase, matching the resource name. No trailing slash on prefix.

### Pydantic BaseModel for Responses
**Source:** `app/routers/ai.py` lines 16-20
**Apply to:** `ContentResponse` in `content.py`, `HealthResponse` in `health.py`

All response shapes use `class Name(BaseModel)` with typed fields. Route handlers pass the model as `response_model=` on the decorator and return an instance directly — FastAPI serialises it.

### HTTPException for API Errors
**Source:** `app/routers/ai.py` lines 25-26
**Apply to:** `GET /content/{content_id}` in `content.py`

```python
raise HTTPException(status_code=404, detail="Content not found")
```

Use `HTTPException` from `fastapi`. No try/except needed around the dict lookup itself — it cannot raise.

### Router Registration in main.py
**Source:** `app/main.py` lines 15-16
**Apply to:** content router registration

```python
app.include_router(health.router)
app.include_router(ai.router)
app.include_router(content.router)  # add at end
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tests/conftest.py` | test fixture | — | No test infrastructure exists in the codebase; greenfield setup |
| `tests/test_content.py` | test | — | No test files exist; greenfield |
| `tests/test_health.py` | test | — | No test files exist; greenfield |

For all three test files, patterns are derived from RESEARCH.md (FastAPI TestClient + monkeypatch pattern) rather than existing codebase analogs.

---

## Metadata

**Analog search scope:** `app/`, `app/routers/`, root config files
**Files scanned:** 6 (`app/config.py`, `app/main.py`, `app/routers/ai.py`, `app/routers/health.py`, `requirements.txt`, `.planning/phases/01-security-bot-foundation/01-PATTERNS.md`)
**Pattern extraction date:** 2026-05-14
