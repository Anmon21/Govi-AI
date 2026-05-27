# Pitfalls Research — v1.2 Admin Panel & Multi-Page Support

**Project:** Govi Facebook Messenger Customer Support Bot
**Domain:** Adding multi-tenant admin panel + Facebook OAuth Page connection + DB-backed content to an existing single-page rule-based Messenger bot
**Researched:** 2026-05-27
**Overall confidence:** HIGH (platform constraints are well-documented; SQLite/Node.js multi-tenant patterns are well-established engineering problems)

---

## Critical Pitfalls

Mistakes that cause rewrites or major incidents.

---

### Pitfall 1: Page Access Token Derived from User Token — Invalidated When Admin Loses Page Role

**What goes wrong:** The Facebook OAuth flow for connecting a Page yields a Page Access Token that is derived from the connecting user's access token. That user must hold an admin, editor, or moderator role on the Page. If they later lose that role, revoke the app's permissions, change their Facebook password, or the user account is disabled, the stored Page Access Token becomes invalid immediately. The bot silently stops sending messages — Facebook returns error code `190` (OAuthException) inside an HTTP 200 response body, which the current `sendMessage` implementation does not catch.

**Why it happens:** The stored token is not a permanent credential — it is a capability tied to a specific human's relationship with both the Page and the Facebook App. Developers store it as if it were a static API key and never implement token health checks.

**Consequences:** The bot goes dark for that client's Page. No alert is raised because Facebook Graph API errors are in the response body (HTTP 200), not as HTTP errors. Admins don't notice until customers complain. The only fix is to have the client re-authenticate via OAuth.

**Prevention:**
- Implement a token health-check job that calls `GET /{page-id}?access_token={token}` once per hour for each stored token. If it returns error code 190, mark the Page as `token_invalid` in the DB and alert the tenant via the admin panel.
- Show a "Page Disconnected — Reconnect" banner in the admin panel when token status is `invalid`.
- Store the `user_id` that granted the token so you can identify which user needs to re-authorize.
- Prefer system-user tokens via Meta Business Manager for production deployments where a human page admin leaving shouldn't break the integration — but this requires Meta Business Manager setup.

**Detection:** Error code `190` or `463` in Graph API response bodies; `pages_messaging` permission absent in token debug response.

**Phase to address:** Phase 1 of v1.2 (OAuth flow implementation — build health check alongside token storage, not after).

---

### Pitfall 2: Short-Lived User Token Stored Instead of Long-Lived Page Token

**What goes wrong:** The Facebook OAuth callback returns a short-lived user access token (valid ~1–2 hours). From this token you must exchange to a long-lived user token (60 days) and then call `/{user-id}/accounts` to get the long-lived Page Access Token (no expiry). If you store the short-lived token directly (or store the intermediate 60-day token), Page calls start failing within hours or days with no obvious error.

**Why it happens:** OAuth guides often stop at step 1 (the initial code exchange). The 3-step process (short-lived user → long-lived user → Page token) is under-documented. Developers test immediately after OAuth, see it working, and ship. Failure surfaces after the initial valid period.

**Consequences:** Stored tokens expire. The bot fails for all clients who connected their pages. Full re-authentication required for every client.

**Prevention:**
- The token exchange pipeline must be: `code → short-lived user token → long-lived user token (60-day) → /{user-id}/accounts → long-lived Page Access Token`.
- Never store the short-lived token or the intermediate user token. Store only the Page Access Token returned from `/{user-id}/accounts`.
- Verify by calling `GET /debug_token?input_token={token}&access_token={app_id}|{app_secret}` before persisting — check `expires_at` in the response. A Page Token from a long-lived user token should return `expires_at: 0` (non-expiring).
- Log the `token_type` and `expires_at` fields in the DB alongside the token for debugging.

**Detection:** `expires_at` field in DB is non-zero; token debug returns `data.expires_at > 0`.

**Phase to address:** Phase 1 of v1.2 (OAuth callback handler).

---

### Pitfall 3: Not Calling `/{page-id}/subscribed_apps` After OAuth — Bot Receives No Webhook Events for the New Page

