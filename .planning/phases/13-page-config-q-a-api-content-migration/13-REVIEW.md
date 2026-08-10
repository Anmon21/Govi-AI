---
phase: 13-page-config-q-a-api-content-migration
reviewed: 2026-08-10T02:35:00Z
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
  critical: 2
  warning: 12
  info: 8
  total: 22
status: issues_found
---

# Phase 13: Code Review Report

**Reviewed:** 2026-08-10T02:35:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Reviewed the phase-13 content migration surface: the DB-backed `/content` read API,
the tenant-scoped page config + Q&A CRUD in `app/routers/pages.py`, the one-time
vault→DB seed script, and the four test modules. All 72 tests pass; that is not
evidence of correctness. Every finding below that is marked "proven" was reproduced
against a live `TestClient` instance, not inferred from reading.

Two ship-blocking defects: `scripts/seed_qa.py` destroys a page's entire Q&A
content when `VAULT_PATH` is unset or wrong and reports success while doing it, and
the `/content` contract change landed without its only consumer being updated, so
the production bot's Q&A flow is currently 100% broken on `main`.

The bulk of the remaining findings cluster around one architectural gap: the
`qa_items.category_id` self-referencing foreign key is global (`app/db.py:54`)
while every application-layer guard that protects it is page-scoped. That mismatch
is what produced the original CR-01/WR-01, and it is still present after the
13-05 fix.

### Verification of prior findings (13-05 fix)

Per the task brief, the previously-reported CR-01 (retype orphaning) and WR-01
(unhandled `IntegrityError` on delete) were re-tested rather than assumed.

- **CR-01 — partially fixed.** The guard at `app/routers/pages.py:516-520` correctly
  blocks the same-page case and correctly releases once the last dependent is gone.
  It does **not** block the cross-page case: a category with a dependent on another
  page still retypes to `question` with a 200, leaving a dangling reference. See WR-02.
- **WR-01 — partially fixed.** The 409 guard at `app/routers/pages.py:568-572`
  covers the same-page case, but no `sqlite3.IntegrityError` handler was ever added.
  `DELETE /pages/{id}/qa/{item_id}` still raises an unhandled `IntegrityError`
  (500 / stack trace) whenever a dependent exists outside the guard's page scope.
  See WR-01 below.
- **New defect introduced by the fix.** The 409 guard combined with the pre-existing
  permissiveness of `_validate_category_ref` makes two mutually-referencing
  categories permanently undeletable, with an error message that states a false
  reason. See WR-03.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: `seed_qa` wipes a page's entire Q&A content when the vault is missing, and reports success

**File:** `scripts/seed_qa.py:79-81`, `scripts/seed_qa.py:120-121` (with `scripts/seed_qa.py:22-24`)

**Issue:** `load_vault_items()` returns an empty list when `settings.vault_path` is
unset or points at a missing directory (`scripts/seed_qa.py:22-24`) — it only prints
a message. `seed()` does not check that result. It proceeds unconditionally to
`DELETE FROM qa_items WHERE page_id = ?`, inserts nothing, commits, and prints
`Seeded 0 categories, 0 questions for page <id>`.

Reproduced against a live DB: a page with 4 curated Q&A rows, seeded with
`vault_path="/nonexistent/path"`, ends with 0 rows and a success message.

```
page2 qa_items before seed: 4
VAULT_PATH not set or directory missing: '/nonexistent/path/does/not/exist'
Seeded 0 categories, 0 questions for page fb-p2
page2 qa_items AFTER seed with bad VAULT_PATH: 0
DATA LOSS: True
```

There is no backup, no confirmation prompt, no `--dry-run`, and no transaction the
operator can back out of — `conn.commit()` at line 120 is unconditional. A single
mistyped `VAULT_PATH` (or a `.env` loaded from the wrong working directory, which
is plausible given `settings.vault_path` defaults to `""` in `app/config.py:8`)
permanently destroys a tenant's content. `tests/test_seed_qa.py` has no coverage
for this path.

**Fix:** Fail closed before the destructive statement, and make the wipe explicit.

