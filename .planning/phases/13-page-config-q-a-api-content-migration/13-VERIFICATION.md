---
phase: 13-page-config-q-a-api-content-migration
verified: 2026-07-22T06:10:33Z
status: gaps_found
score: 22/24 must-haves verified
overrides_applied: 0
gaps:
  - truth: "A client can edit a Q&A item via PUT /pages/{page_id}/qa/{item_id}"
    status: failed
    reason: "update_qa performs a whole-row replace with no check for whether item_id is referenced as category_id by other qa_items rows on the page. A category that has questions pointing at it can be silently retyped to 'question' (or any other field changed) via a 200 OK response — the referencing questions keep their old category_id but that row is no longer type='category', so the content read API (which filters categories by type='category') can never surface it again and the dependent questions become unreachable. Confirmed reproducible against the live endpoint: POST category -> POST question(category_id=category) -> PUT category {type:'question'} returns 200, silently orphaning the question. Matches 13-REVIEW.md CR-01 (Critical), which remains unresolved in the shipped code."
    artifacts:
      - path: "app/routers/pages.py"
        issue: "update_qa (~lines 486-538) has no guard against changing type away from 'category' when other qa_items rows reference the item as category_id"
    missing:
      - "A check in update_qa (before the UPDATE) that rejects (400) a type change away from 'category' if `SELECT 1 FROM qa_items WHERE category_id = ? AND page_id = ?` finds a dependent row, per the fix already specified in 13-REVIEW.md CR-01"
  - truth: "A client can delete a Q&A item via DELETE /pages/{page_id}/qa/{item_id}"
    status: failed
    reason: "delete_qa executes DELETE with no check for dependent rows first. Because qa_items.category_id REFERENCES qa_items(id) and PRAGMA foreign_keys=ON (app/db.py:9), deleting a category that still has one or more questions pointing at it raises an unhandled sqlite3.IntegrityError ('FOREIGN KEY constraint failed'), which FastAPI surfaces as an unhandled 500 rather than a clean 4xx. Confirmed reproducible: creating a category, creating a question with that category_id, then DELETE-ing the category raises IntegrityError inside the request. This is not an edge case — any category that has ever been assigned to a question cannot be deleted through this endpoint without crashing. Matches 13-REVIEW.md WR-01 (Warning), which remains unresolved in the shipped code."
    artifacts:
      - path: "app/routers/pages.py"
        issue: "delete_qa (~lines 541-559) does not check for dependent qa_items rows before executing DELETE FROM qa_items"
    missing:
      - "A dependent-rows check in delete_qa (before the DELETE) that returns a clean error (e.g. 409) when `SELECT 1 FROM qa_items WHERE category_id = ? AND page_id = ?` finds a dependent row, per the fix already specified in 13-REVIEW.md WR-01"
deferred:
  - truth: "A client can update the welcome/greeting text for their Page via the API and the bot immediately serves the new text to users on Get Started (Roadmap SC1, bot-serving half)"
    addressed_in: "Phase 14"
    evidence: "Phase 14 goal: 'The bot handles webhook events from multiple Facebook Pages by fetching the correct token and content config per Page ID from FastAPI.' 13-CONTEXT.md explicitly states 'Out of scope: Bot-side consumption of these endpoints (Phase 14 — BOT-01/02/03)'."
  - truth: "A client can update the persistent menu labels and structure for their Page via the API; the change is visible in Messenger after the API call (Roadmap SC2, bot/Messenger-visible half)"
    addressed_in: "Phase 14"
    evidence: "13-CONTEXT.md <deferred>: 'FastAPI-side persistent-menu installation to the Graph API on OAuth completion — already captured in Phase 14 CONTEXT <deferred>. Phase 13 only stores/serves menu_json; it does not install the menu to Messenger.'"
  - truth: "The bot serves the updated Q&A tree without a restart (Roadmap SC3, bot-serving half)"
    addressed_in: "Phase 14"
    evidence: "Phase 14 SC1: 'An inbound webhook event carrying Page ID A is processed using Page A's token and content...' messenger-bot/src/index.ts currently calls GET /content without the now-required page_id / X-Internal-Key — bot rewiring onto this phase's API is Phase 14's explicit deliverable (BOT-01/02/03)."
  - truth: "Running the seed script migrates vault Q&A into the database, and the bot continues to respond correctly to Q&A queries using DB-backed content (Roadmap SC5, bot-response half)"
    addressed_in: "Phase 14"
    evidence: "Same as above — the bot has not yet been rewired to pass page_id/X-Internal-Key to /content*; that rewiring is Phase 14's BOT-01/02/03 scope per 13-CONTEXT.md."
