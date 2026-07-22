---
phase: 13-page-config-q-a-api-content-migration
reviewed: 2026-07-22T00:00:00Z
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
  warning: 2
  info: 3
  total: 6
status: issues_found
---

# Phase 13: Code Review Report

**Reviewed:** 2026-07-22T00:00:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Reviewed the Phase 13 vault→DB content migration: HMAC-guarded content read
endpoints (`app/routers/content.py`), the tenant-scoped page-config write +
internal HMAC read and Q&A CRUD (`app/routers/pages.py`), the one-time seed
script (`scripts/seed_qa.py`), and the accompanying tests.

The security fundamentals are solid: every SQL statement uses `?` placeholders
(no f-string SQL), `hmac.compare_digest` provides constant-time internal-key
comparison, and JWT tenant scoping is consistently enforced on the write paths
via `_require_owned_page`. Cross-tenant isolation is well covered by tests.

The defects are concentrated in **referential integrity within the Q&A CRUD
path** — precisely the area flagged for scrutiny. The whole-row `update_qa`
endpoint can silently corrupt the category→question relationship, and
`delete_qa` will crash with an unhandled 500 when a category still has dependent
questions because of the `qa_items.category_id → qa_items.id` foreign key.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: `update_qa` can silently break category→question referential integrity

**File:** `app/routers/pages.py:486-538`
**Issue:** `update_qa` is a whole-row replace that accepts an arbitrary `type`
(`"category"` or `"question"`) with no guard against changing the `type` of an
item that other questions already reference as their `category_id`.

Scenario:
1. Category C (id=5) exists; questions Q1, Q2 have `category_id = 5`.
2. Admin PUTs `{"type": "question", "title": "...", ...}` to
   `/pages/{page_id}/qa/5`.
3. The update succeeds. Row 5 is now a `question`, but Q1/Q2 still point at it
   via `category_id = 5`.

`_validate_category_ref` (pages.py:384-395) only validates the *edited row's own*
`category_id`; it never checks whether the row being edited is itself referenced
as a category by other rows. The FK (`category_id REFERENCES qa_items(id)`) is
satisfied because row 5 still exists — the FK does not encode the
`type='category'` requirement (that is "enforced at application layer" per the
schema comment at db.py:53, but this endpoint does not enforce it here).

Downstream impact: the content read API filters categories with
`type = 'category'` (content.py:74-86), so those questions become permanently
unreachable through the menu — silent data corruption that surfaces only as
"missing" content for end users. This is directly in the referential-integrity
scope called out for this phase.

**Fix:** Before applying a `type` change away from `category`, reject the update
if the item is still referenced. For example, add to `update_qa` before the
`UPDATE`:
```python
if request.type != "category":
    referencing = conn.execute(
        "SELECT 1 FROM qa_items WHERE category_id = ? AND page_id = ? LIMIT 1",
        (item_id, page_id),
    ).fetchone()
    if referencing:
        raise HTTPException(
            status_code=400,
            detail="Cannot change type: this category is referenced by questions",
        )
```

## Warnings

### WR-01: `delete_qa` on a referenced category raises an unhandled 500

**File:** `app/routers/pages.py:541-559`
**Issue:** `delete_qa` deletes a single `qa_items` row without checking for
dependent rows. Because `PRAGMA foreign_keys=ON` (db.py:9) and
`qa_items.category_id REFERENCES qa_items(id)` with the default `NO ACTION`
(RESTRICT) behaviour, deleting a category that still has questions pointing at it
raises `sqlite3.IntegrityError` ("FOREIGN KEY constraint failed") at statement
conclusion. That exception is unhandled, so FastAPI returns a generic 500 rather
than a clean 400/409, and the admin gets no actionable error.

(No data loss occurs — `conn.commit()` is never reached — but the crash is a poor
and confusing failure mode for a normal admin action.)

**Fix:** Detect the dependency and return a clean error, or explicitly delete/
detach children first per the intended product behaviour:
```python
dependents = conn.execute(
    "SELECT 1 FROM qa_items WHERE category_id = ? AND page_id = ? LIMIT 1",
    (item_id, page_id),
).fetchone()
if dependents:
    raise HTTPException(
        status_code=409,
        detail="Category has questions; delete or reassign them first",
    )
```

### WR-02: Webhook subscriptions are not compensated when a later page fails

**File:** `app/routers/pages.py:116-154`
**Issue:** `_store_pages_and_subscribe` calls `fb_client.subscribe_page_webhook`
inside the loop (line 145) for each page before `conn.commit()`. If page N's
subscribe raises, the `except` block rolls back all DB writes — but pages 1..N-1
remain subscribed at Facebook with no corresponding DB row. Those pages are then
live at Facebook yet invisible to Govi (bot can't serve them, admin can't
disconnect them because there is no row). The external side effect is not
rolled back with the transaction.

**Fix:** Persist and commit all page rows first, then perform webhook
subscriptions (ideally best-effort with per-page status), so a subscribe failure
cannot leave FB-side state that has no DB record. At minimum, track which pages
were subscribed and unsubscribe them on rollback.

## Info

### IN-01: Internal-key HMAC check is duplicated three times

**File:** `app/routers/content.py:30-37`, `app/routers/pages.py:567-573`,
`app/routers/pages.py:606-612`
**Issue:** The identical `INTERNAL_SECRET not configured` / `compare_digest` /
`403 Forbidden` block is copy-pasted in `content._check_internal_key` and twice
inline in `pages.py`. Divergence risk if the guard ever changes (e.g., adding
logging or a header-name change).
**Fix:** Extract a single shared dependency (e.g., a FastAPI
`Depends(require_internal_key)` in a shared `app/auth.py` or `app/internal.py`)
and reuse it across all three call sites.

### IN-02: Category nesting permits multi-node cycles

**File:** `app/routers/pages.py:501-505`
**Issue:** `update_qa` blocks only the direct self-reference
(`category_id == item_id`). Because `_validate_category_ref` permits a category
to reference another category, an admin can construct a cycle A→B→A across two
updates. No current read path recurses categories, so this is latent rather than
an active bug, but any future tree/menu traversal could loop.
**Fix:** If category nesting is not a product requirement, reject `category_id`
on `type='category'` items entirely. If it is, add cycle detection.

### IN-03: `type` query/param name shadows the builtin

**File:** `app/routers/content.py:54`, `app/routers/pages.py:67,75`
**Issue:** Using `type` as a field/parameter name shadows the `type` builtin.
Harmless in these scopes but mildly error-prone; project naming conventions favor
descriptive names.
**Fix:** Consider `item_type` for readability. Low priority — leave if it
conflicts with an external API contract.

---

_Reviewed: 2026-07-22T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
