---
phase: 13-page-config-q-a-api-content-migration
verified: 2026-08-11T12:00:00Z
status: gaps_found
score: 24/25 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 24/25
  gaps_closed: []
  gaps_remaining:
    - "Running scripts/seed_qa.py never silently destroys a page's existing Q&A content when VAULT_PATH is unset or misconfigured — it fails closed instead of reporting false success (truth #25)"
  regressions: []
gaps:
  - truth: "Running scripts/seed_qa.py never silently destroys a page's existing Q&A content when VAULT_PATH is unset or misconfigured — it fails closed instead of reporting false success"
    status: partial
    reason: "Plan 13-06 added a guard (`if not items: ... sys.exit(1)`, scripts/seed_qa.py:81-83) that correctly fixes the three cases it targeted (unset vault_path, missing directory, existing-but-empty directory) — confirmed by re-running tests/test_seed_qa.py (9 passed) and the full suite (76 passed). However the guard checks the wrong quantity: it gates on whether load_vault_items() returned ANY items, not on whether any of those items survive the type/category filtering into an actual INSERT. load_vault_items() accepts any non-empty string as `type` (scripts/seed_qa.py:45) and does not require every question's `category` to resolve. Two independently-reproduced misconfigurations still produce a non-empty `items` list, pass the guard unchanged, execute the unconditional `DELETE FROM qa_items WHERE page_id = ?` (line 85), insert zero rows, reach `conn.commit()` (line 124), and print the false-success line `Seeded 0 categories, 0 questions` at exit code 0 — exactly the failure mode the truth prohibits, just reached through different inputs than the ones 13-06 tested. Reproduced myself, independent of both 13-REVIEW.md's transcript and the SUMMARY's claims: (a) a vault directory containing one .md file with `type: faq` (any non-'category'/'question' type value) — seeded a page to 5 real rows, pointed vault_path at the faq-only dir, re-ran seed(): items list had 1 entry (guard did not trip), DELETE executed, 0 inserted, `Seeded 0 categories, 0 questions for page fb-repro-page`, exit_code=0, rows after=0. (b) a questions-only directory (categories one level up, as would happen if an operator points VAULT_PATH at a `vault/questions/` subfolder or a reorganised vault) — same page seeded to 5 rows, re-ran against the questions-only dir: items list had 1 entry, guard did not trip, DELETE executed, `Skipping question 'q-products-01': unknown category 'cat-products'`, `Seeded 0 categories, 0 questions for page fb-repro-page-2`, exit_code=0, rows after=0. Both reproductions match 13-REVIEW.md CR-01's independent reproduction (cases a and b) byte-for-byte in behavior. This is squarely Phase 13's own DB-02 deliverable (scripts/seed_qa.py) and is not covered by any 13-CONTEXT.md deferral."
    artifacts:
      - path: "scripts/seed_qa.py"
        issue: "Guard at lines 81-83 checks `if not items:` (the raw list length from load_vault_items()) instead of checking whether any row was actually inserted (`category_count + question_count == 0`, evaluated after both insert loops, before conn.commit()). A vault directory with non-category/non-question typed items, or a questions-only directory whose questions reference categories not present in the scanned directory, both produce a non-empty `items` list that passes the current guard, then lose every item to the type filters (lines 90, 102) or the unknown-category skip (lines 106-109), still executing the DELETE (line 85) and commit (line 124) unconditionally."
    missing:
      - "Gate on rows actually written (category_count + question_count == 0), placed after both insert loops and before conn.commit(), with conn.rollback() and sys.exit(1) on trip — per the fix specified in 13-REVIEW.md CR-01 — so the DELETE is undone rather than just 'not yet committed further work'"
      - "Regression test coverage in tests/test_seed_qa.py for the two surviving trigger cases: a vault directory of non-Q&A frontmatter types (e.g. `type: note`), and a questions-only directory whose questions' `category` values do not resolve in the same scanned directory"