---

# Phase 13: Page Config, Q&A API + Content Migration Verification Report

**Phase Goal:** All bot content (welcome text, menu, Q&A, escalation settings) is served from the database per Page ID; the existing /content HTTP contract is preserved; the Obsidian vault is retired.
**Verified:** 2026-07-22T06:10:33Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | GET /content?type=category&page_id=<fb_id> + valid X-Internal-Key returns that page's categories | ✓ VERIFIED | `app/routers/content.py:51-94` (`list_content`); `tests/test_content.py::test_list_categories_only` passes |
| 2 | GET /content?type=question&category=<id>&page_id=<fb_id> returns filtered questions | ✓ VERIFIED | `content.py:73-79`; `test_content.py::test_list_questions_filtered_by_category` passes |
| 3 | GET /content/{id}?page_id=<fb_id> returns the question body | ✓ VERIFIED | `content.py:97-123`; `test_content.py::test_get_content_returns_body` passes |
| 4 | Missing/wrong X-Internal-Key returns 403 (D-01) | ✓ VERIFIED | `content.py:30-37 _check_internal_key`; `test_content_list_forbidden_without_key`, `test_content_get_forbidden_without_key` pass |
| 5 | `{items:[{id,type,title}]}` / `{id,type,title,body}` shapes unchanged | ✓ VERIFIED | `content.py:13-27` models byte-identical field names/nesting to pre-migration contract |
| 6 | Vault fully retired (`_vault`, `load_vault`, `/content/reload` gone) | ✓ VERIFIED | `grep -rnE "_vault|load_vault|/content/reload|vault_loaded|content_count" app/` returns nothing |
| 7 | GET /health returns 200 `{status:'ok'}`, no vault fields | ✓ VERIFIED | `app/routers/health.py:1-13`; `pytest tests/test_health.py` passes |
| 8 | Client can replace welcome_text/menu_json/escalation_psid/escalation_message in one PUT | ✓ VERIFIED | `pages.py:303-371 put_page_config`; `test_put_config_creates_then_updates` passes |
| 9 | PUT creates page_configs row if absent, overwrites if present | ✓ VERIFIED | `pages.py:325-353` insert-or-update on `page_configs.page_id` (UNIQUE) |
| 10 | menu_json accepts flat `[{title,payload}]`, rejects nested/malformed (D-04) | ✓ VERIFIED | `MenuItem(extra="forbid")` `pages.py:36-40`; `test_put_config_rejects_nested_menu` passes |
| 11 | Tenant cannot write to a page it does not own (404, no leak) (D-02) | ✓ VERIFIED | `pages.py:316-321` ownership check before any write; `test_put_config_cross_tenant_404` passes |
| 12 | GET /internal/pages/{page_fb_id}/config returns config behind HMAC | ✓ VERIFIED | `pages.py:595-644`; `test_internal_config_returns_config` passes |
| 13 | Internal config read 403 without valid key, 404 unknown page_fb_id | ✓ VERIFIED | `pages.py:606-621`; `test_internal_config_forbidden_without_key`, `test_internal_config_unknown_page_404` pass |
| 14 | Client can list page's Q&A items via GET /pages/{page_id}/qa | ✓ VERIFIED | `pages.py:398-428 list_qa`; `test_qa_full_crud_cycle` passes |
| 15 | Client can create a category or question via POST /pages/{page_id}/qa | ✓ VERIFIED | `pages.py:431-474 create_qa`; manual repro + tests confirm 201 |
| 16 | Client can edit a Q&A item via PUT /pages/{page_id}/qa/{item_id} | ✗ FAILED | Confirmed by direct reproduction: PUT can silently retype a referenced category away from `type='category'`, orphaning dependent questions with no error (see Gaps — matches 13-REVIEW.md CR-01, unresolved) |
| 17 | Client can delete a Q&A item via DELETE /pages/{page_id}/qa/{item_id} | ✗ FAILED | Confirmed by direct reproduction: DELETE on a category with a dependent question raises an unhandled `sqlite3.IntegrityError` (500), not a clean error (see Gaps — matches 13-REVIEW.md WR-01, unresolved) |
| 18 | A question's category_id must reference an existing category on the same page, else 400 | ✓ VERIFIED | `_validate_category_ref` `pages.py:384-395`; `test_qa_post_invalid_category_ref_400`, `test_qa_category_ref_other_page_rejected_400` pass |
| 19 | Tenant cannot list or mutate Q&A on a page it does not own (404) (D-02) | ✓ VERIFIED | `_require_owned_page` used by all 4 Q&A endpoints; `test_qa_cross_tenant_404` passes |
| 20 | Running seed_qa.py --page-fb-id migrates vault categories/questions into qa_items | ✓ VERIFIED | `scripts/seed_qa.py:65-121 seed()`; `test_seed_migrates_categories_and_questions` passes |
| 21 | Questions land with category_id resolved to the newly-inserted integer category id | ✓ VERIFIED | `seed_qa.py:83-111` two-pass insert w/ `category_map`; `test_seed_resolves_category_fk` passes |
| 22 | Re-running the script wipes and reloads, idempotent, no duplicates (D-03) | ✓ VERIFIED | `seed_qa.py:81` unconditional `DELETE FROM qa_items WHERE page_id = ?`; `test_seed_is_idempotent` passes |
| 23 | The script ensures a page_configs row exists with schema defaults | ✓ VERIFIED | `seed_qa.py:113-118` WHERE-NOT-EXISTS insert; `test_seed_creates_page_configs_row` passes |
| 24 | An unknown --page-fb-id exits non-zero, writes nothing | ✓ VERIFIED | `seed_qa.py:70-76` exits before any writes; `test_seed_unknown_page_fb_id_exits` passes |

