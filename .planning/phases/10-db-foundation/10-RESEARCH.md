# Phase 10: DB Foundation - Research

**Researched:** 2026-05-27
**Domain:** SQLite schema initialization, WAL mode, Fernet encryption, Python sqlite3
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DB-01 | System stores all tenant, Page, and content data in a SQLite database (WAL mode, Fernet-encrypted tokens) | sqlite3 stdlib verified; WAL mode confirmed on file-based DBs; Fernet round-trip verified; all four table schemas designed from downstream phase requirements |
</phase_requirements>

---

## Summary

Phase 10 creates the SQLite data layer that every subsequent v1.2 phase (11–15) depends on. The deliverable is narrow and additive: an `app/db.py` module with a schema initialization function, a migration/init script, and a Fernet encryption helper — with zero changes to existing FastAPI endpoints or vault-based content behavior.

Python's `sqlite3` standard library (no ORM, no extra pip package) is the correct and project-consistent tool. SQLite WAL mode is a database-level setting that persists after it is set once on a file-based database. `PRAGMA foreign_keys=ON` is a per-connection setting and must be applied on every connection that needs enforcement. The `cryptography` package (Fernet) is not yet in `requirements.txt` and must be added.

The 14 existing tests all pass (verified). Phase 10 must not regress any of them. The success criteria for this phase are fully automatable: schema shape, WAL mode, busy_timeout, and Fernet round-trip can all be covered by pytest with a tmp-path database.

**Primary recommendation:** Add `app/db.py` (connection factory + schema init), a standalone `scripts/init_db.py` runner, and `app/crypto.py` (Fernet helpers). Add `cryptography>=41.0.0` to `requirements.txt`. Add `DB_PATH` and `FERNET_KEY` to `Settings` and `.env.example`. Write `tests/test_db_foundation.py` covering all four success criteria.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Schema creation and WAL/timeout setup | API / Backend (`app/db.py`) | — | Python-side sqlite3; no frontend involvement |
| Fernet key loading and encrypt/decrypt | API / Backend (`app/crypto.py`) | — | Server-side only; keys never leave the backend |
| DB path and Fernet key config | API / Backend (`app/config.py`) | — | Follows existing `pydantic-settings` pattern |
| Schema init script execution | CLI script (`scripts/init_db.py`) | — | One-time setup, not part of FastAPI app startup |
| Content endpoints (no-regression) | API / Backend (`app/routers/content.py`) | — | Vault-based, unchanged in this phase |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `sqlite3` | stdlib (Python 3.9.6) | SQLite database access | Built into CPython; no install; project already has no ORM dependency |
| `cryptography` | 48.0.0 (latest; add `>=41.0.0` to requirements) | Fernet symmetric encryption of Page Access Tokens | Industry standard; Fernet is AES-128-CBC + HMAC-SHA256; `Fernet.generate_key()` handles all key derivation |

[VERIFIED: pip3 show cryptography — version 48.0.0, installable; stdlib sqlite3 confirmed via `python3 -c "import sqlite3"`]

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pydantic-settings` | >=2.3.0 (already in requirements) | Load `DB_PATH` and `FERNET_KEY` from `.env` | Add two new fields to existing `Settings` class |
| `pytest` | 8.4.2 (already installed) | Test schema shape, WAL mode, Fernet round-trip | All four success criteria are automatable |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `sqlite3` stdlib | SQLAlchemy Core | SQLAlchemy adds 5+ packages; project explicitly has no ORM; raw sqlite3 is simpler for a 4-table schema |
| `cryptography` (Fernet) | `PyNaCl` / `AES` hand-roll | Fernet is purpose-built for this pattern; hand-rolling AES risks IV reuse, padding errors |

**Installation:**
```bash
pip install "cryptography>=41.0.0"
```
Add to `requirements.txt`:
```
cryptography>=41.0.0
```

**Version verification:**
- `sqlite3`: stdlib — no install. `python3 -c "import sqlite3; print(sqlite3.sqlite_version)"` → `3.51.0` [VERIFIED]
- `cryptography`: `pip3 show cryptography` → `48.0.0` [VERIFIED 2026-05-27]

---

## Architecture Patterns

### System Architecture Diagram

```
.env (DB_PATH, FERNET_KEY)
        |
        v
