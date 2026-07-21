# Phase 13: Page Config, Q&A API + Content Migration - Context

**Gathered:** 2026-07-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Move all bot content — welcome/greeting text, persistent menu, Q&A tree, and escalation settings — out of the Obsidian vault and into the existing SQLite database (`page_configs` + `qa_items`, already created in Phase 10), served **per Page ID**. This phase delivers three things:

1. **DB-backed read API** — replaces the vault-backed `app/routers/content.py`. Preserves the existing `/content` HTTP response shapes and `?type=` / `?category=` query semantics, adds a **required `page_id` query param** (locked by Phase 14 D-03), and is protected by the `X-Internal-Key` HMAC pattern (D-01). The Obsidian vault is retired.
2. **Write API** — the content-editor endpoints Phase 15's admin UI will call: consolidated config PUT + REST Q&A CRUD, JWT-authenticated and tenant-ownership scoped (D-02).
3. **One-time seed script** — migrates existing vault Q&A into the DB for a target Page (DB-02, D-03).

**In scope:** `CONTENT-01` (welcome text), `CONTENT-02` (persistent menu labels/structure), `CONTENT-03` (Q&A categories + answers CRUD), `CONTENT-04` (escalation PSID + handoff message), `DB-02` (vault→DB seed). Read endpoints DB-backed + page-scoped + HMAC-protected. Retire vault (`load_vault`/`_vault`/`/content/reload`).

**Out of scope:** Bot-side consumption of these endpoints (Phase 14 — `BOT-01/02/03`). FastAPI-side persistent-menu installation to the Graph API (deferred — see Phase 14 CONTEXT `<deferred>`). Admin panel UI (Phase 15). Schema changes — the Phase 10 schema already models everything needed.

</domain>

<decisions>
## Implementation Decisions