```python
def seed(page_fb_id: str, force: bool = False) -> None:
    ...
        items = load_vault_items()
        if not items:
            print(
                f"Refusing to seed: no valid vault items found under "
                f"{settings.vault_path!r}. Existing content for {page_fb_id!r} left intact."
            )
            sys.exit(1)

        existing = conn.execute(
            "SELECT COUNT(*) AS c FROM qa_items WHERE page_id = ?", (page_id,)
        ).fetchone()["c"]
        if existing and not force:
            print(
                f"Page {page_fb_id!r} already has {existing} Q&A rows. "
                f"Re-run with --force to wipe and reload."
            )
            sys.exit(1)

        conn.execute("DELETE FROM qa_items WHERE page_id = ?", (page_id,))
```

Add `parser.add_argument("--force", action="store_true", ...)` and pass it through.
Add regression tests for both the empty-vault and non-empty-target cases.

---

### CR-02: `/content` contract change ships without its only consumer — the bot's Q&A flow is broken on `main`

**File:** `app/routers/content.py:51-57`, `app/routers/content.py:97-102`
(consumer: `messenger-bot/src/index.ts:264`, `:292`, `:327`)

**Issue:** The rewritten `/content` endpoints now require two things that did not
exist in the previous contract:

1. `page_id: str = Query(...)` — a required query parameter (`content.py:53`, `:100`)
2. A valid `X-Internal-Key` header, enforced by `_check_internal_key` (`content.py:58`, `:103`)

The messenger bot — the sole consumer of these endpoints — sends neither:

```typescript
// messenger-bot/src/index.ts:264
const response = await axios.get(`${GOVI_AI_URL}/content?type=category`);
// messenger-bot/src/index.ts:292
const url = `${GOVI_AI_URL}/content?type=question&category=${encodeURIComponent(categoryId)}`;
// messenger-bot/src/index.ts:327
const response = await axios.get(`${GOVI_AI_URL}/content/${encodeURIComponent(questionId)}`);
```

`grep` for `X-Internal-Key`, `axios.defaults`, or any interceptor in
`messenger-bot/src/index.ts` returns nothing. Every one of these calls now fails —
422 on the missing required `page_id` (FastAPI validation runs before the handler),
or 403 once `page_id` is supplied. The bot's `catch` blocks then route users to
`sendApologyWithMenu`, so the entire Q&A browsing feature returns
"Something went wrong fetching that" for every user, on every page.

This directly falsifies Phase 13 success criterion #5: *"...and the bot continues
to respond correctly to Q&A queries using DB-backed content."* It is currently false.

I confirmed the bot-side rewrite is scoped to Phase 14 (`14-CONTEXT.md:27` D-03
specifies exactly this query-param contract). That explains the sequencing but does
not change the state of the repository: `main` currently ships a regression that
takes the primary user-facing feature offline. A breaking contract change and its
consumer update must land together, or the old contract must remain served until
the consumer catches up.

**Fix:** Either (a) pull the minimal bot-side change into this phase — thread the
page id through and attach the header:

```typescript
const INTERNAL_KEY = process.env.INTERNAL_SECRET ?? "";
const contentClient = axios.create({ headers: { "X-Internal-Key": INTERNAL_KEY } });

await contentClient.get(
  `${GOVI_AI_URL}/content?type=category&page_id=${encodeURIComponent(pageFbId)}`
);
```

or (b) keep the old unauthenticated, page-less behaviour serving a default page
until Phase 14 lands, behind an explicit deprecation flag. Do not leave `main` in
the current state.

---

## Warnings

### WR-01: `delete_qa` still has no `IntegrityError` handler — the original 500 is reachable

**File:** `app/routers/pages.py:556-580` (guard at `:568-572`, delete at `:574-576`)

**Issue:** The 13-05 fix added a pre-check but never added the safety net the original
WR-01 called for. `_has_dependent_qa_items` (`pages.py:398-404`) filters on
`page_id = ?`, while the FK it is protecting —
`category_id INTEGER REFERENCES qa_items(id)` at `app/db.py:54` — has no page scope
at all. Any dependent row outside the guard's page still trips SQLite.

