# Phase 14: Bot Multi-Page Routing - Context

**Gathered:** 2026-07-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Convert the Node.js Messenger bot from a single-page process (one hardcoded `FACEBOOK_PAGE_ACCESS_TOKEN`) into a page-aware router. For every inbound webhook event, the bot resolves the correct Page's access token and content from FastAPI using the Page ID on the event, and isolates per-user state (user name, last message) per Page. The `PAGE_ACCESS_TOKEN` global is removed from all runtime code in the bot.

**In scope:** replace `PAGE_ACCESS_TOKEN` usage in `messenger-bot/src/index.ts` at all 7 call sites (`fetchUserName`, `sendMessage`, `passThreadControl`, `sendTypingIndicator`, and the outbound content/OAuth helpers), thread Page ID through the webhook handler, page-scope the in-memory caches, and add a user-visible fallback when the internal FastAPI lookup fails.

**Out of scope:** FastAPI-side Messenger profile installation on OAuth completion (see Deferred), Phase 13 DB-backed content contract itself (Phase 14 only consumes it), UI/admin panel work.

</domain>

<decisions>
## Implementation Decisions

### Token fetch cadence
- **D-01:** The bot fetches the Page access token from `GET /internal/pages/{page_fb_id}/access-token` on **every webhook event** — no in-process token cache. Simplicity and always-fresh tokens win over shaving 5–20ms per event. Token rotation is handled implicitly.

### Per-page cache key scheme
- **D-02:** `userNameCache` and `lastMessageCache` remain single `Map<string, ...>` instances keyed by the **composite string `${pageFbId}:${psid}`**. Callers build the key at each read/write site. No nested maps, no side-tables. This is the minimal-change scheme and matches how the existing code already treats these Maps.

### Content endpoint page-scoping
- **D-03:** The bot passes Page ID to FastAPI content endpoints as a **query parameter**: `/content?type=category&page_id=<pageFbId>` and `/content/{content_id}?page_id=<pageFbId>`. Phase 13 must accept `page_id` as a required query param on all content endpoints. Rationale: preserves existing URL shape, keeps `page_id` in the same visibility class as the existing `type`/`category` filter params, and is trivially testable via curl.

### Fallback UX when FastAPI is unreachable
- **D-04:** When the internal token endpoint (or a content endpoint) fails for a given Page ID, the bot **silently retries once with a ~500ms backoff**, then sends a **generic apology message** to the user: something like "Sorry, we're having trouble right now. Please try again in a moment." No menu quick replies are attached (we don't know the Page's menu). Errors are logged server-side. The bot process must not crash.

### Messenger profile installation
- **D-05:** The bot's boot-time `setupMessengerProfile()` call is **removed entirely** in Phase 14 — this is the last remaining `PAGE_ACCESS_TOKEN` runtime call site. Per-Page profile installation (persistent menu, greeting, Get Started button) becomes the responsibility of the FastAPI OAuth callback (`app/routers/pages.py` `_store_pages_and_subscribe`). See Deferred for the FastAPI-side follow-up.

### Claude's Discretion
- Exact wording of the fallback apology message — copy is not load-bearing; match tone of existing `sendApologyWithMenu`.
- Exact HTTP client retry mechanism (naive `await new Promise(...); retry` vs a helper) — implementer's choice.
- Whether to introduce a small `pageContext` object (`{ pageFbId, accessToken }`) that gets threaded through `handleWebhookEvent`, or to pass `pageFbId` + fetch-token-inside-each-sender. Prefer whatever keeps the diff small and readable.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope + roadmap
- `.planning/ROADMAP.md` §"Phase 14: Bot Multi-Page Routing" — goal, requirements, success criteria
- `.planning/REQUIREMENTS.md` — BOT-01, BOT-02, BOT-03 definitions

### Prior-phase artifacts (contracts this phase consumes)
- `app/routers/pages.py:245` — `GET /internal/pages/{page_fb_id}/access-token` endpoint (Phase 12) with `X-Internal-Key` HMAC auth via `settings.internal_secret`. This is the token-fetch endpoint the bot uses on every event.
- `.planning/phases/12-page-connection-api-facebook-oauth/12-02-PLAN.md` — original design of the internal endpoint
- `app/config.py` — `internal_secret` setting the bot must be given (mirror as `INTERNAL_SECRET` in `messenger-bot/.env`)

