---
phase: 03-product-q-a-flow
plan: 01
subsystem: content-api
tags:
  - python
  - fastapi
  - vault
  - content-api
dependency_graph:
  requires:
    - 02-02 (vault service with load_vault, _vault, GET /content/{id}, POST /content/reload)
  provides:
    - GET /content?type=&category= listing endpoint
    - ContentListItem, ContentListResponse Pydantic models
    - Optional category field in vault loader
    - vault-sample/ seed directory (5 files)
  affects:
    - 03-02 (bot plan will consume GET /content?type=category and GET /content?type=question&category=X)
tech_stack:
  added: []
  patterns:
    - FastAPI Query parameter with empty-string default for optional-but-required param
    - In-memory dict scan for listing (O(n), acceptable for small vaults)
    - Route ordering: @router.get("") declared before @router.get("/{id}") to prevent misrouting
key_files:
  created:
    - vault-sample/cat-shipping.md
    - vault-sample/cat-products.md
    - vault-sample/q-shipping-01.md
    - vault-sample/q-shipping-02.md
    - vault-sample/q-products-01.md
    - .planning/phases/03-product-q-a-flow/03-01-SUMMARY.md
  modified:
    - app/routers/content.py
    - tests/test_content.py
decisions:
  - "Route GET /content declared before GET /{content_id} to prevent FastAPI path-parameter misrouting — verified by line number comparison (85 vs 102)"
  - "type query uses Query('') default (not Ellipsis) so both empty-string and missing params produce our specific 400 detail rather than FastAPI's 422"
  - "category field stored as None on category-type files (no parent category); equality check item.get('category') == category handles this cleanly"
  - "Titles in vault-sample kept to <=20 chars for Messenger quick reply compatibility: 'Shipping time?' (14), 'Ship abroad?' (12), 'Products certified?' (19)"
metrics:
  duration: ~15 minutes
  completed: 2026-05-15
  tasks_completed: 3
  tasks_total: 3
  files_modified: 2
  files_created: 6
---

# Phase 03 Plan 01: Content Listing API + Vault Sample Summary

**One-liner:** GET /content listing endpoint with type/category filters backed by 5-file vault-sample seed demonstrating the category/question schema.

## What Was Built

Plan 01 of Phase 3 adds the API half of the product Q&A vertical slice. The bot (Plan 02) now has a way to dynamically discover categories and questions without hard-coded IDs.

Three changes were made:

1. `app/routers/content.py` — extended with two new Pydantic models (`ContentListItem`, `ContentListResponse`) and a new `GET /content` endpoint with `?type=` and `?category=` query filters. The vault loader now threads an optional `category` field through each stored item.

2. `tests/test_content.py` — four new test functions appended (no existing tests modified). All 12 content tests plus 2 health tests pass (14 total).

3. `vault-sample/` — new directory at repo root with 5 markdown files: 2 category files, 3 question files across 2 categories.

## Pytest Results (14/14 GREEN)

```
============================= test session starts ==============================
platform darwin -- Python 3.9.6, pytest-8.4.2, pluggy-1.6.0
collected 14 items

tests/test_content.py::test_vault_loads_at_startup PASSED
tests/test_content.py::test_get_content_by_id PASSED
tests/test_content.py::test_get_content_missing_returns_404 PASSED
tests/test_content.py::test_missing_vault_soft_fails PASSED
tests/test_content.py::test_disabled_files_excluded PASSED
tests/test_content.py::test_malformed_frontmatter_skipped PASSED
tests/test_content.py::test_enabled_string_true_rejected PASSED
tests/test_content.py::test_reload_endpoint PASSED
tests/test_content.py::test_list_categories_only PASSED
tests/test_content.py::test_list_questions_filtered_by_category PASSED
tests/test_content.py::test_list_unknown_category_returns_empty PASSED
tests/test_content.py::test_list_missing_type_returns_400 PASSED
tests/test_health.py::test_health_includes_vault_stats PASSED
tests/test_health.py::test_health_vault_loaded_true_when_vault_reachable PASSED

============================== 14 passed in 0.04s
```

## Smoke Test Transcripts (vault-sample/)

All run via FastAPI TestClient with `_vault` loaded from `vault-sample/`:

```
GET /content?type=category
200 {"items": [{"id": "cat-products", "type": "category", "title": "Products"},
               {"id": "cat-shipping", "type": "category", "title": "Shipping"}]}

GET /content?type=question&category=cat-shipping
200 {"items": [{"id": "q-shipping-01", "type": "question", "title": "Shipping time?"},
               {"id": "q-shipping-02", "type": "question", "title": "Ship abroad?"}]}

GET /content?type=question&category=does-not-exist
200 {"items": []}

GET /content?type=
400 {"detail": "type query parameter is required"}

GET /content/q-shipping-01
200 {"id": "q-shipping-01", "type": "question", "title": "Shipping time?",
     "body": "Standard orders ship within 1-2 business days..."}
```

## Route Ordering

Confirmed correct: `@router.get("")` on line 85, `@router.get("/{content_id}")` on line 102. The listing handler is declared first, preventing FastAPI from misrouting `/content?type=category` to the path-parameter handler.

## Title Lengths in vault-sample/

All question titles are within the 20-char Messenger quick reply limit:

| File | Title | Length |
|------|-------|--------|
| q-shipping-01.md | Shipping time? | 14 |
| q-shipping-02.md | Ship abroad? | 12 |
| q-products-01.md | Products certified? | 19 |

Category titles: "Shipping" (8), "Products" (8).

## Commits

| Task | Type | Hash | Description |
|------|------|------|-------------|
| 1 | feat | 2c57cec | Add GET /content listing endpoint with type/category filters |
| 2 | test | 4f3f205 | Add 4 pytest cases for listing endpoint |
| 3 | chore | 5f5bb28 | Add vault-sample/ seed with 2 categories and 3 questions |

## Deviations from Plan

None — plan executed exactly as written. All acceptance criteria met on first attempt.

## Open Follow-ups for Plan 02

- Bot quick reply payloads must map category IDs returned by `GET /content?type=category` to `CATEGORY:{id}` payload strings so the next handler can call `GET /content?type=question&category={id}`.
- Bot must handle `{"items": []}` from an unknown/empty category gracefully (e.g., "No questions found under this category yet.").
- The `content_count` from `GET /health` will report 5 when `VAULT_PATH=./vault-sample` — operators can use this to confirm the vault is wired correctly before adding their own content.

## Self-Check: PASSED

- app/routers/content.py: FOUND
- tests/test_content.py: FOUND
- vault-sample/cat-shipping.md: FOUND
- vault-sample/cat-products.md: FOUND
- vault-sample/q-shipping-01.md: FOUND
- vault-sample/q-shipping-02.md: FOUND
- vault-sample/q-products-01.md: FOUND
- Commit 2c57cec: FOUND
- Commit 4f3f205: FOUND
- Commit 5f5bb28: FOUND
- pytest 14/14: PASSED
