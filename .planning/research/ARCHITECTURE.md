# Architecture Patterns: Admin Panel & Multi-Page Support

**Project:** Govi Facebook Messenger Customer Support Bot — v1.2
**Researched:** 2026-05-27
**Confidence:** HIGH — grounded in existing codebase analysis + official Meta docs + verified library patterns

---

## Context: What Exists Today

The system is two independent processes:

- **Messenger Bot** (`messenger-bot/src/index.ts`, ~420 LOC): Express/TypeScript, handles Facebook webhook, drives rule-based menus, reads content from FastAPI, sends messages via Graph API. Single-page: `PAGE_ACCESS_TOKEN` is a single env var.
- **FastAPI backend** (`app/`): Python, serves Q&A content from Obsidian vault markdown files, no database.

No database exists. Content is file-based. Page identity is implicit (one token, one page).

---

## Target Architecture (v1.2)

```text
┌─────────────────────────────────────────────────────────────────┐
│                  Admin Panel  (React + Vite + TypeScript)        │
│   admin-panel/src/  — served as static files on port 5173 (dev) │
│   Login, tenant management, page connection, content editor      │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTP (axios, JWT Bearer)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│               FastAPI backend  (Python, port 8000)              │
│   app/routers/auth.py        — POST /auth/login, /auth/refresh  │
│   app/routers/tenants.py     — CRUD /admin/tenants              │
│   app/routers/pages.py       — CRUD /admin/pages, OAuth flow    │
│   app/routers/page_config.py — CRUD /admin/pages/{id}/config    │
│   app/routers/content.py     — EXISTING (keep for bot use)      │
│   app/db/database.py         — SQLAlchemy async engine (SQLite)  │
│   app/db/models.py           — ORM models                       │
│   app/db/crud.py             — DB query helpers                 │
└────────────┬──────────────────────────────────────────┬─────────┘
             │ DB read on each webhook (page lookup)    │ alembic migrations
             │                                           ▼
             │                              ┌────────────────────┐
             │                              │   govi.db (SQLite) │
             │                              │   Tenants          │
             │                              │   Pages            │
             │                              │   PageConfig       │
             │                              └────────────────────┘
             │ HTTP GET /content?page_id=...  (new param)
             ▼
┌─────────────────────────────────────────────────────────────────┐
│           Messenger Bot  (Node.js/TypeScript, port 3000)         │
│   src/index.ts  — webhook handler (MODIFIED: extract page_id,  │
│                   look up token + config from FastAPI per event) │
│   src/pageContext.ts — NEW: fetch and cache per-page config      │
└────────────────────────────┬────────────────────────────────────┘
                             │ POST /webhook (all pages → same URL)
                             │ Graph API calls (token from DB lookup)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              Facebook Messenger Platform                         │
│   Multiple Pages, each subscribed to the same webhook URL        │
└─────────────────────────────────────────────────────────────────┘
```

---

## New Components Required

| Component | Type | Location | Purpose |
|-----------|------|----------|---------|
| Admin Panel | New service | `admin-panel/` | React SPA: tenant + page + content management |
| SQLite database | New persistence | `govi.db` (project root) | Stores tenants, pages, per-page config |
| DB layer | New module | `app/db/` | SQLAlchemy models, async engine, CRUD helpers |
| Auth router | New module | `app/routers/auth.py` | JWT login/refresh for super-admin + tenants |
| Tenant router | New module | `app/routers/tenants.py` | Super-admin CRUD for tenant accounts |
| Pages router | New module | `app/routers/pages.py` | Per-tenant page connection (OAuth flow) |
| Page config router | New module | `app/routers/page_config.py` | Per-page welcome text, menu, Q&A, escalation |
| Page context module | New module | `messenger-bot/src/pageContext.ts` | Cache page token + config keyed by page_id |

## Modified Components

