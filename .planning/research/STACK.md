# Stack Research

**Project:** Govi Facebook Messenger Customer Support Bot
**Researched:** 2026-05-14
**Source note:** WebSearch, Bash, and WebFetch tools were unavailable in this environment.
All findings are from training knowledge (cutoff August 2025) cross-checked against the
existing codebase. Confidence levels reflect this constraint.

---

## Recommended Stack

### Facebook Messenger Platform — Send API & Webhooks

**Approach: Raw HTTP via axios (no wrapper SDK)**

- Library: `axios ^1.7.x` (already installed)
- Graph API version: `v21.0` (upgrade from current v19.0 in codebase)
- Rationale: Facebook does not publish or maintain an official Node.js Messenger SDK.
  The community "fbmessenger" and "fb" npm packages are abandoned (last release 2018–2019).
  All production Messenger bots make raw Graph API calls. The existing codebase already
  does this correctly — `axios.post('https://graph.facebook.com/v19.0/me/messages', ...)`.
  The only change needed is version bump and adding support for Quick Replies and
  Generic Templates (button payloads), which are plain JSON fields in the same POST body.
- Confidence: HIGH (official Facebook docs confirm no SDK; pattern is stable since 2016)

**Messenger message types needed for this project:**

| Type | Graph API field | Use case |
|------|----------------|----------|
| Text message | `message: { text }` | Simple answers |
| Quick Replies | `message: { text, quick_replies: [{...}] }` | Menu navigation |
| Generic Template | `message: { attachment: { type: "template", payload: { template_type: "generic", elements: [...] } } }` | Product cards |
| Typing indicator | `sender_action: "typing_on"` | UX while loading |

- Confidence: HIGH (these message types have been stable in the Messenger Platform for 5+ years)

**Webhook handling — no changes needed:**
The existing webhook pattern in `messenger-bot/src/index.ts` (acknowledge with 200
immediately, then process async) is correct. Facebook requires a 200 response within 20
seconds. The existing code does this correctly (res.sendStatus(200) before the async loop).

**What to add for Quick Replies / button payloads:**
Quick Reply postbacks arrive as `event.message.quick_reply.payload` (not `event.message.text`).
The existing event handler only checks `event.message?.text` — this must be extended to
also handle `event.message?.quick_reply?.payload` and `event.postback?.payload`.

---

### Rule-Based Conversation Flow — State Machine

**Approach: Hand-rolled state map (no framework)**

- Library: None — implement a plain TypeScript `Map<string, ConversationState>` per user
- Rationale: XState v5 is the gold standard for TypeScript state machines and would work,
  but it introduces significant complexity (actors, context, guards, spawning) that is
  disproportionate to this problem. This bot has a shallow menu tree: a user selects a
  topic, gets an answer or sub-menu, and either escalates or resets. A simple per-user
  state object stored in a `Map` is sufficient and eliminates a 40kB dependency.
  The state machine surface is: `{ state: 'idle' | 'main_menu' | 'product_qa' | 'escalation', context: { ... } }`.
- Confidence: HIGH (this is a well-established pattern for simple menu bots)

**If complexity grows beyond 3 levels of nesting, reconsider:**
- XState v5 (`xstate ^5.18.x`) — adds actor model, persistence, visualization via Stately
- Confidence for XState recommendation: MEDIUM (training knowledge, verify current v5 API)

**In-memory session store:**
- Use `Map<string, UserSession>` in the Node.js process for v1
- No Redis needed — single-process deployment, session loss on restart is acceptable for
  a support bot (user just starts over)
- Confidence: HIGH (appropriate for stated deployment constraints)

---

### Obsidian Markdown Parsing — Python

**Component 1: YAML frontmatter parsing**

