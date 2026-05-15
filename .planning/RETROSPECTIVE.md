# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — Govi Messenger Bot MVP

**Shipped:** 2026-05-15
**Phases:** 5 | **Plans:** 11

### What Was Built

1. HMAC-SHA256 webhook verification, Graph API error detection, token-safe logging
2. Obsidian vault service — FastAPI loads/caches/reloads Q&A content from markdown with stable IDs
3. Full product Q&A menu flow — category → question → answer via quick replies
4. Human escalation — Facebook Handover Protocol + admin Messenger notification with graceful fallback
5. Typing indicator before answers + fully documented .env.example

### What Worked

- **TDD RED→GREEN wave split** was highly effective — Wave 0 test scaffolds caught implementation mistakes early (Phase 1 test runner setup, Phase 3 test assertion counts for typing indicator)
- **UI-SPEC for non-visual phases** — generating a UI-SPEC for the typing indicator UX locked the `finally` block ordering before planning, preventing a common mistake (typing_off not sent on error paths)
- **Facebook Graph API scope-matching** — all three new bot handlers (sendCategoryMenu, sendQuestionMenu, sendAnswer) reused the exact same axios.post + SEC-03 error pattern, making code review trivial
- **Vault hot-reload via POST /content/reload** — operator can update Q&A content without server restart, a key operational win

### What Was Inefficient

- **SUMMARY.md missing from 03-02** — plan was executed but the summary commit only updated STATE.md, creating a stale artifact that blocked phase completion tracking. Recovered by writing the SUMMARY.md retroactively from git history.
- **REQUIREMENTS.md checkboxes not auto-updated** — all 18 requirements were implemented but only POLISH-01 was marked [x] in the file, requiring manual fix at milestone close
- **Two gsd-plan-phase invocations for Phase 5** — first invocation hit the UI gate; needed a second run with `--skip-ui` after generating UI-SPEC separately

### Patterns Established

- `sendTypingIndicator(recipientId, action)` — exported helper following SEC-03 pattern; reuse for any new Graph API helper
- Prefix-match payload dispatch (`MENU_*`, `CATEGORY:`, `QUESTION:`) in handleWebhookEvent — extend by adding new exact-match cases before prefix checks
- Wave 0 = RED tests for behavior contract, Wave 1 = GREEN implementation
- `finally` block for cleanup (typing_off, logging) that must fire regardless of success/failure

### Key Lessons

- **Document human-only tests in UAT files immediately** — phases 1, 4, and 5 all have live Messenger tests; tracking them in HUMAN-UAT.md from the start prevents "did we test this?" confusion at milestone close
- **Validate SUMMARY.md commit includes the file** — the safe-resume gate now catches this, but checking `git show <hash> --stat` after each plan is faster
- **POST handler dead-ends need postback dispatch** — persistent menu sends postbacks, not quick replies; CR-01 (postback handler not dispatching MENU_PRODUCT_HELP) should be fixed before launch

### Cost Observations

- Model mix: Opus (planner), Sonnet (researcher, executor, verifier, checker, reviewer)
- Sessions: 2 (initial then continuation)
- Notable: Planner on Opus produced high-quality PLAN.md files with precise acceptance criteria; executor on Sonnet was fast and stayed in scope

## Cross-Milestone Trends

| Metric | v1.0 |
|--------|------|
| Phases | 5 |
| Plans | 11 |
| Days | 2 |
| Test coverage | 22 TS + 14 Py |
| Code review findings | 21 total (advisory) |
