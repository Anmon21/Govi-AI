# Roadmap: Govi Facebook Messenger Customer Support Bot

## Milestones

- ✅ **v1.0 Govi Messenger Bot MVP** — Phases 1–5 (shipped 2026-05-15)
- ✅ **v1.1 UX Polish & Hardening** — Phases 6–9 (shipped 2026-05-20)
- 🔄 **v1.2 Admin Panel & Multi-Page Support** — Phases 10–15 (in progress)

## Phases

<details>
<summary>✅ v1.0 Govi Messenger Bot MVP (Phases 1–5) — SHIPPED 2026-05-15</summary>

- [x] Phase 1: Security + Bot Foundation (3/3 plans) — completed 2026-05-14
- [x] Phase 2: Vault Service (2/2 plans) — completed 2026-05-14
- [x] Phase 3: Product Q&A Flow (2/2 plans) — completed 2026-05-15
- [x] Phase 4: Human Escalation (2/2 plans) — completed 2026-05-15
- [x] Phase 5: Polish + Hardening (2/2 plans) — completed 2026-05-15

Full archive: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 UX Polish & Hardening (Phases 6–9) — SHIPPED 2026-05-20</summary>

- [x] Phase 6: Bug Fixes & Hardening (1/1 plans) — completed 2026-05-20
- [x] Phase 7: Helpfulness Feedback (1/1 plans) — completed 2026-05-20
- [x] Phase 8: Answer Truncation (1/1 plans) — completed 2026-05-20
- [x] Phase 9: User Memory & Personalization (1/1 plans) — completed 2026-05-20

</details>

### v1.2 Admin Panel & Multi-Page Support

- [ ] **Phase 10: DB Foundation** - SQLite schema, WAL mode, Fernet encryption setup — the data layer every subsequent phase depends on
- [ ] **Phase 11: Auth & Tenant Management API** - FastAPI login, JWT sessions, and super-admin CRUD for client accounts
- [ ] **Phase 12: Page Connection API + Facebook OAuth** - Clients connect Facebook Pages via OAuth with atomic webhook subscription; App Review submitted
- [ ] **Phase 13: Page Config, Q&A API + Content Migration** - DB-backed content endpoints that preserve the existing HTTP contract; Obsidian vault retired via seed script
- [ ] **Phase 14: Bot Multi-Page Routing** - Bot reads token + config per Page ID from FastAPI; PAGE_ACCESS_TOKEN global removed; per-page state isolation
- [ ] **Phase 15: Admin Panel UI** - React SPA built against stable APIs: tenant management, page connection, and full per-page content editor

---

## Phase Details

### Phase 6: Bug Fixes & Hardening
**Goal**: The bot handles persistent menu taps correctly, never crashes from an unhandled async rejection, fails loudly at startup if VERIFY_TOKEN is missing, and never leaks tokens in error logs
**Depends on**: Nothing (first v1.1 phase)
**Requirements**: DEBT-01, DEBT-02, DEBT-03, DEBT-04
**Success Criteria** (what must be TRUE):
  1. Tapping "Product Help" or "Main Menu" in the Messenger persistent menu navigates the user to the expected menu — no dead-end or silent failure
  2. An exception thrown inside the webhook async processing loop is caught, logged, and does not crash the bot process
  3. Starting the bot without VERIFY_TOKEN set exits immediately with a readable error message before accepting any connections
  4. An unexpected (non-Axios) error produces a log entry containing no raw error object and therefore cannot expose auth tokens
**Plans**: 1 plan
Plans:
- [x] 06-01-PLAN.md — Apply four surgical patches to messenger-bot/src/index.ts (DEBT-01 postback routing, DEBT-02 per-event try/catch, DEBT-03 VERIFY_TOKEN startup guard, DEBT-04 non-Axios log sanitization) plus a `debt-fixes.test.ts` covering DEBT-01/02/04

### Phase 7: Helpfulness Feedback
**Goal**: Users can tell the bot whether an answer helped, receive a positive acknowledgment when satisfied, or be routed to a human agent when not
**Depends on**: Phase 6
**Requirements**: UX-01, UX-02, UX-03
**Success Criteria** (what must be TRUE):
  1. After every Q&A answer message, the user sees "Was this helpful?" with Yes and No quick reply buttons
  2. Tapping "Yes" shows a short thank-you message followed by the main menu
  3. Tapping "No" immediately enters the escalation flow — same path as the explicit escalation option
**Plans**: 1 plan
Plans:
- [x] 07-01-PLAN.md — Add FEEDBACK_QUICK_REPLIES constant, swap sendAnswer quick replies, add HELPFUL_YES/HELPFUL_NO handler cases, write feedback.test.ts (UX-01, UX-02, UX-03)

