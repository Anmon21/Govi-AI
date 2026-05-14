# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

<!-- GSD:project-start source:PROJECT.md -->
## Project

**Govi Facebook Messenger Customer Support Bot**

A rule-based Facebook Messenger chatbot for Govi (e-commerce/retail) that guides customers through structured menus to answer product questions and escalate to a human agent. The system includes an admin panel for managing Q&A content without code changes.

**Core Value:** Customers can get instant product answers and reach a human through Messenger — 24/7, without developer involvement in content updates.

### Constraints

- **Tech stack**: Node.js/TypeScript for the Messenger bot, Python/FastAPI for the backend — maintain existing split
- **Platform**: Facebook Messenger only — no other channels in v1
- **Deployment**: No containerization currently — same manual deploy pattern
- **Scope**: Standalone system — no integration with order management or inventory
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.x - FastAPI backend (`app/`)
- TypeScript 5.4 - Facebook Messenger bot (`messenger-bot/src/`)
- JavaScript (compiled output) - TypeScript compiles to CommonJS in `messenger-bot/dist/`
## Runtime
- Runtime: CPython (3.9.6 on development machine; no version pin file present)
- Virtual env: `.venv/` or `venv/` (gitignored, must be created manually)
- Runtime: Node.js (v26.0.0 on development machine; no `.nvmrc` pin present)
- Package Manager: npm 11.12.1
- Lockfile: `messenger-bot/package-lock.json` (present)
## Frameworks
- FastAPI >=0.115.0 - HTTP API framework (`app/main.py`)
- Uvicorn >=0.30.0 (standard extras) - ASGI server (`main.py`)
- Pydantic >=2.7.0 - Request/response validation (`app/routers/ai.py`)
- Pydantic-Settings >=2.3.0 - Environment config loading (`app/config.py`)
- Express 4.19 - HTTP server for webhook handler (`messenger-bot/src/index.ts`)
- Not detected in either component
- ts-node-dev 2.0 - TypeScript hot-reload dev server (`messenger-bot/`)
- tsc (TypeScript compiler 5.4) - Compiles `src/` → `dist/`
## Key Dependencies
- `anthropic` >=0.30.0 - Anthropic Claude API client; all AI inference goes through this (`app/routers/ai.py`)
- `httpx` >=0.27.0 - Async HTTP client; available in Python env (not yet used directly, pulled as FastAPI dependency)
- `axios` ^1.7.0 - HTTP client used by the bot to call both the Govi AI API and the Facebook Graph API (`messenger-bot/src/index.ts`)
- `python-dotenv` >=1.0.0 - `.env` loading for Python side
- `dotenv` ^16.4.0 - `.env` loading for Node side
## Configuration
- Loaded via `pydantic-settings` from `.env` at repo root
- Config class: `app/config.py` → `Settings`
- Required var: `ANTHROPIC_API_KEY`
- Optional vars: `APP_ENV` (default: `development`), `APP_PORT` (default: `8000`)
- Example: `.env.example`
- Loaded via `dotenv` from `messenger-bot/.env`
- Required vars: `FACEBOOK_VERIFY_TOKEN`, `FACEBOOK_PAGE_ACCESS_TOKEN`
- Optional vars: `GOVI_AI_URL` (default: `http://localhost:8000`), `PORT` (default: `3000`)
- Example: `messenger-bot/.env.example`
- Config: `messenger-bot/tsconfig.json`
- Target: ES2020, module system: CommonJS
- Source: `messenger-bot/src/`, Output: `messenger-bot/dist/`
- Strict mode: enabled
## Platform Requirements
- Python 3.x with pip (no pinned version)
- Node.js with npm (no pinned version)
- Two separate `.env` files required (root and `messenger-bot/`)
- Both services run independently; bot expects API at `GOVI_AI_URL`
- Python API: any ASGI-compatible host; Uvicorn serves on `0.0.0.0:APP_PORT`
- Messenger bot: any Node.js host; Express listens on `PORT`
- No containerization config detected (no Dockerfile, no docker-compose)
- No CI/CD config detected
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- snake_case for all module files: `main.py`, `config.py`, `health.py`, `ai.py`
- `__init__.py` used to mark packages (empty files in `app/` and `app/routers/`)
- Single `index.ts` entry point per directory under `src/`
- Python: snake_case async functions — `async def chat(request: ChatRequest)`, `async def health_check()`
- TypeScript: camelCase async functions — `async function sendMessage(recipientId: string, text: string)`
- Python: snake_case — `send_id`, `user_text`, `page_access_token`
- TypeScript: SCREAMING_SNAKE_CASE for module-level constants from env — `VERIFY_TOKEN`, `PAGE_ACCESS_TOKEN`, `GOVI_AI_URL`; camelCase for local variables — `senderId`, `userText`
- PascalCase Pydantic models — `ChatRequest`, `ChatResponse`, `Settings`
- All request/response models inherit from `pydantic.BaseModel`
- Settings model inherits from `pydantic_settings.BaseSettings`
- Lowercase string tags matching the router prefix without slash — `tags=["ai"]`, `tags=["health"]`
## Code Style
- No formatter config file detected (no `.prettierrc`, `biome.json`, `ruff.toml`, or `pyproject.toml`)
- Python code uses 4-space indentation consistently
- TypeScript uses 2-space indentation
- No ESLint or Ruff config detected
- TypeScript compiled with `strict: true` in `messenger-bot/tsconfig.json` — enforces strict null checks and type safety
- No enforced limit; lines kept short in practice (longest observed ~80 chars)
## Import Organization
- None. Python uses absolute package paths from project root — `from app.config import settings`, `from app.routers import health, ai`
- TypeScript uses relative paths (only one file exists)
## Error Handling
- Use `HTTPException` from FastAPI for API error responses: `raise HTTPException(status_code=500, detail="...")`
- Guard with explicit checks before external calls: check `settings.anthropic_api_key` before instantiating client
- No try/except blocks in Python routers — errors from `anthropic` SDK propagate unhandled (see CONCERNS.md)
- try/catch wrapping async external calls in `messenger-bot/src/index.ts`
- On error: log with `console.error(...)` then send a user-facing fallback message
- Acknowledge Facebook webhook receipt immediately before processing (res.sendStatus(200) before the async loop)
## Logging
- Log verified webhook: `console.log("Webhook verified")`
- Log inbound messages: `console.log(`[${senderId}] ${userText}`)`
- Log errors: `console.error("Error calling Govi AI:", err)`
- Python side: no logging calls present
## Comments
- Short inline comments on non-obvious intent — `// Webhook verification — Facebook calls this once when you register the webhook`
- Short inline comments on time constraints — `// Acknowledge receipt immediately — Facebook requires this within 20s`
- Comments use em-dash style: `// Description — detail`
- Not used
## Function Design
- Python routers return Pydantic response model instances directly — FastAPI serializes them
- TypeScript async helpers return `Promise<void>` with explicit annotation
## Module Design
- Routers expose a single `router = APIRouter(...)` instance per file
- Config exposes a single `settings = Settings()` singleton at module level
- App factory in `app/main.py` — `app` is the FastAPI instance
- No exports — `messenger-bot/src/index.ts` is a self-contained executable entry point
- `app/__init__.py` and `app/routers/__init__.py` are empty; no re-exports
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## System Overview
```text
```
## Component Responsibilities
| Component | Responsibility | File |
|-----------|----------------|------|
| Root runner | Boot uvicorn with config | `main.py` |
| FastAPI app | Mount middleware, routers | `app/main.py` |
| Settings | Load env vars via pydantic-settings | `app/config.py` |
| AI router | Accept chat requests, call Claude API | `app/routers/ai.py` |
| Health router | Liveness check | `app/routers/health.py` |
| Messenger bot | Facebook webhook gateway, forward to Govi AI | `messenger-bot/src/index.ts` |
## Pattern Overview
- Stateless: no session or conversation history persisted between requests
- Each `POST /ai/chat` call is a standalone single-turn Claude invocation
- The messenger bot is an optional front-end gateway; the FastAPI backend is independently usable
- Configuration is entirely environment-variable driven via `.env` files in each service root
## Layers
- Purpose: Start the ASGI server
- Location: `main.py` (project root)
- Contains: `uvicorn.run` call reading `app_port` from settings
- Depends on: `app.config.settings`, uvicorn
- Used by: Developer / process manager (e.g., `python main.py`)
- Purpose: FastAPI app construction, CORS, router registration
- Location: `app/main.py`
- Contains: `FastAPI` instance, `CORSMiddleware` (allow all origins), router includes
- Depends on: `app/routers/`
- Used by: uvicorn ASGI runner
- Purpose: HTTP route definitions and request/response handling
- Location: `app/routers/ai.py`, `app/routers/health.py`
- Contains: `APIRouter` instances, Pydantic request/response models, route functions
- Depends on: `app/config.py`, Anthropic SDK
- Used by: `app/main.py`
- Purpose: Centralised settings loaded from `.env`
- Location: `app/config.py`
- Contains: `Settings(BaseSettings)` singleton `settings`
- Depends on: pydantic-settings
- Used by: `app/main.py` (port), `app/routers/ai.py` (API key)
- Purpose: Facebook Messenger webhook verification and message routing
- Location: `messenger-bot/src/index.ts`
- Contains: Express app, GET/POST `/webhook` handlers, `sendMessage` helper
- Depends on: Govi AI API (`GOVI_AI_URL`), Facebook Graph API
- Used by: Facebook Messenger platform (external)
## Data Flow
### Primary Chat Request Path (via Messenger)
### Direct API Chat Path
### Webhook Verification Path
- None. All requests are stateless. No database, cache, or in-memory store exists. Each chat call is independent.
## Key Abstractions
- Purpose: Typed contract for the `/ai/chat` endpoint
- Location: `app/routers/ai.py:10-21`
- Pattern: Inline Pydantic `BaseModel` — defined in the same file as the route
- Purpose: Single source of truth for all environment-sourced config
- Location: `app/config.py`
- Pattern: `pydantic_settings.BaseSettings` with `model_config = {"env_file": ".env"}`; imported as `settings` module-level singleton
## Entry Points
- Location: `app/main.py` — `app` object
- Triggers: uvicorn targets `"app.main:app"`
- Responsibilities: Middleware wiring, router mounting
- Location: `main.py` (project root)
- Triggers: `python main.py`
- Responsibilities: Reads `settings.app_port`, starts uvicorn with reload
- Location: `messenger-bot/src/index.ts`
- Triggers: `npm run dev` (ts-node-dev) or `npm start` (compiled JS)
- Responsibilities: Express server on `PORT` (default 3000), webhook handling
## Architectural Constraints
- **Statefulness:** No conversation history. Each `/ai/chat` call carries only the single user message and a hardcoded system prompt (`"You are Govi AI, a helpful and concise assistant."`). Multi-turn conversations are not supported.
- **CORS:** `allow_origins=["*"]` — fully open. Suitable for development; must be tightened for production.
- **API key instantiation:** `anthropic.Anthropic(api_key=...)` is constructed inside the route handler on every request (`app/routers/ai.py:28`). No client reuse/pooling.
- **Threading:** FastAPI runs async (`async def chat`); the Anthropic SDK call is synchronous (blocking the event loop). For high concurrency this should use `await` with an async client or `run_in_executor`.
- **Global state:** `settings` is a module-level singleton in `app/config.py`. No other shared mutable state.
- **Circular imports:** None detected.
## Anti-Patterns
### Anthropic client instantiated per request
### Synchronous SDK call inside async route
## Error Handling
- Missing API key raises `HTTPException(500)` before any external call (`app/routers/ai.py:25-27`)
- Messenger bot wraps the Govi AI call in `try/catch`; on error it sends a fallback message to the user and logs to `console.error` (`messenger-bot/src/index.ts:53-56`)
- No error handling on the FastAPI side for Anthropic API failures (network errors or rate limits will surface as unhandled 500s)
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
