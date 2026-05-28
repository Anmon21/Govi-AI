# Requirements — v1.2 Admin Panel & Multi-Page Support

**Milestone:** v1.2
**Status:** Draft
**Last updated:** 2026-05-27

---

## v1.2 Requirements

### Tenant Management

- [x] **TENANT-01**: Super-admin can create a client account (email + password) via the admin panel
- [x] **TENANT-02**: Super-admin can view a list of all client accounts and their connected Pages
- [x] **TENANT-03**: Super-admin can delete or deactivate a client account (disconnects their Pages)

### Facebook Page Connection

- [ ] **PAGE-01**: Client can connect a Facebook Page via OAuth ("Connect with Facebook" button) — full 3-step token exchange with webhook subscription
- [ ] **PAGE-02**: Client can view a list of their connected Pages and connection status
- [ ] **PAGE-03**: Client can disconnect a Page (removes stored token and webhook subscription)
- [ ] **PAGE-04**: Client can see a token health indicator per Page and trigger reconnect if the token is revoked

### Per-Page Content Editing

- [ ] **CONTENT-01**: Client can edit the welcome/greeting text shown to users on Get Started for their Page
- [ ] **CONTENT-02**: Client can edit the persistent menu labels and structure for their Page
- [ ] **CONTENT-03**: Client can create, edit, and delete Q&A categories and answers for their Page (replaces Obsidian vault)
- [ ] **CONTENT-04**: Client can edit escalation settings for their Page (admin PSID and handoff message)

### Database Foundation

- [x] **DB-01**: System stores all tenant, Page, and content data in a SQLite database (WAL mode, Fernet-encrypted tokens)
- [ ] **DB-02**: Existing Obsidian vault Q&A content is migrated to the database via a one-time seed script

### Bot Architecture

- [ ] **BOT-01**: The bot routes each incoming webhook event to the correct Facebook Page using the Page ID from the event payload, and fetches the matching token + config from the database
- [ ] **BOT-02**: The bot reads all Q&A content from the database; the Obsidian vault dependency is removed
- [ ] **BOT-03**: The bot's in-memory caches (user name, session state) are scoped per Page ID so multiple Pages do not share state

---

## Future Requirements (deferred)

- Bulk CSV import of Q&A content — deferred to v1.3
- Analytics dashboard (message volume, escalation rate) — deferred to v1.3
- Automated token health-check background job — deferred to v1.3
- Content change preview (static render of menu tree and answer text) — deferred to v1.3
- Audit log (who changed what per Page) — deferred to v1.3
- Self-service client registration with invitation emails — deferred (out of scope for admin-managed model)

---

## Out of Scope (v1.x)

- Multi-level user roles (e.g. Page editors vs. Page owners within a tenant) — role model is super-admin + client only
- White-labeling the admin panel — single-brand tool
- Drag-and-drop flow builder — Messenger tree limits make it not worth the implementation cost
- Conversation inbox / live chat — separate product category
- Broadcast messaging — not a Messenger bot concern
- Rich text / HTML in Q&A answers — Messenger only supports plain text

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DB-01 | Phase 10 | Complete |
| TENANT-01 | Phase 11 | Complete |
| TENANT-02 | Phase 11 | Complete |
| TENANT-03 | Phase 11 | Complete |
| PAGE-01 | Phase 12 | Pending |
| PAGE-02 | Phase 12 | Pending |
| PAGE-03 | Phase 12 | Pending |
| PAGE-04 | Phase 12 | Pending |
| CONTENT-01 | Phase 13 | Pending |
| CONTENT-02 | Phase 13 | Pending |
| CONTENT-03 | Phase 13 | Pending |
| CONTENT-04 | Phase 13 | Pending |
| DB-02 | Phase 13 | Pending |
| BOT-01 | Phase 14 | Pending |
| BOT-02 | Phase 14 | Pending |
| BOT-03 | Phase 14 | Pending |
