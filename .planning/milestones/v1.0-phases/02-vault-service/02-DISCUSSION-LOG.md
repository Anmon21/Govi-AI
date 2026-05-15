# Phase 2: Vault Service - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-14
**Phase:** 2-Vault Service
**Areas discussed:** Vault directory layout, Missing vault startup behavior

---

## Vault Directory Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Flat folder — all .md files in one directory | VAULT_PATH points to a single folder containing all Q&A files. Simple discovery: load every .md file in that folder. No subdirectory traversal needed. | ✓ |
| Nested folders — category subfolders inside VAULT_PATH | VAULT_PATH contains category subdirectories, each holding question .md files. Loader must recurse into subdirectories. | |

**User's choice:** Flat folder — all .md files in one directory

**Q: Should the loader also pick up .md files in subdirectories?**

| Option | Description | Selected |
|--------|-------------|----------|
| Top-level only — ignore subdirectories | Only .md files directly inside VAULT_PATH are loaded. Anything in subfolders is ignored automatically. | ✓ |
| Recursive — scan all nested folders | Every .md file anywhere under VAULT_PATH is considered. Requires explicit exclusion patterns. | |

**User's choice:** Top-level only — ignore subdirectories
**Notes:** Chosen for simplicity; avoids needing to handle Obsidian's `.obsidian/` config folder and attachment subdirectories.

---

## Missing Vault Startup Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Warn and continue with empty content | Server starts normally, logs a warning, and serves zero content files. Content endpoints return 404. Useful for local dev before the vault is configured. | ✓ |
| Hard fail — refuse to start | Server exits at startup with a clear error message if VAULT_PATH is missing or the directory doesn't exist. | |

**User's choice:** Warn and continue with empty content
**Notes:** Developer-friendly — allows running the API locally before the Obsidian vault is configured.

---

## Claude's Discretion

- In-memory dict keyed by frontmatter `id` for the content cache
- `python-frontmatter` library for parsing
- New `app/routers/content.py` following APIRouter pattern from `ai.py`
- `vault_path: str = ""` added to Settings in `app/config.py`
- Extend `/health` endpoint with vault stats (vault_loaded, content_count)
- Include `POST /content/reload` in Phase 2 (per roadmap success criteria)
- Frontmatter schema: id, type, title, enabled (from REQUIREMENTS.md VAULT-03)

## Deferred Ideas

None — discussion stayed within phase scope.
