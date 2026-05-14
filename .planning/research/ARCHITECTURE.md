# Architecture Research

**Project:** Govi Facebook Messenger Customer Support Bot
**Researched:** 2026-05-14
**Confidence:** HIGH — grounded in existing codebase; no speculative components

---

## System Overview

```text
┌─────────────────────────────────────────────────────────┐
│            Obsidian Vault (local filesystem)             │
│   /path/to/vault/*.md  — Q&A content, menu definitions  │
└────────────────────────┬────────────────────────────────┘
                         │ read on startup + optional reload
                         ▼
┌─────────────────────────────────────────────────────────┐
│           Govi AI API  (Python / FastAPI)                │
│   app/routers/content.py  — GET /content/menu           │
│   app/routers/content.py  — GET /content/answer/{id}    │
│   app/services/vault.py   — markdown parser, cache       │
│   app/routers/health.py   — GET /health                 │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP GET (axios, internal network)
                         ▼
┌─────────────────────────────────────────────────────────┐
│        Messenger Bot  (Node.js / Express / TypeScript)   │
│   src/index.ts          — webhook entry point            │
│   src/menu.ts           — rule engine, state machine     │
│   src/messenger.ts      — Graph API send helpers         │
│   src/session.ts        — in-memory session store        │
└────────────────────────┬────────────────────────────────┘
                         │ POST /webhook (Facebook → bot)
                         │ Graph API calls (bot → Facebook)
                         ▼
┌─────────────────────────────────────────────────────────┐
│              Facebook Messenger Platform                 │
│   Webhook events inbound / Send API outbound             │
│   Page inbox visible to admin (human escalation)         │
└─────────────────────────────────────────────────────────┘
```

The Anthropic SDK call in `app/routers/ai.py` is removed entirely. The `/ai` router
is replaced (or retired) with a `/content` router. The messenger bot's forward-to-AI
logic is replaced with a local rule engine that drives menus and calls FastAPI only
for content lookup.

---

## Component Boundaries

### Messenger Bot (Node.js / TypeScript)

- **Responsibility:** All Facebook interaction. Owns the webhook, owns session state,
  owns menu navigation logic, owns Graph API calls.
- **Data it owns:** Per-user session state (current menu position, awaiting-escalation
  flag). Ephemeral — lives in-process memory, not persisted.
- **What it does NOT do:** Parse markdown, store Q&A content, know anything about file
  paths. It asks FastAPI for content by ID and renders what it gets back.
- **Internal modules to create:**
  - `src/session.ts` — `Map<senderId, SessionState>` where `SessionState = { menuPath: string[], awaitingEscalation: boolean }`.
  - `src/menu.ts` — takes a session + incoming message text/postback, returns the next
    reply (text or quick-reply buttons) and updates session.
  - `src/messenger.ts` — thin wrappers over the Graph API: `sendText`, `sendQuickReplies`, `sendButtons`.

### Govi AI API (Python / FastAPI)

- **Responsibility:** Content layer. Reads Obsidian vault markdown files, parses them
  into structured Q&A + menu data, and exposes that data via HTTP endpoints.
- **Data it owns:** The parsed, in-memory content cache loaded from the vault.
- **What it does NOT do:** Manage conversation state, call Facebook, know about users
  or sessions.
- **New modules to create:**
  - `app/services/vault.py` — loads and parses markdown files from `VAULT_PATH` into a
    `ContentCache` dict at startup. Exposes `get_menu(menu_id)` and `get_answer(answer_id)`.
  - `app/routers/content.py` — `GET /content/menu/{menu_id}` and
    `GET /content/answer/{answer_id}` endpoints; thin wrappers over the vault service.

---

## Data Flow

### Step-by-step: Obsidian vault content reaching a Messenger user