### Phase 8: Answer Truncation
**Goal**: Long answers are broken into a readable preview so the chat thread is not overwhelmed, and users can retrieve the full text on demand
**Depends on**: Phase 6
**Requirements**: UX-04, UX-05
**Success Criteria** (what must be TRUE):
  1. An answer longer than ~200 characters is sent as a truncated message ending with "..." and a "Read more" quick reply button
  2. Tapping "Read more" sends the complete, untruncated answer text as a follow-up message
  3. Answers at or under ~200 characters are delivered as-is with no truncation or "Read more" button
**Plans**: 1 plan
Plans:
- [x] 08-01-PLAN.md — Add ANSWER_THRESHOLD + PAYLOAD_PREFIX_READ_MORE constants, modify sendAnswer with word-boundary truncation branch, add sendReadMoreAnswer function, add READ_MORE: dispatch case in handleWebhookEvent, write truncation.test.ts with 9 cases (UX-04, UX-05)
**UI hint**: yes

### Phase 9: User Memory & Personalization
**Goal**: Returning users are greeted by name, making the bot feel aware of who they are without requiring any persistent storage
**Depends on**: Phase 6
**Requirements**: UX-06, UX-07
**Success Criteria** (what must be TRUE):
  1. On a user's first interaction, the bot fetches their first name from the Graph API and stores it in an in-memory Map keyed by PSID
  2. On a subsequent Get Started or welcome trigger from the same PSID, the greeting message includes the user's first name
  3. If the Graph API call fails or returns no name, the bot falls back to a generic greeting without surfacing an error to the user
**Plans**: 1 plan
Plans:
- [x] 09-01-PLAN.md — Add userNameCache Map, fetchUserName helper with sentinel pattern, fetch-once guard in handleWebhookEvent, updated sendWelcomeMessage with name branch, write personalization.test.ts with 8 cases (UX-06, UX-07)
**UI hint**: yes

### Phase 10: DB Foundation
**Goal**: A SQLite database with the full v1.2 schema is initialized, WAL mode is enabled, and Page Access Tokens can be Fernet-encrypted at rest — no service behavior changes yet
**Depends on**: Phase 9
**Requirements**: DB-01
**Success Criteria** (what must be TRUE):
  1. Running the DB initialization script creates all four tables (tenants, pages, page_configs, qa_items) with correct foreign keys and indexes
  2. The database opens in WAL mode with a 5-second busy_timeout so concurrent reads and writes do not deadlock
  3. A Fernet key loaded from environment can encrypt and decrypt a sample token string round-trip without data loss
  4. The existing FastAPI content endpoints return the same responses as before this phase (no regression)
**Plans**: 3 plans
Plans:
**Wave 1**
- [x] 10-01-PLAN.md — Wave 0 test scaffold + app/db.py (get_connection + init_schema for tenants/pages/page_configs/qa_items with WAL, busy_timeout, FKs)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 10-02-PLAN.md — Settings db_path/fernet_key + cryptography dependency + .env.example + app/crypto.py Fernet helpers + test_fernet_round_trip

**Wave 3** *(blocked on Wave 2 completion)*
- [ ] 10-03-PLAN.md — scripts/init_db.py CLI runner + .gitignore SQLite sidecars + human no-regression checkpoint on /health and /content endpoints

### Phase 11: Auth & Tenant Management API
**Goal**: A super-admin can log in and manage client accounts via FastAPI endpoints secured by JWT — clients see only their own data
**Depends on**: Phase 10
**Requirements**: TENANT-01, TENANT-02, TENANT-03
**Success Criteria** (what must be TRUE):
  1. Calling POST /auth/login with valid super-admin credentials returns a signed JWT; invalid credentials return 401
  2. A super-admin can create a new client account (email + hashed password) via POST /admin/tenants and the account appears in the tenant list
  3. A super-admin can retrieve a list of all client accounts with their connected Page count via GET /admin/tenants
  4. A super-admin can delete or deactivate a client account via DELETE /admin/tenants/{id}; the client's Pages are disconnected and their data is inaccessible
  5. Every tenant-scoped endpoint rejects requests whose JWT tenant_id does not match the resource — no cross-tenant data access is possible
**Plans**: TBD

### Phase 12: Page Connection API + Facebook OAuth
**Goal**: Clients can connect their Facebook Pages via OAuth with full 3-step token exchange and automatic webhook subscription; token health is visible per Page
**Depends on**: Phase 11
**Requirements**: PAGE-01, PAGE-02, PAGE-03, PAGE-04
**Success Criteria** (what must be TRUE):
  1. Clicking "Connect with Facebook" redirects the client through the Facebook OAuth flow and, on completion, stores a long-lived Page Access Token (Fernet-encrypted) and subscribes the Page's webhook — all in one atomic operation
  2. The client can view all their connected Pages with a status badge (active / token revoked) via GET /pages
  3. The client can disconnect a Page via DELETE /pages/{id}; the stored token is deleted and the webhook subscription is removed from Facebook
  4. A Page whose token has been revoked shows a "Reconnect" indicator and the client can re-initiate OAuth to restore it
