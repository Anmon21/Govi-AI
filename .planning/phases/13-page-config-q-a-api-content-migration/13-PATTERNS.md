# Phase 13: Page Config, Q&A API + Content Migration - Pattern Map

**Mapped:** 2026-07-21
**Files analyzed:** 8 (2 rewrites, 2 modifications, 1 new script, 3 test files)
**Analogs found:** 7 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `app/routers/content.py` (rewrite) | controller/router | request-response (read-only CRUD subset) | `app/routers/pages.py` (HMAC guard @245-275) + itself (response models to preserve) | exact (guard) / role-match (queries) |
| `app/routers/pages.py` (extend) | controller/router | CRUD | itself — `disconnect_page` (164-196), `list_pages` (128-161) | exact |
| `app/main.py` (modify) | config / app-factory | event-driven (startup lifespan) | itself | exact |
| `scripts/seed_qa.py` (new) | script/utility | batch | `scripts/init_db.py` (CLI structure) + `app/routers/content.py::load_vault()` (parsing logic to lift) | exact (script shape) / exact (parsing) |
| `tests/test_content.py` (rewrite) | test | request-response | itself (existing structure) + `tests/test_pages.py` internal-key tests (469-527) | role-match |
| `tests/test_pages.py` (extend) | test | CRUD | itself — ownership-scoping tests (`test_internal_token_404_after_disconnect`, cross-tenant 404 pattern) | exact |
| `tests/conftest.py` (extend) | fixture/config | N/A | itself — `db_client` fixture (36-64) | exact |
| `tests/test_seed_qa.py` (new) | test | batch | none — no existing test covers `scripts/init_db.py` | no analog |

## Pattern Assignments

### `app/routers/content.py` (rewrite — DB-backed read endpoints)

**Analogs:** `app/routers/pages.py` for the HMAC guard; the **current** `app/routers/content.py` for the response-shape contract that MUST NOT change.

**Contract to preserve verbatim** (`app/routers/content.py:18-32`):
```python
class ContentResponse(BaseModel):
    id: str
    type: str
    title: str
    body: str


class ContentListItem(BaseModel):
    id: str
    type: str
    title: str


class ContentListResponse(BaseModel):
    items: list[ContentListItem]
```
Note: `qa_items.id` is an integer in the DB (D-03 decision: "DB integer `qa_items.id` returned to the bot as a string") — cast to `str(row["id"])` when building these models. Do not change the field names/nesting.