**What goes wrong:** Storing the Page Access Token is not enough. For each new Page connected via OAuth, you must explicitly call `POST /{page-id}/subscribed_apps?subscribed_fields=messages,messaging_postbacks&access_token={page_token}` to subscribe the Page to your Facebook App's webhook. Without this call, the webhook URL receives zero events for that Page even though the token is valid and the app-level webhook is configured.

**Why it happens:** The separation between "having a Page token" and "subscribing the Page to the app webhook" is non-obvious. App-level webhook configuration in the Facebook App Dashboard only registers the callback URL and verify token — it does not automatically subscribe all authorized Pages.

**Consequences:** The bot appears to work (token is valid, can call Graph API), but incoming Messenger messages never arrive. The issue is invisible until a customer sends a test message and gets no response.

**Prevention:**
- After successfully storing a Page Access Token, immediately call `POST /{page-id}/subscribed_apps` with `subscribed_fields=messages,messaging_postbacks` using the page token.
- Log the subscription response and store `webhook_subscribed: true` in the DB per Page record.
- Add a health-check that calls `GET /{page-id}/subscribed_apps` to verify the subscription is still active.
- The required fields for a Messenger bot are: `messages`, `messaging_postbacks`. Add `messaging_optins` if opt-in flows are used.

**Detection:** Zero incoming webhook events after connecting a Page; `GET /{page-id}/subscribed_apps` returns empty data or does not include your app.

**Phase to address:** Phase 1 of v1.2 (OAuth callback — subscription call must be atomic with token storage).

---

### Pitfall 4: Missing `entry.id` Routing — All Pages Share One Bot Instance But Only One Page Gets Handled Correctly

**What goes wrong:** The current bot uses a module-level constant `PAGE_ACCESS_TOKEN` loaded from env at startup. When multiple Pages send webhooks to the same endpoint, each event's `entry.id` identifies which Page it came from, but the bot uses the same token for all responses. Events from Page B are processed using Page A's token, which makes Graph API calls fail or return wrong data.

**Why it happens:** The single-page assumption is baked into every function (`sendMessage`, `fetchUserName`, `passThreadControl`, `sendTypingIndicator`, `setupMessengerProfile`). All of them hardcode `PAGE_ACCESS_TOKEN`. Refactoring to multi-page requires threading the correct token through every function call.

**Consequences:** Messages sent to Page B's users arrive appearing to come from Page A (or fail entirely). `fetchUserName` fetches from wrong page graph context. `setupMessengerProfile` called at startup (line 532 of `index.ts`) runs against whichever token was last loaded — overwriting all other pages' persistent menus.

**Prevention:**
- Route on `entry.id` (the Page ID) at the top of the webhook POST handler: `const pageId = entry.id`.
- Look up the Page record from DB using `pageId` to get the correct `pageToken`, `content`, and `config`.
- Thread `pageToken` as a parameter through every downstream function (`sendMessage(recipientId, text, { pageToken })`) — do not use a global constant.
- Eliminate the module-level `PAGE_ACCESS_TOKEN` constant entirely. Fail fast on startup only if no pages exist in the DB.
- The `setupMessengerProfile` call on startup (line 532) must be removed from the startup path entirely — per-page profile setup should run on demand when a Page is connected via OAuth.

**Detection:** Log the `entry.id` and token source on each webhook — verify they match.

**Phase to address:** Phase 2 of v1.2 (multi-page bot refactor — the single largest structural change in this milestone).

---

### Pitfall 5: Cross-Tenant Data Leak — Forgetting `tenant_id` Filter on One DB Query

**What goes wrong:** With a multi-tenant SQLite schema, every query that reads per-tenant data (Pages, Q&A content, escalation settings, etc.) must include a `WHERE tenant_id = ?` clause using the value from the authenticated JWT, not from a client-supplied parameter. If even one endpoint omits this filter — a common mistake when adding endpoints under time pressure — Tenant A can read Tenant B's page configuration, Q&A content, or Page Access Tokens.

