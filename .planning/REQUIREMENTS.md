# Requirements — Govi Facebook Messenger Customer Support Bot

**Version:** v1
**Status:** Active
**Last updated:** 2026-05-14

---

## v1 Requirements

### CORE — Bot Foundation

- [ ] **CORE-01**: User sees a welcome message with navigation options when they first message the Page (Get Started postback handler)
- [ ] **CORE-02**: User can access a persistent hamburger menu at any time with top-level navigation options (max 3 items, configured via Messenger Profile API)
- [ ] **CORE-03**: User navigates all flows via quick reply buttons — no free-text input required at any point
- [ ] **CORE-04**: User sees a helpful re-anchor message with menu options when they type free text (fallback handler — never silent)

### SEC — Security

- [ ] **SEC-01**: Webhook verifies X-Hub-Signature-256 HMAC before processing any incoming event (fix to existing handler)
- [ ] **SEC-02**: Bot detects and logs Graph API errors returned inside HTTP 200 responses (fix to existing send helper)
- [ ] **SEC-03**: Application logs never contain PAGE_ACCESS_TOKEN or other secrets (fix to existing error logging)

### VAULT — Obsidian Integration

- [ ] **VAULT-01**: FastAPI loads Q&A content from Obsidian vault at startup via a configured local directory path (VAULT_PATH env var)
- [ ] **VAULT-02**: FastAPI serves content by stable frontmatter ID via clean HTTP endpoints (GET /content/{id})
- [ ] **VAULT-03**: Vault file format uses a defined frontmatter schema (id, type, title, enabled) for bot-readable discovery — files without `enabled: true` are ignored

### QA — Product Q&A

- [ ] **QA-01**: User can browse product Q&A by category (category menu via quick replies)
- [ ] **QA-02**: User can select a specific question from a category's question list (question sub-menu)
- [ ] **QA-03**: User sees the answer text fetched from the Obsidian vault sent as a Messenger message
- [ ] **QA-04**: Admin can reload vault content without restarting the server (POST /content/reload endpoint)

### ESC — Human Escalation

- [ ] **ESC-01**: User can tap "Contact Human" from the menu or any screen to trigger escalation
- [ ] **ESC-02**: Admin receives a Messenger notification (via their Page-Scoped PSID) when a user requests escalation
- [ ] **ESC-03**: Thread control transfers to the Page inbox via Facebook Handover Protocol when escalation is triggered
- [ ] **ESC-04**: Admin notification includes the customer's last message so admin has context before responding

### POLISH

- [x] **POLISH-01**: Bot shows a typing indicator (typing_on action) while fetching answers from the FastAPI content API

---

## v2 Requirements

*Deferred — users expect these but v1 ships without them*

- "Was this helpful?" quick reply after each answer — lightweight feedback signal
- Question-level feedback forwarded to admin — helps improve content
- Answer length truncation + "Read more" link — handle long Obsidian answers gracefully
- Returning user memory — greet by name on repeat visits
- Multi-language support — English only in v1

---

## Out of Scope

- **Custom admin web UI** — Obsidian vault is the content management interface; no web UI needed
- **AI / NLP-powered responses** — rule-based menus only; free-text NLP is a maintenance trap
- **Order tracking / store backend integration** — standalone system, no Shopify/WooCommerce
- **Conversation history persistence** — stateless sessions with TTL are sufficient for a support bot
- **Rich media carousels / image messages** — requires structured product data the vault doesn't provide
- **Multi-channel support** — Facebook Messenger only in v1

---

## Traceability

| REQ-ID | Phase | Notes |
|--------|-------|-------|
| CORE-01 | Phase 1 | Get Started postback — bot skeleton |
| CORE-02 | Phase 1 | Persistent menu — bot skeleton |
| CORE-03 | Phase 1 | Quick reply navigation — bot skeleton |
| CORE-04 | Phase 1 | Free-text fallback — bot skeleton |
| SEC-01 | Phase 1 | HMAC signature fix — blocking security issue |
| SEC-02 | Phase 1 | Graph API error detection fix — blocking security issue |
| SEC-03 | Phase 1 | Token leak fix in error logging — blocking security issue |
| VAULT-01 | Phase 2 | Vault startup load via VAULT_PATH |
| VAULT-02 | Phase 2 | Content served by frontmatter ID |
| VAULT-03 | Phase 2 | Frontmatter schema + enabled discovery |
| QA-01 | Phase 3 | Category menu via quick replies |
| QA-02 | Phase 3 | Question sub-menu |
| QA-03 | Phase 3 | Answer delivery from vault |
| QA-04 | Phase 2 | POST /content/reload — admin hot-reload |
| ESC-01 | Phase 4 | "Contact Human" entry point |
| ESC-02 | Phase 4 | Admin Messenger notification |
| ESC-03 | Phase 4 | Handover Protocol thread transfer |
| ESC-04 | Phase 4 | Last message included in admin notification |
| POLISH-01 | Phase 5 | Typing indicator during vault fetch |
