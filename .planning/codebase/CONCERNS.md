# Codebase Concerns

**Analysis Date:** 2026-05-14

## Tech Debt

**`node_modules` committed to git:**
- Issue: `messenger-bot/node_modules/` is tracked in git (1,650+ files). `node_modules` is absent from `.gitignore`.
- Files: `.gitignore`, `messenger-bot/node_modules/`
- Impact: Bloated repository, binary/generated files in version control, conflicts on every `npm install`, slow clones.
- Fix approach: Add `node_modules/` to `.gitignore`, then run `git rm -r --cached messenger-bot/node_modules`.

**`reload=True` hardcoded in the production entrypoint:**
- Issue: `main.py` passes `reload=True` to `uvicorn.run` unconditionally, including when `APP_ENV=production`.
- Files: `main.py` (line 5)
- Impact: File-watching reloader is active in production, increasing memory use and causing unpredictable worker restarts. Uvicorn docs explicitly warn against this.
- Fix approach: Gate on `settings.app_env != "production"` — e.g., `reload=settings.app_env == "development"`.

**Synchronous Anthropic SDK call inside an `async` handler:**
- Issue: `client.messages.create(...)` in `app/routers/ai.py` (line 30) is a blocking synchronous call made directly inside an `async def` endpoint. The standard `anthropic` SDK is synchronous.
- Files: `app/routers/ai.py` (lines 28–35)
- Impact: Blocks the entire asyncio event loop for the duration of the API call, making the server unresponsive to all other requests while waiting on Anthropic.
- Fix approach: Use `anthropic.AsyncAnthropic` client with `await client.messages.create(...)`, or run the sync call in a thread pool via `asyncio.to_thread(...)`.

**`httpx` in requirements but never imported:**
- Issue: `requirements.txt` lists `httpx>=0.27.0` but no file in `app/` imports or uses it.
- Files: `requirements.txt`
- Impact: Unnecessary dependency adds install time and attack surface.
- Fix approach: Remove `httpx` from `requirements.txt`.

**New Anthropic client instantiated on every request:**
- Issue: `anthropic.Anthropic(...)` is constructed inside the `chat` handler on every call (line 28 of `app/routers/ai.py`), not at module or app startup.
- Files: `app/routers/ai.py` (line 28)
- Impact: Overhead of client initialization (connection pool creation, config parsing) on every request. Wasteful for a long-lived server process.
- Fix approach: Instantiate the client once at module level (after settings are loaded) and reuse it across requests.

## Security Considerations

