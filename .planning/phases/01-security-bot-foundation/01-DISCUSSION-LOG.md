# Phase 1: Security + Bot Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-14
**Phase:** 1-Security + Bot Foundation
**Areas discussed:** Fallback message, App Secret readiness

---

## Fallback Message

| Option | Description | Selected |
|--------|-------------|----------|
| Friendly + helpful | e.g. "I work best with the buttons below — here's what I can help with:" | ✓ |
| Direct + minimal | e.g. "Please use the menu to navigate." | |
| You decide | Claude picks the best tone for a retail support bot | |

**User's choice:** Friendly + helpful tone

---

| Option | Description | Selected |
|--------|-------------|----------|
| Main menu buttons | Show the same top-level options as the persistent menu — consistent navigation | ✓ |
| Just a single "Main Menu" button | One button that resets to the top level | |
| You decide | Claude picks the best recovery UX | |

**User's choice:** Main menu buttons — quick replies mirror the persistent menu top level

---

## App Secret Readiness

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — I have it | Can add to messenger-bot/.env as FACEBOOK_APP_SECRET | |
| Not yet — I need to find it | Haven't set up a Facebook App yet or don't know where to find it | ✓ |
| Already in .env | Already configured | |

**User's choice:** Does not have App Secret yet

---

| Option | Description | Selected |
|--------|-------------|----------|
| Write code now, skip if absent | Verify signature when set; skip with warning when absent — lets development proceed | ✓ |
| Block on missing secret | Bot refuses to start if not set — strict but stops testing without Facebook setup | |

**User's choice:** Write HMAC code now, gracefully skip when FACEBOOK_APP_SECRET is absent

---

## Claude's Discretion

- Welcome message text — Claude to use sensible defaults for an e-commerce support bot
- Persistent menu item labels — Claude to choose based on the 2 main capabilities (Product Help, Contact Human) + optional third item, all ≤20 chars
- node_modules git cleanup — Claude to handle as background Phase 1 task

## Deferred Ideas

None.