| Component | Change | Why |
|-----------|--------|-----|
| `app/routers/content.py` | Add `page_id` filter to all queries | Content is now per-page, not global |
| `app/config.py` | Add `db_path`, `jwt_secret`, `facebook_app_secret`, `facebook_app_id` | New required config |
| `app/main.py` | Register new routers; initialize DB on startup | Wire new components |
| `messenger-bot/src/index.ts` | Extract `entry.id` (page_id); route all Graph API calls through `pageContext` | Multi-page token dispatch |
| `messenger-bot/.env.example` | Remove `FACEBOOK_PAGE_ACCESS_TOKEN` (now in DB); add `ADMIN_API_URL` | Config changes |

---

## SQLite Schema

Single shared database, single file. Shared-table multi-tenancy (tenant_id FK on every table). This is correct at this scale — a few tenants, a few pages each. Database-per-tenant would be premature.

```sql
-- Tenants: super-admin creates these. Super-admin is tenant_id=1 or a role flag.
CREATE TABLE tenants (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,          -- bcrypt
    role        TEXT NOT NULL DEFAULT 'client',  -- 'super_admin' | 'client'
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Pages: each tenant connects one or more Facebook Pages via OAuth.
CREATE TABLE pages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    facebook_page_id TEXT NOT NULL UNIQUE,   -- the FB Page ID from the webhook entry.id
    page_name       TEXT NOT NULL,
    page_access_token TEXT NOT NULL,         -- long-lived token, stored encrypted
    subscribed_at   TEXT NOT NULL DEFAULT (datetime('now')),
    active          INTEGER NOT NULL DEFAULT 1   -- 0=disabled
);

-- PageConfig: one row per page, all customizable content.
CREATE TABLE page_configs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id         INTEGER NOT NULL UNIQUE REFERENCES pages(id) ON DELETE CASCADE,
    welcome_text    TEXT NOT NULL DEFAULT 'Welcome! How can I help you today?',
    menu_config     TEXT NOT NULL DEFAULT '[]',  -- JSON array of menu items
    escalation_admin_psid TEXT,                  -- ADMIN_PSID for this page
    escalation_message TEXT NOT NULL DEFAULT 'Connecting you with a human agent.',
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- QAItems: replaces Obsidian vault. Content belongs to a page.
CREATE TABLE qa_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id     INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    item_type   TEXT NOT NULL,   -- 'category' | 'question'
    category_id INTEGER REFERENCES qa_items(id),  -- NULL for categories
    title       TEXT NOT NULL,
    body        TEXT NOT NULL DEFAULT '',
    sort_order  INTEGER NOT NULL DEFAULT 0,
    enabled     INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_pages_facebook_page_id ON pages(facebook_page_id);
CREATE INDEX idx_qa_items_page_id_type ON qa_items(page_id, item_type);
CREATE INDEX idx_qa_items_category ON qa_items(category_id);
```

**Key design decisions:**
- `pages.facebook_page_id` is the lookup key on every webhook event (`entry.id` in the payload)
- `page_configs.menu_config` stored as JSON text for flexibility without schema churn; bot parses at load time
- `qa_items` replaces Obsidian vault entirely; category/question hierarchy via self-referencing FK
- Page access tokens must be encrypted at rest (AES-256 or Fernet) — plain storage is unacceptable

---

## Multi-Page Bot: Token Dispatch

### The Problem Today

`PAGE_ACCESS_TOKEN` is a module-level constant. Every Graph API call uses it. This must become a per-event lookup.

### The Incoming Webhook Payload

Facebook delivers all pages' events to the same webhook URL. The `entry.id` field is the Facebook Page ID:

```json
{
  "object": "page",
  "entry": [
    {
      "id": "123456789",           // ← this is the Facebook Page ID
      "time": 1234567890,
      "messaging": [{ "sender": { "id": "..." }, ... }]
    }
  ]
}
```

### Lookup Pattern

