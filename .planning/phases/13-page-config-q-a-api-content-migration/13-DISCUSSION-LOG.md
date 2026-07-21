# Phase 13: Page Config, Q&A API + Content Migration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-21
**Phase:** 13-page-config-q-a-api-content-migration
**Areas discussed:** Read-endpoint auth, Write API shape, Seed script behavior, Menu JSON schema

---

## Read-endpoint auth

| Option | Description | Selected |
|--------|-------------|----------|
| X-Internal-Key HMAC | Reuse Phase 12 pattern (pages.py:245): bot sends X-Internal-Key, FastAPI verifies via hmac.compare_digest. Consistent; blocks internet reads of any page's content by page_id enumeration. | ✓ |
| Public + page_id only | Keep /content open, just add required page_id. Simplest, but anyone could enumerate page_id and read any tenant's content. | |
| You decide | — | |

**User's choice:** X-Internal-Key HMAC.
**Notes:** Bot already carries INTERNAL_SECRET for the Phase 12 token endpoint, so no new secret is introduced.

---

## Write API shape

| Option | Description | Selected |
|--------|-------------|----------|
| Config PUT + Q&A CRUD | One PUT /pages/{id}/config replaces the whole page_configs row; Q&A gets REST CRUD. Matches 1:1 config row + 1:many qa rows. | ✓ |
| Granular per-field endpoints | Separate PUT per field (welcome/menu/escalation) + Q&A CRUD. Finer saves but larger surface. | |
| You decide | — | |

**User's choice:** Config PUT + Q&A CRUD.
**Notes:** All write endpoints JWT-auth (get_current_tenant) + tenant-ownership scoped.

---

## Seed script behavior — targeting + idempotency

| Option | Description | Selected |
|--------|-------------|----------|
| CLI --page-fb-id, wipe+reload | Operator passes target Page FB ID; script wipes that page's qa_items then re-inserts. Fully idempotent. | ✓ |
| CLI arg, skip-existing | Same targeting, skip items that already exist by match. Avoids clobbering edits but risks stale/dupe rows. | |
| You decide | — | |

**User's choice:** CLI --page-fb-id, wipe+reload.

## Seed script behavior — config seeding

| Option | Description | Selected |
|--------|-------------|----------|
| Q&A only; ensure empty config row | Migrate only Q&A; ensure a page_configs row exists with schema defaults. Client fills config via Phase 15 editor. | ✓ |
| Also seed config from env/bot defaults | Additionally backfill welcome/menu/escalation from bot's current hardcoded values. | |
| You decide | — | |

**User's choice:** Q&A only; ensure empty config row.

---

## Menu JSON schema

| Option | Description | Selected |
|--------|-------------|----------|
| Flat [{title,payload}] | Array of postback items mirroring the bot's MAIN_MENU_QUICK_REPLIES; maps 1:1 to FB persistent-menu postback call_to_actions. No submenus. | ✓ |
| FB-native nested call_to_actions | Facebook's own format with optional nesting (postback/web_url, 3-level submenus). Future-proof but more to validate. | |
| You decide | — | |

**User's choice:** Flat [{title,payload}].

---

## Claude's Discretion

- ID scheme — DB integer ids returned as strings (bot treats ids opaquely; verified). Old vault frontmatter string ids not preserved.
- `category_id` referential integrity for questions — enforced at application layer per schema comment.
- Exact validation rules / error-response bodies for write endpoints; whether menu_json validation rejects unknown keys.
- Whether to delete POST /content/reload entirely (recommended — vault retired).

## Deferred Ideas

- FastAPI-side persistent-menu installation on OAuth (already deferred in Phase 14 CONTEXT).
- Nested / multi-level persistent menu (rejected in favor of flat schema).
- Bulk CSV import, content-change preview, audit log — already deferred to v1.3 in REQUIREMENTS.md.