### Prior-phase artifacts (contracts Phase 14 depends on but does NOT block)
- `.planning/phases/13-*` — **Not yet created.** Phase 13 will change `/content` to be DB-backed and must accept `page_id` as a required query param (D-03 above). Phase 14 planner should coordinate this contract with Phase 13 planner or gate execution on Phase 13 completion.

### Codebase context maps
- `.planning/codebase/ARCHITECTURE.md` — two-service split, stateless request path
- `.planning/codebase/CONVENTIONS.md` — TypeScript/Python style, error-handling patterns (SEC-03 token-safe logging)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `messenger-bot/src/index.ts` `handleWebhookEvent(event)` — already the single entry point for all events. Page ID is available as `entry.id` in the outer webhook loop (`body.entry[].id`) and needs to be threaded into `handleWebhookEvent(event, pageFbId)`.
- `messenger-bot/src/index.ts` `sendApologyWithMenu` — existing pattern for "graceful degradation to user + main menu". The new fallback for FastAPI-unreachable uses the same idea but without the menu (D-04).
- `app/routers/pages.py` `get_internal_page_access_token` (line 245) — already exists, exact shape the bot needs. Returns `{"access_token": "<plain>"}`. Uses `hmac.compare_digest` on `X-Internal-Key`.
- `axios` HTTP client is already the standard bot HTTP client — reuse for the internal token fetch.

### Established Patterns
- **SEC-03 token-safe error logging** — never `console.error(err)` on axios errors; log `err.message` + `err.response?.data` only. Applies to the new internal-fetch call site too, because the URL contains no token but the response body will.
- **Per-event try/catch** (Phase 6, DEBT-02) — `handleWebhookEvent` is already wrapped in a per-event `try/catch` at `messenger-bot/src/index.ts:107`. Any new throws from the token-fetch path get caught there; user-facing fallback should happen inside `handleWebhookEvent`, not at the outer catch.
- **`sendMessage` swallows its own errors** — nested error paths (e.g., "the apology send itself fails") already just log and continue; keep that pattern.

### Integration Points
- `body.entry[].id` from the webhook payload → threads into `handleWebhookEvent(event, pageFbId)` → composite cache keys + token fetch parameter.
- `messenger-bot/.env` — adds `INTERNAL_SECRET` (must match FastAPI `settings.internal_secret`) and `GOVI_AI_URL` (already present). Removes `FACEBOOK_PAGE_ACCESS_TOKEN`.
- `messenger-bot/.env.example` — mirror the changes above so the docs stay accurate.

### Call sites of `PAGE_ACCESS_TOKEN` to update (7 total)
`messenger-bot/src/index.ts` lines 14, 126, 155, 181, 207, 517. Success criterion #2 requires zero references in runtime code after the phase; test files (`debt-fixes.test.ts`, `sendMessage.test.ts`) will need updates to inject a per-call token instead of a module-level env var.

</code_context>

<specifics>
## Specific Ideas

- The user's exact ordering: token fetch simplicity beats caching complexity. Prefer "fetch every event, always fresh" even at the cost of one extra HTTP hop per event.
- Composite key `${pageFbId}:${psid}` is preferred over structural nesting because it is the smallest diff to existing code.
- Query-param page routing (D-03) is the format Phase 13 must design its endpoints to accept.

</specifics>

<deferred>
## Deferred Ideas

- **FastAPI-side per-Page Messenger profile installation** — When a client completes OAuth and their Pages are stored (`_store_pages_and_subscribe` in `app/routers/pages.py`), the callback should call the Graph API `/{page_fb_id}/messenger_profile` to install the persistent menu, greeting, and Get Started button using the fresh page token. This replaces the removed bot-side `setupMessengerProfile()` and is a small addition to the Phase 12 OAuth flow. Belongs in either a hot-patch to Phase 12 or a new small phase (e.g., Phase 14.5 / Phase 15 prerequisite). Do not scope-creep into Phase 14 itself — Phase 14 only removes the bot-side call.
- **Long-lived token cache with invalidation** — rejected for now (D-01) but if per-event latency ever becomes an issue in production, revisit with a short TTL cache.
- **Nested/enumerable per-page state** — rejected (D-02); if a "disconnect Page → clear all its user state" feature is ever needed, revisit key scheme.

</deferred>

---

*Phase: 14-bot-multi-page-routing*
*Context gathered: 2026-07-21*
