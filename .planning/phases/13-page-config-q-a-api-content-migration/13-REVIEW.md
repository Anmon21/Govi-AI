---
phase: 13-page-config-q-a-api-content-migration
reviewed: 2026-08-11T04:10:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - app/main.py
  - app/routers/content.py
  - app/routers/health.py
  - app/routers/pages.py
  - scripts/seed_qa.py
  - tests/conftest.py
  - tests/test_content.py
  - tests/test_health.py
  - tests/test_pages.py
  - tests/test_seed_qa.py
findings:
  critical: 1
  warning: 18
  info: 11
  total: 30
status: issues_found
---

# Phase 13: Code Review Report

**Reviewed:** 2026-08-11T04:10:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Second adversarial pass over the phase-13 surface: the DB-backed `/content` read API,
the tenant-scoped config + Q&A write API in `app/routers/pages.py`, the vault→DB seed
script, and the four test modules. Every finding below marked "proven" was reproduced
against a live SQLite DB / `TestClient`, not inferred from reading. The suite passing
(76 tests) is not evidence of correctness — three of the proven defects below sit
directly under code the suite exercises.

**Status of prior findings, per the review brief:**

- **CR-01 (13-06 fix) — verified real, but incomplete.** The `if not items:` guard at
  `scripts/seed_qa.py:81-83` does fire before the `DELETE` at line 85 and does preserve
  content for the three cases the new tests cover (unset / missing dir / empty dir).
  I confirmed that. But the guard checks the *wrong* quantity: it gates on "did the
  vault parse into any items", not on "will any rows be written". Two realistic
  misconfigurations still walk straight past it and wipe the page's entire Q&A
  content while printing a success message and exiting 0. See **CR-01** below — this
  is not a re-report of the closed finding, it is the surviving half of it.
- **WR-12 (`--force` / row-count precheck)** — not raised. It conflicts with locked
  decision D-03 (idempotent wipe+reload) and would break `test_seed_is_idempotent`.
- **CR-02 (bot `/content` contract)** — out of scope, deferred to Phase 14 per D-01.
- **WR-01 / WR-02 / WR-03 / WR-04 / WR-05 / WR-06 / WR-07 / WR-08 / WR-09 / WR-10 /
  WR-11** — all re-tested, all still present. Re-verified with fresh reproductions
  where the prior report's proof was ambiguous; carried forward with the same IDs.

Seven findings are new to this pass (WR-12 through WR-18, IN-09 through IN-11), all
proven: silent partial content loss on a partially-broken vault, three separate paths
that turn a DB/deserialization failure into an unhandled 500, JWT purpose confusion,
a replayable OAuth state token, and event-loop blocking that lets a slow Facebook
response take the bot offline.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: `seed_qa` still destroys a page's entire Q&A content — the 13-06 guard checks the wrong quantity

**File:** `scripts/seed_qa.py:81-83` (guard), `scripts/seed_qa.py:85` (DELETE),
`scripts/seed_qa.py:89-115` (inserts), `scripts/seed_qa.py:124-125` (commit + success print)

**Issue:** The guard added by 13-06 aborts only when `load_vault_items()` returns an
*empty list*. It does not verify that any row will actually be inserted. Between the
guard and the `DELETE` there are three more filters that can silently drop every
single item:

- `item["type"] != "category"` / `!= "question"` (lines 90, 102) — items with any
  other `type` value are skipped. `load_vault_items` only requires `type` to be a
  non-empty string (line 45), so a vault of `type: note` / `type: article` files
  parses cleanly into `items` and inserts nothing.
- `category_id is None` → "unknown category" skip (lines 106-109) — questions whose
  category file is not in the same directory are all skipped.

In both cases `items` is non-empty, the guard passes, `DELETE FROM qa_items WHERE
page_id = ?` runs, zero rows are inserted, `conn.commit()` at line 124 is
unconditional, and line 125 prints **`Seeded 0 categories, 0 questions`** with exit
code 0.

Reproduced twice against a live DB seeded with the real `vault-sample/` content
(5 rows):

```
# (a) VAULT_PATH pointed at a markdown directory with non-Q&A frontmatter types
rows before: 5
Seeded 0 categories, 0 questions for page fb-1
rows after: 0 DATA LOSS: True

# (b) VAULT_PATH pointed at a questions-only subfolder (categories live one level up)
rows before: 5
Skipping question 'q-products-01': unknown category 'cat-products'
Skipping question 'q-shipping-01': unknown category 'cat-shipping'
Skipping question 'q-shipping-02': unknown category 'cat-shipping'
Seeded 0 categories, 0 questions for page fb-1
rows after: 0 DATA LOSS: True
```