- Library: `python-frontmatter ^1.1.0`
- Install: `pip install python-frontmatter`
- Rationale: Obsidian uses YAML frontmatter (the `---` block at the top of notes).
  `python-frontmatter` is the de facto standard for this — it parses the YAML header
  and returns both `post.metadata` (dict) and `post.content` (body string) cleanly.
  The alternative `PyYAML` requires manual splitting on `---` delimiters, which breaks
  on edge cases (triple-dash in code blocks, etc.). `python-frontmatter` handles this.
- Confidence: MEDIUM (library is well-established; version pinned from training knowledge —
  verify latest on PyPI before pinning in requirements.txt)

**Component 2: Wikilink resolution**

- Library: None — implement with `re` (stdlib regex)
- Rationale: Obsidian wikilinks have the format `[[Note Name]]` or `[[Note Name|alias]]`.
  No Python library specifically targets Obsidian wikilinks with active maintenance.
  `wikitextparser` parses MediaWiki syntax, not Obsidian. A simple regex resolves wikilinks
  to file paths: `re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', content)`.
  For this project, wikilinks in Q&A content likely reference other vault notes — the
  FastAPI layer only needs to resolve them to file paths, not render full HTML.
- Confidence: HIGH (stdlib regex is the correct tool; no external lib needed)

**Component 3: Vault file discovery**

- Library: `pathlib` (stdlib)
- Rationale: `pathlib.Path(vault_root).rglob('*.md')` is sufficient to enumerate all
  markdown files. No additional library needed. Folder structure maps directly to
  menu categories (e.g., `vault/products/shoes.md` → Products > Shoes).
- Confidence: HIGH (stdlib is correct here)

**Component 4: Markdown body parsing (optional)**

