# Feature Landscape

**Domain:** Multi-tenant Facebook Messenger bot admin panel (v1.2)
**Project:** Govi AI — Admin Panel & Multi-Page Support
**Researched:** 2026-05-27
**Confidence:** HIGH for UX/auth patterns (stable domain); MEDIUM for Facebook OAuth specifics (Meta docs are accurate but app review timelines are unpredictable)

---

## Context: What Already Exists

v1.0/v1.1 shipped a working single-page Messenger bot. v1.2 adds an admin panel web app on top of the existing FastAPI backend. The features below describe only what is **new** in v1.2. The bot behaviors (menus, Q&A, escalation, greetings, typing indicators) are already built and are table stakes for the bot layer, not for this milestone.

**Dependency boundary:** All new admin panel features depend on the bot's existing webhook handler being refactored to be page-aware (reads page_id from the incoming event and looks up config + token per page from DB). That refactor is a prerequisite for all content editing features to have effect.

---

## Table Stakes

Features users (super-admin and tenant clients) expect. Missing any of these makes the admin panel feel incomplete or untrustworthy.

---

### 1. Super-Admin: Create and Manage Client Accounts

**What:** A super-admin UI where the platform operator (Govi team) creates client accounts by entering email + initial password. Clients receive a credential set and can log in. The super-admin sees all clients, can deactivate accounts, and cannot accidentally see one client's data when navigating.

**Why expected:** This is the entry point to the entire system. Without it, adding new clients requires direct DB manipulation. Every multi-tenant SaaS has this.

**Complexity:** Low. Standard CRUD (create account, list accounts, deactivate). No invitation email required in v1 — super-admin hands credentials to the client directly.

**Dependencies:** JWT-based auth (see auth flow below), tenant_id column on all data models, RBAC with two roles: `super_admin` and `client`.

**Notes:**
- Two roles only: `super_admin` (one or a handful of operators) and `client` (each tenant).
- `super_admin` role must be hardcoded or seeded — not self-created through the UI.
- Tenant isolation enforcement: every API query must filter by `tenant_id` extracted from the JWT. A missing filter is a data leak. This is the most important security invariant in the system.

---

### 2. Client Login and Session

**What:** Clients log in with email + password via a standard login form. On success, they receive a JWT. The session shows only their own Pages and content — they have no visibility into other tenants' data.

**Why expected:** Basic auth. If clients can see each other's data, the product is broken.

**Complexity:** Low. Email/password + JWT. No SSO, no magic links, no MFA needed in v1.

**Dependencies:** Password hashing (bcrypt), JWT issuance with `tenant_id` and `role` claims, middleware that validates the token and injects tenant context on every request.

**Notes:**
- Store `tenant_id` in the JWT payload so the server never has to look it up separately.
- JWTs should expire in 24h with no refresh token in v1 (simplest path). A forced re-login every day is acceptable for an internal admin tool.
- Super-admin and client login can share the same login page — role determines what they see after.

---

### 3. Facebook Page Connection via OAuth ("Connect with Facebook")

**What:** A client clicks "Connect with Facebook" on their dashboard. This triggers the Facebook OAuth login dialog, the user grants permissions, and the app exchanges the auth code for a user access token, then calls `GET /me/accounts` to list Pages the user manages. The client selects which Page to connect. The app exchanges the user token for a long-lived Page access token and stores it in the DB against the tenant and page_id.

**Why expected:** This is the core mechanism for connecting the bot to a client's Page. Manual token entry would be error-prone and fragile. Every Messenger bot SaaS platform (Chatfuel, ManyChat, Botpress) uses this exact flow.

**Complexity:** High. Multiple OAuth steps, error states (user denies, page not listed, token exchange fails), token storage, and the Facebook App Review requirement (see Pitfalls).

**Required Facebook permissions for the OAuth scope:**
- `pages_messaging` — send/receive messages on behalf of the Page
- `pages_manage_metadata` — subscribe to webhook events, update Page settings
- `pages_show_list` — enumerate Pages the user manages (required by `pages_messaging`)

**Token storage:** Store the long-lived Page access token (not the user access token) in the DB. Long-lived Page access tokens do not expire if the user keeps the app connected. Short-lived tokens (~1-2h) are not suitable for a bot.

**Token exchange flow:**
1. Redirect to `https://www.facebook.com/v25.0/dialog/oauth` with `scope=pages_messaging,pages_manage_metadata,pages_show_list`
2. On callback, exchange code for short-lived user token via `GET /oauth/access_token`
3. Exchange short-lived user token for long-lived user token via `GET /oauth/access_token?grant_type=fb_exchange_token`
4. Call `GET /me/accounts` with long-lived user token to list Pages + their Page access tokens
5. Store the Page access token from step 4 (these are long-lived by default when derived from a long-lived user token)