On every webhook event, before any Graph API call, the bot must resolve the page's token and config from the database via FastAPI:

```
entry.id (Facebook Page ID)
  → GET http://localhost:8000/internal/pages/{facebook_page_id}/context
  → returns { page_access_token, welcome_text, escalation_admin_psid, escalation_message, menu_config }
  → bot uses token for all Graph API calls for this event
```

A `/internal/pages/{id}/context` endpoint on FastAPI serves page context to the bot. This endpoint is internal-only (not exposed to the admin panel UI users) and protected by a shared secret between the two services.

### In-Process Cache

The bot caches page context in a `Map<facebookPageId, PageContext>` to avoid a DB lookup on every single event. Cache entries are refreshed on a TTL (5 minutes is sufficient — config changes are not real-time critical). The existing `userNameCache` and `lastMessageCache` patterns in `index.ts` already demonstrate this Map-based cache pattern.

```typescript
// messenger-bot/src/pageContext.ts
interface PageContext {
  pageAccessToken: string;
  welcomeText: string;
  escalationAdminPsid: string | null;
  escalationMessage: string;
  menuConfig: MenuItem[];
  cachedAt: number;
}

const PAGE_CONTEXT_TTL_MS = 5 * 60 * 1000;
const pageContextCache = new Map<string, PageContext>();

export async function getPageContext(facebookPageId: string): Promise<PageContext | null> { ... }
```

All functions that currently accept `PAGE_ACCESS_TOKEN` as a module-level constant (`sendMessage`, `passThreadControl`, `sendTypingIndicator`, `fetchUserName`) must be refactored to accept `pageAccessToken: string` as a parameter. This is the most invasive change in the bot.

---

## Facebook OAuth: Page Connection Flow

The admin panel connects a client's Facebook Page to the system. The flow:

```
1. Admin panel: client clicks "Connect with Facebook"
   → Frontend redirects to:
     https://www.facebook.com/v21.0/dialog/oauth
       ?client_id={APP_ID}
       &redirect_uri={BACKEND_URL}/oauth/facebook/callback
       &scope=pages_show_list,pages_messaging,pages_manage_metadata
       &state={JWT_of_tenant_id}   ← CSRF protection

2. User grants permission on Facebook
   → Facebook redirects to /oauth/facebook/callback?code=...&state=...

3. FastAPI /oauth/facebook/callback:
   a. Verify state JWT (contains tenant_id)
   b. Exchange code → short-lived user token:
      GET https://graph.facebook.com/v21.0/oauth/access_token
        ?client_id=...&client_secret=...&redirect_uri=...&code=...
   c. Exchange short-lived → long-lived user token:
      GET https://graph.facebook.com/v21.0/oauth/access_token
        ?grant_type=fb_exchange_token&client_id=...&client_secret=...&fb_exchange_token=...
   d. Fetch pages the user administers:
      GET https://graph.facebook.com/v21.0/me/accounts?access_token={long_lived_user_token}
      → returns [{id, name, access_token (long-lived page token), tasks}, ...]
   e. For each page returned:
      - Upsert row in `pages` table (encrypt token before storing)
      - Upsert default row in `page_configs`
      - POST /me/subscribed_apps?subscribed_fields=messages,messaging_postbacks,messaging_optins
        with the page's access token (subscribes the page to the webhook)
   f. Redirect back to admin panel with success/error

4. Admin panel: shows connected pages list
```

Required Facebook App permissions: `pages_show_list`, `pages_messaging`, `pages_manage_metadata`. These require Facebook App Review before use by non-test users.

Long-lived Page Access Tokens from step (d) do not expire (they only invalidate if the user changes their Facebook password or the Page role changes). Store them encrypted.

---

## Admin Panel: Component Structure

React + Vite + TypeScript SPA. New third service at `admin-panel/`. Communicates with FastAPI only.