```
1. FastAPI startup
   app/services/vault.py reads all *.md files under VAULT_PATH.
   Each file is parsed into a structured dict:
     { id, type: "menu"|"answer", title, items/body }
   Result stored in a module-level ContentCache dict.
   Startup fails fast if VAULT_PATH is missing or no files found.

2. User sends a message on Messenger
   Facebook POSTs a webhook event to messenger-bot POST /webhook.
   Bot ACKs immediately with HTTP 200 (existing pattern — keep this).

3. Bot resolves session
   src/session.ts looks up senderId in the in-memory Map.
   If no session exists, creates one at the root menu.

4. Bot determines intent
   src/menu.ts inspects the incoming payload:
   - Quick-reply postback payload → navigate to the specified menu/answer ID
   - Free text "hi"/"hello"/"start" → reset to root menu
   - Free text matching no known command → send "I didn't understand" + re-send current menu
   - "Talk to a human" → trigger escalation flow

5. Bot fetches content from FastAPI (when needed)
   GET http://localhost:{GOVI_AI_PORT}/content/menu/{menu_id}
   or GET .../content/answer/{answer_id}
   FastAPI returns JSON from its in-memory cache (no disk I/O on request).

6. Bot renders response
   src/messenger.ts calls the Graph API:
   - Menu node → sendQuickReplies(senderId, title, options[])
   - Answer node → sendText(senderId, body) then sendQuickReplies back to parent menu
   - Escalation → sendText(senderId, "Connecting you to a human...") + notify admin

7. Session updated
   src/session.ts stores new menuPath position after each interaction.
```

### Human escalation sub-flow

```
User taps "Talk to a human" button
  → Bot sets session.awaitingEscalation = true
  → Bot sends user a confirmation message via Graph API
  → Bot sends a message to the admin's own Messenger inbox:
      POST /me/messages with recipient: { id: ADMIN_PSID }
      Body: "Customer {senderId} is requesting human support."
  → Conversation thread in Page inbox becomes visible to admin
  → Admin replies directly in Page inbox — Facebook routes it to the user
  → No further bot responses until user sends a new "start" trigger
      (or session TTL expires)
```