deferred:
  - truth: "A client can update the welcome/greeting text for their Page via the API and the bot immediately serves the new text to users on Get Started (Roadmap SC1, bot-serving half)"
    addressed_in: "Phase 14"
    evidence: "Phase 14 goal: 'The bot handles webhook events from multiple Facebook Pages by fetching the correct token and content config per Page ID from FastAPI.' 13-CONTEXT.md: 'Out of scope: Bot-side consumption of these endpoints (Phase 14 — BOT-01/02/03).'"
  - truth: "A client can update the persistent menu labels and structure for their Page via the API; the change is visible in Messenger after the API call (Roadmap SC2, bot/Messenger-visible half)"
    addressed_in: "Phase 14"
    evidence: "13-CONTEXT.md <deferred>: FastAPI-side persistent-menu installation to the Graph API is explicitly deferred; Phase 13 only stores/serves menu_json."
  - truth: "The bot serves the updated Q&A tree without a restart (Roadmap SC3, bot-serving half)"
    addressed_in: "Phase 14"
    evidence: "Phase 14 SC1: 'An inbound webhook event carrying Page ID A is processed using Page A's token and content...' — the bot rewiring onto this phase's page_id/X-Internal-Key contract is Phase 14 BOT-01/02/03's explicit deliverable."
  - truth: "Running the seed script migrates vault Q&A into the database, and the bot continues to respond correctly to Q&A queries using DB-backed content (Roadmap SC5, bot-response half)"
    addressed_in: "Phase 14"
    evidence: "Re-confirmed this pass: messenger-bot/src/index.ts's exact current /content calls (no page_id, no X-Internal-Key — grep for either returns zero matches) return HTTP 422 against the live app/routers/content.py contract. Treated as deferred, not a Phase 13 blocker, because 13-CONTEXT.md D-01 explicitly designed this two-phase contract-first rollout before implementation and the Phase Boundary explicitly scopes bot-side consumption out of Phase 13. IMPORTANT CAVEAT carried forward again: the bot's Q&A browsing feature is presently non-functional against main until Phase 14 lands — main should not be deployed standalone without Phase 14's bot rewiring or a temporary fallback contract."
---

# Phase 13: Page Config, Q&A API + Content Migration Verification Report