```
admin-panel/
  src/
    api/          — axios instance with JWT interceptors (request: inject Bearer, response: 401 → refresh)
    pages/        — route-level components
      LoginPage.tsx
      DashboardPage.tsx         — tenant's connected pages overview
      PagesPage.tsx             — add/remove pages, OAuth connect button
      PageEditorPage.tsx        — welcome text, menu, Q&A, escalation editors
      TenantsPage.tsx           — super-admin only: create/list tenants
    components/   — shared UI components (table, form, sidebar nav)
    hooks/        — useAuth(), usePageConfig(), useQAItems()
    store/        — JWT tokens in memory (access) + httpOnly cookie (refresh)
  index.html
  vite.config.ts
  tsconfig.json
  package.json
```

Auth model:
- Super-admin creates tenant accounts (email + password)
- Tenants log in; JWT includes `tenant_id` and `role`
- FastAPI enforces: `role=super_admin` required for tenant management endpoints; `role=client` can only see/edit pages belonging to their `tenant_id`
- Access token: short-lived JWT (15 min) in memory. Refresh token: longer-lived JWT (7 days) in httpOnly cookie. Axios interceptor auto-refreshes on 401.

---

## FastAPI: New Router Structure

```
app/
  db/
    database.py      — create_async_engine (sqlite+aiosqlite:///govi.db), get_db dependency
    models.py        — SQLAlchemy ORM models mirroring schema above
    crud.py          — typed query helpers (get_page_by_facebook_id, etc.)
  routers/
    auth.py          — POST /auth/login, POST /auth/refresh, GET /auth/me
    tenants.py       — GET/POST/DELETE /admin/tenants  (super_admin only)
    pages.py         — GET/POST/DELETE /admin/pages, GET /oauth/facebook/callback
    page_config.py   — GET/PUT /admin/pages/{id}/config
    qa.py            — CRUD /admin/pages/{id}/qa
    internal.py      — GET /internal/pages/{facebook_page_id}/context  (bot-facing, shared secret)
    content.py       — MODIFIED: reads from DB instead of vault file; filtered by page_id
    health.py        — unchanged
```

The existing vault-based `content.py` router is replaced with a DB-backed version. The HTTP contract (`GET /content?type=&category=`, `GET /content/{id}`) stays identical so the bot code changes minimally on the content-fetch path.

---

## Data Flow: Webhook Event (Multi-Page)

```
1. Facebook POSTs to /webhook
   Body: { object: "page", entry: [{ id: "PAGE_FB_ID", messaging: [...] }] }

2. Messenger bot: extract pageId = entry.id

3. Bot calls getPageContext(pageId):
   - Cache hit (< 5 min old): return cached PageContext
   - Cache miss: GET /internal/pages/{pageId}/context (FastAPI → DB query)
   - Context not found: log warning, drop event silently (unknown page)

4. For each event in entry.messaging:
   - handleWebhookEvent(event, pageContext)
   - All Graph API calls use pageContext.pageAccessToken
   - Welcome text from pageContext.welcomeText
   - Escalation config from pageContext.escalation*
   - Menu structure from pageContext.menuConfig

5. Content fetch (for Q&A):
   GET /content?type=category&page_id={pageId}
   GET /content/{questionId}?page_id={pageId}
   FastAPI queries qa_items WHERE page_id = {resolved page row id}
```

---

## Build Order: Recommended Phase Sequence

Dependencies flow strictly top-to-bottom. Each phase delivers something runnable and testable before the next starts.

### Phase 10: DB Foundation
**Goal:** SQLite database initialized, ORM models defined, Alembic migration working, `govi.db` created with empty tables.
**Deliverables:**
- `app/db/database.py` — async SQLAlchemy engine (`sqlite+aiosqlite`)
- `app/db/models.py` — Tenant, Page, PageConfig, QAItem ORM models
- `alembic/` — initial migration creating all four tables
- `app/config.py` gains `db_path`, `jwt_secret`, `facebook_app_id`, `facebook_app_secret`
**Verify:** `alembic upgrade head` creates `govi.db` with correct schema. No service changes yet.