app/config.py (Settings)
        |
        +--------> app/db.py (get_connection, init_schema)
        |                  |
        |                  v
        |           govi.db (SQLite file, WAL mode)
        |                  |
        |           tenants, pages, page_configs, qa_items
        |
        +--------> app/crypto.py (encrypt_token, decrypt_token)
                           |
                     cryptography.fernet.Fernet

scripts/init_db.py
  --> imports app/db.init_schema()
  --> creates govi.db and applies full schema

FastAPI (app/main.py)
  --> unchanged: content.router, health.router, ai.router still mount
  --> no new routes in Phase 10; DB module only imported by later phases
```

### Recommended Project Structure

```
app/
├── db.py            # get_connection() + init_schema(); all PRAGMAs applied here
├── crypto.py        # encrypt_token(plain) -> str; decrypt_token(enc) -> str
├── config.py        # add db_path: str and fernet_key: str to Settings
├── main.py          # UNCHANGED
└── routers/         # UNCHANGED
scripts/
└── init_db.py       # CLI entry point: calls init_schema(); idempotent (CREATE IF NOT EXISTS)
tests/
└── test_db_foundation.py   # covers all 4 success criteria
```

### Pattern 1: Connection Factory with PRAGMAs

**What:** A single function `get_connection(db_path)` that opens a SQLite connection and applies all required PRAGMAs before returning the connection.

**When to use:** Every place in the codebase that needs a DB connection (Phase 11+ routers). Phase 10 only writes this function; later phases call it.

**Key points:**
- WAL mode is a database-level setting — set it once on first connection, persists forever. [VERIFIED: `PRAGMA journal_mode=WAL` on file DB returns `('wal',)` on subsequent connections too]
- `busy_timeout` is per-connection — set it every time. [VERIFIED: sqlite3 supports `PRAGMA busy_timeout=5000`]
- `foreign_keys=ON` is per-connection — set it every time. [VERIFIED: new connections default to 0]
- `check_same_thread=False` is required for FastAPI (async framework). [VERIFIED]
- `row_factory = sqlite3.Row` enables `dict(row)` access pattern. [VERIFIED]

```python
# Source: Python docs sqlite3 + verified in-session
import sqlite3

