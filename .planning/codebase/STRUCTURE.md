# Codebase Structure

**Analysis Date:** 2026-05-14

## Directory Layout

```
Govi-AI/                        # Monorepo root
├── main.py                     # Uvicorn boot script
├── requirements.txt            # Python dependencies
├── .env                        # Local env vars (gitignored)
├── .env.example                # Env var template for Python service
├── .gitignore
├── CLAUDE.md                   # Coding guidelines for AI agents
│
├── app/                        # FastAPI Python service
│   ├── __init__.py
│   ├── main.py                 # FastAPI app factory, middleware, routers
│   ├── config.py               # Pydantic settings (env-var config)
│   └── routers/                # Route modules (one file per domain)
│       ├── __init__.py
│       ├── ai.py               # POST /ai/chat — Claude inference endpoint
│       └── health.py           # GET /health — liveness probe
│
├── messenger-bot/              # Facebook Messenger gateway (Node.js)
│   ├── src/
│   │   └── index.ts            # Express server, webhook handlers
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json
│   ├── .env.example            # Env var template for messenger bot
│   └── node_modules/           # (gitignored)
│
└── .planning/                  # GSD planning artifacts (AI agent use)
    └── codebase/               # Auto-generated codebase maps
```

## Directory Purposes

**`app/`:**
- Purpose: The core Python/FastAPI AI service
- Contains: App factory, config, route handlers
- Key files: `app/main.py` (app instance), `app/config.py` (settings), `app/routers/ai.py` (chat endpoint)

**`app/routers/`:**
- Purpose: One Python module per route group
- Contains: `APIRouter` definitions, Pydantic request/response models, route handler functions
- Key files: `app/routers/ai.py`, `app/routers/health.py`

**`messenger-bot/`:**
- Purpose: Standalone Node.js service that bridges Facebook Messenger to the FastAPI backend
- Contains: Single-file Express app (`src/index.ts`), TypeScript config, npm manifests
- Key files: `messenger-bot/src/index.ts`

**`messenger-bot/src/`:**
- Purpose: All TypeScript source for the bot
- Contains: `index.ts` only (not split into modules)

**`.planning/codebase/`:**
- Purpose: AI-generated architecture and convention reference docs
- Generated: Yes (by GSD mapping commands)
- Committed: Yes

## Key File Locations

**Entry Points:**
- `main.py`: Python process entry — runs uvicorn targeting `app.main:app`
- `app/main.py`: FastAPI `app` object — ASGI entry point
- `messenger-bot/src/index.ts`: Express server — Messenger bot entry point

**Configuration:**
- `app/config.py`: `Settings` class — reads `ANTHROPIC_API_KEY`, `APP_ENV`, `APP_PORT` from `.env`
- `.env.example`: Documents required env vars for the Python service
- `messenger-bot/.env.example`: Documents required env vars for the bot (`FACEBOOK_VERIFY_TOKEN`, `FACEBOOK_PAGE_ACCESS_TOKEN`, `GOVI_AI_URL`, `PORT`)

**Core Logic:**
- `app/routers/ai.py`: All AI inference logic — Anthropic client call, request/response models
- `messenger-bot/src/index.ts`: All Messenger gateway logic — webhook verification, message routing, Graph API reply

**Dependencies:**
- `requirements.txt`: Python service deps
- `messenger-bot/package.json`: Node.js service deps

## Naming Conventions

**Python files:**
- `snake_case.py` for all modules (e.g., `config.py`, `health.py`)
- Router files named after the route domain they own (e.g., `ai.py` owns `/ai/*`)

**Python classes:**
- `PascalCase` for Pydantic models and settings (e.g., `ChatRequest`, `ChatResponse`, `Settings`)

**Python variables / functions:**
- `snake_case` for all variables and function names (e.g., `app_port`, `health_check`)

**TypeScript files:**
- Single-file service; no multi-file naming pattern established yet

**Directories:**
- `snake_case` for Python packages (`routers/`)
- `kebab-case` for the Node.js service directory (`messenger-bot/`)

## Where to Add New Code

**New API endpoint (FastAPI):**
- Create a new file in `app/routers/` named after the domain (e.g., `app/routers/users.py`)
- Define an `APIRouter` with an appropriate `prefix` and `tags`
- Register it in `app/main.py` via `app.include_router(...)`
- Add any new env vars to `app/config.py` `Settings` class and `.env.example`

**New Pydantic request/response models:**
- Define inline in the same router file that uses them (follow pattern in `app/routers/ai.py`)
- Move to a shared `app/schemas.py` only if two or more routers need the same model

**New configuration values:**
- Add as a typed field on `Settings` in `app/config.py`
- Add the var name to `.env.example`

**New messenger bot logic:**
- Currently all logic lives in `messenger-bot/src/index.ts`
- For significant additions, extract to `messenger-bot/src/<module>.ts` and import into `index.ts`

**Shared utilities (Python):**
- No `utils/` directory exists yet; create `app/utils.py` for the first shared helper

## Special Directories

**`node_modules/`:**
- Purpose: npm package cache for messenger-bot
- Generated: Yes
- Committed: No (not in `.gitignore` explicitly, but standard practice)

**`.planning/`:**
- Purpose: GSD agent planning and codebase map documents
- Generated: Yes (by `/gsd-map-codebase` and related commands)
- Committed: Yes

**`.claude/`:**
- Purpose: Claude Code local settings
- Generated: Yes
- Committed: No (contains `settings.local.json`)

---

*Structure analysis: 2026-05-14*
