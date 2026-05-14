# Phase 1: Security + Bot Foundation - Context

**Gathered:** 2026-05-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix the 3 broken security issues in the existing webhook handler, then wire the structural bot skeleton: Get Started postback, persistent hamburger menu, and fallback handler for free text. Phase ends when the bot is secure and navigationally complete — customers can open it, see a welcome, use the persistent menu, and never hit a silent dead end. No Q&A content or escalation logic in this phase.

</domain>

<decisions>
## Implementation Decisions

### Fallback Message
- **D-01:** Tone is friendly and helpful — the message acknowledges the user and redirects without friction (e.g., "I work best with the buttons below — here's what I can help with:")
- **D-02:** Quick replies accompanying the fallback message mirror the top-level persistent menu items — consistent navigation, no dead end

### Webhook Security (App Secret)
- **D-03:** Write HMAC-SHA256 signature verification code now (SEC-01), but gate it: when `FACEBOOK_APP_SECRET` is not set in env, skip verification and log a warning — bot remains functional for local development without Facebook setup
- **D-04:** User does not have `FACEBOOK_APP_SECRET` yet — planner must document where to find it (Facebook Developer Dashboard → App Settings → Basic → App Secret) and add it to `messenger-bot/.env.example`

### Welcome Message + Persistent Menu
- **D-05:** Claude's discretion — user did not specify welcome message text or persistent menu item labels. Use sensible defaults appropriate for an e-commerce support bot: welcome message should be warm and brief, persistent menu items should reflect the 2 main capabilities (Product Help and Contact Human) plus a third item if appropriate. Labels must be ≤20 characters. These are placeholder copy — user can adjust before going live.

### Security Fixes (all required, no discretion)
- **D-06:** SEC-01 (HMAC verification) — requires `express.raw()` middleware mounted BEFORE `express.json()` so the raw body is available for signature computation
- **D-07:** SEC-02 (Graph API error detection) — after every `axios.post` to Graph API, check `response.data.error` and log it; do not rely on HTTP status alone
- **D-08:** SEC-03 (token leak in logs) — log only `err.message` and `err.response?.data` in catch blocks, never the full axios error object (which includes `PAGE_ACCESS_TOKEN` in the request URL)

### Tech Debt — node_modules in git
- **D-09:** Claude's discretion — fix `node_modules` committed to git as part of Phase 1 repo cleanup: add `node_modules/` and `messenger-bot/node_modules/` to `.gitignore`, then remove from git tracking with `git rm -r --cached`. This unblocks clean development without affecting the user.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Bot Code (the file being modified)
- `messenger-bot/src/index.ts` — The single bot file; all Phase 1 changes happen here or alongside it

### Project Requirements
- `.planning/REQUIREMENTS.md` — Phase 1 requirements: SEC-01, SEC-02, SEC-03, CORE-01, CORE-02, CORE-03, CORE-04

### Codebase Intelligence
- `.planning/codebase/CONCERNS.md` — Security issues and tech debt; SEC items are documented here with file/line references
- `.planning/codebase/STACK.md` — Existing dependencies; confirms `axios`, `express`, `typescript` available; no new npm packages needed for Phase 1

### Project Context
- `.planning/PROJECT.md` — Constraints: keep Node.js/TypeScript for bot, no new services

### Research Findings
- `.planning/research/PITFALLS.md` — Phase 1 blockers: middleware order for raw body, token leak pattern, startup env var guards
- `.planning/research/SUMMARY.md` — Stack decisions: no Messenger SDK, raw Graph API calls via axios

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `sendMessage(recipientId, text)` in `messenger-bot/src/index.ts:61` — existing Graph API helper; extend to support quick replies by adding `message.quick_replies` field to the payload
- Axios instance already configured with Graph API base pattern — reuse for all new Graph API calls (persistent menu setup, send API)

### Established Patterns
- Environment variables loaded via `dotenv/config` at top of file — add `FACEBOOK_APP_SECRET` following the same pattern
- `res.sendStatus(200)` before the async loop — Facebook's 20s acknowledgement requirement already handled correctly; must not break this
- Constants declared at module level (`VERIFY_TOKEN`, `PAGE_ACCESS_TOKEN`) — follow same pattern for `APP_SECRET`

### Integration Points
- `app.post("/webhook")` handler — this is where HMAC verification middleware slots in (before the existing body processing)
- `express.json()` on line 6 — must be replaced with `express.raw({ type: '*/*' })` first, then JSON parse manually (or use `express.raw` + `express.json` in order with HMAC check between them)
- Graph API URL `https://graph.facebook.com/v19.0/me/messages` — bump to v21.0 per research recommendation; one-line change

</code_context>

<specifics>
## Specific Ideas

- Fallback message pattern: friendly acknowledgement + same quick replies as persistent menu top level — no new navigation structure, just consistent recovery
- HMAC verification: `FACEBOOK_APP_SECRET` absent → `console.warn("FACEBOOK_APP_SECRET not set — skipping webhook signature verification")` and continue processing. Present → verify or return 403.
- node_modules cleanup is a background task that doesn't touch any source files — safe to do first

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 1-Security + Bot Foundation*
*Context gathered: 2026-05-14*
