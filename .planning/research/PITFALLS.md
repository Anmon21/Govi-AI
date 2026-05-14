# Pitfalls Research

**Project:** Govi Facebook Messenger Customer Support Bot
**Domain:** Rule-based Messenger chatbot with local filesystem (Obsidian vault) content
**Researched:** 2026-05-14
**Overall confidence:** HIGH (platform limits are well-documented; filesystem pitfalls are deterministic engineering problems)

---

## Facebook Messenger Platform Gotchas

### No Webhook Signature Verification (Already Missing in Existing Code)

The existing `messenger-bot/src/index.ts` receives POST `/webhook` and immediately processes it without verifying the `X-Hub-Signature-256` header that Facebook sends with every webhook delivery. Any actor who discovers the webhook URL can send forged events — fake messages, fake postbacks — that the bot will process as real.

- Warning signs: No `crypto.createHmac` import anywhere in `index.ts`; no reference to `X-Hub-Signature` in the handler.
- Prevention: Before processing any event, compute `HMAC-SHA256(rawBody, APP_SECRET)` and compare with the header value. Must use the raw request body bytes — `express.json()` parses before you can access raw bytes, so you need `express.raw({ type: 'application/json' })` or capture raw body via a middleware before JSON parsing. Store `FACEBOOK_APP_SECRET` in `.env`.
- Phase to address: Phase 1 (webhook hardening, before any new menu logic is added)

### 20-Second Webhook Response Timeout — Async Work After 200 OK

Facebook requires the webhook endpoint to return HTTP 200 within 20 seconds, or it will retry the delivery (up to several times, causing duplicate event processing). The existing code already handles this correctly — it calls `res.sendStatus(200)` before the async work — but this pattern must be preserved when the rule-based flow replaces the AI call.

- Warning signs: Moving business logic before `res.sendStatus(200)`; synchronous file reads inside the response path before the 200 is sent; awaiting the FastAPI call before responding.
- Prevention: Always send 200 first, then process. Use `setImmediate` or just rely on the fire-and-forget pattern that already exists. Mark any refactor of the handler with a comment: "200 must fire before any await."
- Phase to address: Phase 1 (preserve during refactor; add a code comment)

### Duplicate Event Delivery (Retry Storm)

If the bot returns a non-200, or times out, Facebook retries the same event. For stateful menu flows, processing the same postback twice can corrupt conversation state — e.g., advancing the menu twice or sending duplicate messages.

- Warning signs: Users reporting double responses; logs showing the same `mid` (message ID) processed multiple times; bot state jumping two steps at once.
- Prevention: Log processed message IDs (`mid`) in a short-lived store (in-memory Map with a TTL, or Redis later). On receipt, check if `mid` was already processed; if yes, skip and return 200 silently. For a low-traffic bot, an in-memory Map with a 60-second window is sufficient.
- Phase to address: Phase 2 (when stateful menu flows are introduced)

### Postback Payload Size Limit (1000 characters)

Messenger button postback payloads are capped at 1000 characters. If menu state or routing identifiers are embedded in the payload string (e.g., serialized JSON like `{"category":"products","item":"SKU-12345","depth":3}`), it is easy to exceed this silently — Facebook truncates or rejects the button.

- Warning signs: Buttons that visually render but don't fire the postback; payload strings approaching 200+ characters when serialized; nested JSON in payloads.
- Prevention: Use short opaque identifiers in payloads (e.g., `MENU_PRODUCTS_LIST`, `QA_42`) and resolve them server-side against the vault content. Never embed full content or deep state in the payload itself.
- Phase to address: Phase 2 (menu flow design)

### Quick Reply Limit (13 per message, title 20 characters)

Messenger enforces a maximum of 13 quick replies per message, and each title is capped at 20 characters (truncated silently if exceeded). A menu with more than 13 options, or with long product category names, will be silently truncated on the user's screen.

- Warning signs: Vault files with more than 13 options at any menu level; category names longer than 20 characters in markdown headings used as menu labels.
- Prevention: Enforce these limits in the content-loading layer when parsing vault files. If a menu level has more than 13 options, paginate (add a "See more" quick reply). Validate title lengths when loading vault content and warn/truncate with logging.
- Phase to address: Phase 2 (menu rendering); Phase 3 (vault parser must validate counts and lengths)

### Button Template Limits (3 buttons per template, 640-character message bubble)

Generic templates support a maximum of 3 buttons. Text messages are limited to 640 characters. If Q&A answers from the vault are pasted as long paragraphs, they will be silently truncated in the Messenger UI.

