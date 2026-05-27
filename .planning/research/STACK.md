# Technology Stack

**Project:** Govi Facebook Messenger Customer Support Bot — v1.2 Admin Panel & Multi-Page Support
**Researched:** 2026-05-27
**Scope:** NEW additions only. The existing stack (Express/TypeScript bot, FastAPI/Python backend) is already validated and is not re-researched here. This document covers what needs to be added or changed for the admin panel, Facebook OAuth, SQLite content store, and multi-page bot routing features.

---

## New Service: Admin Panel (React + Vite + TypeScript)

This is a brand-new front-end service. It lives alongside the two existing services (`messenger-bot/` and `app/`).

### Core Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| React | 19.x | UI framework | Current stable; Vite's `react-ts` template provisions it automatically |
| TypeScript | 5.4+ | Type safety | Consistent with `messenger-bot/`; strict mode enforced |
| Vite | 6.x | Build tool + dev server | Fastest React + TS dev experience; `npm create vite@latest -- --template react-ts` scaffolds everything; no CRA or Next.js overhead needed for an SPA |
| Tailwind CSS | 4.x | Utility-first styling | v4 requires only `npm install tailwindcss @tailwindcss/vite`; no PostCSS/Autoprefixer config needed; pairs perfectly with shadcn/ui |
| shadcn/ui | latest | Component library | Copy-paste components built on Radix UI primitives (keyboard-nav and ARIA free); Tailwind-native; no version lock-in; purpose-built for admin dashboards |

**Confidence:** HIGH — Vite + React 19 + Tailwind v4 + shadcn/ui is the dominant 2025–2026 admin stack, verified across multiple sources.

### Routing & Data Fetching

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `react-router-dom` | 7.x | Client-side routing | Simpler learning curve than TanStack Router for a small admin SPA; v7 has adequate TypeScript support; no server rendering needed |
| `@tanstack/react-query` | 5.x | Server state / data fetching | Eliminates manual loading/error state; caching, refetch on focus, optimistic updates out of the box; TypeScript-first since v5 |

**Why not TanStack Router:** TanStack Router's advantage is exhaustive URL search-param type safety. This admin panel has simple routes (`/login`, `/dashboard`, `/pages/:id`). React Router v7 is sufficient and already familiar to most TS developers.

### Form Handling & Validation

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `react-hook-form` | 7.x | Form state management | Uncontrolled components → minimal re-renders; first-class shadcn/ui integration |
| `zod` | 3.x | Schema validation + type inference | One schema = both runtime validation and TypeScript types; pairs with `@hookform/resolvers` |
| `@hookform/resolvers` | 3.x | Bridge react-hook-form ↔ zod | Adapter package; required to connect the two |

**Confidence:** HIGH — react-hook-form + zod is the canonical choice across admin dashboard templates and tutorials as of 2026.

### Installation

```bash
# Create new service directory
npm create vite@latest admin-panel -- --template react-ts
cd admin-panel

# Tailwind v4 (new simplified setup)
npm install tailwindcss @tailwindcss/vite

# Routing + data fetching
npm install react-router-dom @tanstack/react-query

# Forms + validation
npm install react-hook-form zod @hookform/resolvers

# shadcn/ui (CLI-driven; installs components on demand)
npx shadcn@latest init
```

---

## Authentication Layer (New — Spans Bot + FastAPI)

Auth is needed in two places: the FastAPI backend (issues and validates JWTs, stores users in DB) and the admin panel (React client holds the token).

### Python / FastAPI Auth

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `PyJWT` | 2.13.x | JWT encode/decode | Current FastAPI-recommended library (python-jose has slowed maintenance); PyJWT 2.13.0 released May 2026; clean API, actively maintained |
| `pwdlib[argon2]` | latest | Password hashing | Passlib is incompatible with Python 3.13+ and unmaintained; FastAPI docs now recommend pwdlib; ships with Argon2id support — the OWASP-recommended algorithm |
| `python-multipart` | latest | Form body parsing for `/token` endpoint | Required for FastAPI's `OAuth2PasswordRequestForm` |