The admin PSID (Page-Scoped ID of the admin's own Facebook account) is stored as
`ADMIN_PSID` in `messenger-bot/.env`. This requires the admin to have messaged the
Page at least once so Facebook assigns them a PSID.

---

## Conversation State

### Problem

Facebook webhook is stateless by design. Each POST contains only the current message.
The bot has no built-in memory of what menu the user was on.

### Solution: In-process session Map with TTL

Use a `Map<senderId, SessionState>` in `src/session.ts`. This is the right choice for
this scale (single-process Node.js bot, no horizontal scaling requirement, no
persistence requirement between restarts).

```typescript
// src/session.ts
interface SessionState {
  menuPath: string[];       // e.g. ["root", "products", "sizing"]
  awaitingEscalation: boolean;
  lastActivityAt: number;   // unix ms — for TTL eviction
}

const sessions = new Map<string, SessionState>();
const SESSION_TTL_MS = 30 * 60 * 1000; // 30 minutes

export function getSession(senderId: string): SessionState { ... }
export function updateSession(senderId: string, patch: Partial<SessionState>): void { ... }
export function clearSession(senderId: string): void { ... }

// Eviction: call pruneExpiredSessions() on a setInterval (every 5 min is fine)
```

### Why not Redis or a database?

Redis adds a deployment dependency with no benefit at this scale. The bot is a single
Node.js process; in-memory is sufficient. Session loss on restart is acceptable — users
simply re-navigate from the root menu, which takes seconds.

### Why not stateless (reconstruct state from postback payload)?

Embedding full state in every quick-reply payload is possible but brittle: payload size
limits (1000 bytes per Facebook), and escalation state cannot be encoded in a button
payload the user hasn't clicked yet. Thin in-memory session is cleaner.

### Stateless webhook contract

The bot MUST return HTTP 200 within 20 seconds (Facebook requirement — already
implemented). All Graph API calls happen after the 200 response, in the same async
flow that already exists in `messenger-bot/src/index.ts`. No change needed here.

---

## FastAPI: Obsidian Content Loading Strategy

### Recommendation: Load-on-startup with manual reload endpoint

Load all vault content once at FastAPI startup using the `lifespan` pattern. Serve all
requests from the in-memory cache. Provide a `POST /content/reload` endpoint that
re-reads the vault without restarting the process.

```python
# app/services/vault.py
from pathlib import Path

_cache: dict[str, dict] = {}

def load_vault(vault_path: str) -> None:
    """Parse all *.md files and populate _cache. Called at startup."""
    ...

def get_menu(menu_id: str) -> dict | None:
    return _cache.get(menu_id)

def get_answer(answer_id: str) -> dict | None:
    return _cache.get(answer_id)

def reload_vault(vault_path: str) -> int:
    """Re-parse vault in place. Returns count of loaded items."""
    _cache.clear()
    load_vault(vault_path)
    return len(_cache)
```

```python
# app/main.py — lifespan for startup load
from contextlib import asynccontextmanager
from app.services import vault
from app.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    vault.load_vault(settings.vault_path)
    yield

app = FastAPI(lifespan=lifespan)
```

### Why not watchdog / file watcher?

A file watcher (watchdog library) running in the same process as FastAPI creates a
threading hazard: the watcher thread modifies `_cache` while the async event loop
reads it. Handling this safely requires a lock. That complexity is not justified when
the content editor (the Obsidian user) can simply call `POST /content/reload` after
saving. One `curl` command or a Messenger admin command ("reload content") achieves
the same result with zero background threads.

### Why not re-read files on every request?

File I/O on every request is unnecessary latency and couples request throughput to
filesystem speed. The vault content changes rarely (content edits, not per-user). Cache
it.

### Vault markdown format convention

Define a minimal frontmatter convention for Obsidian files so the parser has a stable
contract:

```markdown
---
id: products-sizing
type: menu
title: "Sizing Questions"
---

- What size should I order? → answer:sizing-guide
- Do you ship internationally? → answer:shipping-info
```

```markdown
---
id: sizing-guide
type: answer
title: "Sizing Guide"
---

Our sizing runs true to standard US sizes. Check the chart on the product page.
```

The parser reads `id`, `type`, `title` from frontmatter; body below the `---` is the
answer text or list of menu items. The `python-frontmatter` library handles this
cleanly (one dependency addition to `requirements.txt`).

---

## Build Order

Build in strict dependency order — each step produces something the next step calls.

### 1. FastAPI content router + vault service

**Why first:** Everything else depends on content existing. The bot cannot be tested
without something to call. FastAPI is also independently testable with `curl` before
touching the bot.

**Deliverables:**
- `app/services/vault.py` with `load_vault`, `get_menu`, `get_answer`, `reload_vault`
- `app/routers/content.py` with `GET /content/menu/{id}`, `GET /content/answer/{id}`,
  `POST /content/reload`
- `app/config.py` gains `vault_path: str` field
- At least two sample Obsidian `.md` files for local testing

**Verify:** `curl http://localhost:8000/content/menu/root` returns JSON.

### 2. Session store in the bot

**Why second:** Menu logic depends on session; session has no external dependencies.
Implement and unit-test in isolation before wiring to Messenger.

**Deliverables:**
- `messenger-bot/src/session.ts` — Map, TTL eviction, get/update/clear
- Unit tests (Jest or plain ts-node script)

**Verify:** `getSession("fake-id")` returns default root state; `updateSession` mutates
it; expired sessions are pruned.

### 3. Menu rule engine in the bot

**Why third:** Depends on session (step 2) and content API (step 1). Encapsulates all
navigation logic with no Messenger coupling, making it testable without Facebook.

**Deliverables:**
- `messenger-bot/src/menu.ts` — `handleMessage(senderId, payload): Promise<Reply>`
  calls FastAPI content endpoints, reads/updates session, returns a typed `Reply` object
  (not Graph API calls directly)
- `messenger-bot/src/types.ts` — `Reply`, `MenuNode`, `AnswerNode` interfaces

**Verify:** Given a postback payload for a known menu item, `handleMessage` returns the
correct Reply structure (mock the HTTP call to FastAPI).

### 4. Graph API send helpers

**Why fourth:** Depends on knowing what Reply types exist (step 3). Keeps all Graph API
surface area in one place.

**Deliverables:**
- `messenger-bot/src/messenger.ts` — `sendText`, `sendQuickReplies`, `sendButtons`,
  `notifyAdmin` functions wrapping `axios.post` to the Graph API

**Verify:** With a valid `FACEBOOK_PAGE_ACCESS_TOKEN` in `.env`, manually trigger
`sendText` to a test PSID.

### 5. Wire everything in bot index.ts

**Why fifth:** All pieces exist; now connect them in the webhook handler. Replaces the
current AI-passthrough logic.

**Deliverables:**
- `messenger-bot/src/index.ts` updated: webhook POST handler calls `handleMessage`,
  then maps the `Reply` to the appropriate `messenger.ts` function

**Verify:** End-to-end test with Facebook webhook — send "hi" and receive the root menu
quick-reply buttons.

### 6. Human escalation flow

**Why last:** Depends on all of the above being stable, plus requires the `ADMIN_PSID`
env var which needs a real Facebook Page setup. Implement only after the menu flows work.

**Deliverables:**
- `messenger.ts` gains `notifyAdmin(senderId)` — sends a message to `ADMIN_PSID`
- `menu.ts` handles the escalation trigger postback
- `session.ts` sets `awaitingEscalation = true` and suppresses bot replies while active

**Verify:** Tap "Talk to a human" — admin receives a Messenger notification on their
Page inbox.

---

## Key Architectural Risks

### Risk: Facebook PSID requirement for admin notification

**What can go wrong:** Sending a message to the admin requires the admin's Page-Scoped
ID (PSID), which Facebook only assigns after the admin has sent at least one message to
the Page from their personal account.

**Mitigation:** During setup, the admin must message the Page once. Use the webhook log
to capture their PSID and store it as `ADMIN_PSID` in `.env`. Document this as a
required setup step. If `ADMIN_PSID` is not set, the escalation flow falls back to
logging a console alert — it should not break the bot.

### Risk: In-memory session loss on bot restart

**What can go wrong:** A bot restart (deploy, crash) clears all active sessions. A user
mid-conversation is silently dropped to the start menu on their next message.

**Mitigation:** This is acceptable. The user sees the root menu again and can re-navigate
in seconds. Document it. Do not add a database to solve a cosmetic UX issue at this
scale. If it becomes a real pain point, a Redis session store is a clean upgrade path
(the session interface in `src/session.ts` hides the implementation).

### Risk: Vault markdown format drift

**What can go wrong:** The Obsidian user edits files in a way that breaks the
frontmatter convention (renames a field, changes indentation, removes an ID). The vault
service either silently skips the file or returns malformed content.

**Mitigation:** The `load_vault` function must log a clear warning per file that fails
to parse, with the filename and the specific parse error. FastAPI startup should succeed
(skip bad files) but log loudly. The `POST /content/reload` response should return a
summary of loaded vs skipped files so the admin knows immediately if a file was rejected.

### Risk: FastAPI content cache serves stale content after vault edits

**What can go wrong:** Admin updates a markdown file in Obsidian, but FastAPI is still
serving the old cached version. The bot replies with outdated answers.

**Mitigation:** The `POST /content/reload` endpoint is the cache-bust mechanism. This
requires a manual trigger after edits. For v1 this is fine. The endpoint should require
no authentication in local deployments but this should be noted as a production concern
(anyone who can reach the API can trigger a reload).

### Risk: Bot and FastAPI out of sync on menu/answer IDs

**What can go wrong:** A markdown file is renamed or its `id` frontmatter field is
changed. The bot sends a GET for an ID that no longer exists. FastAPI returns 404. The
bot has no fallback.

**Mitigation:** `menu.ts` must handle a 404 or null response from FastAPI gracefully:
send the user a "Something went wrong, let's start over" message and reset their session
to root. Never surface a raw error to the Messenger user.

### Risk: Session Map grows unbounded

**What can go wrong:** High volume of unique senders over time fills process memory.

**Mitigation:** The TTL eviction in `session.ts` (prune sessions inactive for 30 min
on a 5-minute interval) keeps the Map bounded. At Messenger-chatbot scale for a single
retail brand, this is negligible — thousands of entries, not millions. No action needed
unless traffic profile changes significantly.

---

*Architecture research: 2026-05-14*
