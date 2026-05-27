# Research Summary — v1.2 Admin Panel & Multi-Page Support

**Project:** Govi Facebook Messenger Customer Support Bot
**Researched:** 2026-05-27
**Confidence:** HIGH

---

## Executive Summary

This milestone extends the existing single-page Messenger bot into a multi-tenant platform. A new React admin panel lets clients connect their Facebook Pages via OAuth and edit all bot content (welcome text, menus, Q&A, escalation settings) without code changes. A SQLite database replaces the Obsidian vault. The bot becomes page-aware, reading token + config per Page ID from FastAPI instead of using a hardcoded env var.

The recommended approach is a third process (`admin-panel/`) alongside the two existing services — no containerization. The stack additions are conservative and verified. The most invasive code change is threading a per-page `pageAccessToken` parameter through ~15 helper functions in `index.ts`. The dominant external risk is Facebook App Review for `pages_messaging` — submit during Phase 12 and treat it as a launch blocker on a clock you don't control.

---

## Stack Additions

| Layer | Addition | Version | Why |
|-------|----------|---------|-----|
| Admin panel | React + Vite + TypeScript | React 19, Vite 6, TS 5.4 | Existing TS competency; Vite react-ts template scaffolds instantly |
| Admin panel | Tailwind CSS v4 + shadcn/ui | v4 | No PostCSS config; shadcn copy-paste components with zero runtime lock-in |
| Admin panel | react-router-dom | v7 | Simple routing for a few routes |
| Admin panel | TanStack Query | v5 | Eliminates manual loading/error state; TypeScript-first |
| Admin panel | react-hook-form + zod | v7 / v3 | Canonical form + validation with shadcn/ui integration |
| FastAPI | PyJWT + pwdlib[argon2] | 2.13 / latest | passlib is unmaintained on Python 3.13+; pwdlib is now FastAPI official |
| FastAPI | SQLAlchemy 2 async + aiosqlite | 2.x | Canonical FastAPI async SQLite pattern |
| FastAPI | python-cryptography (Fernet) | latest | Fernet-encrypt Page Access Tokens at rest |
| FastAPI | python-multipart | latest | Required for FastAPI form data (auth) |
| Node.js bot | better-sqlite3 + Drizzle ORM | 12.10 / latest | Synchronous driver correct for single-process Node; lighter than Prisma |

**Remove:** `anthropic` (unused after vault → DB), `python-frontmatter` (Obsidian vault retired)

---

## Expected Features

### Must Have (table stakes)
- Super-admin creates and manages client accounts — no direct DB manipulation needed
- Client login with JWT session (email + password, tenant-scoped)
- Facebook Page OAuth connection (full 3-step exchange + webhook subscription)
- Connected Pages dashboard per client
- Per-page welcome text editor
- Per-page menu label & structure editor
- Per-page Q&A category + answer editor (replaces Obsidian vault)
- Per-page escalation settings editor (admin PSID, handoff message)
- DB-backed bot config (architectural prerequisite for all editing)
- Multi-page webhook routing in bot

### Should Have (differentiators)
- Token health monitoring: status badge + "Reconnect" if revoked
- Content change preview: static rendering of menu tree and answer text
- Audit log: who changed what per Page

### Defer to v1.3
- Bulk CSV import, analytics dashboard, automated token health check background job

### Anti-Features (do not build in v1.2)
- Self-service client registration / invitation emails
- Multi-level roles, white-labeling
- Drag-and-drop flow builder (high cost; Messenger limits make it pointless)
- Conversation inbox, broadcast messaging, rich text in answers

---

## Architecture Approach

**Three services, one DB:**
- `messenger-bot/` (Node.js) — webhook handler; reads page context from FastAPI internal endpoint
- `app/` (FastAPI) — content API + admin API + OAuth callback; owns all DB writes
- `admin-panel/` (React SPA) — communicates with FastAPI only

**SQLite schema (four tables):**
```
tenants      (id, email, password_hash, role, created_at)
pages        (id, tenant_id FK, facebook_page_id, encrypted_access_token, app_subscribed, created_at)
page_configs (id, page_id FK 1:1, welcome_text, escalation_psid, handoff_message, menu_json)
qa_items     (id, page_id FK, parent_id FK self-ref, type[category|question|answer], label, payload, content, sort_order)
```

**Bot page-awareness:** New `pageContext.ts` module — `getPageContext(facebookPageId)` fetches from FastAPI `/internal/pages/{id}/context` with shared-secret header, caches 5 min in `Map<pageId, PageContext>`. All Graph API helpers gain `pageAccessToken: string` parameter. `PAGE_ACCESS_TOKEN` global removed.

**Content HTTP contract preserved:** `app/routers/content.py` keeps the same URL shape + response shape when switching from vault to DB — bot only gains a `page_id` query parameter.

---

## Critical Pitfalls

| # | Pitfall | Prevention |
|---|---------|-----------|
| 1 | **Short-lived user token stored** (expires in ~1 hr) | Complete all 3 OAuth steps; verify `expires_at: 0` before persisting |
| 2 | **Webhook subscription missing after OAuth** (bot gets zero events) | `POST /{page-id}/subscribed_apps` must be atomic with token storage |
| 3 | **Missing `tenant_id` filter → cross-tenant data leak** | Every DB query filters by `tenant_id` from JWT only; IDOR test per endpoint |
| 4 | **Page Access Token unencrypted at rest** | Fernet-encrypt before write; never return in any API response |
| 5 | **`PAGE_ACCESS_TOKEN` global not fully removed** | One surgical commit removes all ~15 call sites; verified by grep |
| 6 | **`setupMessengerProfile()` at startup overwrites per-page menu** | Remove from startup; call on-demand (OAuth connect + menu save) |
| 7 | **SQLite `SQLITE_BUSY` under concurrent load** | WAL mode + 5s busy_timeout at DB initialization |
| 8 | **Vault migration breaks in-flight content** | Expand-then-contract: parallel endpoints during cutover; seed script preserves IDs |
| 9 | **Facebook App Review blocks real client launch** | Submit during Phase 12; add test users as Developer/Tester roles in FB App |

---

## Recommended Phase Order

| Phase | Name | Rationale |
|-------|------|-----------|
| 10 | DB Foundation | Schema must exist before anything else; no service changes |
| 11 | Auth (FastAPI) | Tenant login gates all admin operations |
| 12 | Tenant & Page API + Facebook OAuth | OAuth + webhook subscription atomic; submit App Review here |
| 13 | Page Config, Q&A API + Content Migration | DB-backed content before bot refactor; preserve HTTP contract |
| 14 | Bot Multi-Page Routing | Refactor after content API proven; most invasive change |
| 15 | Admin Panel UI | Built last against stable APIs |

---

## Open Questions

- **Graph API version:** Two research files reference different versions (v21.0 vs v25.0). Confirm current stable at Phase 12 planning time.
- **Admin panel hosting:** Serve static build from FastAPI `StaticFiles` (simpler, one URL, no CORS) or standalone process (cleaner separation)? Resolve before Phase 15.
- **Unused AI router:** `app/routers/ai.py` appears unused after v1.0 rule-based rewrite. Remove in Phase 10 to reduce attack surface?

---

*Ready for roadmap: yes*
