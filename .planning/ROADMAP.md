# Roadmap: Govi Facebook Messenger Customer Support Bot

## Overview

Build a rule-based Facebook Messenger customer support bot on an existing Node.js/FastAPI codebase. The existing AI-passthrough is replaced with structured menu navigation, an Obsidian vault content layer, and a human escalation path. Five phases deliver the system: security fixes and bot skeleton first (blocking risks eliminated early), then the vault content API, then the full Q&A flow, then human escalation, and finally polish hardening before launch.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Security + Bot Foundation** - Fix broken security, wire Get Started / persistent menu / fallback — bot is structurally sound
- [ ] **Phase 2: Vault Service** - FastAPI reads Obsidian vault and serves Q&A content via HTTP endpoints
- [ ] **Phase 3: Product Q&A Flow** - Full menu → category → question → answer flow powered by the vault
- [ ] **Phase 4: Human Escalation** - Contact Human path with Handover Protocol and admin Messenger notification
- [ ] **Phase 5: Polish + Hardening** - Typing indicator and deployment-readiness verification

## Phase Details

### Phase 1: Security + Bot Foundation
**Mode:** mvp
**Goal:** The bot skeleton is secure and structurally complete — customers can open the bot, see a welcome message, navigate the persistent menu, and never get a silent dead end
**Depends on:** Nothing (first phase)
**Requirements:** SEC-01, SEC-02, SEC-03, CORE-01, CORE-02, CORE-03, CORE-04
**Success Criteria** (what must be TRUE):
  1. Sending a forged (invalid signature) POST to /webhook returns 403 — the bot does not process it
  2. A new user who clicks "Get Started" on the Facebook Page receives a welcome message with navigation quick replies
  3. A user who types free text at any point receives a re-anchor message with menu options — the bot never goes silent
  4. A user can open the persistent hamburger menu and see the top-level navigation options at any time
  5. A Graph API send failure (Facebook returns an error body in a 200 response) is logged with message and response data — PAGE_ACCESS_TOKEN does not appear in any log output
**Plans:** 3 plans
Plans:
- [x] 01-01-PLAN.md — Wave 0: test runner wiring, node_modules cleanup, .env.example update, failing test scaffolds (SEC-01/02/03 + CORE-01/02/03/04)
- [x] 01-02-PLAN.md — Wave 1 (security slice): HMAC webhook verification (SEC-01), Graph API error detection (SEC-02), safe error logging (SEC-03), v21.0 bump
- [x] 01-03-PLAN.md — Wave 2 (navigation slice): Messenger Profile setup (CORE-02), Get Started welcome (CORE-01), quick replies (CORE-03), free-text fallback with quick-reply guard (CORE-04)

### Phase 2: Vault Service
**Mode:** mvp
**Goal:** The FastAPI backend can load, cache, and serve Obsidian vault content by stable ID — independently testable with curl before the bot touches it
**Depends on:** Phase 1
**Requirements:** VAULT-01, VAULT-02, VAULT-03
**Success Criteria** (what must be TRUE):
  1. Running `curl /health` after startup confirms the vault loaded and reports the count of enabled content files found
  2. Running `curl /content/{id}` returns the correct title and body text for a vault file with that frontmatter ID
  3. Vault files missing `enabled: true` in their frontmatter are not served and do not appear in content listings
  4. Running `curl -X POST /content/reload` re-reads vault files from disk and reflects edits made since startup — no server restart required
**Plans:** TBD

### Phase 3: Product Q&A Flow
**Mode:** mvp
**Goal:** A customer can browse product categories, select a question, and read the answer — end-to-end, driven entirely by quick reply buttons pulling content from the vault
**Depends on:** Phase 2
**Requirements:** QA-01, QA-02, QA-03, QA-04
**Success Criteria** (what must be TRUE):
  1. A customer tapping "Product Questions" (or equivalent top-level menu item) sees a list of product categories as quick reply buttons
  2. A customer selecting a category sees a list of questions for that category as quick reply buttons
  3. A customer selecting a question receives the answer text from the Obsidian vault as a Messenger message
  4. An admin who edits a vault answer file and calls POST /content/reload sees the updated answer served to customers without restarting the server
**Plans:** TBD

### Phase 4: Human Escalation
**Mode:** mvp
**Goal:** A customer who wants human help can request it from any screen; the admin receives a Messenger notification with context and the thread transfers to the Page inbox
**Depends on:** Phase 3
**Requirements:** ESC-01, ESC-02, ESC-03, ESC-04
**Success Criteria** (what must be TRUE):
  1. A "Contact Human" option is available from the main menu and from any Q&A screen — tapping it always triggers escalation regardless of where the user is in the flow
  2. After a customer requests escalation, the admin receives a Messenger message that includes the customer's last message as context
  3. After escalation, the customer's thread appears in the Page inbox and accepts replies from the admin (Handover Protocol transferred thread control)
  4. If ADMIN_PSID is not configured, escalation fails gracefully — a console log is emitted and the bot sends the customer a "we'll be in touch" message rather than crashing
**Plans:** TBD

### Phase 5: Polish + Hardening
**Mode:** mvp
**Goal:** The bot feels responsive and the deployment is verified clean — ready to go live
**Depends on:** Phase 4
**Requirements:** POLISH-01
**Success Criteria** (what must be TRUE):
  1. When a customer selects a question, a typing indicator appears in the Messenger thread before the answer arrives — the bot does not appear frozen during the API fetch
  2. All environment variables are documented with example values and the bot starts cleanly from a fresh clone with only .env configuration
**Plans:** TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Security + Bot Foundation | 0/3 | Not started | - |
| 2. Vault Service | 0/TBD | Not started | - |
| 3. Product Q&A Flow | 0/TBD | Not started | - |
| 4. Human Escalation | 0/TBD | Not started | - |
| 5. Polish + Hardening | 0/TBD | Not started | - |