- Warning signs: Answers in vault files exceeding a paragraph; designers requesting more than 3 action buttons on a card.
- Prevention: Enforce a maximum answer length (e.g., 600 characters) in the vault content spec. Document this constraint in the vault authoring guide. For longer answers, split into multiple messages sent sequentially.
- Phase to address: Phase 3 (vault content format spec)

### Messaging Outside the 24-Hour Window (Policy Violation)

Facebook's Messenger Platform policy prohibits sending messages to a user more than 24 hours after their last interaction, except via approved Message Tags. For a customer support bot, the human escalation notification to the admin should use the `CUSTOMER_FEEDBACK` or `POST_PURCHASE_UPDATE` tag if the original conversation is older than 24 hours — otherwise the send will fail silently with a policy error in the Graph API response body (not an HTTP error).

- Warning signs: Admin notification messages failing silently in logs; `error code 10` or `error subcode 2018065` in the Facebook API response.
- Prevention: For the human escalation flow, send the admin Messenger notification immediately within the same 24-hour window. Log and surface API error bodies — the current `sendMessage` swallows Graph API errors because axios only throws on HTTP status errors, not on `{"error": {...}}` in a 200 response body.
- Phase to address: Phase 4 (human escalation); also fix `sendMessage` to check `data.error` in Phase 1

### Graph API Error Bodies Inside HTTP 200

The Facebook Graph API returns HTTP 200 even when the message send fails — the actual error is in the JSON body as `{ "error": { "code": ..., "message": ... } }`. The existing `sendMessage` function does not check for this, so send failures are silently swallowed.

- Warning signs: Users not receiving bot responses; no errors logged but messages not delivered; rate limit errors invisible in logs.
- Prevention: After `axios.post(...)`, check if `data.error` exists and throw or log explicitly. Wrap `sendMessage` in a helper that validates the response body.
- Phase to address: Phase 1 (fix before any new logic is built on top of broken error handling)

---

## Rule-Based Conversation Flow Pitfalls

### Stateless Webhook With No Session Store

Each HTTP request to the webhook is stateless. There is no built-in mechanism to remember where a user is in the menu tree between messages. If session state is stored only in memory as a plain JS object (`const sessions = {}`), it works fine on a single process but is lost on every server restart and does not scale past one process.

- Warning signs: Users losing their menu position after bot restart; tests passing locally but breaking under load (multiple processes); "start over" behavior on every message.
- Prevention: For v1 (single-process, low traffic), an in-memory Map is acceptable with explicit documentation of the limitation. Use `Map<senderId, SessionState>` with a TTL (e.g., 30-minute inactivity timeout) to prevent unbounded growth. Document that a process restart resets all sessions — acceptable for a support bot where users can simply start over. If the deployment ever moves to multiple workers, migrate to Redis.
- Phase to address: Phase 2 (state management design decision, document the tradeoff explicitly)

### Treating Text Messages and Postbacks as the Same Code Path

Users can type free text at any point even inside a menu flow. The current code only handles `event.message?.text` and ignores postbacks entirely. A rule-based menu relies on structured postbacks (button presses) for navigation, but users will also type things. Conflating the two leads to menus breaking when users type "yes" instead of pressing a button.

- Warning signs: No handling of `event.postback` in the webhook handler; no separate branch for `message.quick_reply`; text handler treating all text as navigation input.
- Prevention: Separate event dispatch at the top of the handler: `if (event.postback)` → postback handler; `else if (event.message?.quick_reply)` → quick reply handler (use `quick_reply.payload`, not `message.text`); `else if (event.message?.text)` → free text handler (return a gentle "please use the menu" message or re-show the current menu state).
- Phase to address: Phase 2 (event dispatcher refactor)

### Menu State Encoding in Postback Payload Instead of Session

Encoding full navigation state in the postback payload (e.g., `MENU_L1_PRODUCTS_L2_ACCESSORIES_L3_CABLES`) makes payloads grow with depth, hits the 1000-character limit, and makes it impossible to know what menu the user is actually on when they press an old button from a previous message.

- Warning signs: Payload strings that encode path history; logic that reconstructs state entirely from the payload without consulting a session store.
- Prevention: Store current menu state in the session (keyed by sender ID). Postback payloads should be flat action identifiers (`SELECT_CATEGORY_PRODUCTS`). The session store holds where they are; the payload says what they just did.
- Phase to address: Phase 2

### Old Buttons Remaining Tappable in Chat History

Messenger does not disable buttons from previous messages. A user can scroll up and press a button from an earlier message in the conversation, sending a postback that is now out of context with their current session state. This can reset or corrupt menu navigation unexpectedly.

