# Requirements: Govi Facebook Messenger Customer Support Bot — v1.1

**Defined:** 2026-05-15
**Milestone:** v1.1 UX Polish & Hardening
**Core Value:** Customers can get instant product answers and reach a human through Messenger — 24/7, without developer involvement in content updates

## v1.1 Requirements

### Bug Fixes

- [ ] **DEBT-01**: User persistent menu taps (MENU_PRODUCT_HELP, MENU_MAIN) are handled correctly by the postback dispatcher
- [ ] **DEBT-02**: Unhandled promise rejections from the webhook processing loop are caught and logged without crashing the bot
- [ ] **DEBT-03**: Bot fails at startup with a clear error message if VERIFY_TOKEN is not set in the environment
- [ ] **DEBT-04**: Error logging for non-Axios errors omits raw error objects to prevent accidental token leak

### UX Enhancements

- [ ] **UX-01**: User sees "Was this helpful?" quick reply (Yes / No) after every answer
- [ ] **UX-02**: User tapping "Yes" receives a short acknowledgment message and is shown the main menu
- [ ] **UX-03**: User tapping "No" is routed to the escalation flow
- [ ] **UX-04**: Answers longer than ~200 characters are truncated with "..." and a "Read more" quick reply
- [ ] **UX-05**: User tapping "Read more" receives the full answer text as a follow-up message
- [ ] **UX-06**: Bot fetches user's first name via Graph API on first interaction and stores it per PSID in an in-memory Map
- [ ] **UX-07**: Returning user is greeted by name in the welcome / Get Started message

## Future Requirements

### v2+

- **PERS-01**: Persistent user memory across bot restarts (SQLite or equivalent)
- **UX-08**: "Was this helpful?" analytics — track Yes/No counts per question
- **NOTIF-01**: Proactive outreach — admin can message all opted-in users

## Out of Scope

| Feature | Reason |
|---------|--------|
| Persistent user memory (SQLite) | In-memory sufficient for v1.1; restart clears state, acceptable |
| Order tracking / order status | No store backend connected |
| AI-powered free-text responses | Rule-based menus only |
| Shopify / WooCommerce integration | Standalone system |
| Custom admin web UI | Obsidian vault is the content management interface |
| Multi-language support | English only |
| Answer length truncation linking to external URL | Vault entries don't have url fields; follow-up message is simpler |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DEBT-01 | Phase 6 | Pending |
| DEBT-02 | Phase 6 | Pending |
| DEBT-03 | Phase 6 | Pending |
| DEBT-04 | Phase 6 | Pending |
| UX-01 | Phase 7 | Pending |
| UX-02 | Phase 7 | Pending |
| UX-03 | Phase 7 | Pending |
| UX-04 | Phase 8 | Pending |
| UX-05 | Phase 8 | Pending |
| UX-06 | Phase 9 | Pending |
| UX-07 | Phase 9 | Pending |

**Coverage:**
- v1.1 requirements: 11 total
- Mapped to phases: 11 ✓
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-15*
*Last updated: 2026-05-15 — traceability table populated after roadmap creation*