**Why not passlib:** Passlib's last release was 2023 and it breaks on Python 3.13+. The FastAPI docs PR #13917 replaced it with pwdlib. Use pwdlib from the start.

**Why Argon2id over bcrypt:** OWASP 2025 recommendation for new applications. pwdlib makes it trivial — `PasswordHelper(schemes=[Argon2()])`.

**Confidence:** HIGH (PyJWT version from PyPI search; pwdlib from FastAPI official docs PR).

### Node.js / TypeScript Auth (Admin API Calls)

The admin panel calls the FastAPI backend; it does not authenticate directly against the Express bot. No new auth libraries needed in `messenger-bot/`.

The Express bot gains one new behavior: it reads the `page_id` from each incoming webhook event and looks up the corresponding token from the DB. This is a DB query, not an auth flow — covered under Multi-Page Routing below.

### React Admin Panel Auth

No auth library on the React side. Store the JWT access token in memory (React state) on login. Do not put it in localStorage (XSS risk). Use `axios` interceptors (already in the bot, familiar pattern) or plain `fetch` with an `Authorization: Bearer <token>` header. TanStack Query handles the request lifecycle.

**Confidence:** HIGH — memory-only token storage is standard SPA auth practice.

```bash
# Python additions to requirements.txt
pip install pyjwt[crypto] pwdlib[argon2] python-multipart
```

---

## Database Layer (New — SQLite)

### Node.js Bot: better-sqlite3

The Express bot currently reads content from the FastAPI vault API. For v1.2 it will read directly from SQLite using a synchronous driver — the simpler and correct choice for a single-process Node.js service that does not need async DB access.

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `better-sqlite3` | 12.x | SQLite driver for Node.js | Synchronous API; fastest SQLite library for Node.js (7,500+ npm dependents); native bindings with prebuilt binaries for Node 18/20/22/26 |
| `@types/better-sqlite3` | latest | TypeScript types | Type definitions published separately on DefinitelyTyped |
| `drizzle-orm` | latest (v1 beta) | Schema definition + type-safe queries | TypeScript-native ORM; zero dependencies; thin abstraction over SQL; `drizzle-kit` CLI generates migrations; native `better-sqlite3` adapter |
| `drizzle-kit` | latest | Migration CLI | `drizzle-kit generate` + `drizzle-kit migrate` for schema management without running raw SQL |

**Why not Prisma:** Prisma requires a separate query engine binary, adds 20+ MB to the deployment, and its SQLite story has historically lagged behind PostgreSQL. Drizzle is lighter, faster, and has a first-class SQLite + better-sqlite3 adapter.

**Why synchronous better-sqlite3 over node:sqlite (Node 26 built-in):** better-sqlite3 has mature TypeScript types, widespread production use, and prebuilt binaries. Node's built-in `node:sqlite` is experimental as of Node 22/26 and lacks the battle-tested query ergonomics. Use better-sqlite3.

**Confidence:** HIGH — better-sqlite3 12.x verified on npm; drizzle-orm active as of April 2026.

```bash
# In messenger-bot/
npm install better-sqlite3 drizzle-orm
npm install -D @types/better-sqlite3 drizzle-kit
```

### Python / FastAPI: SQLAlchemy 2 + aiosqlite

FastAPI is async. Use async SQLAlchemy 2.0 with the aiosqlite driver. This is the FastAPI-canonical pattern for SQLite.

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `sqlalchemy[asyncio]` | 2.x | ORM + async engine | SQLAlchemy 2.0 has native async support via `create_async_engine`; Pydantic 2 integrates cleanly; the existing codebase already uses Pydantic models so the paradigm is familiar |
| `aiosqlite` | latest | Async SQLite driver | Required by SQLAlchemy's `sqlite+aiosqlite://` connection string |