### Phase 11: Auth (FastAPI)
**Goal:** JWT login/refresh working. Super-admin bootstrapped from env var (seed script). Admin panel can authenticate.
**Deliverables:**
- `app/db/crud.py` — `get_tenant_by_email`, `verify_password`
- `app/routers/auth.py` — `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me`
- Seed script: creates super-admin from `SUPER_ADMIN_EMAIL` / `SUPER_ADMIN_PASSWORD` env vars on first run
- `app/dependencies.py` — `get_current_tenant` FastAPI dependency using JWT decode
**Verify:** `POST /auth/login` with seed credentials returns access + refresh tokens. `GET /auth/me` with Bearer token returns tenant info.

### Phase 12: Tenant & Page Admin API (FastAPI)
**Goal:** CRUD endpoints for tenants and pages operational. OAuth callback stores tokens.
**Deliverables:**
- `app/routers/tenants.py` — GET/POST/DELETE `/admin/tenants` (super_admin only)
- `app/routers/pages.py` — list/delete pages per tenant + `GET /oauth/facebook/callback`
- Token encryption helper (Fernet from `cryptography` library)
- `POST /oauth/facebook/callback` full flow: code exchange → long-lived user token → page list → upsert pages + page_configs → subscribe webhook
**Verify:** Connect a real test Facebook Page through the OAuth flow. Row appears in `pages` table with encrypted token. Page receives subscribed_apps confirmation.

### Phase 13: Page Config & Q&A API (FastAPI)
**Goal:** Per-page content fully editable via API. Bot can read DB-backed content.
**Deliverables:**
- `app/routers/page_config.py` — GET/PUT `/admin/pages/{id}/config` (welcome, escalation)
- `app/routers/qa.py` — full CRUD `/admin/pages/{id}/qa` (categories + questions)
- `app/routers/content.py` MODIFIED — reads from `qa_items` DB table filtered by `page_id` (same HTTP contract as before)
- `app/routers/internal.py` — `GET /internal/pages/{facebook_page_id}/context` protected by shared secret header
**Verify:** Create Q&A items via API, then `GET /content?type=category&page_id=X` returns them. Vault-based content.py retired.

### Phase 14: Bot Multi-Page Routing
**Goal:** Bot reads token + config from DB per event. Works with multiple pages simultaneously.
**Deliverables:**
- `messenger-bot/src/pageContext.ts` — `getPageContext(facebookPageId)` with 5-min TTL cache
- `messenger-bot/src/index.ts` MODIFIED — extract `entry.id`, thread pageContext through all handlers
- All Graph API helpers (`sendMessage`, `sendTypingIndicator`, `passThreadControl`, `fetchUserName`) gain `pageAccessToken: string` parameter
- `handleEscalation` reads admin PSID + escalation message from pageContext (not env vars)
- `handleWebhookEvent` receives `pageContext` and uses it for welcome text + escalation config
- Remove `PAGE_ACCESS_TOKEN` and `ADMIN_PSID` env vars from bot (now in DB)
**Verify:** Two test pages both receive correct responses. Token from each page's context used exclusively.

### Phase 15: Admin Panel UI
**Goal:** React SPA functional for tenant login, page connection, and content editing.
**Deliverables:**
- `admin-panel/` initialized: Vite + React 18 + TypeScript + Tailwind CSS + shadcn/ui + axios
- Login page → JWT stored (access in memory, refresh in httpOnly cookie)
- Pages dashboard: list connected pages, "Connect with Facebook" OAuth button
- Page editor: welcome text, escalation config, Q&A category + question editor
- Super-admin tenant management page
- Axios instance with JWT refresh interceptor
**Verify:** Full manual walkthrough — login → connect page → add Q&A content → send Messenger message → receives correct answer from DB content.

---