### Read endpoint auth + page-scoping
- **D-01:** The DB-backed read endpoints (`GET /content`, `GET /content/{content_id}`) are protected by the **`X-Internal-Key` HMAC** pattern — the exact mechanism used by the Phase 12 internal token endpoint (`app/routers/pages.py:245`, `hmac.compare_digest` on the header vs `settings.internal_secret`). Rationale: consistency with the existing internal-endpoint pattern, and it blocks arbitrary internet reads of any Page's content by enumerating `page_id`. The bot already carries `INTERNAL_SECRET` for the token endpoint (Phase 14 D-01), so no new secret is introduced.
- **Contract preserved:** Response models stay `ContentListResponse` (`{items: [{id, type, title}]}`) and `ContentResponse` (`{id, type, title, body}`). Query semantics stay `?type=category` / `?type=question&category=<id>`. Add **required** `page_id` query param on all read endpoints (Phase 14 will pass the Page's FB id).

### Write API shape
- **D-02:** Two endpoint groups, both `Depends(get_current_tenant)` (JWT) and tenant-ownership scoped (`WHERE ... tenant_id = ?`, the Phase 11 pattern):
  - **Config:** a single `PUT /pages/{page_id}/config` that replaces the whole `page_configs` row (welcome_text + menu_json + escalation_psid + escalation_message together). Chosen because `page_configs` is a 1:1 row per page — one atomic write matches the data shape and keeps the UI simple.
  - **Q&A:** REST CRUD over `qa_items` — list + `POST` / `PUT` / `DELETE` under `/pages/{page_id}/qa[/{item_id}]`.
  - `page_id` in these write paths is the **internal integer `pages.id`** (tenant-scoped resource), distinct from the read endpoints' `page_id` = Facebook `page_fb_id`. Planner: keep this distinction explicit.

### Seed / migration script (DB-02)
- **D-03:** One-time script that:
  - Takes the target Page via CLI **`--page-fb-id`**, resolves it to the internal `pages.id`.
  - Is **idempotent via wipe+reload**: deletes that page's existing `qa_items`, then re-inserts from the vault. Safe to re-run.
  - Migrates **Q&A only** (categories + questions — all the vault contains).
  - **Ensures a `page_configs` row exists** for the page with schema defaults (empty `welcome_text`, `'[]'` `menu_json`, null escalation) so the read API and bot never hit a missing config row. The client fills welcome/menu/escalation later via the Phase 15 editor.
  - May reuse the existing frontmatter-parsing logic from `content.py` `load_vault()` before that function is deleted.

### Menu JSON schema (CONTENT-02)
- **D-04:** `page_configs.menu_json` stores a **flat JSON array of postback items**: `[{"title": "Product Help", "payload": "MENU_PRODUCT_HELP"}, ...]`. Mirrors the bot's current `MAIN_MENU_QUICK_REPLIES` shape exactly and maps 1:1 onto Facebook persistent-menu `postback`-type `call_to_actions`. **No submenus / nesting** (matches current bot behavior; smallest contract to validate).

### Claude's Discretion
- **ID scheme:** DB integer `qa_items.id` returned to the bot as a string. Verified the bot treats content ids **opaquely** (`messenger-bot/src/index.ts` does `payload.slice(...)` then `encodeURIComponent(categoryId)` and passes ids straight back to `/content/{id}`), so stringified integer ids round-trip fine. The old vault frontmatter string ids are **not** preserved — nothing external depends on them.
- **`category_id` referential integrity** for questions is enforced at the application layer (per the schema comment at `app/db.py:53`) — planner decides where.
- Exact validation rules and error-response bodies for write endpoints; whether `menu_json` validation rejects unknown keys.
- Whether to delete the `POST /content/reload` endpoint entirely (recommended — vault retired) vs. repurpose it.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope + requirements
- `.planning/ROADMAP.md` §"Phase 13: Page Config, Q&A API + Content Migration" — goal, success criteria (5 criteria)
- `.planning/REQUIREMENTS.md` — `CONTENT-01`, `CONTENT-02`, `CONTENT-03`, `CONTENT-04`, `DB-02` definitions

### Contract to preserve / replace
- `app/routers/content.py` — **existing vault-backed content router.** Response shapes (`ContentListResponse`, `ContentResponse`) and query semantics (`?type=`, `?category=`) MUST be preserved. `load_vault()` frontmatter logic is reusable by the seed script; `_vault` global and `/content/reload` are retired.
- `messenger-bot/src/index.ts` — the bot consumer (Phase 14 rewires it). Confirms ids are treated opaquely and shows the exact URLs the read API must answer.

### Schema + patterns to reuse
- `app/db.py:37-62` — `page_configs` (welcome_text, menu_json, escalation_psid, escalation_message) and `qa_items` (type CHECK('category'|'question'), title, body, category_id self-ref, enabled) tables. **No schema changes this phase.**
- `app/routers/pages.py:245` — `X-Internal-Key` HMAC verification pattern to mirror on read endpoints (D-01).
- `app/routers/pages.py` (`list_pages`/`disconnect_page`) — `get_current_tenant` JWT dep + `WHERE tenant_id = ?` ownership scoping pattern to mirror on write endpoints (D-02).
- `app/auth.py` `get_current_tenant` — JWT dependency returning `{"sub": tenant_id, ...}`.
- `app/config.py` — `internal_secret` (HMAC key) and `vault_path` (seed source) settings.

### Downstream consumers (this phase defines their contract)
- `.planning/phases/14-bot-multi-page-routing/14-CONTEXT.md` §D-03 — the bot expects `page_id` as a **required query param** on all content endpoints. This phase MUST satisfy that.

### Codebase maps
- `.planning/codebase/ARCHITECTURE.md` — two-service split, stateless request path
- `.planning/codebase/CONVENTIONS.md` — Python style, error-handling (`HTTPException`), SQL `?`-placeholder rule (`app/db.py:4`)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/routers/content.py` `load_vault()` — frontmatter parsing + validation the seed script can lift before this function is deleted.
- `app/db.py` `get_connection(db_path)` — the standard DB access helper (Row factory, foreign_keys=ON, busy_timeout). All new queries use `?` placeholders (never f-strings — `app/db.py:4`).
- `app/routers/pages.py:245` — copy-paste-level template for the `X-Internal-Key` HMAC guard.
- `app/routers/pages.py` write handlers — copy-paste-level template for JWT + ownership-scoped writes.

### Established Patterns
- **Internal-key HMAC** for bot→FastAPI calls (Phase 12) → applies to read endpoints.
- **JWT `get_current_tenant` + `WHERE tenant_id = ?`** for tenant-owned resources (Phase 11) → applies to write endpoints.
- **`HTTPException(status_code=..., detail=...)`** for all API errors (no try/except in routers — Anthropic-SDK-style propagation does not apply here; DB errors should surface as explicit HTTPExceptions).
- **Pydantic response models** defined inline in the router file (`ChatRequest`/`PageResponse` style).

### Integration Points
- **Read endpoints** ← consumed by the bot in Phase 14: `GET /content?type=category&page_id=<page_fb_id>`, `GET /content?type=question&category=<id>&page_id=<page_fb_id>`, `GET /content/{id}?page_id=<page_fb_id>`, all with `X-Internal-Key`.
- **Write endpoints** ← consumed by Phase 15 admin UI (JWT bearer).
- **Seed script** ← reads the vault via `settings.vault_path`, writes `qa_items` + ensures `page_configs` row for the `--page-fb-id` target.
- **`page_id` overloading:** read endpoints use `page_id` = Facebook `page_fb_id` (bot's identifier); write endpoints use the internal integer `pages.id`. Keep these clearly separated in code + tests.

</code_context>

<specifics>
## Specific Ideas

- Read-API response shapes are load-bearing for the bot — **do not change field names or nesting** (`{items:[{id,type,title}]}` and `{id,type,title,body}`).
- `menu_json` is deliberately the same shape as the bot's existing `MAIN_MENU_QUICK_REPLIES` (`{title, payload}`) so Phase 14 can adopt it with minimal translation.
- Seed idempotency is wipe-and-reload per page — explicitly re-runnable, no fuzzy matching.

</specifics>

<deferred>
## Deferred Ideas

- **FastAPI-side persistent-menu installation** to the Graph API on OAuth completion — already captured in Phase 14 CONTEXT `<deferred>`. Phase 13 only stores/serves `menu_json`; it does not install the menu to Messenger.
- **Nested / multi-level persistent menu** — rejected in favor of flat `[{title,payload}]` (D-04). Revisit if a submenu structure is ever needed.
- **Bulk CSV import of Q&A**, **content-change preview**, **audit log (who changed what per page)** — all already deferred to v1.3 in `REQUIREMENTS.md`.

### Reviewed Todos (not folded)
None — no pending todos matched this phase.

</deferred>

---

*Phase: 13-page-config-q-a-api-content-migration*
*Context gathered: 2026-07-21*
