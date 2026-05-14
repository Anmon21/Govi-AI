# Research Summary

**Project:** Govi Facebook Messenger Customer Support Bot
**Domain:** Rule-based Messenger chatbot with Obsidian vault content layer
**Researched:** 2026-05-14
**Confidence:** HIGH

## Recommended Stack

Keep the existing two-service split exactly as-is. No migrations, no new services.

| Component | What to use | Why |
|-----------|-------------|-----|
| Messenger bot | Node.js / Express / TypeScript (existing) | No changes to core; replace AI-passthrough with menu engine |
| Content API | Python / FastAPI (existing) | Replace `/ai` router with `/content` router; add vault service |
| Graph API calls | axios (already installed), raw HTTP | No Messenger SDK exists with active maintenance |
| Vault parsing | `python-frontmatter ^1.1.0` (add to requirements.txt) | Handles YAML frontmatter + body split correctly; only new dependency |
| Session state | In-memory `Map<senderId, SessionState>` with 30-min TTL | No Redis — single process, session loss on restart is acceptable |
| Menu engine | Hand-rolled TypeScript state map | XState is wrong-scale for 2-3 menu levels |

**Do not add:** NLP frameworks, XState, Redis, obsidiantools, wikitextparser, or any npm Messenger SDK (all abandoned). The Anthropic SDK and `/ai` router are retired entirely.

**Version note:** Bump Graph API from v19.0 to v21.0 (one-line change in `sendMessage`). Verify `python-frontmatter` version on PyPI before pinning — version from training knowledge.

## Table Stakes Features

Build in this order (each step depends on the one above):

1. **Get Started postback + welcome message** — silence on first message reads as "bot is broken"
2. **Persistent menu** (hamburger, 3 top-level items max) — recovery path when users get lost
3. **Quick reply buttons for all navigation** — users will not type; without buttons the bot is unusable
4. **Fallback handler for free text** — re-anchor to menu with helpful message; never silent
5. **Product Q&A flow** (menu → category → question → vault answer) — the core value proposition
6. **Human escalation with Handover Protocol** — required exit path; without it users leave

**Hard Messenger platform limits to design around:**
- 13 quick replies max per message, 20-character title limit (enforced in menu engine)
- 3 top-level persistent menu items max
- 640 characters recommended for message text; 2000 hard limit
- Handover Protocol setup required for bot-to-human thread transfer

**Defer to v2+:** NLP intent detection, analytics dashboard, multi-language support, rich media carousels, conversation history persistence, order tracking.

**Good-to-have in v1 (low effort, high value):** Typing indicator, "Was this helpful?" quick reply after answers, escalation context forwarding to admin, `POST /content/reload` for vault refresh without restart.

## Architecture in a Nutshell

**Who owns what:**
- Node.js bot owns all Facebook interaction: webhook, session state, menu navigation, Graph API calls.
- FastAPI owns all content: reads Obsidian vault at startup, caches it in memory, serves it via clean HTTP endpoints.
- Neither service knows the other's internals. Bot asks FastAPI for content by ID; FastAPI never calls Facebook.

**Build order (strict dependency chain):**
1. FastAPI vault service + `/content` router — independently testable with curl before touching the bot
2. Bot session store (`src/session.ts`) — unit-testable in isolation
3. Bot menu engine (`src/menu.ts`) — returns typed Reply objects, no direct Graph API calls
4. Bot Graph API helpers (`src/messenger.ts`) — thin wrappers over axios
5. Wire everything in `src/index.ts` (replace AI-passthrough)
6. Human escalation flow (last — requires real Facebook Page setup for admin PSID)

**Vault file format (must be defined before Phase 3):**
```
---
id: products-sizing        # stable key the bot uses — never change after publishing
type: menu | answer
title: "Sizing Questions"
enabled: true              # discovery mechanism; bot ignores files without this
---
Body text here (for answers) or list of items (for menus).
```

Use frontmatter-based discovery (`enabled: true`), not filename-based, so vault renames don't break the bot. Cache content at startup; expose `POST /content/reload` to refresh without restart.

## Watch Out For

**1. No webhook signature verification (fix first, before anything else)**
The existing handler processes any POST to `/webhook` without verifying `X-Hub-Signature-256`. Anyone who discovers the URL can forge events. Fix: `HMAC-SHA256(rawBody, FACEBOOK_APP_SECRET)` before processing. Requires `express.raw()` before `express.json()` — middleware order matters.

**2. Graph API errors silently swallowed inside HTTP 200**
Facebook returns `{ "error": {...} }` inside a 200 response when sends fail. The current axios call only catches HTTP status errors, not body errors. Fix: check `response.data.error` after every Graph API call. Also: log only `err.message` and `err.response?.data`, never the full axios error (PAGE_ACCESS_TOKEN is in the request URL).

**3. Vault parser silent failures**
Obsidian files contain `[[wikilinks]]`, may have UTF-8 BOM bytes, and the vault root has `.obsidian/` and `.trash/` system directories. A naive parser produces silent wrong output. Fix: open files with `utf-8-sig` encoding, regex-strip wikilinks before parsing, exclude system directories by path, use `enabled: true` frontmatter for file discovery. Log clearly on per-file parse failure — never silently skip.

**4. Postback payload bloat corrupts navigation state**
1000-character payload limit. Encoding navigation path in payloads (`MENU_L1_PRODUCTS_L2_SIZING`) hits this limit and makes stale button presses from old messages corrupt session state. Fix: use flat opaque IDs (`MENU_PRODUCTS`, `QA_SIZING`), resolve server-side. Session holds where user is; payload says what they just did.

**5. Admin PSID is a setup blocker for escalation**
Sending a Messenger notification to the admin requires their Page-Scoped ID (PSID), which only exists after the admin has messaged the Page at least once from their personal account. Fix: document this as a required setup step. Escalation should gracefully degrade to console log if `ADMIN_PSID` is not set — it must not crash the bot.

## Open Questions

| Question | Impact | When to decide |
|----------|--------|----------------|
| Vault markdown format convention | Blocks Phase 3 — parser and vault files must use the same schema | Before Phase 3 planning; needs agreement with content author |
| Hosting platform (Railway / Render / Fly.io / self-host) | Determines TLS setup, process management approach, env var management in Phase 6 | Before Phase 6 planning |
| Handover Protocol current configuration steps | May have changed in Facebook developer console UI since research cutoff | Verify before Phase 5 implementation |
| Keep or remove Anthropic SDK | `anthropic ^0.30.0` is in requirements.txt; if AI is fully removed, delete it to reduce attack surface | Decide at project start |
| `python-frontmatter` current version | Training knowledge (cutoff Aug 2025) — version `^1.1.0` needs PyPI verification before pinning | Before Phase 3 starts |