**Why it happens:** SQL queries are written manually; there is no automatic filter enforcement like PostgreSQL RLS or an ORM scope. The responsibility falls on each developer writing each query. Background jobs, list endpoints added after MVP, and admin "view all" endpoints are the most common places this filter is forgotten.

**Consequences:** Information disclosure: page tokens, Q&A content, client email addresses, escalation PSIDs. If page tokens are exposed, a bad actor can send messages from a client's Page. This is a security incident requiring client notification.

**Prevention:**
- Never trust `tenant_id` from the request body or URL parameters. Always extract it from the verified JWT payload server-side.
- Use a query-builder wrapper or repository layer that automatically appends `tenant_id` — do not scatter raw SQL with `WHERE tenant_id = ?` throughout request handlers.
- Write a test for every API endpoint that: (a) authenticates as Tenant A, (b) attempts to read a resource belonging to Tenant B using a known ID, and (c) asserts a 404 or 403.
- Super-admin endpoints that intentionally bypass tenant scoping must be clearly marked and require a separate `super_admin` role claim in the JWT — not just checking `isAdmin`.

**Detection:** Automated IDOR tests per endpoint; code review checklist item: "Does this query filter by tenant_id from JWT?"

**Phase to address:** Phase 1 of v1.2 (DB schema design — tenant_id enforcement must be a first-class constraint from the start, not retrofitted).

---

## Moderate Pitfalls

---

### Pitfall 6: Facebook App Review Gate Blocks Production Launch for `pages_messaging`

**What goes wrong:** The `pages_messaging` permission is an advanced permission requiring Meta App Review before it can be used by users outside your app's development team. In Development Mode, only app admins, developers, and test users can use the bot. Once you build the admin panel and start onboarding real clients (who are not in your Facebook App's developer console), they hit a permissions wall — they can grant OAuth access but messages won't go through.

**Why it happens:** Building the admin panel and OAuth flow is straightforward to test internally (where the developer IS an app admin). The App Review blocker only surfaces when you try to add real external clients.

**Consequences:** The entire multi-tenant admin panel is built but cannot be used by real clients until App Review is approved (timeline: typically 5-7 business days if submission is clean; can be longer if rejected and resubmitted).

**Prevention:**
- Submit App Review for `pages_messaging` and `pages_manage_metadata` early — ideally before or in parallel with admin panel development, not after.
- During development, add each test client as a Test User or Developer role in the Facebook App dashboard.
- Prepare the App Review submission materials (demo video, test credentials, use-case description) as part of the phase that implements OAuth flow, not as a separate afterthought.
- Review requirement: `pages_messaging` requires demonstrating valid customer service use case and compliance with Messenger policy.

**Detection:** OAuth succeeds but message sends return `permissions error` or `application does not have permission` for external users.

**Phase to address:** Phase 1 of v1.2 (flag as external dependency with lead time; do not wait until feature-complete to start review).

---

### Pitfall 7: OAuth `state` Parameter Missing — CSRF Vulnerability in Page Connection Flow

**What goes wrong:** The Facebook OAuth flow redirects users to a callback URL with a `code` parameter. Without a cryptographically random `state` parameter that is verified on callback, a CSRF attack can cause a tenant to connect an attacker-controlled Facebook Page to their account instead of their own. The attacker initiates the OAuth flow, captures the authorization URL with their code, and tricks the victim into completing the callback.

**Why it happens:** The `state` parameter is optional in the OAuth spec. Many quick-start implementations omit it. The attack surface is real but requires a targeted social engineering step, so it often goes unmitigated in internal tools.

**Consequences:** An attacker can link their Page token to a legitimate tenant's account. The tenant's admin panel now manages the attacker's Page instead of their own.

**Prevention:**
- Generate `crypto.randomBytes(32).toString('hex')` as the state value.
- Store it in the user's server-side session (not in a cookie accessible to JS) before redirecting to Facebook.
- On callback, verify `req.query.state === session.oauthState` before processing the `code`.
- Invalidate the state after use (one-time use).

**Detection:** OAuth callback handler that processes `code` without checking `state`.

**Phase to address:** Phase 1 of v1.2 (OAuth implementation).

---

