# Govi Facebook Messenger Customer Support Bot

## What This Is

A rule-based Facebook Messenger chatbot for Govi (e-commerce/retail) that guides customers through structured menus to answer product questions and escalate to a human agent. Content is managed via an Obsidian vault — no code changes needed to update Q&A answers.

**Shipped v1.0 (2026-05-15):** Bot is feature-complete and ready to deploy. Automated test coverage: 22 Node.js + 14 Python tests, all green.

## Core Value

Customers can get instant product answers and reach a human through Messenger — 24/7, without developer involvement in content updates.

## Current State

**Version:** v1.0 (shipped 2026-05-15)
**Status:** All 5 phases complete. Awaiting production deployment and live Messenger UAT.

**Codebase:**
- `messenger-bot/src/index.ts` — Node.js/TypeScript bot (~350 LOC): webhook handler, menu routing, Q&A flow, escalation, typing indicator
- `app/routers/content.py` — FastAPI vault router (~120 LOC): content listing, single-item fetch, reload endpoint
- 22 Node.js tests + 14 Python tests, all passing

**Pending before launch:**
- Production deployment (ngrok/hosting + Facebook App configuration)
- Live Messenger UAT: 5 Phase 1 scenarios + 1 Phase 4 + 1 Phase 5 (typing indicator)

## Requirements

### Validated (v1.0)

- ✓ Facebook Messenger webhook integration with HMAC-SHA256 verification — v1.0, Phase 1
- ✓ Rule-based menu system replacing AI passthrough — v1.0, Phase 1
- ✓ Get Started welcome + persistent menu + free-text fallback (CORE-01–04) — v1.0, Phase 1
- ✓ Token-safe error logging, Graph API error detection (SEC-01–03) — v1.0, Phase 1
- ✓ Obsidian vault integration — FastAPI reads/caches/reloads Q&A content (VAULT-01–03) — v1.0, Phase 2
- ✓ Product Q&A flow — category → question → answer via quick replies (QA-01–03) — v1.0, Phase 3
- ✓ Vault content reload without server restart (QA-04) — v1.0, Phase 2
- ✓ Human escalation — Handover Protocol + admin Messenger notify + graceful fallback (ESC-01–04) — v1.0, Phase 4
- ✓ Typing indicator before answers + full .env.example documentation (POLISH-01) — v1.0, Phase 5

### Active

- [ ] Live Messenger UAT — 7 human-only scenarios pending production deployment

### Out of Scope (v1)

- Order tracking / order status — no store backend connected
- AI-powered free-text responses — using rule-based menus only
- Shopify / WooCommerce integration — standalone system
- Custom admin web UI — Obsidian vault is the content management interface
- Multi-language support — English only for v1
- Answer length truncation + "Read more" link — deferred to v2
- "Was this helpful?" quick reply — deferred to v2
- Returning user memory / greet by name — deferred to v2

## Context

Started from an existing Node.js/Express Messenger bot that forwarded all messages to a FastAPI backend calling Claude. v1.0 replaced the AI passthrough with structured rule-based menus, added an Obsidian vault content layer, and implemented human escalation via Facebook Handover Protocol.

**Architecture:** Two-service split maintained — Node.js bot handles Messenger interaction, FastAPI handles content serving. No containerization; both services run as processes.

## Constraints

- **Tech stack**: Node.js/TypeScript for the Messenger bot, Python/FastAPI for the backend — maintain existing split
- **Platform**: Facebook Messenger only — no other channels in v1
- **Deployment**: No containerization currently — same manual deploy pattern
- **Scope**: Standalone system — no integration with order management or inventory

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Rule-based menus over AI | Deterministic, easier to manage than LLM responses | ✓ Good — zero hallucination risk, operator-controlled UX |
| Obsidian as content store | User already uses Obsidian — no custom admin UI needed | ✓ Good — zero new tooling, frontmatter IDs as stable keys |
| Local file path vault access | Simplest integration — FastAPI reads markdown directly | ✓ Good — POST /content/reload enables hot updates without restart |
| Keep FastAPI backend | Already exists, well-structured, serves as content API layer | ✓ Good — Python side handles content, Node side handles Messenger |
| Notify admin via Messenger | Simplest human handoff — no extra tooling needed | ✓ Good — requires ADMIN_PSID setup (admin must message Page once) |
| sendTypingIndicator scope: sendAnswer only | POLISH-01 says "while fetching answers" — scoped to avoid over-engineering | ✓ Good — no false indicators on menu navigation |

## Known Technical Debt (v1.0)

From code review findings (see phase REVIEW.md files):
- **CR-01** (Phase 3/5): Postback handler doesn't dispatch MENU_PRODUCT_HELP/MENU_MAIN from persistent menu — postback taps dead-end
- **CR-02** (Phase 3/5): Webhook async loop has no try/catch — unhandled rejection risk in Node 15+
- **WR-01** (Phase 3): VERIFY_TOKEN uses `!` assertion — undefined === undefined bypass if env var missing at startup
- **WR-05** (Phase 5): Non-Axios else branches log raw `err` — potential token leak for unexpected error types

---
*Last updated: 2026-05-15 after v1.0 milestone completion*