Case (b) is the likely one in practice: an operator points `VAULT_PATH` at
`vault/questions/` instead of `vault/`, or at a vault that has been reorganised into
subfolders since (`os.scandir` at line 26 does not recurse). There is no backup, no
`--dry-run`, and no non-zero exit to catch it in a deploy script. The existing tests
(`tests/test_seed_qa.py:142-201`) only parametrise over `unset` / `missing_dir` /
`empty_dir` — all three of which produce an empty `items` list and therefore only
exercise the half of the problem that was fixed.

**Fix:** Gate on rows actually written, immediately before the commit, and roll back
if nothing was inserted. This covers every current and future skip path, including
ones added later:

```python
        # ... after both insert loops, before the page_configs INSERT
        if category_count + question_count == 0:
            conn.rollback()
            print(
                f"Refusing to seed: {len(items)} vault item(s) parsed from "
                f"{settings.vault_path!r} but none were insertable as a category or "
                f"question. Existing content for {page_fb_id!r} left intact."
            )
            sys.exit(1)

        conn.execute(
            "INSERT INTO page_configs (page_id, welcome_text, menu_json) ..."
        )
        conn.commit()
```

Extend the `bad_vault_kind` parametrisation in
`tests/test_seed_qa.py:142` with two more cases — a directory of `type: note`
frontmatter, and a questions-only directory — asserting the same
`SystemExit(1)` + content-preserved + `"Seeded" not in out` contract.

---

## Warnings

### WR-01: `delete_qa` still has no `sqlite3.IntegrityError` handler — the 500 is reachable

**File:** `app/routers/pages.py:556-580` (guard at `:568-572`, delete at `:574-576`);
helper `app/routers/pages.py:398-404`

**Issue:** Unchanged since the last pass — `import sqlite3` still does not appear in
`pages.py`. `_has_dependent_qa_items` filters on `page_id = ?` while the FK it guards
(`category_id INTEGER REFERENCES qa_items(id)`, `app/db.py:54`) has no page scope, so
any dependent outside the guard's page reaches the raw `DELETE`.

Re-reproduced cleanly (a page-2 row referencing a page-1 category with no same-page
dependents, so the 409 pre-check cannot mask it):

```
DELETE RAISED UNHANDLED: IntegrityError FOREIGN KEY constraint failed
```

The API cannot currently create such a reference (`_validate_category_ref` is
page-scoped on both create and update), so this is latent rather than actively
exploitable — but the seed script, `scripts/init_db.py`, a restore, or any future
bulk-import writes directly to `qa_items` with no such guard. `delete_qa` also has no
`conn.rollback()`; it relies on `close()` rolling back implicitly.

**Fix:**

```python
import sqlite3
...
        try:
            conn.execute(
                "DELETE FROM qa_items WHERE id = ? AND page_id = ?", (item_id, page_id)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            raise HTTPException(
                status_code=409,
                detail="Item is still referenced by other Q&A content",
            )
```

---

### WR-02: retype guard is page-scoped while the FK is global — cross-page orphans still land

**File:** `app/routers/pages.py:516-520` (guard), `app/routers/pages.py:398-404` (helper)

**Issue:** Same root cause as WR-01. Re-reproduced with a clean fixture:

```
RETYPE cross-page -> 200 {'id': 1, 'type': 'question', 'category_id': None, ...}
  p2 dependent now points at: [(2, 1, 'question')]   # (dependent id, category_id, parent type)
```

The dependent now references a `question`-typed row — the exact orphan state the
13-05 fix was written to prevent. `_validate_category_ref` would reject that
reference on any subsequent write, so the row is stuck: it cannot be updated again
without first clearing `category_id`.

**Fix:** Match the helper's scope to the FK's scope. The `page_id` filter buys nothing
(`qa_items.id` is globally unique) and only creates blind spots:

```python
def _has_dependent_qa_items(conn, item_id: int) -> bool:
    """Report whether ANY qa_items row references item_id as its category_id."""
    row = conn.execute(
        "SELECT 1 FROM qa_items WHERE category_id = ? LIMIT 1", (item_id,)
    ).fetchone()
    return bool(row)
```

Update both call sites (`pages.py:516`, `pages.py:568`) and add cross-page regression
coverage.

---

### WR-03: category→category references create cycles, and the 409 that blocks them states a false reason

