<!-- refreshed: 2026-05-14 -->
# Architecture

**Analysis Date:** 2026-05-14

## System Overview

```text
┌──────────────────────────────────────────────────────────────┐
│               Facebook Messenger Platform                    │
│               (external - sends webhook events)              │
└───────────────────────────┬──────────────────────────────────┘
                            │ POST /webhook
                            ▼
┌──────────────────────────────────────────────────────────────┐
│              Messenger Bot (Node.js / Express)               │
│              `messenger-bot/src/index.ts`                    │
│  - Webhook verification (GET /webhook)                       │
│  - Incoming message handler (POST /webhook)                  │
│  - Calls Govi AI API, replies via Graph API                  │
└───────────────────────────┬──────────────────────────────────┘
                            │ POST /ai/chat  (HTTP via axios)
                            ▼
┌──────────────────────────────────────────────────────────────┐
│              Govi AI API (Python / FastAPI)                  │
│              `app/main.py`                                   │
├──────────────────────────┬───────────────────────────────────┤
│   Router: /health        │   Router: /ai                    │
│  `app/routers/health.py` │  `app/routers/ai.py`             │
│   GET /health            │   POST /ai/chat                  │
└──────────────────────────┴──────────────┬────────────────────┘
                                          │ Anthropic SDK
                                          ▼
┌──────────────────────────────────────────────────────────────┐
│              Anthropic Claude API (external)                 │
│              `client.messages.create(...)`                   │
└──────────────────────────────────────────────────────────────┘
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

**Overall:** Two-service gateway pattern — a thin Node.js webhook receiver delegates AI inference to a Python FastAPI backend. No shared database; services communicate over HTTP.

**Key Characteristics:**
- Stateless: no session or conversation history persisted between requests
- Each `POST /ai/chat` call is a standalone single-turn Claude invocation
- The messenger bot is an optional front-end gateway; the FastAPI backend is independently usable
- Configuration is entirely environment-variable driven via `.env` files in each service root

## Layers

**Entry Point / Boot Layer:**
- Purpose: Start the ASGI server
- Location: `main.py` (project root)
- Contains: `uvicorn.run` call reading `app_port` from settings
- Depends on: `app.config.settings`, uvicorn
- Used by: Developer / process manager (e.g., `python main.py`)

**Application / Middleware Layer:**
- Purpose: FastAPI app construction, CORS, router registration
- Location: `app/main.py`
- Contains: `FastAPI` instance, `CORSMiddleware` (allow all origins), router includes
- Depends on: `app/routers/`
- Used by: uvicorn ASGI runner

**Router / Handler Layer:**
- Purpose: HTTP route definitions and request/response handling
- Location: `app/routers/ai.py`, `app/routers/health.py`
- Contains: `APIRouter` instances, Pydantic request/response models, route functions
- Depends on: `app/config.py`, Anthropic SDK
- Used by: `app/main.py`

**Configuration Layer:**
- Purpose: Centralised settings loaded from `.env`
- Location: `app/config.py`
- Contains: `Settings(BaseSettings)` singleton `settings`
- Depends on: pydantic-settings
- Used by: `app/main.py` (port), `app/routers/ai.py` (API key)

**Messenger Gateway (separate service):**
- Purpose: Facebook Messenger webhook verification and message routing
- Location: `messenger-bot/src/index.ts`
- Contains: Express app, GET/POST `/webhook` handlers, `sendMessage` helper
- Depends on: Govi AI API (`GOVI_AI_URL`), Facebook Graph API
- Used by: Facebook Messenger platform (external)

## Data Flow

### Primary Chat Request Path (via Messenger)

1. Facebook delivers a `POST /webhook` to the messenger bot (`messenger-bot/src/index.ts:27`)
2. Bot immediately ACKs with `200` to satisfy Facebook's 20s requirement (`messenger-bot/src/index.ts:36`)
3. Bot extracts `senderId` and `userText` from the event payload (`messenger-bot/src/index.ts:43-44`)
4. Bot POSTs `{ message: userText }` to `GOVI_AI_URL/ai/chat` via axios (`messenger-bot/src/index.ts:48`)
5. FastAPI receives the request at `POST /ai/chat` (`app/routers/ai.py:23`)
6. Router instantiates an `anthropic.Anthropic` client and calls `messages.create` (`app/routers/ai.py:28-35`)
7. Claude API responds; router returns `ChatResponse` JSON (`app/routers/ai.py:37-42`)
8. Messenger bot calls `sendMessage` to post the reply back via Graph API (`messenger-bot/src/index.ts:52`)

### Direct API Chat Path

1. Client sends `POST /ai/chat` with `{ message, model?, max_tokens? }` to FastAPI
2. `app/routers/ai.py` validates request via `ChatRequest` Pydantic model
3. Claude API is called; `ChatResponse` (reply, model, token counts) is returned

### Webhook Verification Path

1. Facebook sends `GET /webhook?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...`
2. Bot checks token matches `FACEBOOK_VERIFY_TOKEN`; echoes challenge if valid (`messenger-bot/src/index.ts:13-24`)

**State Management:**
- None. All requests are stateless. No database, cache, or in-memory store exists. Each chat call is independent.

## Key Abstractions

**ChatRequest / ChatResponse (Pydantic models):**
- Purpose: Typed contract for the `/ai/chat` endpoint
- Location: `app/routers/ai.py:10-21`
- Pattern: Inline Pydantic `BaseModel` — defined in the same file as the route

**Settings singleton:**
- Purpose: Single source of truth for all environment-sourced config
- Location: `app/config.py`
- Pattern: `pydantic_settings.BaseSettings` with `model_config = {"env_file": ".env"}`; imported as `settings` module-level singleton

## Entry Points

**FastAPI ASGI app:**
- Location: `app/main.py` — `app` object
- Triggers: uvicorn targets `"app.main:app"`
- Responsibilities: Middleware wiring, router mounting

**Process runner:**
- Location: `main.py` (project root)
- Triggers: `python main.py`
- Responsibilities: Reads `settings.app_port`, starts uvicorn with reload

**Messenger bot:**
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

**What happens:** `client = anthropic.Anthropic(...)` is called inside `async def chat` on every HTTP request (`app/routers/ai.py:28`).
**Why it's wrong:** Creates a new HTTP connection pool on every request; wastes memory and adds latency.
**Do this instead:** Instantiate the client once at module level (or use FastAPI `lifespan`) and reuse it across requests.

### Synchronous SDK call inside async route

**What happens:** `client.messages.create(...)` is a blocking call inside an `async def` handler (`app/routers/ai.py:30`).
**Why it's wrong:** Blocks the event loop for the duration of the Anthropic API call, degrading concurrency.
**Do this instead:** Use the async Anthropic client (`AsyncAnthropic`) with `await client.messages.create(...)`.

## Error Handling

**Strategy:** Minimal — only one explicit guard exists.

**Patterns:**
- Missing API key raises `HTTPException(500)` before any external call (`app/routers/ai.py:25-27`)
- Messenger bot wraps the Govi AI call in `try/catch`; on error it sends a fallback message to the user and logs to `console.error` (`messenger-bot/src/index.ts:53-56`)
- No error handling on the FastAPI side for Anthropic API failures (network errors or rate limits will surface as unhandled 500s)

## Cross-Cutting Concerns

**Logging:** `console.log`/`console.error` in the messenger bot only. FastAPI relies on uvicorn's default access log. No structured logging.
**Validation:** Pydantic models on FastAPI routes. No input validation in the messenger bot beyond checking `event.message?.text` existence.
**Authentication:** None on the FastAPI API (any caller can POST `/ai/chat`). Facebook webhook is verified by token comparison in the messenger bot.

---

*Architecture analysis: 2026-05-14*