Reproduced: a `qa_items` row on page 2 referencing a category on page 1 (which the
schema permits — the DB accepted the insert without complaint), then
`DELETE /pages/1/qa/{cat_id}`:

```
DELETE RAISED UNHANDLED: IntegrityError FOREIGN KEY constraint failed
```

Today the HTTP API cannot create such a row (`_validate_category_ref` is page-scoped
on both create and update), so this is latent rather than actively exploitable. But
"no code path currently produces it" is exactly the assumption that produced the
original bug, and there is no handler standing between a stray row and a 500 with a
stack trace. Note also that `delete_qa` has no `conn.rollback()` — it relies on
`close()` implicitly rolling back.

**Fix:** Keep the 409 pre-check for the good error message, and add the safety net:

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

### WR-02: retype guard is page-scoped while the FK is global — cross-page orphans still possible

**File:** `app/routers/pages.py:516-520` (guard), `app/routers/pages.py:398-404` (helper)

**Issue:** Same root cause as WR-01, different symptom. With a dependent row on a
different page, retyping a category to `question` succeeds with a 200 and leaves the
dependent pointing at a `question`-typed row — precisely the orphan state CR-01 was
raised to prevent.

Reproduced:

```
PUT retype -> 200 {'id': 1, 'type': 'question', ...}
page2 rows after retype (orphaned ref?): [(2, 'question', 1)]
parent type of page2 question: [('question',)]
```

`_validate_category_ref` would now reject that reference, so the DB holds a state
the API considers invalid — the row can never be updated again without first
clearing `category_id`.

**Fix:** Make the dependent lookup match the FK's scope. The `page_id` filter buys
nothing (an id is globally unique) and only creates blind spots:

```python
def _has_dependent_qa_items(conn, item_id: int) -> bool:
    """Report whether ANY qa_items row references item_id as its category_id."""
    row = conn.execute(
        "SELECT 1 FROM qa_items WHERE category_id = ? LIMIT 1", (item_id,)
    ).fetchone()
    return bool(row)
```

Update both call sites (`pages.py:516`, `pages.py:568`) accordingly and add
regression coverage for the cross-page case.

---

### WR-03: category→category references allow cycles that make both rows permanently undeletable, with a false error message

**File:** `app/routers/pages.py:384-395` (`_validate_category_ref`),
`app/routers/pages.py:398-404`, `app/routers/pages.py:568-572`

**Issue:** `_validate_category_ref` only checks that `category_id` points at *a
category on this page*. It never checks that the row being written is itself a
question. So a `type="category"` row can carry a `category_id` pointing at another
category. `update_qa`'s self-reference check (`pages.py:510-513`) blocks only the
direct `C → C` case; indirect cycles pass.

Reproduced — a two-node cycle, after which both rows are permanently stuck:

```
POST category with category_id -> 201 {'id': 2, 'type': 'category', 'category_id': 1}
PUT C1.category_id = C2 (creates 2-cycle) -> 200 {'id': 1, 'category_id': 2}
DELETE C1 -> 409
DELETE C2 -> 409
remaining items: [(1, 'category', 2), (2, 'category', 1)]
```

Two compounding problems:

1. The 409 message is *"Category has questions; delete or reassign them first"* —
   there are no questions. The message names the wrong entity and points the operator
   at a nonexistent fix. Escaping requires guessing that you must first PUT
   `category_id: null` on one of them.
2. Nothing in the data model wants nested categories (see WR-04), so this is
   accidental capability, not a feature.

**Fix:** Reject `category_id` on category-typed rows in both `create_qa` and
`update_qa`, and make the 409 message accurate.

```python
def _validate_category_ref(conn, page_id: int, item_type: str, category_id: Optional[int]) -> None:
    if category_id is None:
        return
    if item_type == "category":
        raise HTTPException(
            status_code=400, detail="category_id is only valid on items of type 'question'"
        )
    ...

# and at pages.py:568-572
raise HTTPException(
    status_code=409,
    detail="This category is still referenced by other Q&A items; reassign or delete them first",
)
```

---

### WR-04: nested categories are served to the bot as top-level menu entries

**File:** `app/routers/content.py:73-86`