- Warning signs: Users reporting the bot "going backwards"; session state jumping to an earlier menu position; logs showing a postback payload that doesn't match the current session state.
- Prevention: Design postback payloads to be idempotent for the user's benefit — if a user presses an old "Back to Main Menu" button, the bot should treat it gracefully rather than erroring. Avoid payloads that assume a specific prior state. Validate the current session state when a postback arrives and handle the "stale button" case explicitly (e.g., "Let's start fresh" + show main menu).
- Phase to address: Phase 2

---

## Obsidian Vault File Reading Pitfalls

### Assuming Vault Path Exists at Startup

If `VAULT_PATH` is configured but the directory does not exist (e.g., on a new deployment, the vault path is wrong, or the drive is unmounted), FastAPI will start successfully but fail at runtime when the first content request arrives. This produces an opaque 500 error with no useful message to the operator.

- Warning signs: `FileNotFoundError` or `OSError` on first content request rather than at startup; `VAULT_PATH` not validated in `config.py`; no health check that verifies vault accessibility.
- Prevention: At startup, validate that `VAULT_PATH` is set, the directory exists, and is readable. Fail fast with a clear error message: `"Vault path '/path/to/vault' does not exist or is not readable"`. Add vault accessibility to the `/health` endpoint response.
- Phase to address: Phase 3 (vault integration)

### Obsidian Wikilinks Breaking Standard Markdown Parsers

Obsidian uses `[[Page Name]]` wikilink syntax and `![[image.png]]` embed syntax that are not valid CommonMark. Any standard Python markdown parser (`markdown`, `mistune`, `python-markdown2`) will fail to parse these correctly — wikilinks will be passed through as literal text or cause parse errors.

- Warning signs: Wikilink syntax appearing as raw `[[...]]` text in API responses; linked pages not being followed; `![[embed]]` appearing in answers verbatim.
- Prevention: Either (a) strip wikilinks before parsing (regex: `\[\[([^\]|]+)(?:\|[^\]]+)?\]\]` → extract display text or page name), or (b) use a vault-aware parser like `obsidian-md` patterns. For a Q&A content model, the simplest approach is to design vault files to avoid wikilinks in answer text — document this constraint in the content authoring guide.
- Phase to address: Phase 3

### Frontmatter YAML Parsing Inconsistency

Obsidian files commonly start with YAML frontmatter delimited by `---`. Standard markdown parsers do not strip frontmatter — it appears as the first paragraph of content. If Q&A files use frontmatter for metadata (tags, category, order), the parser must explicitly strip and parse it before processing content.

- Warning signs: YAML frontmatter appearing as the first line of answer text (e.g., `---` at the start of responses); `tags:` and `category:` appearing in menu labels.
- Prevention: Use `python-frontmatter` library to parse vault files. It correctly splits frontmatter from body content. Make frontmatter the canonical place for menu metadata (category, order, enabled flag) and body text the answer content.
- Phase to address: Phase 3

### File Encoding Assumptions (BOM, Non-UTF-8)

Obsidian saves files as UTF-8 without BOM on macOS by default, but files created by other apps or synced from Windows may have a UTF-8 BOM (`\xef\xbb\xbf`) or Windows line endings (`\r\n`). `open(path, 'r')` on macOS uses UTF-8 by default, but if even one file has a BOM, the YAML frontmatter parser will fail because `---` becomes `\xef\xbb\xbf---`.

- Warning signs: Frontmatter parser failing on specific files but not others; "invalid start byte" errors; `\r` appearing in parsed content.
- Prevention: Always open vault files with `open(path, 'r', encoding='utf-8-sig')` — the `utf-8-sig` codec strips the BOM if present and reads plain UTF-8 otherwise. Normalize line endings with `.replace('\r\n', '\n')`.
- Phase to address: Phase 3

### Vault Structure Drift (Files Renamed/Moved Break Bot)

The FastAPI layer needs to discover Q&A content files. If it uses hardcoded file paths or a fragile naming convention (e.g., `products.md`, `shipping.md`), any rename or reorganization of the vault by the content author breaks the bot at runtime with no warning.

- Warning signs: `FileNotFoundError` after a vault edit session; bot serving stale content because files were renamed; content author unaware their changes affect the live bot.
- Prevention: Use a discovery-based approach — scan the vault directory for `.md` files that contain a frontmatter `enabled: true` or a specific tag (e.g., `tags: [govi-bot]`). This decouples bot logic from specific filenames. Reload content on each request (with a short cache TTL, e.g., 30 seconds) rather than once at startup so vault edits take effect quickly.
- Phase to address: Phase 3

### Recursive Vault Scanning Hitting Non-Content Files