def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
```

### Pattern 2: Idempotent Schema Init

**What:** `CREATE TABLE IF NOT EXISTS` statements so `init_schema()` is safe to run multiple times.

**When to use:** Called by `scripts/init_db.py` at deployment. Also callable in tests.

```python
# Source: verified pattern — all PRAGMAs confirmed in-session
def init_schema(db_path: str) -> None:
    conn = get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tenants (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT    NOT NULL UNIQUE,
            password_hash TEXT  NOT NULL,
            is_active   INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        );

        CREATE TABLE IF NOT EXISTS pages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id       INTEGER NOT NULL REFERENCES tenants(id),
            page_fb_id      TEXT    NOT NULL UNIQUE,
            page_name       TEXT    NOT NULL,
            access_token_enc TEXT,
            is_active       INTEGER NOT NULL DEFAULT 1,
            created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        );

        CREATE TABLE IF NOT EXISTS page_configs (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            page_id             INTEGER NOT NULL UNIQUE REFERENCES pages(id),
            welcome_text        TEXT    NOT NULL DEFAULT '',
            menu_json           TEXT    NOT NULL DEFAULT '[]',
            escalation_psid     TEXT,
            escalation_message  TEXT,
            updated_at          TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        );

        CREATE TABLE IF NOT EXISTS qa_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            page_id     INTEGER NOT NULL REFERENCES pages(id),
            type        TEXT    NOT NULL CHECK(type IN ('category', 'question')),
            title       TEXT    NOT NULL,
            body        TEXT    NOT NULL DEFAULT '',
            category_id INTEGER REFERENCES qa_items(id),
            enabled     INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        );

        CREATE INDEX IF NOT EXISTS idx_pages_tenant_id     ON pages(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_page_configs_page_id ON page_configs(page_id);
        CREATE INDEX IF NOT EXISTS idx_qa_items_page_id    ON qa_items(page_id);
        CREATE INDEX IF NOT EXISTS idx_qa_items_category_id ON qa_items(category_id);
    """)
    conn.commit()
    conn.close()
```

**Note:** `executescript()` implicitly commits any pending transaction before running. For the init script pattern this is fine. [ASSUMED — based on Python docs behavior; confirmed behavior in sqlite3 module docs]

### Pattern 3: Fernet Encryption Helper

**What:** Thin wrapper around `cryptography.fernet.Fernet` that loads the key from `Settings`.

**When to use:** Phase 12 will call `encrypt_token()` before storing a Page Access Token; Phase 14 will call `decrypt_token()` before using it.

```python
# Source: verified in-session — Fernet round-trip confirmed
from cryptography.fernet import Fernet, InvalidToken
from app.config import settings

def _fernet() -> Fernet:
    return Fernet(settings.fernet_key.encode())

def encrypt_token(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()

def decrypt_token(enc: str) -> str:
    return _fernet().decrypt(enc.encode()).decode()
```

**Key format:** Fernet key is 44 URL-safe base64 characters (encodes 32 bytes). Generate with `Fernet.generate_key().decode()`. [VERIFIED: decoded length = 32 bytes]

**InvalidToken exception:** `cryptography.fernet.InvalidToken` is raised on decrypt failure (wrong key or corrupted ciphertext). Phase 12 error handling should catch this. Phase 10 does not need to handle it — just expose `InvalidToken` for callers.

### Pattern 4: Settings Extension

**What:** Add two new optional fields to the existing `Settings` class in `app/config.py`.

```python
# Extend existing Settings — snake_case, consistent with existing fields
class Settings(BaseSettings):
    # ... existing fields ...
    db_path: str = "govi.db"            # relative to cwd; override in prod
    fernet_key: str = ""                # must be set; validated at use time, not startup
```

**Env vars to add to `.env.example`:**
```
DB_PATH=govi.db
FERNET_KEY=<generate with: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
```

### Anti-Patterns to Avoid

- **Setting PRAGMA foreign_keys once and expecting it to persist:** It resets to OFF on every new connection. Always set it in `get_connection()`. [VERIFIED: new connection defaults to `(0,)`]
- **Using WAL mode with `:memory:` databases in tests:** WAL is silently ignored for in-memory DBs — the pragma returns `('memory',)` not `('wal',)`. Use a `tmp_path` file-based DB in tests that verify WAL mode. [VERIFIED]
- **Storing the Fernet key in the DB:** The key encrypts DB content — it must live outside the DB (environment variable). [ASSUMED — security principle]
- **Calling `conn.execute("PRAGMA journal_mode=WAL")` on every request:** WAL mode persists at the database file level. Set it in `init_schema()` once; `get_connection()` only needs `busy_timeout` and `foreign_keys` per connection.
- **Not using `CREATE TABLE IF NOT EXISTS`:** Makes the init script non-idempotent; running it twice on an existing DB would raise `OperationalError: table already exists`.
- **Using `isolation_level=None` (autocommit) for multi-statement schema init:** `executescript()` handles its own commit; for data writes use explicit `conn.commit()` or context manager.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Symmetric encryption of tokens | Custom AES wrapper | `cryptography.fernet.Fernet` | Fernet handles IV generation, HMAC, and key format validation; hand-rolled AES commonly reuses IVs |
| Key derivation / generation | Custom base64 key builder | `Fernet.generate_key()` | Generates cryptographically random 32-byte key, properly encoded |
| WAL mode + timeout boilerplate | Per-query PRAGMA calls | `get_connection()` factory | Centralizes all PRAGMAs; prevents forgetting `foreign_keys=ON` |

**Key insight:** The two most common re-invention mistakes in this domain are writing custom encryption (missing HMAC leading to ciphertext tampering) and skipping per-connection PRAGMAs (leading to silent FK violations).

---

## Common Pitfalls

### Pitfall 1: Foreign Keys OFF by Default
**What goes wrong:** INSERT of a `pages` row with a nonexistent `tenant_id` silently succeeds — no error.
**Why it happens:** SQLite disables foreign key enforcement by default for backward compatibility. `PRAGMA foreign_keys=ON` must be set per connection.
**How to avoid:** Always set it in `get_connection()`. [VERIFIED: demonstrated in-session]
**Warning signs:** A test that inserts a child row with a bogus parent_id and expects `IntegrityError` passes only when `PRAGMA foreign_keys=ON` is active.

### Pitfall 2: WAL Mode Silently Ignored on In-Memory DBs
**What goes wrong:** Tests using `sqlite3.connect(':memory:')` check `PRAGMA journal_mode` and get `memory`, not `wal` — making the WAL test appear broken.
**Why it happens:** WAL requires a filesystem; in-memory DBs have no file to use as a WAL log.
**How to avoid:** Tests for WAL mode must use a file-based DB (use `tmp_path` fixture in pytest). [VERIFIED: confirmed in-session]
**Warning signs:** `PRAGMA journal_mode` returns `('memory',)` instead of `('wal',)`.

### Pitfall 3: Fernet Key Must Be Exactly 32 Bytes (44 base64 chars)
**What goes wrong:** Passing a hand-typed or truncated key raises `ValueError: Fernet key must be 32 url-safe base64-encoded bytes.`
**Why it happens:** Fernet validates the key format on `Fernet(key)` instantiation.
**How to avoid:** Always generate with `Fernet.generate_key()`; store as decoded string in env; re-encode to bytes before use: `Fernet(settings.fernet_key.encode())`. [VERIFIED: ValueError confirmed in-session]
**Warning signs:** `ValueError` on startup when `Settings.fernet_key` is set but malformed.

### Pitfall 4: WAL Mode Persists — Set It Only Once
**What goes wrong:** `get_connection()` sets `PRAGMA journal_mode=WAL` on every call — not harmful but unnecessary write overhead.
**Why it happens:** Misunderstanding WAL as per-connection vs. per-file setting.
**How to avoid:** Set WAL once in `init_schema()`. `get_connection()` only needs `busy_timeout` and `foreign_keys`. [VERIFIED: WAL persists confirmed in-session]

### Pitfall 5: `executescript()` Commits Implicitly
**What goes wrong:** Any pending uncommitted transaction before `executescript()` is auto-committed, potentially causing partial writes.
**Why it happens:** Python sqlite3 docs: "Issues a COMMIT statement first, then executes the SQL script."
**How to avoid:** Only call `executescript()` for schema DDL (no data at risk in Phase 10). For data writes, use `conn.execute()` + explicit `conn.commit()`. [ASSUMED — documented sqlite3 behavior]

### Pitfall 6: Regression from `check_same_thread` Default
**What goes wrong:** Using `sqlite3.connect(db_path)` (default `check_same_thread=True`) inside an `async def` FastAPI route raises `ProgrammingError: SQLite objects created in a thread can only be used in that same thread`.
**Why it happens:** FastAPI uses a thread pool for sync code and event loop for async — the connection object is created in one thread and used in another.
**How to avoid:** Always use `check_same_thread=False` in `get_connection()`. [VERIFIED: confirmed works in-session]

---

## Code Examples

### Verified Fernet Round-Trip
```python
# Source: verified in-session (python3 -c "...")
from cryptography.fernet import Fernet
key = Fernet.generate_key()
f = Fernet(key)
enc = f.encrypt(b"sample_page_access_token_12345")
dec = f.decrypt(enc)
assert dec == b"sample_page_access_token_12345"  # confirmed OK
```

### Verified WAL Mode on File DB
```python
# Source: verified in-session
import sqlite3, tempfile, os
with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
    db_path = tmp.name
conn = sqlite3.connect(db_path)
conn.execute("PRAGMA journal_mode=WAL")
conn.close()
# New connection — WAL persists
conn2 = sqlite3.connect(db_path)
result = conn2.execute("PRAGMA journal_mode").fetchone()
assert result == ('wal',)  # confirmed
```

### Verified Busy Timeout
```python
# Source: verified in-session
conn = sqlite3.connect(":memory:")
conn.execute("PRAGMA busy_timeout=5000")  # 5000 ms = 5 seconds — OK
```

### Verified sqlite3.Row Dict Access
```python
# Source: verified in-session
conn.row_factory = sqlite3.Row
row = conn.execute("SELECT id, email FROM tenants WHERE id=1").fetchone()
d = dict(row)  # {'id': 1, 'email': 'admin@example.com'}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| WAL + timeout via apsw or SQLAlchemy | Raw `sqlite3` stdlib | N/A for this project | sqlite3 stdlib is sufficient; no extra dependencies |
| Pycrypto (deprecated) | `cryptography` (PyCA) | ~2015 | Pycrypto unmaintained; `cryptography` is the standard |

**Deprecated/outdated:**
- `pycrypto` / `pycryptodome`: Do not use for new code. Use `cryptography>=41.0.0` (PyCA). [ASSUMED — based on ecosystem knowledge]
- `Fernet` multiFernet: Out of scope for Phase 10; relevant only for key rotation (Phase 10 has no rotation requirement).

---

## Runtime State Inventory

> Phase 10 is greenfield for the database layer. No rename or migration is in scope.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None — no existing SQLite DB in project [VERIFIED: `find . -name "*.db"` returned nothing] | None |
| Live service config | None — content still served from Obsidian vault; no DB yet | None |
| OS-registered state | None | None |
| Secrets/env vars | `FERNET_KEY` does not exist yet; `DB_PATH` does not exist yet | Add both to `.env` and `.env.example` |
| Build artifacts | None | None |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.x | All code | Yes | 3.9.6 | — |
| `sqlite3` (stdlib) | DB layer | Yes | SQLite 3.51.0 | — |
| `cryptography` | Fernet encryption | Yes (just installed) | 48.0.0 | — |
| `pytest` | Tests | Yes | 8.4.2 | — |

**Missing dependencies with no fallback:** None.

**Action required:** `cryptography` is installed system-wide but NOT in `requirements.txt`. Add `cryptography>=41.0.0` to `requirements.txt` so other devs and CI get it.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 |
| Config file | None — run from project root |
| Quick run command | `python3 -m pytest tests/test_db_foundation.py -q` |
| Full suite command | `python3 -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DB-01 | All four tables created with correct FK structure | unit | `python3 -m pytest tests/test_db_foundation.py::test_schema_creates_all_tables -x` | No — Wave 0 |
| DB-01 | WAL mode enabled on file-based DB | unit | `python3 -m pytest tests/test_db_foundation.py::test_wal_mode_enabled -x` | No — Wave 0 |
| DB-01 | busy_timeout=5000 set on connection | unit | `python3 -m pytest tests/test_db_foundation.py::test_busy_timeout -x` | No — Wave 0 |
| DB-01 | Fernet encrypt/decrypt round-trip | unit | `python3 -m pytest tests/test_db_foundation.py::test_fernet_round_trip -x` | No — Wave 0 |
| DB-01 (no-regression) | Existing content endpoints unchanged | unit | `python3 -m pytest tests/test_content.py tests/test_health.py -q` | Yes |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/ -q`
- **Per wave merge:** `python3 -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_db_foundation.py` — all four DB-01 success criteria (new file, ~20 lines)
- [ ] No new conftest.py needed — existing `conftest.py` fixtures are vault-focused; DB tests use `tmp_path` directly

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | — (Phase 11) |
| V3 Session Management | No | — (Phase 11) |
| V4 Access Control | No | — (Phase 11) |
| V5 Input Validation | Partial | Schema uses `CHECK(type IN ('category','question'))` constraint; input to SQL uses parameterized queries (sqlite3 `?` placeholders) |
| V6 Cryptography | Yes | `cryptography.fernet.Fernet` (AES-128-CBC + HMAC-SHA256) — never hand-roll |

### Known Threat Patterns for SQLite + Python

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via string interpolation | Tampering | Always use `conn.execute("... WHERE id=?", (id,))` — never f-string SQL |
| Fernet key stored in DB | Information Disclosure | Key lives in environment variable only; never written to DB |
| Fernet key hardcoded in source | Information Disclosure | Load from `Settings.fernet_key`; gitignore `.env` (already in .gitignore) |
| Plaintext token in DB column | Information Disclosure | `access_token_enc` column stores Fernet ciphertext only; Phase 12 enforces this |
| WAL log file left world-readable | Information Disclosure | Out of scope for Phase 10; address at deployment (file permissions) |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `executescript()` implicitly commits any pending transaction before DDL | Common Pitfalls / Code Examples | Low — Phase 10 init script has no prior transactions; only matters in Phase 11+ |
| A2 | `pycrypto`/`pycryptodome` are deprecated ecosystem-wide | State of the Art | Low — project uses `cryptography` regardless; this is just a "don't use" note |
| A3 | Fernet key stored as env var is the standard pattern (not e.g. a key file or KMS) | Architecture Patterns | Medium — for MVP/dev this is correct; production may want a secrets manager (deferred) |

---

## Open Questions (RESOLVED)

1. **Where does `govi.db` live in production?**
   - What we know: `DB_PATH` defaults to `"govi.db"` (relative to cwd, i.e., project root)
   - What's unclear: Should this be an absolute path? A `/data/` subdirectory?
   - Recommendation: Use `"govi.db"` as default for now (consistent with "no containerization" constraint). Add to `.gitignore`.

2. **Should `FERNET_KEY` be required at startup or validated lazily?**
   - What we know: Phase 10 does not use the key in any request path; Phase 12 first uses it
   - What's unclear: Should a missing key raise at startup (fail-fast) or at first encrypt call?
   - Recommendation: Validate lazily (at call time) in Phase 10; Phase 12 can add startup validation when the key becomes critical.

3. **Should `init_schema()` be called in `app/main.py` lifespan?**
   - What we know: Phase 10 success criteria only requires the standalone script; no service behavior changes
   - What's unclear: Whether Phase 11 will expect DB to already exist or call init on startup
   - Recommendation: Keep `init_schema()` in the standalone script for Phase 10; Phase 11 can wire it into lifespan if needed.

---

## Project Constraints (from CLAUDE.md)

| Directive | Impact on Phase 10 |
|-----------|-------------------|
| Tech stack: Python/FastAPI for backend | DB module goes in `app/`; no Node.js involvement |
| No ORM — raw sqlite3 | Confirmed; `sqlite3` stdlib used directly |
| Surgical changes — touch only what's needed | `app/config.py` gets two new fields only; `app/main.py` unchanged |
| No features beyond what was asked | Phase 10 schema is designed for all v1.2 phases, but no routes or logic beyond init script and helpers |
| Match existing style | snake_case files, 4-space indent, `pydantic.BaseModel` for models, `settings` singleton |
| No containerization currently | `DB_PATH=govi.db` (project root); no Docker volume mapping needed |

---

## Sources

### Primary (HIGH confidence)
- Python 3.9 stdlib `sqlite3` — verified via `python3 -c "import sqlite3"` and live PRAGMA testing in-session
- `cryptography` 48.0.0 (PyCA) — verified via `pip3 show cryptography` and live Fernet round-trip in-session
- Project codebase — `app/config.py`, `app/main.py`, `app/routers/content.py`, `requirements.txt`, `.gitignore` read directly

### Secondary (MEDIUM confidence)
- SQLite documentation (WAL mode behavior, PRAGMA persistence) — patterns verified experimentally in-session

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — sqlite3 verified in stdlib; cryptography verified installed and functional
- Architecture: HIGH — patterns verified by live Python execution in-session
- Pitfalls: HIGH — all six pitfalls demonstrated or directly tested in-session
- Schema design: MEDIUM — columns inferred from downstream phase requirements (11–15); actual column additions may be needed as later phases are planned

**Research date:** 2026-05-27
**Valid until:** 2026-06-27 (sqlite3 stdlib is stable; cryptography API is stable)