**Issue:** `list_content` applies the `category_id` filter only when the caller
passes `category` — for `type=category` it never filters on `category_id` at all.
Any child category created per WR-03 is therefore returned in the top-level category
list alongside its own parent.

Reproduced (C2 is a child of C1):

```
/content?type=category -> 200 {'items': [{'id': '1', 'title': 'C1'}, {'id': '2', 'title': 'C2'}]}
```

The bot maps these straight into quick replies (`messenger-bot/src/index.ts:274-278`),
so a sub-topic surfaces as a peer of its parent in the user-facing menu.

**Fix:** Once WR-03 is fixed, categories can never have a parent and this resolves
itself. Belt-and-braces, make the intent explicit in the query:

```python
rows = conn.execute(
    "SELECT id, type, title FROM qa_items "
    "WHERE page_id = ? AND type = ? AND enabled = 1 AND category_id IS NULL "
    "ORDER BY id ASC",
    (internal_page_id, type),
).fetchall()
```

(applied only to the `type='category'` branch).

---

### WR-05: disabling a category does not hide its questions

**File:** `app/routers/content.py:73-94`, `app/routers/content.py:113-117`

**Issue:** The `enabled = 1` filter is applied per-row with no regard for the
parent category's state. Setting `enabled: false` on a category removes it from the
menu but leaves every question underneath it fully readable.

Reproduced:

```
categories visible: {'items': []}
questions under disabled cat: {'items': [{'id': '5', 'type': 'question', 'title': 'Q'}]}
```

Because the bot embeds content ids directly in quick-reply payloads
(`CATEGORY:<id>` / `QUESTION:<id>`, `messenger-bot/src/index.ts:277`, `:307`), a
user with an older message in their thread can still tap through to content the
admin believes they have taken down. An admin who disables a category to pull
incorrect or outdated information has not actually pulled it.

**Fix:** Filter on the parent's `enabled` state as well.

```python
rows = conn.execute(
    "SELECT q.id, q.type, q.title FROM qa_items q "
    "LEFT JOIN qa_items c ON q.category_id = c.id "
    "WHERE q.page_id = ? AND q.type = ? AND q.enabled = 1 "
    "  AND (q.category_id IS NULL OR c.enabled = 1) "
    "ORDER BY q.id ASC",
    (internal_page_id, type),
).fetchall()
```

Apply the same join to `get_content` (`content.py:113-117`).

---

### WR-06: no size or count validation on any admin-supplied content field

**File:** `app/routers/pages.py:36-48` (`MenuItem`, `PageConfigRequest`),
`app/routers/pages.py:66-80` (`QAItemCreateRequest`, `QAItemUpdateRequest`)

**Issue:** Every string field is a bare `str` and `menu_json` is an unbounded
`list[MenuItem]`. The API accepts values that Facebook will reject at send time.

Reproduced:

```
POST title='' -> 201 {'id': 6, 'title': '', ...}
PUT config welcome_text 100k chars -> 200
PUT config 50 menu items (FB max 3) -> 200
```

Relevant Messenger limits: message text 2000 chars, quick-reply title 20 chars,
postback payload 1000 chars (the bot's own type declares `payload: string; // ≤1000 chars`
at `messenger-bot/src/index.ts:24`), persistent menu 3 top-level items. An empty
`title` produces a quick reply Facebook refuses outright. The admin API is the only
validation boundary before this data reaches Facebook; failures currently surface as
opaque Graph API errors in bot logs, far from the user who caused them.

**Fix:** Constrain the models.

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

### WR-07: re-seeding reassigns every content id, silently breaking authored menu payloads

**File:** `scripts/seed_qa.py:81-111`; weak test at `tests/test_seed_qa.py:89-108`

**Issue:** `seed()` deletes and re-inserts, and `qa_items.id` is
`INTEGER PRIMARY KEY AUTOINCREMENT` (`app/db.py:48`), so ids never repeat — every
item gets a brand-new id on each run.

Reproduced:

```
ids after 1st seed: [6, 7, 8, 9, 10]
ids after 2nd seed: [11, 12, 13, 14, 15]
ids stable across re-seed: False
```