**File:** `app/routers/pages.py:384-395` (`_validate_category_ref`),
`app/routers/pages.py:510-513`, `app/routers/pages.py:568-572`

**Issue:** `_validate_category_ref` checks only that `category_id` points at *a
category on this page* — never that the row being written is a question. The
self-reference check at `:510-513` blocks only the direct `C → C` case. Re-reproduced
through the public admin API:

```
create child category with category_id -> 201 {'id': 2, 'type': 'category', 'category_id': 1}
make 2-cycle                          -> 200 {'id': 1, 'type': 'category', 'category_id': 2}
DELETE parent                         -> 409 {'detail': 'Category has questions; delete or reassign them first'}
```

Both rows are now undeletable, and the 409 names an entity that does not exist —
there are no questions. The only escape is guessing that you must first
`PUT category_id: null` on one of them. Nothing in the data model wants nested
categories (D-04 explicitly rejects nesting), so this is accidental capability.

**Fix:** Reject `category_id` on category-typed rows in both `create_qa` and
`update_qa`, and make the 409 accurate:

```python
def _validate_category_ref(conn, page_id: int, item_type: str, category_id: Optional[int]) -> None:
    if category_id is None:
        return
    if item_type == "category":
        raise HTTPException(
            status_code=400, detail="category_id is only valid on items of type 'question'"
        )
    ...

# pages.py:568-572
raise HTTPException(
    status_code=409,
    detail="This item is still referenced by other Q&A content; reassign or delete it first",
)
```

---

### WR-04: nested categories are served to the bot as top-level menu entries

**File:** `app/routers/content.py:73-86`

**Issue:** `list_content` applies the `category_id` filter only when the caller passes
`category`; for `type=category` it never filters on `category_id`. Any child category
created per WR-03 is returned alongside its own parent. Re-reproduced:

```
/content?type=category&page_id=fb-1 ->
  {'items': [{'id': '1', 'title': 'Parent'}, {'id': '2', 'title': 'Child'}]}
```

The bot maps these straight into quick replies, so a sub-topic surfaces as a peer of
its parent.

**Fix:** Fixing WR-03 removes the cause. Make the intent explicit anyway, on the
`type='category'` branch:

```python
"SELECT id, type, title FROM qa_items "
"WHERE page_id = ? AND type = ? AND enabled = 1 AND category_id IS NULL "
"ORDER BY id ASC"
```

---

### WR-05: disabling a category does not hide its questions

**File:** `app/routers/content.py:73-94`, `app/routers/content.py:113-117`

**Issue:** `enabled = 1` is applied per-row with no regard for the parent category's
state. Re-reproduced end-to-end through the write API and then the read API:

```
categories:                  {'items': []}                       # parent hidden
questions under disabled cat:{'items': [{'id': '3', 'title': 'Q under parent'}]}
direct GET question:         200
```

The bot embeds content ids directly in quick-reply payloads (`CATEGORY:<id>` /
`QUESTION:<id>`), so a user with an older message in their thread can still tap
through to content the admin believes they have taken down. An admin who disables a
category to pull incorrect information has not pulled it.

**Fix:** Filter on the parent's state as well, in both list and get:

```python
"SELECT q.id, q.type, q.title FROM qa_items q "
"LEFT JOIN qa_items c ON q.category_id = c.id "
"WHERE q.page_id = ? AND q.type = ? AND q.enabled = 1 "
"  AND (q.category_id IS NULL OR c.enabled = 1) "
"ORDER BY q.id ASC"
```

---

### WR-06: no size or count validation on any admin-supplied content field

**File:** `app/routers/pages.py:36-48`, `app/routers/pages.py:66-80`

**Issue:** Every string field is a bare `str`; `menu_json` is an unbounded
`list[MenuItem]`. Re-reproduced:

```
POST qa title=''                                        -> 201
PUT config welcome_text 100_000 chars, 50 menu items
    (titles 500 chars, payloads 5000 chars)             -> 200
```

Messenger limits: message text 2000, quick-reply title 20, postback payload 1000,
persistent menu 3 top-level items. This API is the only validation boundary before
the data reaches Facebook; violations currently surface as opaque Graph API errors in
bot logs, far from the admin who caused them. An empty `title` yields a quick reply
Facebook refuses outright.

**Fix:**