- Library: `markdown-it-py ^3.0.x` (only if HTML rendering is needed)
- Rationale: If the FastAPI layer needs to strip markdown syntax from answer bodies
  before sending to Messenger (which doesn't render markdown), `markdown-it-py` converts
  markdown to HTML, then `re.sub(r'<[^>]+>', '', html)` strips tags to plain text.
  Alternatively, `mistune ^3.0.x` is lighter. For v1, plain text extraction with a simple
  regex to strip `**bold**`, `_italic_`, etc. may be sufficient without a full parser.
- Confidence: MEDIUM (both libraries are real and maintained; version numbers from training
  knowledge — verify on PyPI)

**Obsidian-specific: `.obsidian/` folder**

The vault root contains a `.obsidian/` config directory. The file discovery must exclude it:
`[p for p in Path(vault_root).rglob('*.md') if '.obsidian' not in p.parts]`

---

### FastAPI Backend — Content API Layer

**Keep existing stack, add vault configuration:**

- `fastapi ^0.115.x` — already installed, no change
- `pydantic-settings ^2.x` — already installed; add `OBSIDIAN_VAULT_PATH` to `Settings`
- `python-frontmatter ^1.1.0` — add to requirements.txt
- `watchfiles ^0.24.x` (optional) — hot-reload vault content without restarting FastAPI
  if the vault changes frequently during content editing sessions
- Confidence: HIGH for FastAPI/pydantic (in use); MEDIUM for watchfiles version

**New endpoints needed:**

| Endpoint | Purpose |
|----------|---------|
| `GET /content/topics` | List top-level vault folders as menu topics |
| `GET /content/topics/{topic}` | List notes within a topic folder |
| `GET /content/qa/{note_path}` | Return parsed Q&A for a specific note |
| `GET /health` | Already exists |

---

### TypeScript / Node.js — No Changes to Core

- `typescript ^5.4.x` — already installed, no change needed
- `express ^4.19.x` — already installed; Express 5.x exists but migration is unnecessary
- `axios ^1.7.x` — already installed, no change needed
- `dotenv ^16.4.x` — already installed, no change needed

**Add for type safety on Messenger payloads:**
No official `@types/facebook-messenger` package exists on DefinitelyTyped with active
maintenance. Define local TypeScript interfaces for the webhook payload shape and
Send API request body — this is 30 lines of interface definitions, not a dependency.

---

## What NOT to Use

| Library | Reason to Avoid |
|---------|----------------|
| `fbmessenger` (npm) | Last published 2019, targets Messenger Platform v1 (deprecated). API surface no longer matches current Graph API. |
| `fb` (npm) | Abandoned 2018. No Send API support for Quick Replies or templates. |
| `botframework-connector` (npm) | Microsoft Bot Framework overhead — designed for multi-channel (Teams, Slack, etc.). Massive dependency footprint for a single-channel Messenger bot. |
| `Dialogflow` / `Rasa` | NLU frameworks intended for intent classification. This project is explicitly rule-based — these add complexity with no benefit. |
| `XState v5` (for v1) | Correct tool, wrong scale. Menu depth of 2–3 levels does not justify actor-model complexity. Revisit if the flow grows. |
| `boto3` / `Redis` for sessions | No persistence requirement stated. In-memory Map is sufficient. Over-engineering for v1. |
| `PyYAML` (alone) | Correct YAML parser, but requires manual frontmatter delimiter splitting. `python-frontmatter` wraps PyYAML and handles the splitting correctly. Use `python-frontmatter` instead. |
| `obsidiantools` (Python) | Parses the full Obsidian graph including backlinks, canvas files, etc. Much heavier than needed. This project only needs frontmatter + content from `.md` files. |
| `wikitextparser` (Python) | Parses MediaWiki/Wikipedia wikilink syntax, not Obsidian `[[wikilink]]` format. Wrong tool. |
| Express 5.x | Not a reason to avoid permanently, but not worth migrating to mid-project. Express 4.x is stable and the existing codebase uses it. |

---

## Version Notes

Versions verified against existing `package.json` and `requirements.txt`. External library
versions (python-frontmatter, markdown-it-py, watchfiles) are from training knowledge
(cutoff August 2025). Verify on PyPI before adding to `requirements.txt`.

| Package | Current in Codebase | Recommended | Source |
|---------|--------------------|-----------:|--------|
| `typescript` | `^5.4.0` | `^5.4.0` | package.json (verified) |
| `express` | `^4.19.0` | `^4.19.0` | package.json (verified) |
| `axios` | `^1.7.0` | `^1.7.0` | package.json (verified) |
| `fastapi` | `>=0.115.0` | `>=0.115.0` | requirements.txt (verified) |
| `pydantic` | `>=2.7.0` | `>=2.7.0` | requirements.txt (verified) |
| `pydantic-settings` | `>=2.3.0` | `>=2.3.0` | requirements.txt (verified) |
| `anthropic` | `>=0.30.0` | keep or remove | requirements.txt (verified) |
| `python-frontmatter` | not installed | `^1.1.0` | training knowledge — verify |
| `markdown-it-py` | not installed | `^3.0.0` | training knowledge — verify |
| `watchfiles` | not installed | `^0.24.0` | training knowledge — verify |
| Graph API version | `v19.0` | `v21.0` | training knowledge — verify |

**Graph API version note:** Facebook deprecates Graph API versions on a rolling 2-year
cycle. v19.0 was released early 2024. v21.0 released late 2024. Upgrading the URL in
`sendMessage()` is a one-line change and is low risk — the Send API endpoint shape has
not changed between versions.

**Anthropic SDK note:** `anthropic ^0.30.0` can remain in requirements.txt if the
Anthropic fallback path is kept for complex queries. If fully removing AI, remove it
to reduce attack surface and deployment weight.

---

## Sources

- Existing codebase: `messenger-bot/src/index.ts`, `messenger-bot/package.json`,
  `app/main.py`, `app/routers/ai.py`, `app/config.py`, `requirements.txt` (directly read)
- Facebook Messenger Platform architecture: training knowledge (HIGH confidence for
  stable patterns documented since 2016)
- python-frontmatter, markdown-it-py, watchfiles: training knowledge (MEDIUM confidence —
  verify versions on PyPI before pinning)
- XState v5: training knowledge (MEDIUM confidence on current API surface)