Those ids are the bot's routing keys: `CATEGORY:<id>` and `QUESTION:<id>` payloads
(`messenger-bot/src/index.ts:277`, `:307`) and anything an admin has hand-authored
into `page_configs.menu_json`. After a re-seed, every previously-issued quick reply
404s and any menu entry referencing a content id is dead — with no error at seed
time to indicate it.

Compounding this: `test_seed_is_idempotent` (`tests/test_seed_qa.py:89-108`) asserts
only `first_count == second_count == 5`. It certifies "idempotent" while the ids
underneath churn completely. A test that passes for the wrong reason is worse than
no test — it is why this shipped.

**Fix:** Preserve identity across runs by keying on the vault's stable `id`. Either
add a `vault_id TEXT` column with a `UNIQUE(page_id, vault_id)` constraint and
`INSERT ... ON CONFLICT DO UPDATE`, or at minimum strengthen the test so the current
behaviour cannot be mistaken for idempotence:

```python
def test_seed_is_idempotent(seed_db):
    seed(seed_db.page_fb_id)
    first = _snapshot(seed_db.db_path, seed_db.page_id)   # [(id, type, title, category_id)]
    seed(seed_db.page_fb_id)
    second = _snapshot(seed_db.db_path, seed_db.page_id)
    assert first == second, "re-seeding must preserve item ids — bot payloads depend on them"
```

---

### WR-08: the internal-key check is implemented three separate times

**File:** `app/routers/content.py:30-37`, `app/routers/pages.py:588-594`,
`app/routers/pages.py:627-633`

**Issue:** Three byte-identical copies of the same security-critical logic
(empty-secret 500, `hmac.compare_digest`, 403). Only one is a named, reusable
function; the other two are inlined in handler bodies. Any future change — rotation
support, a minimum-length guard, audit logging, a constant-time fix — will be applied
to one or two of the three. This is the classic shape of a security regression.

**Fix:** Promote to a shared FastAPI dependency and delete the copies.

```python
# app/internal_auth.py
def require_internal_key(
    x_internal_key: Annotated[Optional[str], Header()] = None,
) -> None:
    if not settings.internal_secret:
        raise HTTPException(status_code=500, detail="INTERNAL_SECRET not configured")
    if not hmac.compare_digest((x_internal_key or "").encode(), settings.internal_secret.encode()):
        raise HTTPException(status_code=403, detail="Forbidden")

# usage
@router.get("", response_model=ContentListResponse, dependencies=[Depends(require_internal_key)])
```

---

### WR-09: `page_health` reaches into `fb_client.httpx` and conflates network failure with token revocation

**File:** `app/routers/pages.py:283-292`; related `app/routers/pages.py:209`

**Issue:** Two problems in one block.

1. `fb_client.httpx.get(fb_client.GRAPH_BASE + "/debug_token", ...)` reaches through
   `fb_client` into its imported `httpx` module rather than calling a function on it.
   `fb_client.check_token_health` already performs this exact `debug_token` call
   (`app/fb_client.py:92-105`); this is a duplicate implementation whose only reason
   to exist is that it also needs `expires_at`. Production code now depends on a
   module-attribute path that exists for test monkeypatching.
2. `except Exception: return HealthResponse(is_valid=False, ...)` (`pages.py:291-292`)
   makes a DNS failure, a timeout, or a Facebook 500 indistinguishable from an
   actually-revoked token. `check_token_health` has the same swallow
   (`app/fb_client.py:104-105`), so `GET /pages` marks *every* page `"revoked"`
   during any transient Facebook outage. Per Phase 15 success criterion #4 that will
   render a "Reconnect" warning badge on every healthy page.

**Fix:** Move the call into `fb_client` and distinguish the two failure modes.

```python
# app/fb_client.py
def debug_token(page_access_token: str) -> dict | None:
    """Return the debug_token data dict, or None if Facebook was unreachable."""
    try:
        resp = httpx.get(
            f"{GRAPH_BASE}/debug_token",
            params={
                "input_token": page_access_token,
                "access_token": f"{settings.fb_app_id}|{settings.fb_app_secret}",
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json().get("data", {})
    except httpx.HTTPError:
        return None
```

