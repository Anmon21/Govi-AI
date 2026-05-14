# Govi Facebook Messenger Customer Support Bot

## What This Is

A rule-based Facebook Messenger chatbot for Govi (e-commerce/retail) that guides customers through structured menus to answer product questions and escalate to a human agent. The system includes an admin panel for managing Q&A content without code changes.

## Core Value

Customers can get instant product answers and reach a human through Messenger — 24/7, without developer involvement in content updates.

## Requirements

### Validated

- ✓ Facebook Messenger webhook integration — existing (`messenger-bot/src/index.ts`)
- ✓ FastAPI Python backend with `/ai/chat` and `/health` endpoints — existing (`app/`)
- ✓ Two-service architecture: Node.js bot gateway + Python API — existing
- ✓ Environment-based configuration for both services — existing

### Active

- [ ] Rule-based menu system in the Messenger bot (replace current AI-passthrough)
- [ ] Product Q&A flow — customers can ask product questions via menus
- [ ] Human escalation flow — notify admin on Facebook Page inbox
- [ ] Obsidian vault integration — FastAPI backend reads Q&A content from Obsidian markdown files at a configured local vault path
- [ ] Q&A content format — structured markdown files in Obsidian vault define questions, answers, and menu flows

### Out of Scope

- Order tracking / order status — no store backend connected
- AI-powered free-text responses — using rule-based menus only
- Shopify / WooCommerce integration — standalone system
- Custom admin web UI — Obsidian vault is the content management interface
- Multi-language support — English only for v1

## Context

The Govi-AI repo already contains a working Facebook Messenger bot (`messenger-bot/`) built on Node.js/Express that receives webhooks and forwards all messages to a FastAPI Python backend, which calls Claude via the Anthropic SDK. The current flow is fully AI-driven — every message goes to Claude.

The new direction replaces the AI-passthrough with structured menu flows for customer support, while keeping the FastAPI backend as the API layer (now serving Q&A content and admin functionality instead of AI inference).

**Key architectural insight:** The existing two-service split (Node.js bot + Python API) is well-suited for this pivot — the bot handles Messenger interaction, the API handles content and business logic.

## Constraints

- **Tech stack**: Node.js/TypeScript for the Messenger bot, Python/FastAPI for the backend — maintain existing split
- **Platform**: Facebook Messenger only — no other channels in v1
- **Deployment**: No containerization currently — same manual deploy pattern
- **Scope**: Standalone system — no integration with order management or inventory

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Rule-based menus over AI | Deterministic, easier to manage than LLM responses | — Pending |
| Obsidian as content store | User already uses Obsidian — no custom admin UI needed | — Pending |
| Local file path vault access | Simplest integration — FastAPI reads markdown directly | — Pending |
| Keep FastAPI backend | Already exists, well-structured, serves as content API layer | — Pending |
| Notify admin via Messenger | Simplest human handoff — no extra tooling needed | — Pending |

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
*Last updated: 2026-05-14 after initialization*