### Pitfall 8: SQLite Concurrent Writers From Two Processes — "Database Is Locked" Errors

**What goes wrong:** The architecture runs Node.js (bot + admin API) and Python FastAPI as separate processes sharing a single SQLite file. SQLite allows only one writer at a time. If the FastAPI content router and the Node.js admin API attempt to write simultaneously (e.g., a content save during a bot webhook that writes a cache timestamp), one writer gets `SQLITE_BUSY` ("database is locked") and the operation fails.

**Why it happens:** SQLite is designed for embedded single-process use. Multi-process write contention on the same file is a known limitation. WAL mode helps (allows concurrent reads alongside one writer) but does not eliminate write contention between processes.

**Consequences:** Admin panel content saves fail intermittently during high-traffic bot operation. The failure is non-deterministic and hard to reproduce in development (where traffic is low). In production, it causes lost admin edits with no user-facing error if the error is not surfaced.

**Prevention:**
- Enable WAL mode immediately on DB connection: `PRAGMA journal_mode = WAL`.
- Set a `busy_timeout` on both connections: `PRAGMA busy_timeout = 5000` (5 seconds). This causes the writer to retry rather than failing instantly.
- Designate a single writer process: route all DB writes through the Node.js process (admin API). FastAPI reads content from DB but does not write. This eliminates write contention.
- If FastAPI must write (e.g., content reload triggers), use an HTTP endpoint on the Node.js side rather than direct DB write from Python.

**Detection:** `SQLITE_BUSY` or `database is locked` errors in logs during load; intermittent admin save failures.

**Phase to address:** Phase 1 of v1.2 (DB setup — pragmas must be set before any multi-process access).

---

### Pitfall 9: In-Memory `userNameCache` and `lastMessageCache` Are Not Page-Scoped

**What goes wrong:** The current bot maintains `userNameCache` and `lastMessageCache` as `Map<string, string>` keyed by sender PSID. In a multi-page setup, the same PSID can belong to a user who has messaged different Pages — and more importantly, the caches now hold state for all pages mixed together with no page scoping. A restart clears all state across all pages simultaneously.

**Why it happens:** The caches were designed for a single-page bot. Adding multi-page support without updating the cache key causes PSID collisions if the same user messages two different Pages (PSIDs are page-scoped in Facebook's model, but within one user's Facebook account, they could message two of your managed Pages with different PSIDs — the issue is correctness of the map structure, not collision).

**Prevention:**
- Key the caches by `${pageId}:${psid}` instead of just `psid`. This ensures per-page isolation.
- Document explicitly that these caches are lost on restart — acceptable for this project.
- Do not persist these caches to DB unless there is a specific product requirement (v1.1 explicitly chose in-memory as sufficient).

**Detection:** After restart, all users are greeted with the generic welcome message rather than their name — expected and documented behavior.

**Phase to address:** Phase 2 of v1.2 (multi-page bot refactor).

---

### Pitfall 10: `setupMessengerProfile` Called at Bot Startup — Overwrites All Pages' Persistent Menu

**What goes wrong:** The current `setupMessengerProfile()` is called at Express startup (line 532 of `index.ts`) using the single `PAGE_ACCESS_TOKEN` env var. In a multi-page world with per-page menu configuration stored in DB, calling this function at startup would either: (a) fail because `PAGE_ACCESS_TOKEN` no longer exists, or (b) be called with the wrong token, overwriting a client's customized persistent menu with a hardcoded default.

**Why it happens:** Startup-time profile setup was fine for a single-page bot. The design assumption breaks when the bot becomes config-driven.

**Consequences:** A client's customized persistent menu labels (set via the admin panel) get silently overwritten by hardcoded defaults every time the bot process restarts.

**Prevention:**
- Remove `setupMessengerProfile()` from the startup path entirely.
- Call it on demand: (1) when a new Page is connected via OAuth, and (2) when a tenant saves changes to their menu configuration in the admin panel.
- The content editor save endpoint should trigger a `setupMessengerProfile` call using that Page's token and the new config values.

**Detection:** Persistent menu labels reverting to defaults after bot restarts.