## Component Interaction Matrix

| From | To | Protocol | Auth | Data |
|------|----|----------|------|------|
| Admin Panel | FastAPI `/auth/*` | HTTP/JSON | None (login endpoint) | credentials → JWT |
| Admin Panel | FastAPI `/admin/*` | HTTP/JSON | JWT Bearer | CRUD payloads |
| Admin Panel | Facebook | Browser redirect | OAuth2 code flow | none stored client-side |
| FastAPI | Facebook Graph API | HTTPS | Page Access Token | OAuth code exchange |
| FastAPI | SQLite (`govi.db`) | SQLAlchemy async | File permissions | ORM models |
| Messenger Bot | FastAPI `/internal/*` | HTTP/JSON | Shared secret header | page context |
| Messenger Bot | FastAPI `/content/*` | HTTP/JSON | None (internal network) | Q&A queries |
| Messenger Bot | Facebook Graph API | HTTPS | Per-page token (from DB) | send messages |
| Facebook | Messenger Bot `/webhook` | HTTPS POST | HMAC-SHA256 | webhook events |

---

## Key Architectural Risks

### Risk 1: Token Encryption at Rest
**What:** Page Access Tokens are long-lived and grant full messaging ability on behalf of a Page. Storing them plaintext in SQLite is a critical security failure.
**Prevention:** Encrypt with Python `cryptography` Fernet (`pip install cryptography`). Store `FERNET_KEY` in env. Decrypt only in memory, only when constructing a Graph API call. Never return the raw token in any API response to the admin panel.
**Confidence:** HIGH — this is a firm requirement, not optional.

### Risk 2: Facebook App Review Required for Production
**What:** The `pages_messaging` and `pages_manage_metadata` permissions require Facebook App Review before non-test users can grant them. Development against test Pages is fine; production for real clients requires approval.
**Prevention:** Use test Pages (added as test users in the Facebook App) during development. Plan a Facebook App Review submission as a deployment prerequisite.
**Confidence:** HIGH — confirmed in Meta developer docs.

### Risk 3: Bot Function Signature Refactor Surface
**What:** Changing `sendMessage`, `sendTypingIndicator`, `passThreadControl`, `fetchUserName` to accept `pageAccessToken` as a parameter touches ~15 call sites and all 50 existing tests.
**Prevention:** Make the change in one surgical commit (Phase 14). Update tests to pass a mock `pageContext`. The existing test structure (Node.js built-in test runner) is already in place — update fixtures, not test logic.
**Confidence:** HIGH — invasive but bounded and well-understood.

### Risk 4: Vault Content Migration
**What:** Existing Obsidian vault content must be seeded into `qa_items` when the DB-backed content router is deployed. No automated migration exists today.
**Prevention:** Write a one-time Python seed script (`scripts/seed_from_vault.py`) that reads the vault using the existing `load_vault()` function and inserts rows into `qa_items` for a specified page. Run once during Phase 13 deployment.
**Confidence:** HIGH — the vault parser already exists in `app/routers/content.py`.

### Risk 5: Webhook Subscription on Page Connect
**What:** After storing a Page Access Token, the bot must subscribe the page to receive webhook events. If this subscription POST fails (e.g., insufficient permissions), the page is stored but receives no messages.
**Prevention:** Make the subscription call (`POST /{page_id}/subscribed_apps`) part of the OAuth callback transaction. If it fails, return an error to the admin panel user and do not save the page row. Log the Graph API error detail.
**Confidence:** HIGH.

### Risk 6: SQLite Concurrency (Admin Panel + Bot concurrent writes)
**What:** SQLite single-writer constraint. If the admin panel is editing Q&A while the bot is reading page contexts, writes block reads briefly.
**Prevention:** Enable WAL mode (`PRAGMA journal_mode=WAL`) on database creation. WAL allows concurrent reads during writes, eliminating the primary bottleneck at this scale. Bot reads content; admin panel writes config. This is low-contention by nature.
**Confidence:** HIGH — WAL is standard practice, well-documented.