Obsidian vaults contain system files: `.obsidian/` config directory, `.trash/`, attachment files (`.png`, `.pdf`, `.canvas`), and template files. A naive `glob('**/*.md')` will include template files and deleted-but-not-purged files in `.trash/`.

- Warning signs: Template placeholder content appearing in menus; deleted Q&A entries still showing up; bot loading Obsidian template files as menu items.
- Prevention: Exclude `.obsidian/`, `.trash/`, and any configurable excluded directories when scanning. Use frontmatter-based inclusion (only load files with `enabled: true`) rather than loading all `.md` files and filtering by content.
- Phase to address: Phase 3

### No Cache — Vault Read on Every Request

Reading and parsing all vault markdown files on every incoming message request adds latency proportional to vault size and is unnecessary for content that changes infrequently.

- Warning signs: Response times increasing as vault grows; disk I/O visible in profiling on every request; FastAPI process with high I/O wait.
- Prevention: Implement a simple in-memory content cache with a configurable TTL (30–60 seconds default). On cache miss, reload from disk. This gives near-real-time content updates without per-request disk reads. Do not implement file-watch-based invalidation in v1 — TTL is simpler and sufficient.
- Phase to address: Phase 3

---

## Deployment Pitfalls

### ngrok URL Changing on Every Restart (Dev Workflow Breaks)

The free tier of ngrok generates a new random URL on each process restart. Facebook Messenger webhooks must be re-registered every time the URL changes via the Facebook developer console. This is a significant friction point during development — a forgotten re-registration means the bot stops receiving events with no error visible to the developer.

- Warning signs: Bot not responding after an ngrok restart; no events appearing in webhook logs; developer making code changes but forgetting to update the webhook URL.
- Prevention: Use ngrok's static domain feature (available on free tier as of 2023) or use a paid ngrok account. Alternatively, use `cloudflared tunnel` (Cloudflare's free tunnel service) which supports stable URLs on free tier. Document the re-registration procedure in the project README. Add a startup log line that prints the current expected webhook URL.
- Phase to address: Phase 1 (dev environment setup)

### SSL Required for Webhook — Self-Signed Certs Not Accepted

Facebook requires the webhook URL to use HTTPS with a certificate signed by a trusted CA. Self-signed certificates are explicitly rejected. This means the bot cannot be tested locally without a tunnel service (ngrok, cloudflared) or a publicly accessible server with a real certificate.

- Warning signs: Webhook registration failing with certificate errors; attempts to use `localhost` as the webhook URL; self-signed cert tools being suggested for local dev.
- Prevention: Use ngrok or cloudflared for local development — they provide valid TLS termination from their domain. For production, use a platform that provides managed TLS (Railway, Render, Fly.io). Document this constraint clearly so developers don't waste time with local cert setups.
- Phase to address: Phase 1

### PORT and Environment Variable Mismatch Between Services

The Node.js bot defaults to port 3000; the FastAPI backend defaults to port 8000. The bot calls `GOVI_AI_URL ?? "http://localhost:8000"`. If `GOVI_AI_URL` is misconfigured in production, the bot silently falls back to `localhost:8000` — which works locally but fails in production (where the two services are on different hosts).

- Warning signs: Bot working locally but not in production; `axios` calls failing with connection refused; `GOVI_AI_URL` missing from production `.env`.
- Prevention: Remove the fallback default for `GOVI_AI_URL` — make it a required environment variable that fails loudly at startup if not set. Same for `FACEBOOK_PAGE_ACCESS_TOKEN` and `FACEBOOK_VERIFY_TOKEN`. Add a startup validation step that checks all required env vars before binding the port.
- Phase to address: Phase 1

### Process Crashes Silently — No Restart Policy

If the Node.js or FastAPI process crashes, there is no process manager to restart it. The bot stops working silently until someone manually restarts it.

- Warning signs: Bot unresponsive with no recent logs; process no longer listed in `ps`; users reporting extended outages.
- Prevention: Use `pm2` for the Node.js process and `uvicorn` with a supervisor for FastAPI in production. For the simplest v1 approach: `pm2 start npm -- start` and `pm2 start "uvicorn app.main:app"`. Document this in the deployment guide. For cloud platforms (Render, Railway), this is handled automatically.
- Phase to address: Phase 5 (deployment); note the risk in Phase 1 docs

---

## Security Pitfalls

### Vault Path Exposed in API Responses or Logs

The `VAULT_PATH` environment variable contains a local filesystem path (e.g., `/Users/username/Documents/Obsidian/Govi-Vault`). If this path leaks into error messages returned to the Messenger bot (and thus to users), it reveals the operator's filesystem structure.