**Phase to address:** Phase 2 of v1.2 (multi-page bot refactor) — remove from startup; Phase 3 (admin panel content editor) — trigger on save.

---

### Pitfall 11: Vault-to-DB Migration Breaks FastAPI Content Router Without a Transitional State

**What goes wrong:** The existing FastAPI `content.py` router reads from the Obsidian vault (`_vault` global dict, loaded at startup, reloaded via `POST /content/reload`). When the bot switches to reading content from SQLite, there is a window during migration where either: (a) the FastAPI router still reads from vault but the DB is not yet populated, or (b) the bot is configured to hit DB routes that don't exist yet.

**Why it happens:** The migration is treated as a big-bang switch rather than a parallel-run with a cutover. If the existing vault route goes down before the DB route is functional, the bot's `sendCategoryMenu` / `sendAnswer` calls start returning 500s.

**Consequences:** During migration, customers receive "Something went wrong" error messages and fallback menus. Bot is degraded for the duration of the migration.

**Prevention:**
- Use expand-then-contract: (1) add new DB-backed content endpoints alongside existing vault endpoints, (2) populate the DB with all current vault content, (3) switch bot to call new endpoints, (4) only then deprecate vault endpoints.
- Keep `POST /content/reload` functional until the vault router is officially removed — it's the existing hot-reload mechanism clients may depend on.
- Write a one-time migration script that reads vault files and inserts them into the DB with the same IDs, so that `CATEGORY:`, `QUESTION:` payload IDs in existing Messenger conversations remain valid after cutover.

**Detection:** Bot returning `sendApologyWithMenu` fallbacks during content fetch; FastAPI returning 404 or 500 on content endpoints.

**Phase to address:** Phase 3 of v1.2 (content DB layer) — migration script required before vault retirement.

---

## Minor Pitfalls

---

### Pitfall 12: JWT Secret Shared Between Admin API and Bot Process — Over-broad Token Acceptance

**What goes wrong:** If the admin panel JWT secret and the internal bot service authentication use the same secret (or the bot has no token validation at all), a token issued by the admin panel for a tenant user could theoretically be replayed against internal bot endpoints. More practically: if `jwtSecret` is hardcoded or predictable (e.g., `"secret"`, `"changeme"`), all JWT security is void.

**Prevention:** Generate a random 256-bit JWT secret in `.env`. Do not share it in code or commit it to git. Validate JWT on every admin API request — not just on login.

**Phase to address:** Phase 1 of v1.2 (auth setup).

---

### Pitfall 13: React Admin Panel Calling Backend With `tenant_id` in Request Body — Trusting the Client

**What goes wrong:** A common shortcut is including `tenant_id` as a field in request bodies sent from the React frontend. The backend uses this field to scope data. A user with basic browser devtools can change their tenant_id and read another tenant's data.

**Prevention:** Never accept `tenant_id` from the request body for scoping. Extract it exclusively from the verified JWT payload server-side. The frontend does not need to send it.

**Phase to address:** Phase 2 of v1.2 (admin API implementation).

---

### Pitfall 14: React Dev Proxy Port Conflicts With Existing Services

