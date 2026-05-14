# Coding Conventions

**Analysis Date:** 2026-05-14

## Naming Patterns

**Files (Python):**
- snake_case for all module files: `main.py`, `config.py`, `health.py`, `ai.py`
- `__init__.py` used to mark packages (empty files in `app/` and `app/routers/`)

**Files (TypeScript):**
- Single `index.ts` entry point per directory under `src/`

**Functions:**
- Python: snake_case async functions — `async def chat(request: ChatRequest)`, `async def health_check()`
- TypeScript: camelCase async functions — `async function sendMessage(recipientId: string, text: string)`

**Variables:**
- Python: snake_case — `send_id`, `user_text`, `page_access_token`
- TypeScript: SCREAMING_SNAKE_CASE for module-level constants from env — `VERIFY_TOKEN`, `PAGE_ACCESS_TOKEN`, `GOVI_AI_URL`; camelCase for local variables — `senderId`, `userText`

**Classes / Types (Python):**
- PascalCase Pydantic models — `ChatRequest`, `ChatResponse`, `Settings`
- All request/response models inherit from `pydantic.BaseModel`
- Settings model inherits from `pydantic_settings.BaseSettings`

**Router Tags:**
- Lowercase string tags matching the router prefix without slash — `tags=["ai"]`, `tags=["health"]`

## Code Style

**Formatting:**
- No formatter config file detected (no `.prettierrc`, `biome.json`, `ruff.toml`, or `pyproject.toml`)
- Python code uses 4-space indentation consistently
- TypeScript uses 2-space indentation

**Linting:**
- No ESLint or Ruff config detected
- TypeScript compiled with `strict: true` in `messenger-bot/tsconfig.json` — enforces strict null checks and type safety

**Line Length:**
- No enforced limit; lines kept short in practice (longest observed ~80 chars)

## Import Organization

**Python order (observed in `app/routers/ai.py`):**
1. Standard library / third-party framework imports (`fastapi`, `pydantic`, `anthropic`)
2. Blank line
3. Internal app imports (`from app.config import settings`)

**TypeScript order (observed in `messenger-bot/src/index.ts`):**
1. Side-effect imports first: `import "dotenv/config"`
2. Third-party named imports: `import express, { Request, Response } from "express"`
3. Third-party default imports: `import axios from "axios"`

**Path Aliases:**
- None. Python uses absolute package paths from project root — `from app.config import settings`, `from app.routers import health, ai`
- TypeScript uses relative paths (only one file exists)

## Error Handling

**Python patterns:**
- Use `HTTPException` from FastAPI for API error responses: `raise HTTPException(status_code=500, detail="...")`
- Guard with explicit checks before external calls: check `settings.anthropic_api_key` before instantiating client
- No try/except blocks in Python routers — errors from `anthropic` SDK propagate unhandled (see CONCERNS.md)

**TypeScript patterns:**
- try/catch wrapping async external calls in `messenger-bot/src/index.ts`
- On error: log with `console.error(...)` then send a user-facing fallback message
- Acknowledge Facebook webhook receipt immediately before processing (res.sendStatus(200) before the async loop)

## Logging

**Framework:** `console.log` / `console.error` (no structured logger)

**Patterns:**
- Log verified webhook: `console.log("Webhook verified")`
- Log inbound messages: `console.log(`[${senderId}] ${userText}`)`
- Log errors: `console.error("Error calling Govi AI:", err)`
- Python side: no logging calls present

## Comments

**When to Comment:**
- Short inline comments on non-obvious intent — `// Webhook verification — Facebook calls this once when you register the webhook`
- Short inline comments on time constraints — `// Acknowledge receipt immediately — Facebook requires this within 20s`
- Comments use em-dash style: `// Description — detail`

**JSDoc/TSDoc:**
- Not used

## Function Design

**Size:** All functions are short (< 25 lines each)

**Parameters:** Single typed parameter object for router handlers (`request: ChatRequest`); positional typed args for helpers (`recipientId: string, text: string`)

**Return Values:**
- Python routers return Pydantic response model instances directly — FastAPI serializes them
- TypeScript async helpers return `Promise<void>` with explicit annotation

## Module Design

**Python exports:**
- Routers expose a single `router = APIRouter(...)` instance per file
- Config exposes a single `settings = Settings()` singleton at module level
- App factory in `app/main.py` — `app` is the FastAPI instance

**TypeScript exports:**
- No exports — `messenger-bot/src/index.ts` is a self-contained executable entry point

**Barrel Files:**
- `app/__init__.py` and `app/routers/__init__.py` are empty; no re-exports

---

*Convention analysis: 2026-05-14*