- Warning signs: FastAPI exceptions propagating unhandled to the bot and being sent to the user; `traceback` output containing the vault path; Uvicorn's default exception handler returning stack traces in development mode running in production.
- Prevention: Never return raw exception tracebacks to API callers. Use FastAPI's `exception_handler` to return generic error responses. In the bot, catch all FastAPI errors and send the user a generic fallback message. Set `ENVIRONMENT=production` to suppress debug output.
- Phase to address: Phase 3 (vault integration); Phase 1 (general error handling)

### No Rate Limiting on the FastAPI Content Endpoint

The `/ai/chat` endpoint (and the future content endpoint) is directly accessible to anyone who knows the URL — not just the Node.js bot. Without authentication or rate limiting, it can be abused to exfiltrate vault content or exhaust server resources.

- Warning signs: Endpoint reachable from the internet without credentials; no `Authorization` header checked; no IP-based or token-based throttling.
- Prevention: Add a shared secret between the Node.js bot and FastAPI — the bot sends an `X-Internal-Token` header, and FastAPI validates it. This is not security against a sophisticated attacker but prevents casual abuse. For v1, a single shared secret in `.env` is sufficient. Optionally add `slowapi` rate limiting on the content endpoint.
- Phase to address: Phase 1 (before opening the system to real traffic)

### Page Access Token Logged or Leaked

The `PAGE_ACCESS_TOKEN` is used in the `params` argument of axios calls to the Facebook Graph API. If axios logs requests (e.g., in debug mode), the token appears in query strings in logs. Similarly, if error objects from axios are logged in full, the token is in the URL.

- Warning signs: Full axios request URLs appearing in logs; `access_token=EAA...` visible in log output; error objects logged with `console.error("Error:", err)` which dumps the full axios error including config.url.
- Prevention: Never log the full axios error object. Log only `err.response?.data` and `err.message`. Move the access token from a query param to an `Authorization: Bearer` header (Facebook Graph API accepts both) — header-based tokens are less likely to appear in access logs and proxy logs.
- Phase to address: Phase 1

### CORSMiddleware Allows All Origins (main.py)

The FastAPI backend has `allow_origins=["*"]` — it accepts requests from any origin. For an internal API that should only be called by the Node.js bot, this is unnecessarily permissive. While CORS headers don't protect server-to-server calls, it signals that the API was set up without security scope in mind.

- Warning signs: `allow_origins=["*"]` in `main.py` for an API that has no browser clients.
- Prevention: Since the FastAPI API is called server-to-server (Node.js → FastAPI), CORS is irrelevant — CORS headers are only enforced by browsers. However, the permissive setting is a signal to tighten to the internal-token approach described above. Lock `allow_origins` to the bot's domain once deployed.
- Phase to address: Phase 1 (low priority, note the issue)

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Phase 1: Webhook hardening | Missing signature verification, swallowed Graph API errors, token in logs | Add HMAC verification, check `data.error`, log `err.message` only |
| Phase 1: Env var validation | Silent fallback to localhost defaults masking production misconfiguration | Make all service URLs required env vars with startup validation |
| Phase 2: Menu state design | Session state in memory lost on restart; postback payload bloat | Document in-memory Map limitation; use flat opaque payload IDs |
| Phase 2: Event dispatch | Text and postback events conflated in single handler | Split dispatcher: postback → postback handler, text → fallback handler |
| Phase 3: Vault parser | Wikilinks, frontmatter, BOM, recursive scan hitting system files | Use `python-frontmatter`, `utf-8-sig`, exclude `.obsidian/` and `.trash/` |
| Phase 3: Vault discovery | Hardcoded filenames breaking on vault rename/reorganize | Frontmatter-based inclusion (`enabled: true`), short-TTL cache |
| Phase 4: Human escalation | 24-hour messaging window policy; silent Graph API errors | Use message tags for out-of-window messages; validate API response body |
| Phase 5: Deployment | ngrok URL churn, no process manager, SSL cert requirements | Use static ngrok domain; pm2 for process management; document SSL constraint |

---

## Sources

- Existing codebase: `messenger-bot/src/index.ts`, `app/main.py`, `app/routers/ai.py`, `app/config.py` (HIGH confidence — direct code inspection)
- Facebook Messenger Platform documentation: webhook verification, message limits, policy constraints (HIGH confidence — well-established platform constraints, stable across versions)
- Obsidian file format behavior: frontmatter, wikilinks, vault structure (HIGH confidence — deterministic filesystem behavior)
- Python file I/O: BOM handling, encoding behavior (HIGH confidence — standard library behavior)
