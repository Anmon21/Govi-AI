# Testing Patterns

**Analysis Date:** 2026-05-14

## Test Framework

**Runner:**
- None detected. No `pytest`, `jest`, `vitest`, or any other test runner is configured or installed.
- No test config files found (`pytest.ini`, `setup.cfg`, `pyproject.toml`, `jest.config.*`, `vitest.config.*`)

**Assertion Library:**
- None installed

**Run Commands:**
```bash
# No test commands defined
# Python: no pytest entry in requirements.txt
# TypeScript: no "test" script in messenger-bot/package.json
```

## Test File Organization

**Location:**
- No test files exist anywhere in the repository.

**Naming:**
- No naming convention established.

**Structure:**
```
# No test directories or files present
```

## Test Structure

**Suite Organization:**
- Not established. No examples exist in the codebase.

**Patterns:**
- No setup, teardown, or assertion patterns observed.

## Mocking

**Framework:** None

**Patterns:**
- Not established.

**What to Mock (recommended when tests are added):**
- `anthropic.Anthropic` client in `app/routers/ai.py` — prevents live API calls in unit tests
- `axios.post` calls in `messenger-bot/src/index.ts` — prevents live calls to Facebook Graph API and Govi AI backend
- `app.config.settings` — to test missing-key guard without environment setup

**What NOT to Mock:**
- FastAPI app routing layer — use `httpx.AsyncClient` with `app` directly via `httpx` test transport

## Fixtures and Factories

**Test Data:**
- Not established. No fixtures or factories exist.

**Location:**
- No `conftest.py`, `fixtures/`, or `__fixtures__/` directories present.

## Coverage

**Requirements:** None enforced

**View Coverage:**
```bash
# Not configured — add pytest-cov to requirements.txt to enable:
# pytest --cov=app --cov-report=term-missing
```

## Test Types

**Unit Tests:**
- Not present. Recommended scope when added:
  - `app/routers/ai.py` — mock Anthropic client, test guard for missing API key, test response mapping
  - `app/routers/health.py` — assert `{"status": "ok"}` response
  - `app/config.py` — assert `Settings` reads env vars correctly

**Integration Tests:**
- Not present. Recommended scope when added:
  - FastAPI app via `httpx.AsyncClient` with ASGI transport against `app/main.py`
  - Messenger bot webhook handler via `supertest` against `messenger-bot/src/index.ts`

**E2E Tests:**
- Not used. No framework configured.

## Common Patterns

**Async Testing (recommended pattern for FastAPI when tests are added):**
```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.anyio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

**Error Testing (recommended pattern for the missing-key guard in `app/routers/ai.py`):**
```python
@pytest.mark.anyio
async def test_chat_missing_api_key(monkeypatch):
    monkeypatch.setattr("app.routers.ai.settings.anthropic_api_key", "")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/ai/chat", json={"message": "hello"})
    assert response.status_code == 500
```

## Summary

The codebase has **zero test coverage**. There is no test runner, no test files, and no testing infrastructure for either the Python (`app/`) or TypeScript (`messenger-bot/`) sub-projects. Adding tests is the highest-priority quality gap. Start with `pytest` + `httpx` + `pytest-anyio` for the FastAPI layer and `jest` + `supertest` for the messenger bot.

---

*Testing analysis: 2026-05-14*