Then surface `None` as a distinct `"unknown"` status rather than `"revoked"`.

---

### WR-10: wildcard CORS on a now-authenticated multi-tenant admin API

**File:** `app/main.py:15-20`

**Issue:** `allow_origins=["*"]` with `allow_methods=["*"]` and `allow_headers=["*"]`
was defensible when this app exposed only `/health` and a stateless `/ai/chat`. As of
this phase the same origin policy covers `/auth/login`, `/tenants`, `/pages`,
`/pages/{id}/config`, and the full Q&A CRUD. `allow_credentials` is unset (defaults
`False`), so cookies are not in play and this is not directly exploitable — but it
means any origin on the internet can invoke every admin mutation and read the full
response body the moment it obtains a bearer token, converting any token leak into
immediate cross-origin account takeover. It also leaves no allowlist in place for
the Phase 15 admin SPA.

**Fix:** Move the origin list into config and stop using a wildcard.

```python
# app/config.py
allowed_origins: str = "http://localhost:5173"

# app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allowed_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

---

### WR-11: one static shared `INTERNAL_SECRET` gates every tenant's content and every plaintext page token

**File:** `app/routers/pages.py:583-613`, `app/routers/content.py:30-37`

**Issue:** A single process-wide secret is the only control on:

- `GET /content` and `GET /content/{id}` for *any* `page_fb_id` — cross-tenant read
  of all Q&A content (`content.py:40-48` resolves the page with no tenant scoping,
  by design)
- `GET /internal/pages/{page_fb_id}/access-token`, which returns the **plaintext
  Facebook page access token** for any active page (`pages.py:609-613`)

The blast radius of leaking that one value is total: read every tenant's content, and
take over every connected Facebook page. There is no per-page scoping, no rotation
mechanism, no expiry, and no minimum-length or entropy guard —
`internal_secret: str = ""` in `app/config.py:17` means a one-character secret is
accepted (the handlers fail closed only on empty).

The `hmac.compare_digest` usage itself is correct.

**Fix:** Out of scope for a one-line change, but at minimum add a startup guard, and
plan for per-page scoping:

```python
# app/main.py, at startup
if settings.internal_secret and len(settings.internal_secret) < 32:
    raise RuntimeError("INTERNAL_SECRET must be at least 32 characters")
```

Longer term, replace the shared static secret with short-lived per-page tokens
issued to the bot, so that a leak is bounded in both scope and time.

---

### WR-12: the seed script's destructive wipe has no confirmation, `--dry-run`, or repeat-run guard

**File:** `scripts/seed_qa.py:65-81`, `scripts/seed_qa.py:126-132`

**Issue:** Separate from CR-01 (which is about the empty-vault case), the wipe itself
is unguarded even when the vault is valid. The docstring says "one-time migration"
(`seed_qa.py:128`) but nothing enforces once-only execution, and the argparse
interface exposes no `--dry-run` or `--force`. Running it against a page whose
content has since been curated through the Phase 13 admin API silently discards all
of that work and replaces it with the vault snapshot. The `print` at line 121 reports
what was inserted but never what was destroyed.

**Fix:** Covered by the CR-01 patch (`--force` plus an existing-row check). Also
report the destructive half:

```python
existing = conn.execute(
    "SELECT COUNT(*) AS c FROM qa_items WHERE page_id = ?", (page_id,)
).fetchone()["c"]
...
print(f"Removed {existing} existing rows; seeded {category_count} categories, "
      f"{question_count} questions for page {page_fb_id}")
```

---

## Info

### IN-01: `type` query parameter shadows a builtin and its declaration contradicts its docstring

**File:** `app/routers/content.py:54`, `app/routers/content.py:59-60`

**Issue:** The parameter is named `type`, shadowing the builtin inside the handler
body. It is declared `Query("", description="Required. ...")` — optional with an
empty default — then manually rejected at line 59. The manual 400 is deliberate
(`tests/test_content.py:96-115` asserts 400 rather than 422), but the mismatch
between "Required." in the OpenAPI description and a `""` default is confusing.
The value is also never validated against the known set.

**Fix:** Rename to `item_type` with `alias="type"`, and constrain it:

```python
item_type: str = Query("", alias="type", description="Required. 'category' or 'question'.")
...
if item_type not in ("category", "question"):
    raise HTTPException(status_code=400, detail="type query parameter is required")