**X-Internal-Key HMAC guard — copy this exactly** (`app/routers/pages.py:245-256`):
```python
@router.get("/internal/pages/{page_fb_id}/access-token", include_in_schema=False)
async def get_internal_page_access_token(
    page_fb_id: str,
    x_internal_key: Annotated[Optional[str], Header()] = None,
) -> dict:
    if not settings.internal_secret:
        raise HTTPException(status_code=500, detail="INTERNAL_SECRET not configured")

    provided = (x_internal_key or "").encode()
    expected = settings.internal_secret.encode()
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="Forbidden")
```
Required imports for this pattern: `import hmac`, `from typing import Annotated, Optional`, `from fastapi import Header`. New read endpoints must apply this same guard, then resolve `page_id` (Facebook `page_fb_id` query param, per D-01/D-03) to the internal `pages.id` via a `SELECT id FROM pages WHERE page_fb_id = ? AND is_active = 1` lookup (mirrors `get_internal_page_access_token`'s own `page_fb_id` lookup at `pages.py:259-263`) before querying `qa_items`/`page_configs`. A page_fb_id that doesn't resolve should 404 (mirrors `pages.py:267-268`: `if not row: raise HTTPException(404, ...)`).

**Existing query/list semantics to preserve** (`app/routers/content.py:85-99`, now backed by SQL instead of the `_vault` dict):
```python
@router.get("", response_model=ContentListResponse)
async def list_content(
    type: str = Query("", description="Required. Filter by item type, e.g. 'category' or 'question'."),
    category: Optional[str] = Query(None, description="Optional. When type='question', restrict to a category id."),
):
    if not type:
        raise HTTPException(status_code=400, detail="type query parameter is required")
```
The `type == ""` → 400 check and the `category=None` → no filter behavior are both load-bearing (see `tests/test_content.py::test_list_missing_type_returns_400` and `test_list_unknown_category_returns_empty`) — reproduce with `WHERE page_id = ? AND type = ? AND enabled = 1 [AND category_id = ?]` using `?`-placeholders (`app/db.py:4` convention), never f-strings.

**Retire:** `_vault: dict[str, dict] = {}` (line 15), `load_vault()` (35-82, logic reusable by seed script — see below), `POST /content/reload` (110-115). Also remove the `app/main.py` lifespan hooks that populate `_vault` (see `app/main.py` entry below).

---

### `app/routers/pages.py` (extend — write API: config PUT + Q&A CRUD)

**Analog:** itself. This file already owns the `/pages/{page_id}/*` sub-resource family (`health`, disconnect) — add the new routes here rather than a new file, matching existing router organization (single `router = APIRouter(tags=["pages"])`, no path prefix, full paths declared per-route).

**Imports already present, reusable as-is** (`app/routers/pages.py:1-17`):
```python
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal, Optional
from urllib.parse import urlencode

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app import fb_client
from app.auth import get_current_tenant
from app.config import settings
from app.crypto import encrypt_token, decrypt_token
from app.db import get_connection
```

**JWT + ownership-scoping pattern to copy — `disconnect_page`** (`app/routers/pages.py:164-196`):
```python
@router.delete("/pages/{page_id}", status_code=200)
async def disconnect_page(
    page_id: int, current: dict = Depends(get_current_tenant)
) -> dict:
    tenant_id = int(current["sub"])
    conn = get_connection(settings.db_path)
    try:
        row = conn.execute(
            "SELECT id, page_fb_id, access_token_enc FROM pages "
            "WHERE id = ? AND tenant_id = ? AND is_active = 1",
            (page_id, tenant_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Page not found")
        ...
        conn.commit()
    finally:
        conn.close()
    return {"detail": f"Page {page_id} disconnected"}
```
The new endpoints must reproduce this shape exactly:
1. `tenant_id = int(current["sub"])`
2. Ownership check via `SELECT id FROM pages WHERE id = ? AND tenant_id = ? AND is_active = 1` first — 404 if absent (never leak existence of another tenant's page/row; see `page_health`, `pages.py:199-215`, for the read-side equivalent of the same check).
3. Only after ownership is confirmed, touch `page_configs` / `qa_items` scoped by that `page_id`.
4. `conn.commit()` inside `try`, `conn.close()` in `finally` — no context-manager wrapper used anywhere in this codebase; match it.

**Whole-row replace pattern (`PUT /pages/{page_id}/config`)** — no existing exact analog for an UPSERT/replace; closest shape is the insert-or-update branch in `_store_pages_and_subscribe` (`app/routers/pages.py:69-85`):
```python
existing = conn.execute(
    "SELECT id FROM pages WHERE page_fb_id = ? AND tenant_id = ?",
    (page_fb_id, tenant_id),
).fetchone()

if existing:
    conn.execute(
        "UPDATE pages SET access_token_enc = ?, page_name = ?, is_active = 1 "
        "WHERE page_fb_id = ? AND tenant_id = ?",
        (encrypted, page_name, page_fb_id, tenant_id),
    )
else:
    conn.execute(
        "INSERT INTO pages (tenant_id, page_fb_id, page_name, access_token_enc) "
        "VALUES (?, ?, ?, ?)",
        (tenant_id, page_fb_id, page_name, encrypted),
    )
```
Apply the same existing/insert-else-update branch against `page_configs` keyed on `page_id` (which is `UNIQUE` per `app/db.py:39`), after the ownership check on `pages`. `menu_json` is stored as a JSON string (`TEXT` column, `app/db.py:41`) — serialize the flat `[{title, payload}]` array with `json.dumps` before the write and `json.loads` on the way out (no existing JSON-column analog in this codebase — new pattern, D-04 schema).

**Insert-then-refetch pattern for Q&A `POST`** — copy from `app/routers/tenants.py:41-64` (`create_tenant`):
```python
cur = conn.execute(
    "INSERT INTO tenants (email, password_hash, is_super_admin) VALUES (?, ?, 0)",
    (request.email, pwd_context.hash(request.password)),
)
conn.commit()
new_id = cur.lastrowid
row = conn.execute(
    "SELECT id, email, is_active, is_super_admin, created_at FROM tenants WHERE id = ?",
    (new_id,),
).fetchone()
```
Use `cur.lastrowid` the same way for `qa_items` inserts, then re-`SELECT` to build the response model. Enforce the `category_id` referential check (per the `app/db.py:53` comment — application-layer only, no DB-level FK type constraint) before insert/update: if `category_id` is provided, `SELECT id FROM qa_items WHERE id = ? AND page_id = ? AND type = 'category'` and 400/404 if absent.

**Response models — inline Pydantic style** (mirrors `PageResponse` at `app/routers/pages.py:22-27` and `TenantResponse` at `app/routers/tenants.py:20-25`): define `PageConfigResponse`, `QAItemResponse` (and request bodies `PageConfigRequest`, `QAItemCreateRequest`/`QAItemUpdateRequest`) as `BaseModel` subclasses directly in `pages.py`, next to the existing response models.

---

### `app/main.py` (modify — retire vault lifespan wiring)

**Analog:** itself — minimal, surgical removal only.

**Current lifespan hook to remove** (`app/main.py:14-18`):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    content._vault.clear()
    content._vault.update(content.load_vault())
    yield
```
Since `_vault`/`load_vault()` are retired from `content.py`, this lifespan function (and the `lifespan=lifespan` kwarg on the `FastAPI(...)` constructor at line 21, and the now-unused `content` import reference if nothing else in `main.py` needs it) should be removed or reduced to a no-op `yield`-only lifespan if the app still needs the context-manager shape for other startup concerns. `app.include_router(content.router)` (line 32) stays — the router itself still exists, just DB-backed now.

---

### `scripts/seed_qa.py` (new — one-time vault→DB migration)

**Analog for script shape:** `scripts/init_db.py` (full file, reproduced below — this is the only standalone script in the repo and defines the CLI-script conventions: `sys.path.insert` shim, `if __name__ == "__main__":` guard, plain `print()` progress messages, `app.config.settings` for config, `app.db.get_connection` for DB access):
```python
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passlib.context import CryptContext

from app.db import init_schema, get_connection
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

if __name__ == "__main__":
    init_schema(settings.db_path)
    print(f"Schema initialized at {settings.db_path}")

    if not settings.super_admin_email or not settings.super_admin_password:
        raise RuntimeError("SUPER_ADMIN_EMAIL and SUPER_ADMIN_PASSWORD must be set in .env.")

    conn = get_connection(settings.db_path)
    try:
        existing = conn.execute(
            "SELECT id FROM tenants WHERE is_super_admin = 1"
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO tenants (email, password_hash, is_super_admin)"
                " SELECT ?, ?, 1 WHERE NOT EXISTS"
                " (SELECT id FROM tenants WHERE is_super_admin = 1)",
                (settings.super_admin_email, pwd_context.hash(settings.super_admin_password)),
            )
            conn.commit()
            print(f"Super-admin seeded: {settings.super_admin_email}")
        else:
            print("Super-admin row already present (idempotent skip)")
    finally:
        conn.close()
```
Note the idempotency style: a guard `SELECT` before insert, with a `print()` describing which branch was taken ("already present (idempotent skip)"). `seed_qa.py` should follow the same idempotent-with-print style, but D-03 specifies **wipe+reload** (not guard-and-skip) for `qa_items`: unconditionally `DELETE FROM qa_items WHERE page_id = ?` then re-insert from the vault, every run.

**CLI arg parsing:** no existing script takes CLI args (`init_db.py` reads only from `.env`/`settings`). Use stdlib `argparse` for `--page-fb-id` (no existing analog — new pattern, keep it minimal: one required string arg).

**Frontmatter-parsing logic to lift before `content.py`'s copy is deleted** — `load_vault()` (`app/routers/content.py:35-82`, reproduced in full since the seed script needs nearly all of it):
```python
def load_vault() -> dict[str, dict]:
    vault_path = settings.vault_path
    if not vault_path or not os.path.isdir(vault_path):
        logger.warning("VAULT_PATH not set or directory missing — starting with empty content")
        return {}

    result: dict[str, dict] = {}
    for entry in os.scandir(vault_path):
        if not entry.is_file() or not entry.name.endswith(".md"):
            continue
        try:
            with open(entry.path, encoding="utf-8") as f:
                post = frontmatter.load(f)
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
            logger.warning("Skipping %s: %s", entry.name, e)
            continue

        meta = post.metadata
        if not isinstance(meta.get("enabled"), bool) or not meta["enabled"]:
            continue

        content_id = meta.get("id")
        if not isinstance(content_id, str) or not content_id:
            logger.warning("Skipping %s: missing or non-string 'id'", entry.name)
            continue

        if content_id in result:
            logger.warning("ID collision: '%s' from %s (skipping duplicate)", content_id, entry.name)
            continue

        if not all(isinstance(meta.get(k), str) and meta.get(k) for k in ("type", "title")):
            logger.warning("Skipping %s: missing required string fields (type, title)", entry.name)
            continue

        category_value = meta.get("category")
        if category_value is not None and (not isinstance(category_value, str) or not category_value):
            logger.warning("Skipping %s: 'category' present but not a non-empty string", entry.name)
            continue

        result[content_id] = {
            "id": content_id,
            "type": meta["type"],
            "title": meta["title"],
            "category": category_value,
            "body": post.content,
        }

    return result
```
Required imports for this logic: `os`, `yaml`, `frontmatter`, `logging`. The seed script needs a **two-pass** insert because vault ids are strings but `qa_items` uses autoincrement integer ids with a self-referencing `category_id` FK: pass 1 inserts all `type == "category"` rows and builds a `{vault_string_id: new_int_id}` map; pass 2 inserts `type == "question"` rows resolving `meta["category"]` through that map to the new integer `category_id`. Sample vault fixtures for testing this against are in `vault-sample/*.md` (e.g. `vault-sample/q-products-01.md` has `category: cat-products` referencing `vault-sample/cat-products.md`'s `id: cat-products`).

**Resolving `--page-fb-id` to internal `pages.id`:** `SELECT id FROM pages WHERE page_fb_id = ?` (no tenant/JWT context in a CLI script — this is a superset of the read-endpoint lookup in the new `content.py`, minus the `is_active` filter since a script may target an inactive/test page deliberately; confirm with planner whether to filter `is_active = 1`).

**Ensuring the `page_configs` row exists (D-03)** — use the `INSERT ... SELECT ... WHERE NOT EXISTS` idiom already used in `init_db.py` (see the super-admin insert above) to seed a default row without a second round-trip:
```python
conn.execute(
    "INSERT INTO page_configs (page_id, welcome_text, menu_json)"
    " SELECT ?, '', '[]' WHERE NOT EXISTS"
    " (SELECT id FROM page_configs WHERE page_id = ?)",
    (page_id, page_id),
)
```
(`welcome_text`, `menu_json` defaults already match schema defaults at `app/db.py:40-41`; `escalation_psid`/`escalation_message` are nullable and need no explicit value.)

---

### `tests/test_content.py` (rewrite — DB-backed read endpoint tests)

**Analog:** itself (existing file defines the behavioral contract: 400 on missing `type`, 200+empty-list on unknown category, sorted-by-id list ordering — all of `tests/test_content.py:106-179` stays valid *behaviorally*, just needs the vault-fixture setup swapped for DB rows and a `page_id`/`X-Internal-Key` added to every request) plus `tests/test_pages.py` internal-key guard tests for the new auth layer.

**Existing DB-fixture pattern to reuse — `db_client`** (`tests/conftest.py:36-64`):
```python
@pytest.fixture
def db_client(tmp_path, monkeypatch):
    """TestClient wired to a tmp-path SQLite DB with a seeded super-admin row."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(config_module.settings, "db_path", db_path)
    monkeypatch.setattr(config_module.settings, "jwt_secret", "test-secret-do-not-use-in-prod")
    monkeypatch.setattr(config_module.settings, "fernet_key", Fernet.generate_key().decode())
    monkeypatch.setattr(config_module.settings, "fb_app_id", "test-app-id")
    monkeypatch.setattr(config_module.settings, "fb_app_secret", "test-app-secret")
    monkeypatch.setattr(config_module.settings, "fb_redirect_uri", "http://localhost:8000/auth/facebook/callback")
    monkeypatch.setattr(config_module.settings, "internal_secret", "test-internal-secret")
    init_schema(db_path)
    conn = get_connection(db_path)
    try:
        super_admin_password = "admin-pass"
        conn.execute(
            "INSERT INTO tenants (email, password_hash, is_super_admin) VALUES (?, ?, 1)",
            ("admin@test.local", _pwd_context.hash(super_admin_password)),
        )
        conn.commit()
        row = conn.execute("SELECT id FROM tenants WHERE is_super_admin = 1").fetchone()
        super_admin_id = row["id"]
    finally:
        conn.close()
    with TestClient(app) as c:
        yield SimpleNamespace(
            client=c,
            super_admin_id=super_admin_id,
            super_admin_email="admin@test.local",
            super_admin_password=super_admin_password,
            db_path=db_path,
        )
```
Reuse `db_client` as the base fixture for content tests (it already sets `internal_secret`). Add a page + `qa_items` seed helper alongside `_seed_page` (`tests/test_pages.py:42-55`) — a new `_seed_qa_item(db_path, page_id, type, title, body="", category_id=None)` helper following the same insert-and-return-lastrowid shape.

**HMAC-guard test pattern to copy — `test_internal_token_forbidden_without_key`** (`tests/test_pages.py:487-501`):
```python
def test_internal_token_forbidden_without_key(db_client):
    client = db_client.client
    client_id, _ = _make_client_token(db_client)
    _seed_page(db_client.db_path, client_id, "fb-page-777", "Internal Page", "the-page-token")

    # Missing header
    r_missing = client.get("/internal/pages/fb-page-777/access-token")
    assert r_missing.status_code == 403

    # Wrong secret
    r_wrong = client.get(
        "/internal/pages/fb-page-777/access-token",
        headers={"X-Internal-Key": "wrong-secret"},
    )
    assert r_wrong.status_code == 403
```
Apply the identical missing-header / wrong-secret 403 assertions to `GET /content` and `GET /content/{id}`.

**Existing list/filter test bodies to keep (adjusted for DB + page_id + header)** (`tests/test_content.py:106-179`) — e.g. `test_list_categories_only`, `test_list_questions_filtered_by_category`, `test_list_unknown_category_returns_empty`, `test_list_missing_type_returns_400`: same assertions, same status codes, same sort-by-id ordering — just replace `write_md`+`load_vault()` setup with DB inserts and add `page_id=<page_fb_id>` + the `X-Internal-Key` header to every `client.get(...)` call.

**Tests to delete (vault retired):** `test_vault_loads_at_startup`, `test_missing_vault_soft_fails`, `test_reload_endpoint`, `test_enabled_string_true_rejected` (this one's DB equivalent is just "insert with `enabled=0`, expect excluded" — much simpler, keep the intent not the vault mechanics).

---

### `tests/test_pages.py` (extend — config PUT + Q&A CRUD tests)

**Analog:** itself — the ownership-scoping / cross-tenant-404 pattern already proven for `disconnect_page`/`page_health` in this file. Apply the same shape to the new endpoints: (1) tenant A creates page + config/qa via JWT, (2) tenant B's JWT against the same `page_id` gets 404, (3) tenant A's own JWT succeeds.

**Reusable test helpers already in this file** (`tests/test_pages.py:32-55`):
```python
def _make_client_token(db_client) -> tuple[int, str]:
    """Create a client tenant via super-admin and return (client_id, client_token)."""
    ...

def _seed_page(db_path, tenant_id, page_fb_id, page_name, page_token) -> int:
    """Insert an active page row for tenant_id with an encrypted token; return lastrowid."""
    ...
```
New tests for `PUT /pages/{page_id}/config` and `/pages/{page_id}/qa[/{item_id}]` should live in this file (same module owns the routes) and reuse `_make_client_token` + `_seed_page` directly — no new fixture machinery needed beyond a `_seed_qa_item` helper (see previous section).

---

### `tests/conftest.py` (extend if a shared page+config fixture is warranted)

**Analog:** itself — `db_client` fixture (36-64, shown above). If multiple test files need a pre-seeded page + config row, add a `page_client` fixture layered on top of `db_client` following the same `SimpleNamespace` return-object convention already used.

---

### `tests/test_seed_qa.py` (new — seed script coverage)

**No analog** — `scripts/init_db.py` has zero test coverage in this repo (confirmed: no references to `init_db` anywhere under `tests/`). Planner should decide whether to write direct tests (import the seed script's functions and call them against a `tmp_path` DB + `vault-sample`-style fixture) or treat it as out-of-scope for automated tests, consistent with `init_db.py`'s precedent of no tests. If tests are written, follow the `db_client`/`vault_dir` fixture combination from `tests/conftest.py` (both fixtures already exist independently; a seed-script test needs both together, which no current fixture provides).

## Shared Patterns

### `?`-Placeholder SQL Convention
**Source:** `app/db.py:4` (comment) — enforced throughout `pages.py`, `tenants.py`, `auth.py`
**Apply to:** every new query in `content.py`, `pages.py` extensions, and `seed_qa.py`
```python
# get_connection — callers MUST use ? placeholders, never f-strings, for SQL parameters
```

### DB Connection Lifecycle
**Source:** `app/db.py:5-10`, used identically in every router
**Apply to:** all new endpoints and the seed script
```python
conn = get_connection(settings.db_path)
try:
    ...
    conn.commit()  # only on write paths
finally:
    conn.close()
```

### X-Internal-Key HMAC Guard
**Source:** `app/routers/pages.py:245-256`
**Apply to:** all `content.py` read endpoints (D-01)
(full excerpt under the `content.py` section above)

### JWT `get_current_tenant` + Tenant-Ownership Scoping
**Source:** `app/auth.py:42-43` (dependency) + `app/routers/pages.py:164-177` (usage)
**Apply to:** all `pages.py` write extensions (D-02)
```python
async def get_current_tenant(token: str = Depends(oauth2_scheme)) -> dict:
    return verify_token(token)
```
```python
tenant_id = int(current["sub"])
row = conn.execute(
    "SELECT id FROM pages WHERE id = ? AND tenant_id = ? AND is_active = 1",
    (page_id, tenant_id),
).fetchone()
if not row:
    raise HTTPException(status_code=404, detail="Page not found")
```

### `HTTPException` Error Handling (no try/except)
**Source:** `app/auth.py:25-39`, every router
**Apply to:** all new endpoints — raise `HTTPException(status_code=..., detail=...)` directly; do not wrap DB calls in try/except (matches CLAUDE.md conventions: "no try/except blocks in Python routers").

### Inline Pydantic Response/Request Models
**Source:** `app/routers/pages.py:22-32`, `app/routers/tenants.py:15-38`, `app/routers/ai.py:10-20`
**Apply to:** `PageConfigResponse`/`PageConfigRequest`, `QAItemResponse`/`QAItemCreateRequest`/`QAItemUpdateRequest` in `pages.py`; keep `ContentResponse`/`ContentListResponse`/`ContentListItem` unchanged in `content.py`.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `tests/test_seed_qa.py` | test | batch | No existing test covers the only prior standalone script (`scripts/init_db.py`); no fixture combines `db_client` + `vault_dir` today |
| UPSERT/whole-row-replace for `page_configs` | (pattern, not a file) | CRUD | No existing insert-or-update targets a `UNIQUE`-constrained single-row-per-parent table; closest is the insert/update branch in `_store_pages_and_subscribe` (`pages.py:69-85`), adapted above |
| JSON-serialized column (`menu_json`) | (pattern, not a file) | transform | No existing router reads/writes a JSON-string DB column; `json.dumps`/`json.loads` at the router boundary is a new pattern for this codebase |

## Metadata

**Analog search scope:** `app/`, `app/routers/`, `scripts/`, `tests/`, `vault-sample/`
**Files scanned:** `app/routers/content.py`, `app/routers/pages.py`, `app/routers/tenants.py`, `app/routers/auth.py`, `app/routers/ai.py`, `app/db.py`, `app/auth.py`, `app/config.py`, `app/main.py`, `scripts/init_db.py`, `tests/conftest.py`, `tests/test_content.py`, `tests/test_pages.py`, `vault-sample/*.md`
**Pattern extraction date:** 2026-07-21