**Why not raw sqlite3 module:** FastAPI's async event loop would block on synchronous sqlite3 calls without `run_in_executor` workarounds. aiosqlite solves this cleanly.

**Why not SQLModel:** SQLModel (FastAPI author's project) looks appealing but mixes ORM and Pydantic models in ways that create subtle circular-import and migration headaches. Use separate Pydantic response models and SQLAlchemy table models — the existing codebase already separates these concerns.

**Shared DB file:** Both the Node.js bot (`better-sqlite3`) and the Python FastAPI backend (`aiosqlite`) read the same `.db` file. The Node.js bot reads content/config (read-heavy, low concurrency). FastAPI handles all writes. SQLite's WAL mode handles concurrent reads from two processes safely.

**Confidence:** HIGH — SQLAlchemy 2 + aiosqlite is the FastAPI official example pattern (fastapi.tiangolo.com/tutorial).

```bash
# In Python app
pip install sqlalchemy[asyncio] aiosqlite
```

---

## Facebook OAuth — Page Connection Flow

No Passport.js or OAuth framework needed. The Facebook OAuth flow for Page tokens is a standard server-side code exchange — a handful of HTTP calls.

### Flow (Server-Side, No Library)

1. Admin panel redirects user to `https://www.facebook.com/v21.0/dialog/oauth?client_id=...&redirect_uri=...&scope=pages_manage_metadata,pages_messaging`
2. Facebook redirects back to FastAPI callback endpoint with `?code=...`
3. FastAPI backend exchanges the code for a short-lived user access token (GET to `graph.facebook.com/v21.0/oauth/access_token`)
4. FastAPI exchanges for a long-lived user token (GET to `graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token`)
5. FastAPI calls `GET /me/accounts` to list Pages the user admins, retrieving each Page's `access_token` and `page_id`
6. Store `(page_id, long_lived_page_access_token, page_name)` in SQLite

All these are plain `httpx` async HTTP calls — **no new library needed**. `httpx` is already in `requirements.txt`.

**Why not passport-facebook:** Passport.js is a Node.js library. The OAuth callback is handled by FastAPI (Python), where `httpx` is already available. Adding Passport to the Node.js bot would split the OAuth logic across two services for no benefit.

**Confidence:** HIGH — Facebook Graph API OAuth flow is stable; httpx already installed; Meta developer docs confirm the code-exchange pattern is current for v21.0.

---

## Multi-Page Bot Routing (Node.js)

No new library needed — this is a code change, not a dependency addition.

Each incoming Facebook webhook POST contains `body.entry[].id` which is the Page ID. The bot currently uses a single hardcoded `PAGE_ACCESS_TOKEN`. For multi-page support:

1. On startup, load a `Map<string, PageConfig>` from SQLite (via `better-sqlite3`) — `pageId → { accessToken, welcomeText, menuConfig, qaContent }`
2. On each webhook event, extract `entry.id` (or `messaging[].recipient.id`), look up the `PageConfig` in the Map
3. All Messenger API calls use the per-page `accessToken`
4. Refresh the Map cache on a configurable interval (or via a webhook from the admin panel on content save)

The `recipient.id` in the `messaging` array is the Page ID and is the correct field for routing — it identifies which Page the message was sent to.

**Confidence:** HIGH — this is the documented pattern for multi-page Messenger bots; Facebook's webhook payload structure has been stable since 2016.

---

## CORS Configuration Updates

Both services need CORS updates when the admin panel is added:

**FastAPI (`app/main.py`):** Change `allow_origins=["*"]` to a specific list including the admin panel origin (`http://localhost:5173` in dev, production URL in prod). This is a config change, not a dependency change.

**Express bot:** The Express bot's webhook endpoint is called only by Facebook (not by the admin panel). No CORS changes needed on the bot. If an admin panel needs to call the bot directly (e.g., test endpoint), add `cors` package — but this should be avoided by routing all admin actions through FastAPI.

**Confidence:** HIGH — `cors` package v2.8.5 already available; `allow_origins` in FastAPI is already parameterized.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Python password hashing | `pwdlib[argon2]` | `passlib[bcrypt]` | Passlib unmaintained, broken on Python 3.13+ |
| Python JWT | `PyJWT` | `python-jose` | python-jose maintenance has slowed; PyJWT 2.13.0 released May 2026 |
| Node.js DB | `better-sqlite3` + drizzle | `Prisma` | Prisma adds 20MB binary; overkill for SQLite |
| Node.js DB driver | `better-sqlite3` | `node:sqlite` (built-in) | node:sqlite is experimental in Node 26; no mature type definitions |
| Python DB | `sqlalchemy[asyncio]` + aiosqlite | `SQLModel` | SQLModel mixes concerns; migration story is less mature |
| React routing | `react-router-dom` v7 | TanStack Router | TanStack Router advantages (search-param types) not needed for this simple admin SPA |
| Facebook OAuth | Raw `httpx` calls | `passport-facebook` | passport-facebook is Node.js only; OAuth callback lives in FastAPI |
| Admin UI components | `shadcn/ui` | Material UI, Ant Design | shadcn/ui has no runtime dependency; full component ownership; Tailwind-native |
| Node.js JWT | Not needed (FastAPI issues tokens) | `jose` | Admin auth handled entirely in FastAPI; bot does not issue JWTs |

---

## Complete Stack Delta

What changes from the existing codebase:

### New Service: `admin-panel/`
```
React 19 + Vite 6 + TypeScript 5.4
Tailwind CSS 4 + shadcn/ui
react-router-dom 7
@tanstack/react-query 5
react-hook-form 7 + zod 3 + @hookform/resolvers 3
```

### Python `app/` additions
```
requirements.txt additions:
  pyjwt[crypto]       # JWT auth
  pwdlib[argon2]      # password hashing (replaces passlib)
  python-multipart    # OAuth2 form parsing
  sqlalchemy[asyncio] # async ORM
  aiosqlite           # SQLite async driver
  
requirements.txt removals:
  python-frontmatter  # replaced by DB-backed content
  anthropic           # no longer used (rule-based bot)
```

### Node.js `messenger-bot/` additions
```
package.json additions:
  better-sqlite3      ^12.x   # SQLite sync driver
  drizzle-orm         latest  # type-safe query builder
  
devDependencies additions:
  @types/better-sqlite3  latest
  drizzle-kit            latest  # migration CLI
```

### No changes to
- `express` version (4.x stays)
- `axios` (already used for Graph API calls)
- `typescript` (5.4 stays)
- Facebook webhook handling structure

---

## Sources

- better-sqlite3 npm: https://www.npmjs.com/package/better-sqlite3 (v12.10.0 confirmed)
- drizzle-orm documentation: https://orm.drizzle.team/docs/quick-sqlite/better-sqlite3
- PyJWT PyPI: https://pypi.org/project/PyJWT/ (v2.13.0, released May 2026)
- pwdlib: https://github.com/frankie567/pwdlib (FastAPI official docs PR #13917)
- Vite current releases: https://vite.dev/releases (v6.x current stable)
- TanStack Query v5: https://tanstack.com/query/latest (TypeScript 5.4+ required)
- react-hook-form + zod: https://github.com/react-hook-form/resolvers
- shadcn/ui admin dashboard pattern: https://marmelab.com/blog/2025/04/23/react-admin-with-shadcn.html
- Facebook OAuth manual flow: https://developers.facebook.com/docs/facebook-login/guides/advanced/manual-flow/
- Facebook Page access tokens: https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived/
- SQLAlchemy async + aiosqlite: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
- argon2 npm: https://www.npmjs.com/package/argon2 (v0.44.0; alternative to pwdlib for Node)
- Tailwind CSS v4 + Vite setup: https://dev.to/geane_ramos/how-to-setup-your-vite-project-with-react-typescript-and-tailwindcss-v4-2bkm