```

### IN-02: `int()` parsing makes several distinct URLs alias the same item

**File:** `app/routers/content.py:69`, `app/routers/content.py:106`

**Issue:** Python's `int()` accepts underscore separators and surrounding
whitespace/signs, so `/content/+5`, `/content/ 5 `, and `/content/5` all resolve to
item 5, and `?category=1_0` resolves to category 10. Harmless today (the value is a
bound parameter, so no injection — confirmed by probing `type=' OR 1=1 --`, which
returned `{'items': []}`), but it makes ids non-canonical.

**Fix:** `if not content_id.isdigit(): raise HTTPException(404, ...)` before `int()`.

### IN-03: internal-only `/content` endpoints are published in the public OpenAPI schema

**File:** `app/routers/content.py:51`, `app/routers/content.py:97`

**Issue:** Both endpoints are bot-only and HMAC-gated, yet neither sets
`include_in_schema=False` — unlike their siblings in `pages.py:583` and `pages.py:616`,
which do. They appear in public `/docs` and `/openapi.json`. Inconsistent treatment
of the same security boundary.

**Fix:** Add `include_in_schema=False` to both decorators.

### IN-04: `sys.exit(1)` inside `seed()` makes the function unusable as a library

**File:** `scripts/seed_qa.py:76`

**Issue:** `seed()` terminates the process on a missing page rather than raising.
`tests/test_seed_qa.py:126-128` is forced into `pytest.raises(SystemExit)` as a result.

**Fix:** Raise a domain error from `seed()` and translate it in `__main__`:

```python
raise ValueError(f"No page found with page_fb_id={page_fb_id!r}")
...
if __name__ == "__main__":
    try:
        seed(args.page_fb_id)
    except ValueError as e:
        print(e); sys.exit(1)
```

### IN-05: duplicate vault ids silently overwrite each other

**File:** `scripts/seed_qa.py:93`

**Issue:** `category_map[item["id"]] = cur.lastrowid` — two vault files declaring the
same `id` both insert rows, but only the second wins the mapping. Questions then
attach to whichever category happened to be scanned last (`os.scandir` order is not
guaranteed), non-deterministically.

**Fix:** Detect and report the collision:

```python
if item["id"] in category_map:
    print(f"Skipping duplicate category id {item['id']!r}")
    continue
```

### IN-06: test helpers imported across test modules instead of living in `conftest.py`

**File:** `tests/test_pages.py:12`

**Issue:** `from tests.test_auth import _auth_headers, _create_client, _login` imports
three underscore-prefixed private helpers from a sibling test module, coupling the two
files and causing `test_auth.py` to be imported (and its module-level code executed)
as a side effect of collecting `test_pages.py`.

**Fix:** Move the three helpers into `tests/conftest.py` as fixtures or public helpers.

### IN-07: `MockResponse.raise_for_status` constructs an invalid `HTTPStatusError`

**File:** `tests/test_pages.py:24-26`

**Issue:** `httpx.HTTPStatusError("error", request=None, response=self)` — `request`
is not optional in httpx, and `self` is not a real `httpx.Response`. No current test
drives a status >= 400, so the branch never executes; it will fail confusingly the
first time someone writes an error-path test.

**Fix:** Either drop the branch or build a real `httpx.Request`:

```python
raise httpx.HTTPStatusError(
    "error", request=httpx.Request("GET", "https://graph.facebook.com/"), response=self
)
```

### IN-08: duplicate `HealthResponse` model name across two routers

**File:** `app/routers/pages.py:31-33` vs `app/routers/health.py:7-8`

**Issue:** Two unrelated Pydantic models share the name `HealthResponse`. FastAPI
disambiguates them in the OpenAPI component namespace by appending a module path,
producing awkward generated schema names and confusing any generated client.

**Fix:** Rename the pages one to `PageTokenHealthResponse`.

---

_Reviewed: 2026-08-10T02:35:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
