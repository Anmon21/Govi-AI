# External Integrations

**Analysis Date:** 2026-05-14

## APIs & External Services

**AI / LLM:**
- Anthropic Claude API - Provides all AI inference for chat responses
  - SDK/Client: `anthropic` Python package (`app/routers/ai.py`)
  - Auth: `ANTHROPIC_API_KEY` (root `.env`)
  - Default model: `claude-sonnet-4-6` (overridable per request via `ChatRequest.model`)
  - Endpoint usage: `client.messages.create(...)` — synchronous call

**Social / Messaging:**
- Facebook Messenger Platform (Graph API v19.0) - Sends reply messages back to users
  - Client: `axios` (`messenger-bot/src/index.ts`, `sendMessage()`)
  - Auth: `FACEBOOK_PAGE_ACCESS_TOKEN` (messenger-bot `.env`) — passed as `access_token` query param
  - Endpoint called: `POST https://graph.facebook.com/v19.0/me/messages`

## Data Storage

**Databases:**
- None detected — no database client, ORM, or connection string is present

**File Storage:**
- Local filesystem only — no cloud object storage detected

**Caching:**
- None

## Authentication & Identity

**Auth Provider:**
- None for the Python API — no user auth layer; the API is open (CORS allows all origins)
- Facebook webhook verification — custom token challenge/response in `messenger-bot/src/index.ts` (`GET /webhook`)
  - Verified via: `FACEBOOK_VERIFY_TOKEN` matched against `hub.verify_token` query param

## Monitoring & Observability

**Error Tracking:**
- None

**Logs:**
- Python API: no explicit logging; FastAPI/Uvicorn default stdout logs
- Messenger bot: `console.log` / `console.error` in `messenger-bot/src/index.ts`

## CI/CD & Deployment

**Hosting:**
- Not configured — no Dockerfile, docker-compose, or platform config files present

**CI Pipeline:**
- None

## Webhooks & Callbacks

**Incoming:**
- `GET /webhook` — Facebook webhook verification challenge (`messenger-bot/src/index.ts:13`)
- `POST /webhook` — Facebook Messenger events (user messages) (`messenger-bot/src/index.ts:27`)

**Outgoing:**
- `POST https://graph.facebook.com/v19.0/me/messages` — sends reply messages to Messenger users (`messenger-bot/src/index.ts:62`)
- `POST {GOVI_AI_URL}/ai/chat` — bot calls the Python API for AI inference (`messenger-bot/src/index.ts:48`)

## Service-to-Service Communication

**Bot → API:**
- The messenger bot calls the Govi AI Python API over HTTP
- URL configured via `GOVI_AI_URL` env var (default: `http://localhost:8000`)
- Endpoint: `POST /ai/chat` with `{ message: string }` body
- No auth between services — assumed same private network or localhost

## Environment Configuration

**Required env vars (Python API — root `.env`):**
- `ANTHROPIC_API_KEY` — Anthropic API key

**Required env vars (Messenger Bot — `messenger-bot/.env`):**
- `FACEBOOK_VERIFY_TOKEN` — token used to verify Facebook webhook registration
- `FACEBOOK_PAGE_ACCESS_TOKEN` — Facebook Page token for sending messages

**Optional env vars:**
- `APP_ENV` — Python API environment label (default: `development`)
- `APP_PORT` — Python API port (default: `8000`)
- `GOVI_AI_URL` — Bot's target URL for the Python API (default: `http://localhost:8000`)
- `PORT` — Messenger bot HTTP port (default: `3000`)

**Secrets location:**
- Root `.env` (gitignored) for Python API secrets
- `messenger-bot/.env` (gitignored) for bot secrets
- Example files: `.env.example` and `messenger-bot/.env.example`

---

*Integration audit: 2026-05-14*