**Wildcard CORS policy:**
- Risk: `allow_origins=["*"]` permits any origin to make cross-origin requests to the API.
- Files: `app/main.py` (lines 9–12)
- Current mitigation: None.
- Recommendations: Set `allow_origins` to an explicit list of trusted origins (e.g., the Messenger bot's domain or `localhost` for development). Use the `APP_ENV` setting to differentiate dev vs. production allowed origins.

**No authentication on `/ai/chat`:**
- Risk: The endpoint is publicly accessible. Anyone who discovers the URL can call Anthropic via your API key at your cost.
- Files: `app/routers/ai.py`
- Current mitigation: None — no API keys, tokens, or IP allowlisting.
- Recommendations: Add a shared-secret header check (e.g., `X-API-Key`) or restrict the network-level to only allow the Messenger bot service.

**No rate limiting:**
- Risk: Unconstrained callers can trigger unlimited Anthropic API calls, leading to runaway costs or API quota exhaustion.
- Files: `app/routers/ai.py`, `app/main.py`
- Current mitigation: None.
- Recommendations: Add per-IP or per-sender-ID rate limiting using `slowapi` or a reverse-proxy rule.

**No input length validation on `message`:**
- Risk: A caller can send an arbitrarily large string as `message`, consuming large numbers of tokens and increasing Anthropic API cost per call.
- Files: `app/routers/ai.py` (line 11)
- Current mitigation: `max_tokens` caps the output, but input length is unrestricted.
- Recommendations: Add a `max_length` constraint via Pydantic `Field(max_length=4000)` or similar.

**`max_tokens` is caller-controlled with no upper bound:**
- Risk: A caller can set `max_tokens` to an arbitrarily high value (Anthropic model max), causing expensive responses.
- Files: `app/routers/ai.py` (line 13)
- Current mitigation: Defaults to 1024 but the caller can override with no server-side cap.
- Recommendations: Add `Field(default=1024, ge=1, le=4096)` to enforce a ceiling.

**Facebook webhook has no signature verification:**
- Risk: Any party that knows the webhook URL can POST fake Messenger events. Facebook signs all webhook calls with `X-Hub-Signature-256`.
- Files: `messenger-bot/src/index.ts` (line 27 — the POST handler)
- Current mitigation: None.
- Recommendations: Validate the `X-Hub-Signature-256` header against the raw request body using `HMAC-SHA256` and the app secret before processing any event.

**Non-null assertions on env vars (`!`) in messenger bot:**
- Risk: `FACEBOOK_VERIFY_TOKEN!` and `FACEBOOK_PAGE_ACCESS_TOKEN!` (lines 8–9) suppress TypeScript's undefined check. If the vars are absent at startup, the value is `undefined` at runtime but typed as `string`, causing silent failures.
- Files: `messenger-bot/src/index.ts` (lines 8–9)
- Current mitigation: None.
- Recommendations: Add startup guards that throw a descriptive error if required env vars are missing.

## Performance Bottlenecks

**Synchronous I/O blocking the event loop (see Tech Debt above):**
- Problem: Every call to `/ai/chat` stalls the entire Python asyncio event loop while waiting for the Anthropic HTTP response (typically 1–10 s).
- Files: `app/routers/ai.py` (line 30)
- Cause: `anthropic.Anthropic` (sync client) called without `asyncio.to_thread`.
- Improvement path: Switch to `anthropic.AsyncAnthropic` for non-blocking I/O.

## Fragile Areas

**`message.content[0].text` — unchecked index and field access:**
- Files: `app/routers/ai.py` (line 38)
- Why fragile: Assumes `content` is non-empty and that the first element is always a `TextBlock`. If Anthropic returns a tool-use block, a refusal, or an empty content list, this raises an unhandled `IndexError` or `AttributeError`.
- Safe modification: Check `message.content` length and block type before accessing `.text`.
- Test coverage: None.

**`sendMessage` called inside a `catch` block without its own error handling:**
- Files: `messenger-bot/src/index.ts` (line 55)
- Why fragile: If the fallback `sendMessage` call itself fails (e.g., Facebook Graph API is down), the unhandled promise rejection propagates silently. The user gets no feedback and the error is invisible.
- Safe modification: Wrap the fallback `sendMessage` in its own try/catch with a `console.error`.

**`data.reply` accessed without null check in messenger bot:**
- Files: `messenger-bot/src/index.ts` (line 52)
- Why fragile: If the Govi AI API returns a non-200 status that axios doesn't throw for (or if `data.reply` is absent), `sendMessage` is called with `undefined`, sending a literal "undefined" message to the user.
- Safe modification: Guard with `if (data?.reply)` before sending.

## Test Coverage Gaps

**No tests exist anywhere in the codebase:**
- What's not tested: All business logic — the `/ai/chat` endpoint, webhook verification, Messenger event routing, error paths, config loading.
- Files: `app/routers/ai.py`, `app/routers/health.py`, `messenger-bot/src/index.ts`
- Risk: Any change to core request-handling logic can silently break functionality. The index-out-of-bounds on `message.content[0]` and the unchecked `data.reply` access would not be caught before deployment.
- Priority: High

## Missing Critical Features

**No conversation history / multi-turn context:**
- Problem: Every call to `/ai/chat` sends only a single user message with no prior context. Each Messenger exchange is stateless.
- Blocks: Users cannot have coherent multi-turn conversations. The assistant has no memory of prior exchanges within a session.

**No structured logging or observability:**
- Problem: The Python backend uses no logging library — errors bubble up as unhandled exceptions with only FastAPI's default stderr output. The messenger bot uses bare `console.log/error`.
- Blocks: No way to correlate requests, trace errors to specific users, or monitor Anthropic API latency in production.

---

*Concerns audit: 2026-05-14*
