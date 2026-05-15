# Milestones

## v1.0 Govi Messenger Bot MVP (Shipped: 2026-05-15)

**Phases completed:** 5 phases, 11 plans, 10 tasks

**Key accomplishments:**

- node:test scaffolds for all 10 SEC/CORE behaviors wired via ts-node/register with PORT=0 isolation; node_modules removed from git tracking
- One-liner:
- Task 1 — Messenger Profile setup (CORE-02):
- 1. [Rule 3 - Blocking] pytest 9.x not installable on Python 3.9
- app/routers/content.py
- One-liner:
- Messenger bot wired to vault content API — full menu → category → question → answer flow with payload-prefix dispatch and error-safe re-anchoring
- 7 skipping escalation test stubs for ESC-01/02/03/04 and ADMIN_PSID soft-fail; ADMIN_PSID documented in .env.example; Plan 02 has a precise executable spec
- One-liner:
- Task 1:
- sendTypingIndicator helper + sendAnswer finally-block wrap turns 2 RED tests GREEN, delivering POLISH-01 typing indicator UX and full .env.example documentation in 2 surgical file changes

---