**Phase Goal:** All bot content (welcome text, menu, Q&A, escalation settings) is served from the database per Page ID; the existing /content HTTP contract is preserved; the Obsidian vault is retired
**Verified:** 2026-08-11T12:00:00Z
**Status:** gaps_found
**Re-verification:** Yes — after 13-06 gap-closure plan for truth #25 (seed_qa.py fail-closed guard); truths #16/#17 (closed by 13-05) re-checked for regression

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | GET /content?type=category&page_id=<fb_id> + valid X-Internal-Key returns that page's categories | ✓ VERIFIED | `app/routers/content.py:51-94` (`list_content`); `tests/test_content.py` passes; file unchanged since prior pass (`git diff --stat` between prior verification commit and HEAD touches only `scripts/seed_qa.py` and `tests/test_seed_qa.py`) |
| 2 | GET /content?type=question&category=<id>&page_id=<fb_id> returns filtered questions | ✓ VERIFIED | `content.py:73-79`; unchanged, tests pass |
| 3 | GET /content/{id}?page_id=<fb_id> returns the question body | ✓ VERIFIED | `content.py:97-123`; unchanged, tests pass |
| 4 | Missing/wrong X-Internal-Key returns 403 (D-01) | ✓ VERIFIED | `content.py:30-37 _check_internal_key`; unchanged |
| 5 | `{items:[{id,type,title}]}` / `{id,type,title,body}` shapes unchanged | ✓ VERIFIED | `content.py:13-27` models unchanged |
| 6 | Vault fully retired (`_vault`, `load_vault`, `/content/reload` gone) | ✓ VERIFIED | `grep -rnE "_vault|load_vault|/content/reload|vault_loaded|content_count" app/` returns nothing (re-run this pass) |
| 7 | GET /health returns 200 `{status:'ok'}`, no vault fields | ✓ VERIFIED | `app/routers/health.py` unchanged |
| 8 | Client can replace welcome_text/menu_json/escalation_psid/escalation_message in one PUT | ✓ VERIFIED | `pages.py` `put_page_config`; unchanged, tests pass |
| 9 | PUT creates page_configs row if absent, overwrites if present | ✓ VERIFIED | Insert-or-update on `page_configs.page_id` (UNIQUE); unchanged |
| 10 | menu_json accepts flat `[{title,payload}]`, rejects nested/malformed (D-04) | ✓ VERIFIED | `MenuItem(extra="forbid")`; unchanged, tests pass |
| 11 | Tenant cannot write to a page it does not own (404, no leak) (D-02) | ✓ VERIFIED | Ownership check before any write; unchanged |
| 12 | GET /internal/pages/{page_fb_id}/config returns config behind HMAC | ✓ VERIFIED | Unchanged, tests pass |
| 13 | Internal config read 403 without valid key, 404 unknown page_fb_id | ✓ VERIFIED | Unchanged, tests pass |
| 14 | Client can list page's Q&A items via GET /pages/{page_id}/qa | ✓ VERIFIED | `pages.py list_qa`; unchanged, tests pass |
| 15 | Client can create a category or question via POST /pages/{page_id}/qa | ✓ VERIFIED | `pages.py create_qa`; unchanged, tests pass |
| 16 | Client can edit a Q&A item via PUT /pages/{page_id}/qa/{item_id} | ✓ VERIFIED (regression-checked) | `app/routers/pages.py:398` `_has_dependent_qa_items`, called at `:516` inside `update_qa`. `tests/test_pages.py::test_qa_put_retype_referenced_category_400` (line 940) still present and passing. File unchanged since prior pass (confirmed via `git diff --stat` — only `scripts/seed_qa.py`/`tests/test_seed_qa.py` changed since 0721d2d) |
| 17 | Client can delete a Q&A item via DELETE /pages/{page_id}/qa/{item_id} | ✓ VERIFIED (regression-checked) | `app/routers/pages.py:398` guard, called at `:568` inside `delete_qa`. `tests/test_pages.py::test_qa_delete_referenced_category_409` (line 1015) still present and passing. Unchanged since prior pass |
| 18 | A question's category_id must reference an existing category on the same page, else 400 | ✓ VERIFIED | `_validate_category_ref`; unchanged, tests pass |
| 19 | Tenant cannot list or mutate Q&A on a page it does not own (404) (D-02) | ✓ VERIFIED | `_require_owned_page` used by all 4 Q&A endpoints; unchanged |
| 20 | Running seed_qa.py --page-fb-id migrates vault categories/questions into qa_items | ✓ VERIFIED | `scripts/seed_qa.py seed()`; happy path untouched by 13-06's change; re-confirmed this pass via direct script invocation against `vault-sample/` (2 categories, 3 questions inserted) |
| 21 | Questions land with category_id resolved to the newly-inserted integer category id | ✓ VERIFIED | Two-pass insert w/ `category_map`; unchanged, tests pass |
| 22 | Re-running the script wipes and reloads, idempotent, no duplicates (D-03) | ✓ VERIFIED | `test_seed_is_idempotent` re-run this pass (`1 passed`), confirms 13-06's guard did not break re-runnability against a valid vault |
| 23 | The script ensures a page_configs row exists with schema defaults | ✓ VERIFIED | WHERE-NOT-EXISTS insert; unchanged, tests pass |
| 24 | An unknown --page-fb-id exits non-zero, writes nothing | ✓ VERIFIED | Exits before any writes; unchanged, tests pass |
| 25 | Running scripts/seed_qa.py never silently destroys a page's existing Q&A content when VAULT_PATH is unset/misconfigured — it fails closed instead of reporting false success | ✗ FAILED (still open — not closed by 13-06) | 13-06's guard (`if not items:`, lines 81-83) fixes 3 of 5 known trigger vectors (unset/missing-dir/empty-dir) but checks the wrong quantity. Independently reproduced in this pass (not merely read from 13-REVIEW.md CR-01): a `type: faq`-only vault directory, and a questions-only directory referencing categories not present in the scan, BOTH still pass the guard (non-empty `items`), execute the DELETE, insert 0 rows, commit, and print `Seeded 0 categories, 0 questions` at exit 0 — full data loss with a false success message. See Gaps below |