**Dependencies:** Facebook App (registered with Meta), OAuth callback endpoint in FastAPI, DB table for `pages` (page_id, tenant_id, page_name, page_access_token, connected_at).

**Notes:**
- The `state` parameter in the OAuth redirect must be verified on callback to prevent CSRF.
- App Review is required before non-admin Facebook users can grant these permissions. During development, only users with Developer/Tester/Admin role on the Facebook App can connect Pages. This is fine for internal use.
- One client may have multiple Pages. The UI should allow selecting one Page per connection attempt, not bulk-connecting all Pages at once.

---

### 4. Connected Pages Dashboard

**What:** After connecting a Page, clients see a list of their connected Pages on the dashboard. Each Page shows: Page name, connection status (connected/disconnected), and a link to edit its configuration.

**Why expected:** Clients need to see what they've connected. Without this, there's no way to know if OAuth succeeded or which Pages are active.

**Complexity:** Low. A list view with status indicators.

**Dependencies:** Page connection flow (above), `pages` table.

**Notes:**
- Show a clear call-to-action ("Connect a Facebook Page") when no Pages are connected yet. Empty states with a dead-empty list are confusing.
- "Disconnected" state should appear when the stored token has been revoked (detectable via a failed Graph API call). Don't silently swallow token errors — surface them as a "reconnect" prompt.

---

### 5. Per-Page Welcome Text Editor

**What:** A text field where the client edits the greeting message their bot sends when a user taps "Get Started." Changes are saved to the DB and the bot reads them by page_id on each welcome event.

**Why expected:** Welcome text is the first thing Messenger users see. Every bot admin tool exposes this as an editable field. Without it, all Pages run with the same hardcoded greeting.

**Complexity:** Low. Single text field, save to DB.

**Dependencies:** Per-page config table in DB, bot refactored to read welcome text from DB by page_id.

**Notes:**
- Character limit: Messenger welcome messages support up to 2000 characters. Enforce this in the UI with a counter.
- No markdown rendering needed — Messenger renders plain text only.

---

### 6. Per-Page Menu Structure Editor

**What:** A UI where the client edits menu labels and structure (top-level items, sub-items). Changes save to DB and the bot uses the stored structure to build quick reply flows.

**Why expected:** Menu labels are the navigation backbone of the bot. Every client will have different product categories. Without this editor, all Pages have the same menu labels regardless of business.

**Complexity:** Medium. The menu is a tree (up to 2 levels deep, constrained by Messenger limits). The UI must enforce: max 13 quick replies per level, max 20 characters per label, max 3 top-level persistent menu items.

**Dependencies:** Per-page menu config table in DB, bot refactored to build quick replies from DB config by page_id.

**Notes:**
- The persistent menu (hamburger menu) and the quick-reply menus served in-conversation are separate concepts. The editor should clearly distinguish them.
- Platform constraints are not negotiable — build them into the form validation (character counter, item count cap).
- Do not build a drag-and-drop visual flow builder in v1. A structured form with add/remove/edit fields is sufficient.

---

### 7. Per-Page Q&A Content Editor

**What:** A CRUD interface for managing Q&A content per Page. Clients can: create categories, add questions to categories, write answers, edit or delete existing entries. The bot reads this content from the DB (replacing the Obsidian vault) when serving answers.

**Why expected:** This is the primary content management function — the reason the admin panel exists. Without it, content updates require Obsidian vault access or code changes.

**Complexity:** Medium. Standard CRUD with a two-level hierarchy (category → questions). No rich text needed — plain text answers.

**Dependencies:** `qa_categories` and `qa_items` tables scoped to `page_id`, bot refactored to fetch answers from DB instead of vault.

**Notes:**
- Answer length limit: enforce ~2000 characters (Messenger max). Show a counter.
- Do not build answer versioning or draft/publish in v1. Save = live. Clients can always overwrite.
- Do not build import-from-vault in v1. Manual entry is fine for the initial client count.
- Category ordering matters for menu navigation — support manual reordering (up/down arrows, not drag-and-drop) in v1.

---

### 8. Per-Page Escalation Settings Editor

**What:** A form where the client sets: the admin PSID (the Facebook User ID of the person who receives escalation notifications), and the handoff message the bot sends to the user when escalating.

**Why expected:** Escalation is a v1.0 feature. The PSID and message were previously hardcoded in `.env`. Different Pages must have different escalation targets. Without this, all Pages escalate to the same person.

**Complexity:** Low. Two fields: PSID (string), handoff message (text).

**Dependencies:** Per-page config table in DB, bot reads escalation config from DB by page_id.

