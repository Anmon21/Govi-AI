# Roadmap: Govi Facebook Messenger Customer Support Bot

## Milestones

- ✅ **v1.0 Govi Messenger Bot MVP** — Phases 1–5 (shipped 2026-05-15)
- 🔄 **v1.1 UX Polish & Hardening** — Phases 6–9 (in progress)

## Phases

<details>
<summary>✅ v1.0 Govi Messenger Bot MVP (Phases 1–5) — SHIPPED 2026-05-15</summary>

- [x] Phase 1: Security + Bot Foundation (3/3 plans) — completed 2026-05-14
- [x] Phase 2: Vault Service (2/2 plans) — completed 2026-05-14
- [x] Phase 3: Product Q&A Flow (2/2 plans) — completed 2026-05-15
- [x] Phase 4: Human Escalation (2/2 plans) — completed 2026-05-15
- [x] Phase 5: Polish + Hardening (2/2 plans) — completed 2026-05-15

Full archive: `.planning/milestones/v1.0-ROADMAP.md`

</details>

### v1.1 UX Polish & Hardening

- [ ] **Phase 6: Bug Fixes & Hardening** - Eliminate four v1.0 tech debt issues so the bot handles persistent menu taps, survives async failures, and logs safely
- [ ] **Phase 7: Helpfulness Feedback** - Surface "Was this helpful?" after every answer so users can confirm satisfaction or escalate without hunting for a menu option
- [ ] **Phase 8: Answer Truncation** - Truncate long answers at ~200 chars and let users tap "Read more" for the full text, keeping chat readable on mobile
- [ ] **Phase 9: User Memory & Personalization** - Greet returning users by name using an in-memory PSID map populated on first interaction via Graph API

---

## Phase Details

### Phase 6: Bug Fixes & Hardening
**Goal**: The bot handles persistent menu taps correctly, never crashes from an unhandled async rejection, fails loudly at startup if VERIFY_TOKEN is missing, and never leaks tokens in error logs
**Depends on**: Nothing (first v1.1 phase)
**Requirements**: DEBT-01, DEBT-02, DEBT-03, DEBT-04
**Success Criteria** (what must be TRUE):
  1. Tapping "Product Help" or "Main Menu" in the Messenger persistent menu navigates the user to the expected menu — no dead-end or silent failure
  2. An exception thrown inside the webhook async processing loop is caught, logged, and does not crash the bot process
  3. Starting the bot without VERIFY_TOKEN set exits immediately with a readable error message before accepting any connections
  4. An unexpected (non-Axios) error produces a log entry containing no raw error object and therefore cannot expose auth tokens
**Plans**: 1 plan
Plans:
- [x] 06-01-PLAN.md — Apply four surgical patches to messenger-bot/src/index.ts (DEBT-01 postback routing, DEBT-02 per-event try/catch, DEBT-03 VERIFY_TOKEN startup guard, DEBT-04 non-Axios log sanitization) plus a `debt-fixes.test.ts` covering DEBT-01/02/04

### Phase 7: Helpfulness Feedback
**Goal**: Users can tell the bot whether an answer helped, receive a positive acknowledgment when satisfied, or be routed to a human agent when not
**Depends on**: Phase 6
**Requirements**: UX-01, UX-02, UX-03
**Success Criteria** (what must be TRUE):
  1. After every Q&A answer message, the user sees "Was this helpful?" with Yes and No quick reply buttons
  2. Tapping "Yes" shows a short thank-you message followed by the main menu
  3. Tapping "No" immediately enters the escalation flow — same path as the explicit escalation option
**Plans**: 1 plan
Plans:
- [x] 07-01-PLAN.md — Add FEEDBACK_QUICK_REPLIES constant, swap sendAnswer quick replies, add HELPFUL_YES/HELPFUL_NO handler cases, write feedback.test.ts (UX-01, UX-02, UX-03)

### Phase 8: Answer Truncation
**Goal**: Long answers are broken into a readable preview so the chat thread is not overwhelmed, and users can retrieve the full text on demand
**Depends on**: Phase 6
**Requirements**: UX-04, UX-05
**Success Criteria** (what must be TRUE):
  1. An answer longer than ~200 characters is sent as a truncated message ending with "..." and a "Read more" quick reply button
  2. Tapping "Read more" sends the complete, untruncated answer text as a follow-up message
  3. Answers at or under ~200 characters are delivered as-is with no truncation or "Read more" button
**Plans**: TBD
**UI hint**: yes

### Phase 9: User Memory & Personalization
**Goal**: Returning users are greeted by name, making the bot feel aware of who they are without requiring any persistent storage
**Depends on**: Phase 6
**Requirements**: UX-06, UX-07
**Success Criteria** (what must be TRUE):
  1. On a user's first interaction, the bot fetches their first name from the Graph API and stores it in an in-memory Map keyed by PSID
  2. On a subsequent Get Started or welcome trigger from the same PSID, the greeting message includes the user's first name
  3. If the Graph API call fails or returns no name, the bot falls back to a generic greeting without surfacing an error to the user
**Plans**: TBD
**UI hint**: yes

---

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Security + Bot Foundation | v1.0 | 3/3 | Complete | 2026-05-14 |
| 2. Vault Service | v1.0 | 2/2 | Complete | 2026-05-14 |
| 3. Product Q&A Flow | v1.0 | 2/2 | Complete | 2026-05-15 |
| 4. Human Escalation | v1.0 | 2/2 | Complete | 2026-05-15 |
| 5. Polish + Hardening | v1.0 | 2/2 | Complete | 2026-05-15 |
| 6. Bug Fixes & Hardening | v1.1 | 0/1 | Planned | - |
| 7. Helpfulness Feedback | v1.1 | 0/1 | Planned | - |
| 8. Answer Truncation | v1.1 | 0/? | Not started | - |
| 9. User Memory & Personalization | v1.1 | 0/? | Not started | - |

---

*Last updated: 2026-05-18 — Phase 7 planned (1 plan)*