**Score:** 24/25 truths verified

### Deferred Items

Items not yet met but explicitly and deliberately scoped to Phase 14 per `13-CONTEXT.md`. Re-confirmed still accurate this pass (no code changes touched the bot/API contract boundary since the prior verification).

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | Bot immediately serves updated welcome text on Get Started (Roadmap SC1, bot half) | Phase 14 | Phase 14 goal: "fetching the correct token and content config per Page ID from FastAPI" |
| 2 | Menu changes visible in Messenger after API call (Roadmap SC2, bot half) | Phase 14 | 13-CONTEXT.md `<deferred>`: Graph API menu installation deferred to Phase 14 |
| 3 | Bot serves updated Q&A tree without restart (Roadmap SC3, bot half) | Phase 14 | Phase 14 SC1: per-Page token+content routing on webhook events |
| 4 | Bot continues to respond correctly to Q&A after seeding (Roadmap SC5, bot half) | Phase 14 | `messenger-bot/src/index.ts` still sends neither `page_id` nor `X-Internal-Key` (grep, zero matches); `/content?type=category` without them returns 422 against the live API. Deliberate two-phase rollout per D-01, not a Phase 13 defect. Operational risk flagged: do not deploy Phase 13 standalone without Phase 14 |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/routers/content.py` | DB-backed HMAC-guarded read endpoints keyed on page_fb_id | ✓ VERIFIED | Unchanged since prior pass |
| `app/main.py` | FastAPI app with no vault lifespan wiring | ✓ VERIFIED | No `lifespan`/`_vault` references |
| `app/routers/health.py` | Vault-free health check | ✓ VERIFIED | `HealthResponse = {status: str}` only |
| `tests/test_content.py` | DB-backed read + HMAC + page_id coverage | ✓ VERIFIED | Unchanged, passes |
| `app/routers/pages.py` (Q&A) | Q&A REST CRUD endpoints + models | ✓ VERIFIED | Unchanged since prior pass; `_has_dependent_qa_items` guard intact |
| `tests/test_pages.py` | Config write + internal read + Q&A CRUD coverage | ✓ VERIFIED | Unchanged, passes |
| `scripts/seed_qa.py` | One-time vault->DB Q&A migration CLI | ⚠️ STUB-LIKE DEFECT (still open) | Core migration logic solid (truths #20-24). 13-06 narrowed but did not close the fail-closed gap — guard checks list-emptiness, not insert-emptiness. Independently reproduced continued data loss (truth #25, gap) |
| `tests/test_seed_qa.py` | Seed migration coverage | ⚠️ PARTIAL | 9 tests, all pass, but the new tests only cover 3 of the 5 known trigger vectors (unset/missing_dir/empty_dir); no coverage for non-Q&A-typed vault content or questions-only directories, which still reproduce the destructive path |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `content.py` | `pages` table | `SELECT id FROM pages WHERE page_fb_id = ? AND is_active = 1` | ✓ WIRED | Unchanged |
| `PUT /pages/{page_id}/config` | `page_configs` table | insert-or-update on UNIQUE page_id | ✓ WIRED | Unchanged |
| `update_qa` | `qa_items` (dependent rows) | `_has_dependent_qa_items` before UPDATE → 400 | ✓ WIRED | Unchanged, regression-checked |
| `delete_qa` | `qa_items` (dependent rows) | `_has_dependent_qa_items` before DELETE → 409 | ✓ WIRED | Unchanged, regression-checked |
| `scripts/seed_qa.py` | vault (`settings.vault_path`) | frontmatter parsing + `if not items:` guard | ⚠️ WIRED BUT STILL UNSAFE | Guard narrows but does not close the destructive path — see truth #25 gap |
| `messenger-bot/src/index.ts` | `GET /content` | `axios.get` with page_id + X-Internal-Key | ✗ NOT WIRED (deferred to Phase 14) | Unchanged; confirmed by grep — bot sends neither param |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `GET /content` responses | `qa_items` rows | Live SQLite query, page-scoped | Yes | ✓ FLOWING |
| `scripts/seed_qa.py` seeded rows | vault frontmatter files | `os.scandir(vault_path)` | Yes on a well-formed vault; but the DELETE still executes and commits with zero inserts on two independently-reproduced malformed-but-non-empty vault shapes | ⚠️ STATIC-ON-FAILURE (truth #25 gap, narrowed but not closed) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full Python test suite | `.venv/bin/python -m pytest -q` (repo root) | `76 passed` | ✓ PASS |
| Full messenger-bot test suite | `npm test` (messenger-bot/) | `50 passed` | ✓ PASS |
| `tests/test_seed_qa.py` isolated | `.venv/bin/python -m pytest tests/test_seed_qa.py -q` | `9 passed` | ✓ PASS |
| D-03 idempotency regression | `.venv/bin/python -m pytest tests/test_seed_qa.py -q -k is_idempotent` | `1 passed` | ✓ PASS — 13-06's guard did not break re-runnable wipe+reload |
| `_has_dependent_qa_items` regression (truths #16/#17) | `grep -n "_has_dependent_qa_items" app/routers/pages.py` + `test_qa_put_retype_referenced_category_400`/`test_qa_delete_referenced_category_409` present and passing in full suite | Helper present at line 398, invoked at 516/568; both tests pass | ✓ PASS — no regression |
| Live repro (a): faq-typed-only vault dir, seed twice | Direct `seed()`/`load_vault_items()` invocation (this pass) | Page seeded to 5 real rows; re-seeded against faq-only dir: `items` list has 1 entry (guard did not trip), `Seeded 0 categories, 0 questions for page fb-repro-page`, exit_code=0, rows after=**0** | ✗ FAIL — truth #25 still open, matches 13-REVIEW.md CR-01 case (a) |
| Live repro (b): questions-only vault dir (categories elsewhere), seed twice | Direct `seed()`/`load_vault_items()` invocation (this pass) | Page seeded to 5 real rows; re-seeded against questions-only dir: `Skipping question 'q-products-01': unknown category 'cat-products'`, `Seeded 0 categories, 0 questions for page fb-repro-page-2`, exit_code=0, rows after=**0** | ✗ FAIL — truth #25 still open, matches 13-REVIEW.md CR-01 case (b) |
| Live repro: bot's exact `/content?type=category` call (no page_id/key) | `TestClient` reproduction pattern unchanged from prior pass; `messenger-bot/src/index.ts` grep for `page_id`/`X-Internal-Key`/`INTERNAL_SECRET` | Zero matches, contract mismatch unchanged | ✗ FAIL against literal SC5 wording, treated as **deferred** to Phase 14 per prior judgment (unchanged) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CONTENT-01 | 13-02 | Client can edit welcome/greeting text | ✓ SATISFIED | `PUT /pages/{page_id}/config` `welcome_text` field, tested; unchanged since prior pass |
| CONTENT-02 | 13-02 | Client can edit persistent menu labels/structure | ✓ SATISFIED | `PUT /pages/{page_id}/config` `menu_json` field, tested; unchanged |
| CONTENT-03 | 13-01, 13-03, 13-05 | Client can create, edit, delete Q&A categories and answers | ✓ SATISFIED | Create/list/read solid; edit (PUT) and delete (DELETE) correctly reject the referenced-category case (400/409) — truths #16/#17 confirmed still closed, no regression |
| CONTENT-04 | 13-02 | Client can edit escalation settings | ✓ SATISFIED | `PUT /pages/{page_id}/config` `escalation_psid`/`escalation_message` fields, tested; unchanged |
| DB-02 | 13-04, 13-06 | Vault Q&A migrated via one-time seed script | ⚠️ PARTIALLY SATISFIED (unchanged from prior pass — 13-06 narrowed but did not close the gap) | Happy-path migration is solid and tested (truths #20-24). 13-06 fixed 3 of 5 known trigger vectors for the fail-closed requirement (unset/missing-dir/empty-dir) but the guard checks the wrong quantity (`if not items` instead of `if category_count + question_count == 0`), leaving two independently-reproduced destructive paths open (non-Q&A-typed vault content; questions-only directories with unresolvable categories) |

**Note:** `.planning/REQUIREMENTS.md` still shows CONTENT-01/02/04 and DB-02 as `[ ]` unchecked / "Pending" in its traceability table (only CONTENT-03 is checked). Same pre-existing documentation-sync pattern already flagged as informational in prior verification rounds (also seen for Phase 12's PAGE-01–04) — not a new or phase-specific gap, but DB-02 in particular should not be checked off until truth #25 is actually closed, since REQUIREMENTS.md's own unchecked state happens to be accurate here.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `scripts/seed_qa.py` | 81-124 | Fail-closed guard checks `if not items:` (raw parsed-list length) rather than rows-actually-inserted (`category_count + question_count == 0`); the DELETE (line 85) and commit (line 124) still execute unconditionally once the guard is passed | 🛑 Blocker | Silent, irreversible data loss on the actual one-time migration run remains reachable via two realistic misconfigurations (non-Q&A frontmatter types; questions-only subfolder) — independently reproduced in this pass, confirms 13-REVIEW.md CR-01 (still open) |
| `messenger-bot/src/index.ts:264,292,327` vs `app/routers/content.py:53,58,100,103` | — | Bot's only `/content` consumer sends neither the required `page_id` nor `X-Internal-Key` | ⚠️ Warning (deferred to Phase 14 by explicit 13-CONTEXT.md design) | Bot Q&A browsing is currently non-functional against `main`'s API as shipped. Not a Phase 13 blocker per the pre-planned two-phase rollout, but an urgent deployment-sequencing risk |
| `app/routers/pages.py` (`_has_dependent_qa_items`) | 398-404 | Guard is page-scoped while the `category_id` FK it protects is global — a cross-page dependent (not currently creatable via the API, since `_validate_category_ref` is itself page-scoped) would still hit an unhandled `sqlite3.IntegrityError` on DELETE | ℹ️ Info (latent, not reachable through the current write API; 13-REVIEW.md WR-01/WR-02, carried forward unchanged) | Does not affect truths #16/#17 as stated (the ordinary same-page edit/delete flow is correctly guarded); flagged for awareness only |
| `app/routers/pages.py` (`_validate_category_ref`) | ~384-395 | Does not reject `category_id` on a `type="category"` row — category→category references creatable via the ordinary write API, can form undeletable cycles with a misleading 409 message | ⚠️ Warning (13-REVIEW.md WR-03, carried forward unchanged) | Narrow blast radius; not elevated to a blocking gap, consistent with the prior verification pass's judgment |
| `app/routers/content.py`, `pages.py`, `scripts/seed_qa.py` | multiple | 12 additional Warning/Info findings in 13-REVIEW.md (WR-04–WR-18 except WR-01/02/03 noted above, IN-01–IN-11) | ℹ️ Info | Reviewed; none independently found to falsify a roadmap success criterion or PLAN must-have for this phase beyond truth #25 (already captured as a gap above). Listed in full in `13-REVIEW.md` for follow-up triage, not duplicated here |

No `TBD`/`FIXME`/`XXX` debt markers found in any file modified by this phase (`grep -n "TBD\|FIXME\|XXX"` across `app/routers/pages.py`, `app/routers/content.py`, `scripts/seed_qa.py`, `tests/test_seed_qa.py` returns nothing).

### Human Verification Required

None. All checkable behaviors were verified programmatically in this pass — direct code reads, live script/`seed()` reproductions (both new counter-examples and regression checks), and the full automated test suites (76 Python + 50 messenger-bot tests). The remaining Roadmap success-criteria halves that reference live Messenger/bot behavior remain legitimately deferred to Phase 14 per `13-CONTEXT.md`'s explicit, pre-planned scope boundary.

### Gaps Summary

**Truths #16 and #17 remain genuinely closed — no regression.** `git diff --stat` between the prior verification's base commit (`0721d2d`) and the current `HEAD` shows only `scripts/seed_qa.py` (+4) and `tests/test_seed_qa.py` (+115) changed; `app/routers/pages.py` is byte-identical to the last pass. The `_has_dependent_qa_items` guard, the two regression tests, and the full suite (76 passing, up from 72 due to the 4 new seed_qa tests) all confirm the config/Q&A write API is unchanged and correct.

**Truth #25 (DB-02's fail-closed requirement) is still FAILED — plan 13-06 narrowed the vulnerability but did not close it.** I independently verified this by reading `scripts/seed_qa.py` directly and reproducing two counter-examples myself (not trusting either 13-06-SUMMARY.md's "closing 13-REVIEW.md CR-01 / 13-VERIFICATION.md truth #25" claim or accepting 13-REVIEW.md's transcript at face value):

- **Reproduction (a):** a vault directory containing a single `.md` file with `type: faq` (any type value other than `'category'`/`'question'` passes `load_vault_items`'s validation, which only requires `type` to be a non-empty string). Seeded a page to 5 real rows via the valid `vault-sample/` vault, then re-ran `seed()` pointed at the faq-only directory: `load_vault_items()` returned a 1-element list (the `if not items:` guard at line 81 does not trip), the `DELETE FROM qa_items WHERE page_id = ?` at line 85 executed, both insert loops skipped the item (wrong `type`), `conn.commit()` at line 124 ran, and the script printed `Seeded 0 categories, 0 questions for page fb-repro-page` with exit code 0. All 5 rows gone, false success reported.
- **Reproduction (b):** a questions-only vault directory (the categories those questions reference live in a different, unscanned directory — the realistic "operator points VAULT_PATH at `vault/questions/` instead of `vault/`" scenario `13-REVIEW.md` calls out). Same result: guard doesn't trip (`items` has 1 entry), DELETE executes, the question is skipped via the "unknown category" branch (lines 106-109), commit runs, `Seeded 0 categories, 0 questions` prints, exit 0, all 5 rows gone.

Both reproductions match `13-REVIEW.md` CR-01's independently-documented transcript. The root cause: the guard 13-06 added gates on "did `load_vault_items()` return anything" (`if not items:`), but the truth requires gating on "will anything actually be written" (`category_count + question_count == 0`, checked after both insert loops, immediately before `conn.commit()`, with `conn.rollback()` on trip so the already-issued `DELETE` is undone rather than committed). 13-06 fixed 3 of the 5 known trigger vectors (unset `vault_path`, missing directory, existing-but-empty directory) — those three are genuinely closed and covered by passing regression tests. The other 2 vectors (non-Q&A-typed content; unresolvable-category questions) remain open and are not covered by any existing test.

**Per this verification's explicit instruction to score the truth as written rather than against plan 13-06's own three enumerated test cases:** truth #25 is FAILED. DB-02 remains PARTIALLY SATISFIED. This should be closed with a follow-on gap-closure plan implementing the rows-written gate 13-REVIEW.md CR-01 specifies (which is a narrow, surgical fix — the fifth or sixth line change to the same function 13-06 already touched), plus the two additional regression test cases, before Phase 13 is considered fully done.

No overrides were requested or applied for this gap.

---

_Verified: 2026-08-11T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
