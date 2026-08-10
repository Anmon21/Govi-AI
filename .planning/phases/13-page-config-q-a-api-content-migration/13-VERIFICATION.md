---
phase: 13-page-config-q-a-api-content-migration
verified: 2026-08-10T11:00:00Z
status: gaps_found
score: 24/25 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 22/24
  gaps_closed:
    - "A client can edit a Q&A item via PUT /pages/{page_id}/qa/{item_id} (truth #16 — CR-01/original)"
    - "A client can delete a Q&A item via DELETE /pages/{page_id}/qa/{item_id} (truth #17 — WR-01/original)"
  gaps_remaining: []
  regressions: []
gaps:
  - truth: "Running scripts/seed_qa.py never silently destroys a page's existing Q&A content when VAULT_PATH is unset or misconfigured — it fails closed instead of reporting false success"
    status: failed
    reason: "load_vault_items() returns an empty list (with only a printed warning) when settings.vault_path is unset or not a directory (scripts/seed_qa.py:22-24). seed() does not check for this — it proceeds unconditionally to `DELETE FROM qa_items WHERE page_id = ?` (line 81), inserts nothing, commits, and prints a success message ('Seeded 0 categories, 0 questions for page <id>'). Independently reproduced in this verification pass (not merely trusted from 13-REVIEW.md CR-01): seeded a page with 5 real qa_items rows via a valid vault, then re-ran seed() with vault_path pointed at a nonexistent directory — all 5 rows were deleted, 0 were inserted, and the script printed success. settings.vault_path defaults to \"\" in app/config.py:8, which is exactly the failure condition, making this a highly plausible outcome on the actual first ('one-time') run if VAULT_PATH is not exported in the shell/`.env` the script is run from. This is in-scope for Phase 13 (scripts/seed_qa.py is this phase's own DB-02 deliverable) and is not covered by any 13-CONTEXT.md deferral."
    artifacts:
      - path: "scripts/seed_qa.py"
        issue: "seed() (lines 65-121) never checks that load_vault_items() returned a non-empty list before executing the unconditional DELETE + commit at lines 81/120"
    missing:
      - "A fail-closed guard in seed() that exits non-zero (no DELETE, no commit) when load_vault_items() returns an empty list, per the fix specified in 13-REVIEW.md CR-01"
      - "Regression test coverage for the empty/misconfigured-vault-path case in tests/test_seed_qa.py (currently absent)"
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
    evidence: "Independently reproduced in this verification pass: messenger-bot/src/index.ts's exact current /content calls (no page_id, no X-Internal-Key — confirmed by grep, zero matches for either in the file) return HTTP 422 against the live app/routers/content.py contract. This is real and confirms 13-REVIEW.md CR-02's reproduction. It is treated as deferred, not a Phase 13 blocker, because 13-CONTEXT.md D-01 explicitly and deliberately designed the read contract this way *before* implementation ('Add required page_id query param on all read endpoints (Phase 14 will pass the Page's FB id)'), and 13-CONTEXT.md's Phase Boundary explicitly states bot-side consumption is out of scope for this phase. This is an intentional API-first, consumer-second two-phase rollout, not an accidental omission. IMPORTANT CAVEAT carried into this report: this means the bot's Q&A browsing feature is presently 100% non-functional against `main` until Phase 14 lands — this should be treated as an urgent, high-priority follow-on, and `main` should not be deployed standalone (API-only) to production without also deploying the Phase 14 bot changes, or the old unauthenticated/page-less contract should be temporarily preserved as a fallback."
---

# Phase 13: Page Config, Q&A API + Content Migration Verification Report