```python
from pydantic import Field

class MenuItem(BaseModel):
    model_config = {"extra": "forbid"}
    title: str = Field(min_length=1, max_length=20)
    payload: str = Field(min_length=1, max_length=1000)

class PageConfigRequest(BaseModel):
    welcome_text: str = Field(max_length=2000)
    menu_json: list[MenuItem] = Field(max_length=3)
    escalation_psid: Optional[str] = Field(default=None, max_length=64)
    escalation_message: Optional[str] = Field(default=None, max_length=2000)

class QAItemCreateRequest(BaseModel):
    type: Literal["category", "question"]
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=2000)
    ...
```

---

### WR-07: re-seeding reassigns every content id; the "idempotent" test only counts rows

**File:** `scripts/seed_qa.py:85-115`; test at `tests/test_seed_qa.py:91-110`

**Issue:** Wipe + re-insert against `INTEGER PRIMARY KEY AUTOINCREMENT`
(`app/db.py:48`) means ids never repeat. Re-reproduced:

```
ids after 1st seed: [(1,'category','Products'), (2,'category','Shipping'), (3..5 questions)]
ids after 2nd seed: [(6,'category','Products'), (7,'category','Shipping'), (8..10 questions)]
```

Those ids are the bot's routing keys (`CATEGORY:<id>` / `QUESTION:<id>`) and anything
an admin hand-authored into `page_configs.menu_json`. After a re-seed every
previously-issued quick reply 404s, with nothing at seed time to indicate it.
`test_seed_is_idempotent` asserts only `first_count == second_count == 5`, so it
certifies "idempotent" while the identifiers underneath churn completely.

**Fix:** Key on the vault's stable `id` (add a `vault_id TEXT` column with
`UNIQUE(page_id, vault_id)` and `INSERT ... ON CONFLICT DO UPDATE`), or at minimum
make the test tell the truth:

```python
def _snapshot(db_path, page_id):
    conn = get_connection(db_path)
    try:
        return [tuple(r) for r in conn.execute(
            "SELECT id, type, title, category_id FROM qa_items WHERE page_id = ? ORDER BY id",
            (page_id,))]
    finally:
        conn.close()

assert _snapshot(...) == _snapshot(...), "re-seed must preserve ids — bot payloads depend on them"
```

---

### WR-12: the seed script exits 0 after partial vault failures — silent content loss (NEW)

**File:** `scripts/seed_qa.py:29-52` (per-file skips), `scripts/seed_qa.py:106-109`
(unknown-category skips), `scripts/seed_qa.py:124-125`

**Issue:** Distinct from CR-01, which covers the total-loss case. When *some* items
parse and some do not, the script wipes the page and reloads only the survivors,
prints a "Seeded N categories, M questions" success line, and exits 0. Every skip is
a `print` on stdout that a deploy log will bury.

Reproduced with one corrupt frontmatter file in an otherwise valid vault:

```
Skipping cat-products.md: while parsing a flow sequence ...
Skipping question 'q-products-01': unknown category 'cat-products'
Seeded 1 categories, 2 questions for page fb-1
rows after: [(6,'category','Shipping'), (7,'question','Shipping time?',6), (8,'question','Ship abroad?',6)]
```

One malformed file silently deleted a category and its question from the live page,
and the operator's exit code says success.

**Fix:** Count skips and fail the run (before commit) when any occurred, unless the
operator opts in:

```python
skipped = 0   # incremented at each `continue` in load_vault_items() and the question loop
...
if skipped:
    conn.rollback()
    print(f"Refusing to seed: {skipped} vault item(s) could not be migrated. "
          f"Fix them or re-run with --allow-partial. Existing content left intact.")
    sys.exit(1)
```

Also report the destructive half of the operation: `print(f"Removed {existing} rows; seeded ...")`.

---

### WR-13: check-then-insert races and page transfers surface as unhandled 500s (NEW)

**File:** `app/routers/pages.py:325-353` (`put_page_config`),
`app/routers/pages.py:127-143` (`_store_pages_and_subscribe`)

**Issue:** Both write paths do `SELECT` → branch → `INSERT`, against columns carrying
`UNIQUE` constraints (`page_configs.page_id` at `app/db.py:39`, `pages.page_fb_id` at
`app/db.py:30`). No `sqlite3.IntegrityError` handler exists anywhere in the module,
so a lost race becomes a stack trace.

Proven that the constraints bite:

```
dup insert into page_configs -> IntegrityError UNIQUE constraint failed: page_configs.page_id
```

And a reachable, non-racy instance of the same gap: when a Facebook page is moved
between customers (tenant A disconnects it, tenant B connects it), the UPSERT lookup
is `WHERE page_fb_id = ? AND tenant_id = ?`, misses, and falls through to `INSERT`:

```
_store_pages_and_subscribe([... 'fb-1' ...], other_tenant) -> IntegrityError UNIQUE constraint failed: pages.page_fb_id
```

Tenant B gets a 500 from `/auth/facebook/callback` and can never connect that page.

**Fix:** Use SQLite's atomic upsert instead of check-then-insert, and handle the
remaining constraint explicitly:

```python
conn.execute(
    "INSERT INTO page_configs (page_id, welcome_text, menu_json, escalation_psid, escalation_message) "
    "VALUES (?, ?, ?, ?, ?) "
    "ON CONFLICT(page_id) DO UPDATE SET welcome_text=excluded.welcome_text, "
    "menu_json=excluded.menu_json, escalation_psid=excluded.escalation_psid, "
    "escalation_message=excluded.escalation_message, "
    "updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')",
    (page_id, request.welcome_text, menu_str, request.escalation_psid, request.escalation_message),
)
```

For the page-transfer case, look the page up by `page_fb_id` alone and return a clear
409 ("this Page is already connected to another account") rather than a 500.

---

### WR-14: malformed `menu_json` in the DB takes the bot-facing config endpoint to a 500 (NEW)

**File:** `app/routers/pages.py:662` (`get_internal_page_config`),
`app/routers/pages.py:367` (`put_page_config`)

**Issue:** `[MenuItem(**item) for item in json.loads(config_row["menu_json"])]`
trusts the stored string completely — no `try`, no shape check. Proven with rows the
schema happily accepts:

```
menu_json = '{"not":"a list"}'  -> RAISED UNHANDLED: TypeError  MenuItem() argument after ** must be a mapping, not str
menu_json = 'not json'          -> RAISED UNHANDLED: JSONDecodeError Expecting value: line 1 column 1
```

`page_configs.menu_json` is a plain `TEXT NOT NULL DEFAULT '[]'` column with no CHECK
constraint, writable by `scripts/init_db.py`, restores, manual `sqlite3` sessions, and
any future admin tooling. One bad row 500s the endpoint the bot depends on for every
message, and the same row makes the tenant's own config page un-loadable.

**Fix:** Degrade instead of crashing, and log:

```python
def _parse_menu(raw: str) -> list[MenuItem]:
    try:
        data = json.loads(raw)
        return [MenuItem(**item) for item in data]
    except (json.JSONDecodeError, TypeError, ValidationError):
        return []
```

---

### WR-15: one JWT signing key serves two token purposes; confusion yields unhandled 500s (NEW)

**File:** `app/routers/pages.py:93-113` (state tokens), `app/auth.py:14-27`
(access tokens), consumed at `app/routers/pages.py:176`, `:188`, `:226`, `:261`,
`:313`, `:413`, `:446`, `:504`, `:562`

**Issue:** OAuth state tokens (`{tenant_id, nonce, exp}`) and API access tokens
(`{sub, role, exp}`) are both HS256-signed with `settings.jwt_secret` and carry no
`typ`/audience claim, so each verifies as the other. The handlers then index a claim
that is not there. Proven:

```
access token replayed as OAuth state -> RAISED UNHANDLED: KeyError 'tenant_id'
oauth state replayed as bearer token -> RAISED UNHANDLED: KeyError 'sub'
```