**Score:** 22/24 truths verified

### Deferred Items

Items required by the literal ROADMAP.md success-criteria wording but explicitly scoped to Phase 14 per `13-CONTEXT.md` ("Out of scope: Bot-side consumption of these endpoints (Phase 14 — BOT-01/02/03)"). The messenger bot (`messenger-bot/src/index.ts`) still calls `GET /content` without `page_id` or `X-Internal-Key`, which is expected — Phase 14 rewires it.

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | Bot immediately serves updated welcome text on Get Started (Roadmap SC1, bot half) | Phase 14 | Phase 14 goal: "fetching the correct token and content config per Page ID from FastAPI" |
| 2 | Menu changes visible in Messenger after API call (Roadmap SC2, bot half) | Phase 14 | 13-CONTEXT.md `<deferred>`: Graph API menu installation deferred to Phase 14 |
| 3 | Bot serves updated Q&A tree without restart (Roadmap SC3, bot half) | Phase 14 | Phase 14 SC1: per-Page token+content routing on webhook events |
| 4 | Bot continues to respond correctly to Q&A after seeding (Roadmap SC5, bot half) | Phase 14 | Bot not yet rewired to pass `page_id`/`X-Internal-Key`; Phase 14 BOT-01/02/03 |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/routers/content.py` | DB-backed HMAC-guarded read endpoints keyed on page_fb_id | ✓ VERIFIED | `hmac.compare_digest` present, `page_fb_id` resolution present, vault code absent |
| `app/main.py` | FastAPI app with no vault lifespan wiring | ✓ VERIFIED | No `lifespan`/`_vault` references; imports cleanly |
| `app/routers/health.py` | Vault-free health check | ✓ VERIFIED | `HealthResponse = {status: str}` only |
| `tests/test_content.py` | DB-backed read + HMAC + page_id coverage | ✓ VERIFIED | 10 tests, all pass |
| `tests/conftest.py` | Vault fixtures removed, db_client retained | ✓ VERIFIED | No `write_md`/`vault_dir`/`content_module`; `db_client` intact |
| `app/routers/pages.py` (config) | PUT /pages/{page_id}/config + GET /internal/.../config | ✓ VERIFIED | Both endpoints present and functioning |
| `app/routers/pages.py` (Q&A) | Q&A REST CRUD endpoints + models | ⚠️ PARTIAL | GET/POST solid; PUT/DELETE exist and pass their plan's own tests but have confirmed referential-integrity/crash defects (CR-01, WR-01) not covered by the plan's must-haves |
| `tests/test_pages.py` | Config write + internal read + Q&A CRUD coverage | ✓ VERIFIED | 31 tests, all pass (does not cover the CR-01/WR-01 scenarios) |
| `scripts/seed_qa.py` | One-time vault->DB Q&A migration CLI | ✓ VERIFIED | argparse, wipe+reload, page_configs default row, no import from retired router |
| `tests/test_seed_qa.py` | Seed migration coverage | ✓ VERIFIED | 5 tests, all pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `content.py` | `pages` table | `SELECT id FROM pages WHERE page_fb_id = ? AND is_active = 1` | ✓ WIRED | `content.py:40-48 _resolve_page_id` |
| `content.py` | `qa_items` table | `SELECT ... FROM qa_items WHERE page_id = ?` | ✓ WIRED | `content.py:74-86` |
| `PUT /pages/{page_id}/config` | `pages` table | ownership check `WHERE id = ? AND tenant_id = ?` | ✓ WIRED | `pages.py:316-321` |
| `PUT /pages/{page_id}/config` | `page_configs` table | insert-or-update on UNIQUE page_id | ✓ WIRED | `pages.py:325-353` |
| `GET /internal/pages/{page_fb_id}/config` | `pages` + `page_configs` | page_fb_id resolution then config read | ✓ WIRED | `pages.py:614-627` |
| Q&A CRUD endpoints | `pages` table | ownership check | ✓ WIRED | `_require_owned_page` used by all 4 endpoints |
| POST/PUT Q&A | `qa_items` (category rows) | app-layer `type = 'category'` check | ⚠️ PARTIAL | `_validate_category_ref` validates the *incoming* category_id but does not protect existing category rows from being retyped away while still referenced (CR-01) |
| `scripts/seed_qa.py` | vault (`settings.vault_path`) | frontmatter parsing | ✓ WIRED | `load_vault_items()` |
| `scripts/seed_qa.py` | `qa_items` + `page_configs` | two-pass insert + ensure-config-row | ✓ WIRED | `seed()` |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite | `pytest -q` (repo root) | `70 passed` | ✓ PASS |
| Content/pages/seed/health tests isolated | `pytest tests/test_seed_qa.py tests/test_content.py tests/test_health.py tests/test_pages.py -q` | `47 passed` | ✓ PASS |
| `seed_qa.py --help` | `python scripts/seed_qa.py --help` | exit 0, shows `--page-fb-id` | ✓ PASS |
| Retype a referenced category via PUT | Live `TestClient` repro: POST category → POST question(category_id) → PUT category `{type:"question"}` | `200 OK`, category silently becomes a `question` row while the earlier question still points at it as `category_id` | ✗ FAIL — confirms CR-01 |
| Delete a category with a dependent question via DELETE | Live `TestClient` repro: POST category → POST question(category_id) → DELETE category | `sqlite3.IntegrityError: FOREIGN KEY constraint failed` raised unhandled inside the request (not caught, surfaces as 500) | ✗ FAIL — confirms WR-01 |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CONTENT-01 | 13-02 | Client can edit welcome/greeting text | ✓ SATISFIED | `PUT /pages/{page_id}/config` `welcome_text` field, tested |
| CONTENT-02 | 13-02 | Client can edit persistent menu labels/structure | ✓ SATISFIED | `PUT /pages/{page_id}/config` `menu_json` field with flat-array validation, tested |
| CONTENT-03 | 13-01, 13-03 | Client can create, edit, delete Q&A categories and answers | ⚠️ PARTIALLY SATISFIED | Create/list/read side fully solid and tested; edit (PUT) and delete (DELETE) exist and pass their own plan's tests but have confirmed defects (CR-01 silent corruption, WR-01 unhandled crash) for the realistic case of a category with dependent questions |
| CONTENT-04 | 13-02 | Client can edit escalation settings | ✓ SATISFIED | `PUT /pages/{page_id}/config` `escalation_psid`/`escalation_message` fields, tested |
| DB-02 | 13-04 | Vault Q&A migrated via one-time seed script | ✓ SATISFIED | `scripts/seed_qa.py`, 5 passing tests covering migration, FK resolution, idempotency, defaults, unknown-page exit |

**Note:** `.planning/REQUIREMENTS.md` still shows all five IDs as `[ ]` unchecked / "Pending" in its traceability table. This matches the pre-existing pattern for Phase 12's PAGE-01–04 (also still "Pending" despite that phase being marked complete in ROADMAP.md) — appears to be a documentation-sync step not performed during phase execution, not specific to this phase. Flagged as informational, not a gap.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/routers/pages.py` | 486-538 (`update_qa`) | Missing referencing-row check before type change | 🛑 Blocker | Silent data corruption — orphaned questions become unreachable through the content API (13-REVIEW.md CR-01, confirmed reproducible) |
| `app/routers/pages.py` | 541-559 (`delete_qa`) | Missing dependent-row check before DELETE | ⚠️ Warning | Unhandled `sqlite3.IntegrityError` → 500 on a common admin action (13-REVIEW.md WR-01, confirmed reproducible) |
| `app/routers/pages.py` | 116-154 (`_store_pages_and_subscribe`) | Webhook subscribe not compensated on later-page failure | ℹ️ Info | Pre-existing Phase 12 code, not modified by Phase 13; out of this phase's scope (13-REVIEW.md WR-02) |
| `app/routers/content.py:30-37`, `pages.py:567-573`, `pages.py:606-612` | — | HMAC guard block duplicated 3x | ℹ️ Info | Divergence risk if the guard logic changes (13-REVIEW.md IN-01) |
| `app/routers/pages.py:501-505` | — | Category self-reference blocked but multi-node cycles (A→B→A) still possible | ℹ️ Info | Latent; no current read path recurses categories (13-REVIEW.md IN-02) |
| `app/routers/content.py:54`, `pages.py:67,75` | — | `type` param name shadows builtin | ℹ️ Info | Cosmetic (13-REVIEW.md IN-03) |