**What goes wrong:** The existing bot runs on port 3000 and FastAPI on port 8000. Vite's default dev server is also port 5173. If React's Vite proxy is misconfigured to target the wrong port for the admin API, API calls silently go to the wrong service (e.g., the Messenger bot's Express server), which returns 404s that are easy to misdiagnose as CORS issues.

**Prevention:** Assign distinct ports: bot on 3000, FastAPI on 8000, admin API (if separate) on 3001 or serve admin API from the bot's Express server on a `/admin` prefix. Document all ports in `.env.example`. Vite proxy should explicitly target the admin API port, not the bot port.

**Detection:** Admin API calls returning HTML or unexpected 404s; Express bot logs showing unexpected `/api/...` requests.

**Phase to address:** Phase 2 of v1.2 (React admin panel setup).

---

### Pitfall 15: Escalation `ADMIN_PSID` Is Now Per-Page — Global Env Var Breaks for Multiple Clients

**What goes wrong:** The current `handleEscalation` reads `process.env.ADMIN_PSID` as a single global value. In a multi-page setup, each client has their own admin PSID for their Page's inbox. Using a global env var means all escalations route to the original admin's Messenger, not the client's designated agent.

**Prevention:** Store `admin_psid` per Page record in the DB alongside the Page Access Token and content config. The `handleEscalation` function must accept the page config as a parameter, not read from `process.env`.

**Phase to address:** Phase 2 of v1.2 (multi-page bot refactor).

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| OAuth flow implementation | Short-lived token stored; `state` CSRF skipped; `subscribed_apps` call missing | 3-step exchange; crypto state in session; subscription call atomic with token store |
| Token storage schema | No token health-check; no invalidation status | Store `token_status`, `token_granted_by_user_id`, `webhook_subscribed` columns; hourly health-check job |
| App Review gating | External clients blocked until `pages_messaging` approved | Submit App Review in parallel with development; add test clients as Developer roles immediately |
| Multi-page webhook routing | `PAGE_ACCESS_TOKEN` global constant used for all pages | Route on `entry.id`; thread `pageToken` through all functions; remove startup `setupMessengerProfile` |
| Multi-page state caches | `userNameCache`/`lastMessageCache` not page-scoped | Key as `${pageId}:${psid}` |
| DB multi-tenant design | Missing `WHERE tenant_id = ?` on any single endpoint | Repository layer enforcing tenant scope; IDOR test per endpoint |
| SQLite multi-process access | Write contention causing `SQLITE_BUSY` | WAL mode + `busy_timeout = 5000`; single-writer process rule |
| Vault-to-DB content migration | Bot goes dark during migration window | Expand-then-contract; migration script preserving IDs; parallel endpoints before cutover |
| Per-page persistent menu setup | `setupMessengerProfile` at startup overwrites DB-configured menus | Remove from startup; call on OAuth connect and on admin content save |
| Admin panel client data isolation | `tenant_id` trusted from request body | JWT-only tenant scoping; frontend never sends tenant_id |
| Escalation settings per page | Global `ADMIN_PSID` env var routes all escalations to single inbox | Per-page `admin_psid` in DB; passed as config parameter to `handleEscalation` |
| JWT security | Weak secret; tokens not validated on every request | Random 256-bit secret; middleware validates on all admin routes |

---

## Sources

- Existing codebase: `messenger-bot/src/index.ts` (direct code inspection — HIGH confidence)
- Meta Developers: Access Tokens Guide — https://developers.facebook.com/docs/facebook-login/guides/access-tokens/ (HIGH confidence)
- Meta Developers: Long-Lived Token Exchange — https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived/ (HIGH confidence)
- Meta Developers: Webhooks for Pages / `subscribed_apps` endpoint — https://developers.facebook.com/docs/graph-api/webhooks/getting-started/webhooks-for-pages/ (HIGH confidence)
- Meta Developers: Messenger Profile API (per-page operation confirmed) — https://developers.facebook.com/docs/messenger-platform/reference/messenger-profile-api/ (HIGH confidence)
- Meta Developers: Facebook Login Manual Flow / state parameter — https://developers.facebook.com/documentation/facebook-login/guides/advanced/manual-flow (HIGH confidence)
- Multi-tenant SaaS data isolation patterns — https://medium.com/@instatunnel/multi-tenant-leakage-when-row-level-security-fails-in-saas-da25f40c788c (MEDIUM confidence)
- Multi-tenant React SPA patterns — https://marmelab.com/blog/2022/12/14/multitenant-spa.html (MEDIUM confidence)
- better-sqlite3 WAL mode and concurrency — https://deepwiki.com/WiseLibs/better-sqlite3/3.4-wal-mode-and-performance-tuning (HIGH confidence — official library documentation)
- SQLite concurrent writes — https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/ (HIGH confidence)
- OWASP Multi-Tenant Security Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html (HIGH confidence)
- Auth0: OAuth State Parameter — https://auth0.com/docs/secure/attack-protection/state-parameters (HIGH confidence)
- Facebook community thread on token community invalidation — https://developers.facebook.com/community/threads/587797631846246/ (MEDIUM confidence)
