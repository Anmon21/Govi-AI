# Phase 2: Vault Service - Context

**Gathered:** 2026-05-14
**Status:** Ready for planning

<domain>
## Phase Boundary

FastAPI reads `.md` files from a local Obsidian vault directory, parses YAML frontmatter, caches enabled content in memory, and serves it by stable ID via `GET /content/{id}`. Phase ends when the content API is independently testable with curl — vault loads at startup, content is served by ID, and health reflects vault status. No Messenger bot integration in this phase; Phase 3 wires the bot to this API.

</domain>

<decisions>
## Implementation Decisions

### Vault Directory Layout
- **D-01:** VAULT_PATH points to a single flat directory — all `.md` content files live at the top level of that folder. No nested category subfolders.
- **D-02:** Only `.md` files directly inside VAULT_PATH are loaded — subdirectory traversal is disabled. Anything in subfolders (Obsidian attachments, templates, `.obsidian/` config) is automatically ignored.

### Missing Vault Startup Behavior
- **D-03:** If VAULT_PATH is not set or the directory does not exist at startup, the server starts normally, logs a warning, and serves zero content files. Content endpoints return 404. The service does not refuse to start — this keeps local development working before the vault is configured.

### Claude's Discretion
- In-memory dict keyed by frontmatter `id` for the content cache — fast lookup by ID, simple invalidation on reload
- `python-frontmatter` library for parsing Obsidian/Jekyll-style frontmatter (no alternatives needed)
- New `app/routers/content.py` following the existing `APIRouter(prefix="/content", tags=["content"])` pattern
- Extend `app/config.py` Settings with `vault_path: str = ""` — empty string triggers the D-03 soft-fail path
- Extend `GET /health` to include `vault_loaded: bool` and `content_count: int` (Phase 2 success criterion 1)
- `POST /content/reload` hot-reload endpoint included in this phase (Phase 2 success criterion 4) — reloads vault without restart
- Frontmatter schema from REQUIREMENTS.md VAULT-03: `id` (str), `type` (str), `title` (str), `enabled` (bool) — files without `enabled: true` are excluded from cache and not served

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing FastAPI App (files being modified/extended)
- `app/config.py` — Settings singleton pattern; add `vault_path: str = ""` here
- `app/main.py` — Router registration; new content router mounts here
- `app/routers/ai.py` — APIRouter pattern to replicate in `app/routers/content.py`
- `app/routers/health.py` — Health endpoint to extend with vault stats

### Project Requirements
- `.planning/REQUIREMENTS.md` — Phase 2 requirements: VAULT-01, VAULT-02, VAULT-03; also QA-04 (reload endpoint, included in Phase 2 delivery per roadmap success criteria)

### Project Context
- `.planning/PROJECT.md` — Constraints: Python/FastAPI for backend; no containerization; standalone system

### Codebase Intelligence
- `.planning/codebase/STACK.md` — Existing Python dependencies; `python-frontmatter` is NOT yet in requirements.txt — must be added
- `.planning/codebase/ARCHITECTURE.md` — Two-service split and FastAPI layer patterns

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Settings(BaseSettings)` in `app/config.py` — add `vault_path` field following the same `str = ""` default pattern as other optional vars
- `APIRouter` in `app/routers/ai.py` — exact pattern for new `app/routers/content.py`
- `GET /health` in `app/routers/health.py` — extend response to include vault stats

### Established Patterns
- Pydantic `BaseModel` for all request/response shapes — use for `ContentResponse(id, type, title, body)` and extended health response
- Module-level `settings` singleton imported from `app.config` — vault service reads `settings.vault_path` at load time
- Router registered in `app/main.py` via `app.include_router(...)` — follow same pattern for content router

### Integration Points
- `app/main.py` — add `from app.routers import content` and `app.include_router(content.router)`
- `app/config.py` — add `vault_path: str = ""` to Settings
- `.env.example` at repo root — document `VAULT_PATH=/path/to/your/obsidian/vault/govi-content`

</code_context>

<specifics>
## Specific Ideas

- Soft-fail pattern for missing vault: `if not settings.vault_path or not os.path.isdir(settings.vault_path): logger.warning("VAULT_PATH not set or directory missing — starting with empty content"); return` — no exception raised, service continues
- Hot-reload via `POST /content/reload`: re-runs the same load function, replaces the in-memory dict atomically

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 2-Vault Service*
*Context gathered: 2026-05-14*
