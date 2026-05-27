# Govi Facebook Messenger Customer Support Bot

## What This Is

A rule-based Facebook Messenger chatbot for Govi (e-commerce/retail) that guides customers through structured menus to answer product questions and escalate to a human agent. Content is managed via an Obsidian vault — no code changes needed to update Q&A answers.

**Shipped v1.0 (2026-05-15):** Bot is feature-complete and ready to deploy. Automated test coverage: 22 Node.js + 14 Python tests, all green.

## Core Value

Customers can get instant product answers and reach a human through Messenger — 24/7, without developer involvement in content updates.

## Current Milestone: v1.2 Admin Panel & Multi-Page Support

**Goal:** A web-based admin panel that lets you add client tenants, each connecting their Facebook Page via OAuth and customizing their bot's content end-to-end — no Obsidian vault, no code changes, no manual involvement.

**Target features:**
- Tenant management: you add clients (email + password), they see only their own Pages
- Facebook OAuth: clients connect Pages via "Connect with Facebook" — tokens stored in DB automatically
- Per-page content editor: welcome text, menu labels, Q&A categories + answers, escalation settings (admin PSID, handoff message)
- DB-backed content: replaces Obsidian vault entirely; bot reads config from DB by Page ID
- Bot becomes page-aware: handles webhooks from multiple Pages using the right token + content per Page

## Current State

**Version:** v1.2 (in progress)
**Previous:** v1.1 shipped 2026-05-20 — UX polish & hardening complete
**Status:** Milestone v1.2 started — defining requirements for Admin Panel & Multi-Page Support

**Codebase:**
- `messenger-bot/src/index.ts` — Node.js/TypeScript bot (~420 LOC): webhook handler, menu routing, Q&A flow, escalation, typing indicator, DEBT-01–04 fixes, personalized greetings
- `app/routers/content.py` — FastAPI vault router (~120 LOC): content listing, single-item fetch, reload endpoint
- 50 Node.js tests, all passing

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

### Validated (v1.1, Phase 06)

- ✓ Fix DEBT-01: Postback handler dispatches MENU_PRODUCT_HELP/MENU_MAIN — Phase 06
- ✓ Fix DEBT-02: Per-event try/catch in webhook loop prevents crash on single bad event — Phase 06
- ✓ Fix DEBT-03: VERIFY_TOKEN fail-fast guard at startup (process.exit(1) if unset) — Phase 06
- ✓ Fix DEBT-04: All 7 non-Axios error branches sanitized — no token leak via log objects — Phase 06

### Validated (v1.1, Phases 07–09)

- ✓ "Was this helpful?" quick reply after answers — No → escalation (UX-01–03) — Phase 07
- ✓ Answer truncation (~200 chars) + "Read more" quick reply → full answer as follow-up (UX-04–05) — Phase 08
- ✓ In-memory returning user memory — greet by name (per PSID Map) (UX-06–07) — Phase 09

### Active (v1.2)

- [ ] Tenant management — admin creates client accounts; clients see only their own Pages
- [ ] Facebook OAuth page connection — clients connect Pages via "Connect with Facebook"
- [ ] Per-page welcome text customization
- [ ] Per-page menu label & structure editor
- [ ] Per-page Q&A content editor (replaces Obsidian vault)
- [ ] Per-page escalation settings editor (admin PSID, handoff message)
- [ ] DB-backed content store — bot reads config from DB by Page ID
- [ ] Multi-page bot — handles webhooks from multiple Pages with per-Page token + config
- [ ] Live Messenger UAT — 7 human-only scenarios pending production deployment

### Out of Scope (v1.x)

- Order tracking / order status — no store backend connected
- AI-powered free-text responses — using rule-based menus only
- Shopify / WooCommerce integration — standalone system
- Custom admin web UI — Obsidian vault is the content management interface
- Multi-language support — English only
- Persistent user memory (SQLite/DB) — in-memory is sufficient for v1.1

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

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-27 — Milestone v1.2 started: Admin Panel & Multi-Page Support*