### Risk 7: JWT Secret Rotation
**What:** `jwt_secret` in env signs all admin panel tokens. If it must rotate, all sessions invalidate simultaneously.
**Prevention:** Document the rotation procedure. For v1.2 this is acceptable — small number of admin users, not customer-facing tokens.
**Confidence:** MEDIUM — acceptable risk for this use case.

---

## Anti-Patterns to Avoid

### Anti-Pattern: Store Page Access Token Unencrypted
**Why bad:** Tokens grant full posting, messaging, and page management ability. A DB read by any SQL tool exposes them.
**Instead:** Fernet encryption at write time, decryption only at Graph API call time.

### Anti-Pattern: Single Content Table for All Pages Without page_id Index
**Why bad:** As Q&A items grow, unindexed queries scan all rows. The index `idx_qa_items_page_id_type` ensures fast per-page filtered queries.
**Instead:** Always filter `WHERE page_id = ?` and rely on the defined index.

### Anti-Pattern: Expose `/internal/` Endpoints Without Auth
**Why bad:** The `GET /internal/pages/{id}/context` endpoint returns decrypted page tokens. Without protection, any caller who knows the URL gets all page tokens.
**Instead:** Require a shared secret header (`X-Internal-Secret`) checked against an env var. The bot sets this header; the admin panel never calls this endpoint.

### Anti-Pattern: Return Page Access Token in Admin Panel API Responses
**Why bad:** The admin panel JavaScript receives it, the token appears in browser devtools, and JS bundle security model doesn't protect it.
**Instead:** Admin panel API responses show page metadata (name, ID, connected status) only. Token is never returned.

### Anti-Pattern: React State for Access Token (localStorage)
**Why bad:** XSS can read localStorage; if the admin panel is ever compromised, JWT access tokens leak.
**Instead:** Access token in memory (React state/context). Refresh token in httpOnly cookie (browser blocks JS access). This is the standard pattern confirmed by 2024 sources.

---

## Scalability Notes

This architecture is appropriate for the stated scale: a small number of tenants, a few Facebook Pages each, and the existing single-process deployment model.

| Concern | At current scale (1–10 pages) | If scale grows (100+ pages) |
|---------|-------------------------------|----------------------------|
| SQLite concurrency | WAL mode sufficient | Consider PostgreSQL |
| Bot page context cache | In-memory Map, TTL refresh | Fine as-is |
| Admin API auth | JWT, no session DB | Fine as-is |
| Token storage | SQLite + Fernet | Same pattern, different DB |
| Vault → DB migration | One-time script per page | Fully DB-native, no migration |

---

## Sources

- Existing codebase: `messenger-bot/src/index.ts`, `app/routers/content.py`, `app/config.py`, `requirements.txt`, `messenger-bot/package.json` (directly read)
- Meta developer docs: [Access Token Guide](https://developers.facebook.com/docs/facebook-login/guides/access-tokens/), [Long-Lived Tokens](https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived/), [Webhooks for Pages](https://developers.facebook.com/docs/graph-api/webhooks/getting-started/webhooks-for-pages/) (fetched and read)
- Facebook Page ID in webhook: confirmed via entry.id field in webhook payload structure (HIGH confidence, stable since Messenger Platform v1)
- SQLAlchemy 2.0 + aiosqlite + FastAPI pattern: multiple 2024–2025 sources, consistent pattern
- JWT auth pattern (access in memory, refresh in httpOnly cookie): multiple 2024 sources, confirmed best practice
- better-sqlite3 vs aiosqlite: aiosqlite chosen because FastAPI backend is already Python; no reason to introduce a second DB connection from the Node.js bot
- WAL mode for SQLite concurrency: SQLite official documentation (HIGH confidence)

*Architecture research: 2026-05-27*
