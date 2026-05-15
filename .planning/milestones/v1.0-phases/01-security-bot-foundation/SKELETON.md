# Walking Skeleton — Govi Facebook Messenger Customer Support Bot

**Phase:** 1
**Generated:** 2026-05-14

## Capability Proven End-to-End

A new Facebook Messenger user who clicks "Get Started" on the Govi Page receives a welcome message with quick-reply navigation, can open the persistent hamburger menu at any time, and will never hit a silent dead end — while every inbound webhook event is HMAC-verified before processing.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Messenger bot runtime | Node.js 26 + TypeScript 5.4 (existing) | Two-service split mandated by CLAUDE.md and PROJECT.md; do not change |
| Backend runtime | Python 3.x + FastAPI (existing, untouched in Phase 1) | Phase 2+ uses this for vault content; Phase 1 leaves it as-is |
| Web framework (bot) | Express 4.22 (installed) | Already in place; `express.raw()` covers HMAC body-capture need |
| HTTP client | axios 1.16 (installed) | Already used for Govi AI call; reused for all Graph API calls |
| Cryptography | Node.js built-in `crypto` (HMAC-SHA256, `timingSafeEqual`) | No new dependency; satisfies V6 (Cryptography) ASVS controls |
| Config loading | `dotenv` from `messenger-bot/.env` (existing pattern) | New `FACEBOOK_APP_SECRET` follows same module-level constant style |
| Test runner | Node.js built-in `node:test` + `ts-node` loader | Zero new npm dependencies; runs `.ts` test files directly |
| Graph API version | v21.0 | Bumped from existing v19.0 per RESEARCH.md (conservative vs latest v25.0) |
| Directory layout | Single-file bot entry (`messenger-bot/src/index.ts`) + sibling `src/tests/` | Matches existing single-file pattern; tests live next to source |
| Deployment | Local dev via `npm run dev` (ts-node-dev); manual deploy pattern unchanged | PROJECT.md constraint: no containerization in v1 |

## Stack Touched in Phase 1

- [x] Project scaffold — `node:test` runner wired into `messenger-bot/package.json`; tests directory created
- [x] Routing — `POST /webhook` (now HMAC-verified) and `GET /webhook` (verify-token handshake) both serve
- [x] External integration touchpoint — `POST /me/messenger_profile` configures `get_started` + `persistent_menu` once at startup
- [x] UI / interaction — Messenger `quick_replies` rendered on welcome + fallback messages; persistent menu reachable from hamburger
- [x] Deployment / local run — `npm run dev` in `messenger-bot/` starts the bot end-to-end; `node --test src/tests/` runs full unit suite in ~5s

## Out of Scope (Deferred to Later Slices)

- Quick-reply payload routing beyond the GET_STARTED postback — `MENU_PRODUCT_HELP`, `MENU_CONTACT_HUMAN`, `MENU_MAIN` payloads are configured in the persistent menu but their handlers are stubbed (`continue;` after acknowledgement). Real navigation arrives in Phase 3.
- Obsidian vault content service — Phase 2.
- Product Q&A category/question navigation — Phase 3.
- Human escalation via Handover Protocol + admin PSID notification — Phase 4.
- Typing indicator (`typing_on` Sender Action) — Phase 5.
- AI-passthrough `/ai/chat` Python endpoint — left intact for now; superseded by vault calls in Phase 3.
- Conversation state / session memory — explicitly out of scope per REQUIREMENTS.md "Out of Scope" section.
- New npm dependencies — none in Phase 1 (RESEARCH.md confirms zero new packages needed).

## Subsequent Slice Plan

Each later phase adds one vertical slice on top of this skeleton without altering its architectural decisions:

- **Phase 2:** Vault Service — FastAPI loads Obsidian vault from `VAULT_PATH`, serves content by frontmatter ID via `GET /content/{id}` and `POST /content/reload`. Independently testable with `curl` before the bot touches it.
- **Phase 3:** Product Q&A Flow — Bot's quick-reply payload dispatcher (stubbed in Phase 1) now routes to vault categories/questions; answers fetched from FastAPI and sent as Messenger messages.
- **Phase 4:** Human Escalation — "Contact Human" payload triggers Handover Protocol + admin Messenger notification with the customer's last message.
- **Phase 5:** Polish + Hardening — Typing indicator during vault fetch; final env var documentation pass; clean-clone smoke test.