**Phase Goal:** All bot content (welcome text, menu, Q&A, escalation settings) is served from the database per Page ID; the existing /content HTTP contract is preserved; the Obsidian vault is retired
**Verified:** 2026-08-10T11:00:00Z
**Status:** gaps_found
**Re-verification:** Yes — after gap closure (13-05 plan for truths #16/#17), plus independent assessment of two Critical findings from a fresh 13-REVIEW.md code review

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | GET /content?type=category&page_id=<fb_id> + valid X-Internal-Key returns that page's categories | ✓ VERIFIED | `app/routers/content.py:51-94` (`list_content`); `tests/test_content.py` passes; re-confirmed unchanged since prior verification |
| 2 | GET /content?type=question&category=<id>&page_id=<fb_id> returns filtered questions | ✓ VERIFIED | `content.py:73-79`; test coverage passes |
| 3 | GET /content/{id}?page_id=<fb_id> returns the question body | ✓ VERIFIED | `content.py:97-123`; test coverage passes |
| 4 | Missing/wrong X-Internal-Key returns 403 (D-01) | ✓ VERIFIED | `content.py:30-37 _check_internal_key`; independently re-confirmed via live TestClient call in this pass |
| 5 | `{items:[{id,type,title}]}` / `{id,type,title,body}` shapes unchanged | ✓ VERIFIED | `content.py:13-27` models unchanged |
| 6 | Vault fully retired (`_vault`, `load_vault`, `/content/reload` gone) | ✓ VERIFIED | `grep -rnE "_vault|load_vault|/content/reload|vault_loaded|content_count" app/` returns nothing (re-run this pass) |
| 7 | GET /health returns 200 `{status:'ok'}`, no vault fields | ✓ VERIFIED | `app/routers/health.py:1-13` unchanged |
| 8 | Client can replace welcome_text/menu_json/escalation_psid/escalation_message in one PUT | ✓ VERIFIED | `pages.py` `put_page_config`; test coverage passes |
| 9 | PUT creates page_configs row if absent, overwrites if present | ✓ VERIFIED | Insert-or-update on `page_configs.page_id` (UNIQUE) |
| 10 | menu_json accepts flat `[{title,payload}]`, rejects nested/malformed (D-04) | ✓ VERIFIED | `MenuItem(extra="forbid")`; test passes |
| 11 | Tenant cannot write to a page it does not own (404, no leak) (D-02) | ✓ VERIFIED | Ownership check before any write |
| 12 | GET /internal/pages/{page_fb_id}/config returns config behind HMAC | ✓ VERIFIED | Unchanged, tests pass |
| 13 | Internal config read 403 without valid key, 404 unknown page_fb_id | ✓ VERIFIED | Unchanged, tests pass |
| 14 | Client can list page's Q&A items via GET /pages/{page_id}/qa | ✓ VERIFIED | `pages.py list_qa`; tests pass |
| 15 | Client can create a category or question via POST /pages/{page_id}/qa | ✓ VERIFIED | `pages.py create_qa`; tests pass |
| 16 | Client can edit a Q&A item via PUT /pages/{page_id}/qa/{item_id} | ✓ VERIFIED (gap closed) | `app/routers/pages.py:507-511` — `_has_dependent_qa_items(conn, page_id, item_id)` guard now rejects (400 "Cannot change type: this category is referenced by questions") a type-change away from `'category'` while dependents exist, evaluated BEFORE the UPDATE. Read the code directly (not just the SUMMARY): guard is present, page-scoped, state-based (re-checked live, not cached). `tests/test_pages.py::test_qa_put_retype_referenced_category_400` (lines 940-1000) exercises the reject case, the non-over-trigger case, AND the guard-releases-once-dependency-removed case, all in one test. Full suite green (72 passed) |
| 17 | Client can delete a Q&A item via DELETE /pages/{page_id}/qa/{item_id} | ✓ VERIFIED (gap closed) | `app/routers/pages.py:576-580` — same guard now rejects (409 "Category has questions; delete or reassign them first") a DELETE while dependents exist, evaluated BEFORE the DELETE statement, replacing the prior unhandled `sqlite3.IntegrityError`. `tests/test_pages.py::test_qa_delete_referenced_category_409` (lines 1015-1067) covers reject, no-partial-delete, and guard-release-after-dependency-removed. Verified by direct code read + running the full suite myself (`72 passed`), not by trusting 13-05-SUMMARY.md's claim |
| 18 | A question's category_id must reference an existing category on the same page, else 400 | ✓ VERIFIED | `_validate_category_ref`; tests pass |
| 19 | Tenant cannot list or mutate Q&A on a page it does not own (404) (D-02) | ✓ VERIFIED | `_require_owned_page` used by all 4 Q&A endpoints |
| 20 | Running seed_qa.py --page-fb-id migrates vault categories/questions into qa_items | ✓ VERIFIED | `scripts/seed_qa.py seed()`; test passes; independently re-ran the script logic against `vault-sample/` in this verification pass and confirmed 2 categories / 3 questions inserted |
| 21 | Questions land with category_id resolved to the newly-inserted integer category id | ✓ VERIFIED | Two-pass insert w/ `category_map`; test passes |
| 22 | Re-running the script wipes and reloads, idempotent, no duplicates (D-03) | ✓ VERIFIED | Unconditional `DELETE FROM qa_items WHERE page_id = ?` then reinsert; matches the explicitly-chosen D-03 design (wipe+reload, ids intentionally not preserved per 13-CONTEXT.md — this is accepted design, not a defect) |
| 23 | The script ensures a page_configs row exists with schema defaults | ✓ VERIFIED | WHERE-NOT-EXISTS insert; test passes |
| 24 | An unknown --page-fb-id exits non-zero, writes nothing | ✓ VERIFIED | Exits before any writes; test passes |
| 25 | Running scripts/seed_qa.py never silently destroys a page's existing Q&A content when VAULT_PATH is unset/misconfigured | ✗ FAILED | **New finding, independently reproduced in this pass** (not merely read from 13-REVIEW.md CR-01). `seed()` has no check that `load_vault_items()` returned anything before executing `DELETE FROM qa_items WHERE page_id = ?` and committing. See Gaps below |

**Score:** 24/25 truths verified

### Deferred Items

Items not yet met but explicitly and deliberately scoped to Phase 14 per `13-CONTEXT.md`, confirmed still accurate in this pass (including fresh independent reproduction of the bot/API mismatch CR-02 raised).

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | Bot immediately serves updated welcome text on Get Started (Roadmap SC1, bot half) | Phase 14 | Phase 14 goal: "fetching the correct token and content config per Page ID from FastAPI" |
| 2 | Menu changes visible in Messenger after API call (Roadmap SC2, bot half) | Phase 14 | 13-CONTEXT.md `<deferred>`: Graph API menu installation deferred to Phase 14 |
| 3 | Bot serves updated Q&A tree without restart (Roadmap SC3, bot half) | Phase 14 | Phase 14 SC1: per-Page token+content routing on webhook events |
| 4 | Bot continues to respond correctly to Q&A after seeding (Roadmap SC5, bot half) — **CR-02 independently confirmed this pass** | Phase 14 | Live reproduction: `client.get("/content?type=category")` (the exact call `messenger-bot/src/index.ts:264` makes today, byte-for-byte) returns `422 {'detail': [{'loc': ['query','page_id'], 'msg': 'Field required'}]}` against the current `app/routers/content.py`. `grep` for `page_id`, `X-Internal-Key`, or `INTERNAL_SECRET` in `messenger-bot/src/index.ts` returns zero matches. **Judgment call:** treated as deferred, not a Phase 13 blocker, because 13-CONTEXT.md D-01 explicitly designed this exact two-phase contract-first rollout before any code was written ("Add required page_id query param... Phase 14 will pass the Page's FB id"), and the Phase Boundary section explicitly lists bot-side consumption as out of scope for Phase 13. This is a deliberate sequencing decision, not an accidental regression discovered after the fact — the same reasoning the prior (accepted) 13-VERIFICATION.md applied to this exact class of finding. **However**, this does mean the bot's Q&A browsing feature is presently non-functional against `main` as shipped, and this should be flagged to the user as an urgent operational risk: do not deploy Phase 13's API changes to production standalone without also deploying Phase 14, or without temporarily preserving the old contract as a fallback. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/routers/content.py` | DB-backed HMAC-guarded read endpoints keyed on page_fb_id | ✓ VERIFIED | Unchanged since prior pass; re-read in full this verification |
| `app/main.py` | FastAPI app with no vault lifespan wiring | ✓ VERIFIED | No `lifespan`/`_vault` references |
| `app/routers/health.py` | Vault-free health check | ✓ VERIFIED | `HealthResponse = {status: str}` only |
| `tests/test_content.py` | DB-backed read + HMAC + page_id coverage | ✓ VERIFIED | 211 lines, passes |
| `app/routers/pages.py` (Q&A) | Q&A REST CRUD endpoints + models | ✓ VERIFIED | GET/POST/PUT/DELETE all solid — `_has_dependent_qa_items` guard closes the prior CR-01/WR-01 defects; read in full this pass (665 lines) |
| `tests/test_pages.py` | Config write + internal read + Q&A CRUD coverage, incl. referential-integrity regressions | ✓ VERIFIED | 1067 lines; 33 Q&A/pages-related tests including the two new 13-05 regression tests; full file re-read |
| `scripts/seed_qa.py` | One-time vault->DB Q&A migration CLI | ⚠️ STUB-LIKE DEFECT | Core migration logic is solid and tested (truths #20-24), but has no fail-closed guard against a misconfigured `VAULT_PATH` — independently reproduced destructive data loss with a false success message (truth #25, gap) |
| `tests/test_seed_qa.py` | Seed migration coverage | ⚠️ PARTIAL | 5 tests, all pass, but no coverage for the empty/misconfigured-vault-path destructive path (confirmed by reading the file — no such test exists) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `content.py` | `pages` table | `SELECT id FROM pages WHERE page_fb_id = ? AND is_active = 1` | ✓ WIRED | Unchanged |
| `PUT /pages/{page_id}/config` | `page_configs` table | insert-or-update on UNIQUE page_id | ✓ WIRED | Unchanged |
| `update_qa` | `qa_items` (dependent rows) | `_has_dependent_qa_items` before UPDATE → 400 | ✓ WIRED (newly closed) | `pages.py` — verified by direct code read: guard sits between `_validate_category_ref` and the `UPDATE` statement |
| `delete_qa` | `qa_items` (dependent rows) | `_has_dependent_qa_items` before DELETE → 409 | ✓ WIRED (newly closed) | `pages.py` — verified by direct code read: guard sits between `_require_owned_qa_item` and the `DELETE` statement |
| `scripts/seed_qa.py` | vault (`settings.vault_path`) | frontmatter parsing | ⚠️ WIRED BUT UNSAFE | Wired correctly for the happy path; not fail-safe for the empty-result path (truth #25 gap) |
| `messenger-bot/src/index.ts` | `GET /content` | `axios.get` with page_id + X-Internal-Key | ✗ NOT WIRED (deferred to Phase 14) | Confirmed by grep + live reproduction: bot sends neither param today |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `GET /content` responses | `qa_items` rows | Live SQLite query, page-scoped | Yes | ✓ FLOWING |
| `scripts/seed_qa.py` seeded rows | vault frontmatter files | `os.scandir(vault_path)` | Yes, when `vault_path` valid — **but silently empty (not an error) when invalid**, and the DELETE still executes | ⚠️ STATIC-ON-FAILURE (truth #25 gap) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full Python test suite | `.venv/bin/python -m pytest -q` (repo root) | `72 passed` | ✓ PASS |
| Full messenger-bot test suite | `npm test` (messenger-bot/) | `50 passed` | ✓ PASS |
| 13-05 regression tests isolated | `.venv/bin/python -m pytest tests/test_pages.py -q -k "retype_referenced_category or delete_referenced_category"` | `2 passed` | ✓ PASS |
| Live repro: retype a referenced category via PUT | `TestClient` live call (this pass) | `400 "Cannot change type: this category is referenced by questions"`, row unchanged | ✓ PASS — CR-01(original)/truth #16 gap closed |
| Live repro: delete a category with a dependent question via DELETE | `TestClient` live call (this pass) | `409 "Category has questions; delete or reassign them first"`, no rows deleted | ✓ PASS — WR-01(original)/truth #17 gap closed |
| Live repro: seed_qa.py with valid vault then bad `VAULT_PATH` re-run | Direct `seed()` invocation (this pass) | 5 real rows → 0 rows, script prints "Seeded 0 categories, 0 questions" (false success) | ✗ FAIL — confirms 13-REVIEW.md CR-01 (new), truth #25 |
| Live repro: bot's exact `/content?type=category` call (no page_id/key) | `TestClient` live call, byte-identical to `messenger-bot/src/index.ts:264` | `422 {'detail':[{'loc':['query','page_id'],'msg':'Field required'}]}` | ✗ FAIL against literal SC5 wording, but treated as **deferred** to Phase 14 (see Deferred Items + judgment call above) — confirms 13-REVIEW.md CR-02 |
| Live repro: category→category reference via ordinary write API (WR-03) | `POST /pages/{id}/qa` with `type=category, category_id=<other category>` | `201`, accepted — reachable through the real API, not raw SQL | ⚠️ Confirmed as a real Warning-severity defect (WR-03); not elevated to a blocking gap in this phase — see Anti-Patterns |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CONTENT-01 | 13-02 | Client can edit welcome/greeting text | ✓ SATISFIED | `PUT /pages/{page_id}/config` `welcome_text` field, tested |
| CONTENT-02 | 13-02 | Client can edit persistent menu labels/structure | ✓ SATISFIED | `PUT /pages/{page_id}/config` `menu_json` field, tested |
| CONTENT-03 | 13-01, 13-03, 13-05 | Client can create, edit, delete Q&A categories and answers | ✓ SATISFIED (upgraded from ⚠️ PARTIAL) | Create/list/read solid; edit (PUT) and delete (DELETE) now correctly reject the referenced-category case (400/409) instead of corrupting data or crashing — truths #16/#17 closed by 13-05 |
| CONTENT-04 | 13-02 | Client can edit escalation settings | ✓ SATISFIED | `PUT /pages/{page_id}/config` `escalation_psid`/`escalation_message` fields, tested |
| DB-02 | 13-04 | Vault Q&A migrated via one-time seed script | ⚠️ PARTIALLY SATISFIED (downgraded from ✓ SATISFIED) | Happy-path migration is solid and tested (truths #20-24), but the script is not fail-safe: an unset/wrong `VAULT_PATH` on the actual one-time run silently destroys any existing Q&A content while reporting success (truth #25, independently reproduced) |

**Note:** `.planning/REQUIREMENTS.md` still shows CONTENT-01/02/04 and DB-02 as `[ ]` unchecked / "Pending" in its traceability table (only CONTENT-03 is checked). This matches the same pre-existing documentation-sync pattern already flagged as informational (not a phase-specific gap) in the prior verification round (also seen for Phase 12's PAGE-01–04).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `scripts/seed_qa.py` | 65-81, 120-121 | No check that `load_vault_items()` returned non-empty content before the unconditional `DELETE` + `commit()` | 🛑 Blocker | Silent, irreversible data loss on the actual one-time migration run if `VAULT_PATH` is unset/wrong — independently reproduced (13-REVIEW.md CR-01) |
| `messenger-bot/src/index.ts:264,292,327` vs `app/routers/content.py:53,58,100,103` | — | Bot's only `/content` consumer sends neither the now-required `page_id` nor `X-Internal-Key` | ⚠️ Warning (deferred to Phase 14 by explicit 13-CONTEXT.md design, not a Phase 13 code defect) | Bot Q&A browsing is currently 100% broken against `main`'s API as shipped — independently reproduced (13-REVIEW.md CR-02). Urgent operational risk if deployed standalone; not a Phase 13 blocker per the pre-planned two-phase rollout |
| `app/routers/pages.py` (`_validate_category_ref`) | ~384-395 | Does not reject `category_id` on a `type="category"` row — category→category references are creatable via the ordinary write API and can form undeletable cycles with a misleading 409 message | ⚠️ Warning | Independently reproduced via the real API (not raw SQL) in this pass; matches 13-REVIEW.md WR-03. Not elevated to a blocking gap — narrow blast radius (requires deliberately setting `category_id` on a category, which the not-yet-built Phase 15 admin UI presumably won't expose), and it's Warning-severity in the source review |
| `app/routers/content.py:30-37`, `pages.py` (2 more sites) | — | HMAC guard block duplicated 3x (13-REVIEW.md WR-08) | ℹ️ Info | Divergence risk if the guard logic changes; not phase-blocking |
| `app/main.py:15-20` | — | Wildcard CORS now covers authenticated multi-tenant admin endpoints (13-REVIEW.md WR-10) | ℹ️ Info | Pre-existing pattern from before this phase's scope expansion; not phase-blocking |
| `app/routers/pages.py`, `content.py` | multiple | 9 additional Warning/Info findings in 13-REVIEW.md (WR-02, WR-04–WR-07, WR-09, WR-11, WR-12, IN-01–IN-08) | ℹ️ Info | Reviewed; none independently found to falsify a roadmap success criterion or PLAN must-have for this phase. Listed in full in `13-REVIEW.md` for follow-up triage, not duplicated here |

No `TBD`/`FIXME`/`XXX` debt markers found in any file modified by this phase (`grep -n "TBD\|FIXME\|XXX"` across `app/routers/pages.py`, `app/routers/content.py`, `scripts/seed_qa.py`, `tests/test_pages.py` returns nothing).

### Human Verification Required

None. All checkable behaviors were verified programmatically in this pass — direct code reads, live `TestClient`/script reproductions, and the full automated test suites (72 Python + 50 messenger-bot tests). The remaining Roadmap success-criteria halves that reference live Messenger/bot behavior are legitimately deferred to Phase 14 per `13-CONTEXT.md`'s explicit, pre-planned scope boundary — not items this phase can be human-tested against, and not newly discovered gaps in this pass.

### Gaps Summary

**Truths #16 and #17 (the reason for this re-verification) are genuinely closed.** I read `app/routers/pages.py` directly rather than trusting `13-05-SUMMARY.md`'s narrative: the `_has_dependent_qa_items(conn, page_id, item_id)` helper is real, page-scoped, evaluated fresh on every request (no caching/stickiness), and sits in both `update_qa` (400 guard, before the `UPDATE`) and `delete_qa` (409 guard, before the `DELETE`). The two new regression tests (`test_qa_put_retype_referenced_category_400`, `test_qa_delete_referenced_category_409`) cover the reject case, the non-over-trigger case, and the guard-releases-after-dependency-removed case. The full suite (72 tests) and the isolated `tests/test_pages.py` (33 tests) both pass. CONTENT-03 is now fully satisfied.

**One new blocker was found by independently assessing 13-REVIEW.md's fresh Critical findings, per this verification's explicit instructions**, rather than accepting the review at face value:

1. **CR-01 (seed_qa.py data loss) — independently reproduced, classified as a genuine Phase 13 gap (truth #25).** `scripts/seed_qa.py`'s `seed()` function has no guard against `load_vault_items()` returning empty (which happens whenever `settings.vault_path` — default `""` — is unset or points at a missing directory). It proceeds to unconditionally `DELETE FROM qa_items WHERE page_id = ?`, commits, and prints a false success message. I reproduced this myself: seeded a page with 5 real rows from a valid vault, then re-ran the script with a bad `VAULT_PATH` and watched all 5 rows disappear with "Seeded 0 categories, 0 questions" printed as if nothing were wrong. This is squarely within Phase 13's own scope (`scripts/seed_qa.py` is the DB-02 deliverable), is not covered by any `13-CONTEXT.md` deferral, and is exactly the kind of failure mode a "one-time migration script" is most likely to hit on its actual first real-world run. **This should be closed with a small gap-closure plan (fail-closed guard + regression test, per the fix already specified in 13-REVIEW.md CR-01) before Phase 13 is considered fully done**, following the same pattern as 13-05.

2. **CR-02 (bot/API contract mismatch) — independently reproduced, judged as a legitimate Phase 14 deferral, not a Phase 13 blocker.** I confirmed by direct `TestClient` reproduction that the bot's exact current `/content` calls (no `page_id`, no `X-Internal-Key`) return 422 against the shipped API, and by `grep` that `messenger-bot/src/index.ts` has no knowledge of either. This is real and matches CR-02's reproduction exactly. However, `13-CONTEXT.md`'s D-01 decision explicitly, deliberately designed this exact two-phase contract-first rollout *before implementation began* ("Add required `page_id` query param on all read endpoints (Phase 14 will pass the Page's FB id)"), and the Phase Boundary section explicitly scopes bot-side consumption out of Phase 13. This is the same class of finding the prior (already-accepted) `13-VERIFICATION.md` deferred for the same reason. I am carrying that judgment forward rather than re-litigating it, but flagging it with elevated urgency: **`main` currently ships a non-functional bot Q&A feature if the Phase 13 API changes are deployed without also deploying Phase 14's bot rewiring.** This is a real operational/deployment-sequencing risk that should be surfaced to whoever manages deploys, even though it does not block Phase 13's own code-level goal achievement.

A Warning-severity finding (WR-03, category→category cycles reachable via the ordinary write API) was also independently reproduced but not elevated to a blocking gap — narrow blast radius, Warning-severity in the source review, and no admin UI yet exists (Phase 15) that would expose this input shape to real users.

---

_Verified: 2026-08-10T11:00:00Z_
_Verifier: Claude (gsd-verifier)_