**Plans**: TBD

### Phase 13: Page Config, Q&A API + Content Migration
**Goal**: All bot content (welcome text, menu, Q&A, escalation settings) is served from the database per Page ID; the existing /content HTTP contract is preserved; the Obsidian vault is retired
**Depends on**: Phase 12
**Requirements**: CONTENT-01, CONTENT-02, CONTENT-03, CONTENT-04, DB-02
**Success Criteria** (what must be TRUE):
  1. A client can update the welcome/greeting text for their Page via the API and the bot immediately serves the new text to users on Get Started
  2. A client can update the persistent menu labels and structure for their Page via the API; the change is visible in Messenger after the API call
  3. A client can create, edit, and delete Q&A categories and answers for their Page via the API; the bot serves the updated Q&A tree without a restart
  4. A client can update the escalation PSID and handoff message for their Page via the API
  5. Running the one-time seed script migrates all existing Obsidian vault Q&A content into the database, and the bot continues to respond correctly to Q&A queries using DB-backed content
**Plans**: TBD

### Phase 14: Bot Multi-Page Routing
**Goal**: The bot handles webhook events from multiple Facebook Pages by fetching the correct token and content config per Page ID from FastAPI; the PAGE_ACCESS_TOKEN global is fully removed; per-page state is isolated
**Depends on**: Phase 13
**Requirements**: BOT-01, BOT-02, BOT-03
**Success Criteria** (what must be TRUE):
  1. An inbound webhook event carrying Page ID A is processed using Page A's token and content; an event carrying Page ID B uses Page B's token and content — no cross-page bleed
  2. Grepping the codebase for PAGE_ACCESS_TOKEN returns zero references in runtime code (env var removed, all call sites updated)
  3. User name cache and session state (menu position, read-more buffer) for a PSID on Page A are invisible to the same PSID interacting via Page B
  4. If the FastAPI page-context endpoint is unreachable for a given Page ID, the bot sends a user-facing fallback message instead of crashing
**Plans**: TBD

### Phase 15: Admin Panel UI
**Goal**: A React SPA gives super-admins and clients a full visual interface for tenant management, Facebook Page connection, and per-page content editing — no direct API calls required
**Depends on**: Phase 14
**Requirements**: (UI layer over TENANT-01–03, PAGE-01–04, CONTENT-01–04)
**Success Criteria** (what must be TRUE):
  1. The super-admin can log in, view all tenants, create a new client account, and deactivate an existing one — all from the UI without touching the API directly
  2. A client can log in, see their connected Pages dashboard, click "Connect with Facebook" to add a Page, and disconnect a Page from the same screen
  3. A client can open a Page's content editor and update welcome text, menu labels, Q&A entries, and escalation settings — changes persist immediately in the database
  4. A Page with a revoked token displays a visible warning badge and a "Reconnect" button that launches the OAuth flow
  5. All forms show inline validation errors before submission and a success confirmation on save
**Plans**: TBD
**UI hint**: yes

---

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Security + Bot Foundation | v1.0 | 3/3 | Complete | 2026-05-14 |
| 2. Vault Service | v1.0 | 2/2 | Complete | 2026-05-14 |
| 3. Product Q&A Flow | v1.0 | 2/2 | Complete | 2026-05-15 |
| 4. Human Escalation | v1.0 | 2/2 | Complete | 2026-05-15 |
| 5. Polish + Hardening | v1.0 | 2/2 | Complete | 2026-05-15 |
| 6. Bug Fixes & Hardening | v1.1 | 1/1 | Complete | 2026-05-20 |
| 7. Helpfulness Feedback | v1.1 | 1/1 | Complete | 2026-05-20 |
| 8. Answer Truncation | v1.1 | 1/1 | Complete | 2026-05-20 |
| 9. User Memory & Personalization | v1.1 | 1/1 | Complete | 2026-05-20 |
| 10. DB Foundation | v1.2 | 2/3 | In Progress|  |
| 11. Auth & Tenant Management API | v1.2 | 0/? | Not started | - |
| 12. Page Connection API + Facebook OAuth | v1.2 | 0/? | Not started | - |
| 13. Page Config, Q&A API + Content Migration | v1.2 | 0/? | Not started | - |
| 14. Bot Multi-Page Routing | v1.2 | 0/? | Not started | - |
| 15. Admin Panel UI | v1.2 | 0/? | Not started | - |

---

*Last updated: 2026-05-27 — v1.2 roadmap created (Phases 10–15)*
