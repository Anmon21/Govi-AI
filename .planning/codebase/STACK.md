# Technology Stack

**Analysis Date:** 2026-05-14

## Languages

**Primary:**
- Python 3.x - FastAPI backend (`app/`)
- TypeScript 5.4 - Facebook Messenger bot (`messenger-bot/src/`)

**Secondary:**
- JavaScript (compiled output) - TypeScript compiles to CommonJS in `messenger-bot/dist/`

## Runtime

**Python Environment:**
- Runtime: CPython (3.9.6 on development machine; no version pin file present)
- Virtual env: `.venv/` or `venv/` (gitignored, must be created manually)

**Node Environment:**
- Runtime: Node.js (v26.0.0 on development machine; no `.nvmrc` pin present)
- Package Manager: npm 11.12.1
- Lockfile: `messenger-bot/package-lock.json` (present)

## Frameworks

**Core (Python API):**
- FastAPI >=0.115.0 - HTTP API framework (`app/main.py`)
- Uvicorn >=0.30.0 (standard extras) - ASGI server (`main.py`)
- Pydantic >=2.7.0 - Request/response validation (`app/routers/ai.py`)
- Pydantic-Settings >=2.3.0 - Environment config loading (`app/config.py`)

**Core (Messenger Bot):**
- Express 4.19 - HTTP server for webhook handler (`messenger-bot/src/index.ts`)

**Testing:**
- Not detected in either component

**Build/Dev:**
- ts-node-dev 2.0 - TypeScript hot-reload dev server (`messenger-bot/`)
- tsc (TypeScript compiler 5.4) - Compiles `src/` → `dist/`

## Key Dependencies

**Critical:**
- `anthropic` >=0.30.0 - Anthropic Claude API client; all AI inference goes through this (`app/routers/ai.py`)
- `httpx` >=0.27.0 - Async HTTP client; available in Python env (not yet used directly, pulled as FastAPI dependency)
- `axios` ^1.7.0 - HTTP client used by the bot to call both the Govi AI API and the Facebook Graph API (`messenger-bot/src/index.ts`)

**Infrastructure:**
- `python-dotenv` >=1.0.0 - `.env` loading for Python side
- `dotenv` ^16.4.0 - `.env` loading for Node side

## Configuration

**Environment (Python API):**
- Loaded via `pydantic-settings` from `.env` at repo root
- Config class: `app/config.py` → `Settings`
- Required var: `ANTHROPIC_API_KEY`
- Optional vars: `APP_ENV` (default: `development`), `APP_PORT` (default: `8000`)
- Example: `.env.example`

**Environment (Messenger Bot):**
- Loaded via `dotenv` from `messenger-bot/.env`
- Required vars: `FACEBOOK_VERIFY_TOKEN`, `FACEBOOK_PAGE_ACCESS_TOKEN`
- Optional vars: `GOVI_AI_URL` (default: `http://localhost:8000`), `PORT` (default: `3000`)
- Example: `messenger-bot/.env.example`

**Build (TypeScript):**
- Config: `messenger-bot/tsconfig.json`
- Target: ES2020, module system: CommonJS
- Source: `messenger-bot/src/`, Output: `messenger-bot/dist/`
- Strict mode: enabled

## Platform Requirements

**Development:**
- Python 3.x with pip (no pinned version)
- Node.js with npm (no pinned version)
- Two separate `.env` files required (root and `messenger-bot/`)
- Both services run independently; bot expects API at `GOVI_AI_URL`

**Production:**
- Python API: any ASGI-compatible host; Uvicorn serves on `0.0.0.0:APP_PORT`
- Messenger bot: any Node.js host; Express listens on `PORT`
- No containerization config detected (no Dockerfile, no docker-compose)
- No CI/CD config detected

---

*Stack analysis: 2026-05-14*