No `TBD`/`FIXME`/`XXX` debt markers found in any file modified by this phase. No placeholder/stub patterns found — every endpoint contains real DB queries wired to real logic.

### Human Verification Required

None. All checkable behaviors were verified programmatically (test suite + direct endpoint reproduction). The remaining Roadmap success criteria that reference live Messenger behavior are legitimately deferred to Phase 14 per `13-CONTEXT.md`, not items this phase can be human-tested against.

### Gaps Summary

The read API (Plan 13-01), the config write/internal-read API (Plan 13-02), and the seed script (Plan 13-04) are all solid — every declared must-have is verified against the actual code and passes its tests, the vault is fully retired from every runtime path, and the `/content` HTTP contract is byte-for-byte preserved.

The gap is concentrated in Plan 13-03's `PUT`/`DELETE` Q&A endpoints, exactly where `13-REVIEW.md` flagged it (CR-01 critical, WR-01 warning) — and both are still present in the shipped code, confirmed by direct reproduction against the live endpoints in this verification pass:

1. **`update_qa` can silently corrupt category→question relationships.** A category that has dependent questions can be retyped to `"question"` via a normal 200 OK PUT with no validation, permanently orphaning those questions from the bot-facing content tree with no visible error to the admin.
2. **`delete_qa` crashes with an unhandled 500** when deleting any category that has ever had a question assigned to it, instead of returning a clean 4xx — this affects the majority of realistic category deletions, not an edge case.

Both fixes are already fully specified in `13-REVIEW.md` (a `SELECT 1 FROM qa_items WHERE category_id = ? AND page_id = ?` dependent-row check, gating the type-change in `update_qa` with a 400 and gating the DELETE in `delete_qa` with a 409). This is a small, well-scoped fix, not a re-architecture — but it is a genuine functional defect in the CONTENT-03 write path that should be closed before this phase is considered fully done.

---

_Verified: 2026-07-22T06:10:33Z_
_Verifier: Claude (gsd-verifier)_