**Notes:**
- PSID validation is not easy (it's a large integer). Do not attempt to validate it via the API in v1 — document that the client must get it by having the admin send a message to the Page first.
- Warn clearly in the UI: "If this is wrong, escalations will silently fail."

---

### 9. DB-Backed Bot Config (Replaces Obsidian Vault)

**What:** The FastAPI backend reads bot configuration (welcome text, menu structure, Q&A, escalation settings) from the database by `page_id` on each request, instead of from Obsidian vault files.

**Why expected:** This is the architectural prerequisite for everything else in v1.2. Without it, the admin panel has nowhere to save its data and the bot cannot use it.

**Complexity:** Medium. DB schema design, migration from vault-based reads to DB reads in the FastAPI content router. The bot's `GOVI_AI_URL` calls change from vault endpoints to DB-backed endpoints.

**Dependencies:** Database (PostgreSQL or SQLite), ORM or raw queries, DB migrations.

**Notes:**
- The vault reader in `app/routers/content.py` is replaced entirely. The existing API contract (endpoint paths, response shape) should be maintained where possible to minimize bot changes.
- The `/content/reload` endpoint goes away — DB-backed content is always live.

---

### 10. Multi-Page Webhook Routing

**What:** The Node.js bot receives webhook events that include a `page_id` in each entry. It looks up the correct Page access token and config from the DB (via the FastAPI backend) using that `page_id`, then handles the event with the correct credentials and content.

**Why expected:** Without this, the bot can only serve one Page. It currently uses a single hardcoded `PAGE_ACCESS_TOKEN` from `.env`.

**Complexity:** Medium. The bot's webhook handler already loops over `entry` events — it needs to extract `entry.id` (the page_id) and route each event through a page-aware lookup.

**Dependencies:** DB-backed config (above), FastAPI endpoint to look up page token by page_id, bot refactor to remove hardcoded `PAGE_ACCESS_TOKEN`.

**Notes:**
- Token lookup should be cached in-process (a simple Map keyed by page_id) with a short TTL (e.g., 5 minutes) to avoid a DB call per message.
- If the page_id is not found (deleted or disconnected), drop the event and log it — do not throw.
- The webhook subscription must include the new page's `page_id` when a client connects a Page via OAuth. This means the FastAPI OAuth callback must also call the Graph API to subscribe the app to the new page's webhook fields.

---

## Differentiators

Features that are not expected by default but add meaningful value and differentiate this from a manually managed system.

---

### Token Health Monitoring

**What:** A status indicator on the Connected Pages dashboard showing whether the stored Page access token is still valid. Validated by making a lightweight Graph API call (e.g., `GET /me?fields=id,name`) on page load.

**Why valuable:** Page access tokens can be revoked by the user at any time via Facebook's App Settings. Without this, the bot silently fails to send messages and the client has no idea. A status badge (green/red) with a "Reconnect" button surfaces this immediately.

**Complexity:** Low. One API call per page load, cached for a few minutes.

---

### Content Change Preview (Simulated Conversation)

**What:** A read-only preview panel in the content editor that shows what the bot will say given the current saved config — a simplified simulation of the conversation flow for the current Page.

**Why valuable:** Clients editing menu labels and Q&A answers cannot easily tell how the changes will look in Messenger until they open Messenger and test. A preview reduces error and increases confidence.

**Complexity:** Medium. Not a live Messenger simulation — just rendering the menu tree and answer text in a chat bubble layout using the saved DB config.

**Not:** A live Messenger test (that requires actually messaging the Page). This is a static rendering only.

---

### Audit Log for Content Changes

**What:** A simple log of who changed what and when, per Page. Shown as a chronological list: "Admin changed welcome text on 2026-05-27."

**Why valuable:** When bot behavior changes unexpectedly, the client needs to know if a content change caused it. Without a log, debugging is guesswork.

**Complexity:** Low-Medium. An `audit_log` table with (tenant_id, page_id, user_id, action, timestamp, before_value, after_value). Write a log entry on every save. Display it in a settings page.

---

### Bulk Q&A Import from CSV

**What:** An upload endpoint that accepts a CSV file (columns: category, question, answer) and bulk-inserts Q&A items for a Page, replacing or merging with existing content.

**Why valuable:** Initial content setup via the CRUD form is tedious if a client has 50+ Q&A items. A CSV import reduces onboarding time from hours to minutes.

**Complexity:** Medium. CSV parsing, validation (max length per field, deduplication), preview before confirming import.

**Defer to v1.3** unless onboarding experience proves painful. Manual entry is fine for the first 2-3 clients.

---

## Anti-Features

Do not build these in v1.2. Rationale provided.

---

| Anti-Feature | Why Avoid | What to Do Instead |
|---|---|---|
| Self-service client registration | Opens the platform to arbitrary signups. For an internal tool serving a known set of clients, this adds spam risk and removes operator control. | Super-admin creates accounts manually. |
| Invitation emails | Adds SMTP/email service dependency (SendGrid, SES, etc.) and email deliverability concerns. Not worth it for a small number of clients. | Super-admin hands credentials to clients directly. |
| Multi-level user roles per tenant | "Admin within a tenant," "editor," "viewer" — not needed when each tenant is one person or a small team with identical access needs. | One role per tenant: `client`. All client users have full access to their own Pages. |
| Rich text / markdown in Q&A answers | Messenger renders plain text only. Markdown syntax would appear as literal characters to end users. | Plain text only, with character count. |
| Visual flow builder (drag-and-drop) | High implementation cost (React DnD or similar), high bug surface. For a tree with max 2 levels and 13 nodes, a form-based editor is sufficient. | Structured add/edit/delete form. |
| White-labeling / custom domain per tenant | Adds DNS, SSL cert management, and domain routing complexity. Not needed for this client count. | Single domain for all tenants. |
| Conversation inbox / live chat in the admin panel | Clients can already see and reply to conversations in the standard Facebook Page inbox. Duplicating it here is redundant and requires real-time infrastructure (websockets). | Direct clients to manage conversations in the Facebook Page inbox. |
| Analytics dashboard | Requires a data pipeline, aggregation queries, and charting. Facebook Page Insights provides basic volume data for free. | Add in v1.3 once content is stable. |
| Soft delete / content versioning | Adds complexity to queries and the editor. Save = live = current truth. | Rely on audit log (differentiator) for history. |
| Outbound / broadcast messaging | Requires Facebook App Review for `pages_messaging` with the broadcast use case, plus 24-hour window enforcement and opt-in management. Regulatory minefield. | Respond-only. All conversations user-initiated. |

---

## Feature Dependencies

```
Super-Admin Account Creation
        |
        v
Client Login (JWT + tenant context)
        |
        v
Facebook Page OAuth Connection
        |
        +----> Connected Pages Dashboard
        |               |
        |               v
        |       Token Health Monitor (differentiator)
        |
        +----> DB-Backed Config Store
                        |
                        +----> Welcome Text Editor
                        |
                        +----> Menu Structure Editor
                        |
                        +----> Q&A Content Editor
                        |               |
                        |               +----> Bulk CSV Import (differentiator, defer)
                        |
                        +----> Escalation Settings Editor
                        |
                        v
                Multi-Page Webhook Routing (bot layer)
```

**Critical path:** Auth → OAuth → DB Schema → Bot page-awareness. Everything else is content editing UI layered on top of that foundation.

---

## Messenger Platform Constraints Affecting Admin UI Design

These are hard limits from the Facebook platform, not UX preferences. Build them into form validation.

| Constraint | Limit | Admin UI Impact |
|---|---|---|
| Quick replies per message | 13 max | Menu level item count cap — enforce in editor |
| Quick reply label length | 20 characters | Character counter + hard trim in editor |
| Persistent menu top-level items | 3 max | Top-level menu section cap |
| Persistent menu nested items | 5 max per level | Sub-item count cap |
| Message text length | 2000 characters | Welcome text and answer character limit |
| Page access token | Long-lived but revocable | Token health check needed |
| App Review required for `pages_messaging` | Required for non-app-role users | All clients must be Tester/Developer on the FB App during development; full App Review needed before production launch |

---

## MVP Recommendation for v1.2

Build in this order:

1. **Auth foundation** — super-admin creates client, client logs in, JWT with tenant_id
2. **DB schema** — tenants, pages, page_config, qa_categories, qa_items, escalation_config
3. **Facebook OAuth** — connect Page, store token, list connected Pages
4. **Bot page-awareness** — webhook routing by page_id, token lookup from DB
5. **Welcome text editor** — simplest content field, proves the DB → bot pipeline works
6. **Escalation settings editor** — fixes an existing pain point (currently hardcoded per-env)
7. **Q&A content editor** — replaces vault entirely, main content management function
8. **Menu structure editor** — most complex content form, build last

**Defer to v1.3:**
- Token health monitoring
- Content change preview
- Audit log
- Bulk CSV import

---

## Sources

- Meta Permissions Reference: https://developers.facebook.com/docs/permissions/
- Meta Pages API: https://developers.facebook.com/docs/pages-api/
- Meta Access Token Guide: https://developers.facebook.com/docs/facebook-login/guides/access-tokens/
- WorkOS multi-tenant RBAC guide: https://workos.com/blog/how-to-design-multi-tenant-rbac-saas
- Logto multi-tenant SaaS implementation guide: https://blog.logto.io/build-multi-tenant-saas-application
- Chatfuel multi-page connection pattern (industry reference): https://saleshive.com/vendors/chatfuel/
- Facebook App Review for bots: https://respond.io/blog/skip-facebook-bot-verification
- Meta Messenger App Review: https://developers.facebook.com/docs/messenger-platform/app-review/
- UX account switcher patterns: https://medium.com/ux-power-tools/breaking-down-the-ux-of-switching-accounts-in-web-apps-501813a5908b