Both should be a 400/401. Instead they are unhandled `KeyError`s — 500 plus a stack
trace. There is no privilege escalation today (neither payload satisfies the other
side's authorization checks), but "two token types, one key, no discriminator" is one
added claim away from becoming one, and `int(current["sub"])` / `int(tenant_id_str)`
will `ValueError` on any non-numeric subject for the same reason.

**Fix:** Add a purpose claim and verify it; validate the subject shape once:

```python
payload = {"typ": "oauth_state", "tenant_id": tenant_id, "nonce": ..., "exp": ...}
...
decoded = jwt.decode(state, settings.jwt_secret, algorithms=["HS256"])
if decoded.get("typ") != "oauth_state" or "tenant_id" not in decoded:
    raise HTTPException(status_code=400, detail="Invalid OAuth state")
```

and in `app/auth.py`, reject tokens whose `sub` is missing or non-numeric with a 401.

---

### WR-16: the OAuth state token is replayable for its full 10-minute lifetime (NEW)

**File:** `app/routers/pages.py:93-102`, `app/routers/pages.py:105-113`,
`app/routers/pages.py:174-183`

**Issue:** `create_oauth_state` mints a `nonce` (line 99) but nothing ever records or
consumes it, and `/auth/facebook/callback` is unauthenticated. The state is therefore
a bearer capability to attach Facebook pages to the issuing tenant, valid for ten
minutes and reusable. Proven:

```
1st:          {'pages_connected': 1}
2nd (replay): {'pages_connected': 1}
```

A state value leaking through browser history, a `Referer` header, or a proxy log
lets a third party bind *their* Facebook pages to the victim's tenant — inbound
messages for those pages then flow through the victim's account.

**Fix:** Make state single-use — persist `nonce` (or a `jti`) on issue and delete it
on first successful callback, rejecting any state whose nonce is already consumed.

---

### WR-17: blocking Graph API calls inside `async` handlers stall the whole process (NEW)

**File:** `app/routers/pages.py:200-218` (`list_pages`, one call per page),
`app/routers/pages.py:285-289` (`page_health`)

**Issue:** Both handlers are `async def` but call synchronous `httpx.get` directly on
the event loop. `list_pages` does it in a loop — N pages, N serial blocking calls. No
explicit timeout is set, so each falls back to httpx's default. While that loop runs,
*every other request in the process is frozen*, including the bot's `/content` and
`/internal/pages/{id}/config` calls. A single admin refreshing a 10-page dashboard
during a slow Facebook response takes customer-facing messaging offline for the
duration. This is an availability property, not a throughput optimisation.

**Fix:** Use `httpx.AsyncClient` with an explicit timeout and gather concurrently, or
push the blocking call off-loop:

```python
from fastapi.concurrency import run_in_threadpool
is_valid = await run_in_threadpool(fb_client.check_token_health, page_token)
```

---

### WR-08: the internal-key check is implemented three separate times

**File:** `app/routers/content.py:30-37`, `app/routers/pages.py:588-594`,
`app/routers/pages.py:627-633`

**Issue:** Three byte-identical copies of the same security-critical logic. Only one
is a named function; the other two are inlined in handler bodies — and one of those
(`get_internal_page_config`, added this phase) was written as a fresh copy rather
than a reuse. Any future change (rotation, minimum-length guard, audit logging) will
be applied to one or two of the three.

**Fix:** Promote to a shared dependency and delete the copies:

```python
# app/internal_auth.py
def require_internal_key(x_internal_key: Annotated[Optional[str], Header()] = None) -> None:
    if not settings.internal_secret:
        raise HTTPException(status_code=500, detail="INTERNAL_SECRET not configured")
    if not hmac.compare_digest((x_internal_key or "").encode(), settings.internal_secret.encode()):
        raise HTTPException(status_code=403, detail="Forbidden")

# usage
@router.get("", response_model=ContentListResponse, dependencies=[Depends(require_internal_key)])
```

---

### WR-09: `page_health` reaches into `fb_client.httpx` and conflates network failure with revocation

**File:** `app/routers/pages.py:283-292`; related `app/routers/pages.py:209`

**Issue:** Unchanged. `fb_client.httpx.get(fb_client.GRAPH_BASE + "/debug_token", ...)`
reaches through `fb_client` into its imported module rather than calling a function on
it — production code depending on a path that exists for test monkeypatching — and
duplicates `fb_client.check_token_health` (`app/fb_client.py:90-104`). The bare
`except Exception: return HealthResponse(is_valid=False, ...)` at `:291-292` makes a
DNS failure, a timeout and a Facebook 500 indistinguishable from a revoked token;
`check_token_health` has the same swallow, so `GET /pages` marks *every* page
`"revoked"` during any transient outage.

**Fix:** Move the call into `fb_client` as a `debug_token()` helper that returns
`None` on `httpx.HTTPError` (with an explicit `timeout=`), and surface `None` as a
distinct `"unknown"` status rather than `"revoked"`.

---

### WR-10: wildcard CORS on a now-authenticated multi-tenant admin API

**File:** `app/main.py:15-20`

**Issue:** `allow_origins=["*"]` / `allow_methods=["*"]` / `allow_headers=["*"]` was
defensible when this app served only `/health` and `/ai/chat`. It now covers
`/auth/login`, `/admin/tenants`, `/pages`, `/pages/{id}/config` and the full Q&A CRUD.
`allow_credentials` is unset, so cookies are not in play and this is not directly
exploitable — but any origin can invoke every admin mutation and read the response
body the moment it obtains a bearer token, and there is no allowlist in place for the
Phase 15 SPA.

**Fix:**

```python
# app/config.py
allowed_origins: str = "http://localhost:5173"

# app/main.py
allow_origins=[o.strip() for o in settings.allowed_origins.split(",") if o.strip()],
allow_methods=["GET", "POST", "PUT", "DELETE"],
allow_headers=["Authorization", "Content-Type", "X-Internal-Key"],
```

---

### WR-11: one static `INTERNAL_SECRET` gates every tenant's content and every plaintext page token

**File:** `app/routers/pages.py:583-613`, `app/routers/content.py:30-37`

**Issue:** A single process-wide secret is the only control on cross-tenant reads of
all Q&A content (`_resolve_page_id`, `content.py:40-48`, is deliberately not
tenant-scoped) *and* on `GET /internal/pages/{page_fb_id}/access-token`, which returns
the **plaintext Facebook page access token** for any active page. Leaking that one
value means reading every tenant's content and taking over every connected page.
There is no per-page scoping, no rotation, no expiry, and no entropy floor —
`internal_secret: str = ""` (`app/config.py:17`) means a one-character secret is
accepted; the handlers only fail closed on empty. (The `hmac.compare_digest` usage
itself is correct.)

**Fix:** At minimum add a startup guard, and plan for per-page short-lived tokens:

```python
# app/main.py, at startup
if settings.internal_secret and len(settings.internal_secret) < 32:
    raise RuntimeError("INTERNAL_SECRET must be at least 32 characters")
```

---

### WR-18: the page-scoping guarantees the read API depends on are untested (NEW)

**File:** `tests/test_content.py` (whole module)

**Issue:** `test_content.py` covers auth (403), unknown page (404), and the disabled
flag, but nothing asserts the two isolation properties the internal API actually rests
on. I verified both hold *today* — which means they are exactly the kind of behaviour
that regresses silently:

```
GET /content/{id_on_page1}?page_id=fb-1 -> 200
GET /content/{id_on_page1}?page_id=fb-2 -> 404      # cross-page read blocked
GET /content/{id}?page_id=fb-1 after is_active=0 -> 404   # disconnected page blocked
```

Neither is asserted anywhere. Dropping `AND page_id = ?` from the query at
`content.py:113-117`, or `AND is_active = 1` from `_resolve_page_id`, would turn the
bot's shared internal key into a cross-tenant content reader with a green suite.

**Fix:** Add two tests to `tests/test_content.py`:

```python
def test_get_content_other_page_404(db_client):
    p1 = _seed_page(db_client.db_path, db_client.super_admin_id, "fb-a")
    _seed_page(db_client.db_path, db_client.super_admin_id, "fb-b")
    q = _seed_qa_item(db_client.db_path, p1, "question", "A only", "body")
    assert db_client.client.get(f"/content/{q}?page_id=fb-b", headers=INTERNAL_KEY_HEADER).status_code == 404

def test_inactive_page_content_404(db_client):
    p = _seed_page(db_client.db_path, db_client.super_admin_id, "fb-off", is_active=0)
    _seed_qa_item(db_client.db_path, p, "category", "Hidden")
    assert db_client.client.get("/content?type=category&page_id=fb-off", headers=INTERNAL_KEY_HEADER).status_code == 404
```

---

## Info

### IN-01: `type` query parameter shadows a builtin, contradicts its own description, and is unvalidated

**File:** `app/routers/content.py:54`, `app/routers/content.py:59-60`

**Issue:** Named `type` (shadows the builtin in the handler body), declared
`Query("", description="Required. ...")` — optional with an empty default, then
manually rejected at line 59 (deliberate: `tests/test_content.py:96-115` asserts 400,
not 422). The value is never checked against the known set, so
`GET /content?type=bogus&page_id=...` returns `200 {'items': []}` — a typo in the bot
looks like an empty category rather than an error. (Confirmed no injection: `type=' OR
1=1 --` returns `{'items': []}`; the value is a bound parameter.)

**Fix:** `item_type: str = Query("", alias="type", ...)` and reject anything not in
`("category", "question")` with the same 400.

### IN-02: `int()` parsing makes several distinct URLs alias the same item

**File:** `app/routers/content.py:69`, `app/routers/content.py:106-108`

**Issue:** `int()` accepts leading `+`, surrounding whitespace and Unicode digits, so
`/content/+3` and `/content/%203%20` both resolve to item 3 (verified: both 200).
Harmless today, but ids are non-canonical, which matters if anything ever caches or
logs by URL. Separately, the `raise HTTPException` at line 108 sits inside
`except ValueError` without `from None`, so every bad id logs a chained traceback.

**Fix:** `if not content_id.isdigit(): raise HTTPException(404, ...) from None` before `int()`.

### IN-03: internal-only `/content` endpoints are published in the public OpenAPI schema

**File:** `app/routers/content.py:51`, `app/routers/content.py:97`

**Issue:** Confirmed against the generated spec — `/content` and `/content/{content_id}`
appear in `app.openapi()["paths"]`, unlike their HMAC-gated siblings at `pages.py:583`
and `pages.py:616`, which set `include_in_schema=False`. Inconsistent treatment of the
same security boundary.

**Fix:** Add `include_in_schema=False` to both decorators.

### IN-04: `sys.exit(1)` inside `seed()` makes the function unusable as a library

**File:** `scripts/seed_qa.py:76`, `scripts/seed_qa.py:83`

**Issue:** `seed()` terminates the process rather than raising, which is why
`tests/test_seed_qa.py:129` and `:180` are forced into `pytest.raises(SystemExit)`.

**Fix:** Raise a domain error from `seed()` and translate it in `__main__`.

### IN-05: duplicate vault ids silently overwrite each other

**File:** `scripts/seed_qa.py:97`

**Issue:** `category_map[item["id"]] = cur.lastrowid` — two vault files declaring the
same `id` both insert rows, but only the last one scanned wins the mapping. Questions
then attach to whichever duplicate `os.scandir` happened to yield last, which is not
a guaranteed order.

**Fix:** Detect the collision and skip with a message.

### IN-06: test helpers imported across test modules instead of living in `conftest.py`

**File:** `tests/test_pages.py:12`

**Issue:** `from tests.test_auth import _auth_headers, _create_client, _login` couples
two test modules and makes collecting `test_pages.py` import `test_auth.py` as a side
effect.

**Fix:** Move the three helpers into `tests/conftest.py`.

### IN-07: `MockResponse.raise_for_status` constructs an invalid `HTTPStatusError`

**File:** `tests/test_pages.py:24-26`

**Issue:** `httpx.HTTPStatusError("error", request=None, response=self)` — `request` is
not optional in httpx and `self` is not a real `httpx.Response`. No current test drives
a status >= 400, so the branch never runs; it will fail confusingly the first time
someone writes an error-path test.

**Fix:** Pass a real `httpx.Request("GET", "https://graph.facebook.com/")`, or drop the branch.

### IN-08: duplicate `HealthResponse` model name across two routers

**File:** `app/routers/pages.py:31-33` vs `app/routers/health.py:7-8`

**Issue:** Confirmed in the generated spec — the component namespace now contains
`app__routers__health__HealthResponse` and `app__routers__pages__HealthResponse`.
Any generated client inherits those names.

**Fix:** Rename the pages model to `PageTokenHealthResponse`.

### IN-09: `yaml` is imported directly but PyYAML is not a declared dependency (NEW)

**File:** `scripts/seed_qa.py:7`

**Issue:** The script imports `yaml` (used for the `yaml.YAMLError` handler at line 32)
but `requirements.txt` lists only `python-frontmatter>=1.1.0`. It works today purely
through a transitive install; a future frontmatter release that swaps YAML backends
breaks the migration script with an `ImportError` at the worst possible moment.

**Fix:** Add `PyYAML>=6.0` to `requirements.txt`.

### IN-10: `QAItemCreateRequest` and `QAItemUpdateRequest` are byte-identical (NEW)

**File:** `app/routers/pages.py:66-79`

**Issue:** Two models with identical fields and defaults. Nothing distinguishes create
from update semantics, so the duplication is pure drift risk — a validation rule added
to one (see WR-06) will be missed on the other.

**Fix:** Define one `QAItemRequest` and use it for both handlers until they genuinely diverge.

### IN-11: `/health` no longer verifies anything (NEW)

**File:** `app/routers/health.py:11-13`

**Issue:** The endpoint previously reported `vault_loaded` / `content_count`; it now
returns a constant `{"status": "ok"}` and touches no dependency. A deployment whose
`DB_PATH` is wrong or whose database file is unreadable reports healthy to any
orchestrator or uptime monitor polling this route. Removing the vault fields was
correct for this phase; replacing them with nothing was not necessarily intended.

**Fix:** If this is meant to be a readiness probe, add a cheap
`SELECT 1` against `settings.db_path` and report `db: ok|error`. If it is only a
liveness probe, say so in a comment so nobody wires it to readiness.

---

_Reviewed: 2026-08-11T04:10:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
