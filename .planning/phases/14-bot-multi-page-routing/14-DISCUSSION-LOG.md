# Phase 14: Bot Multi-Page Routing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-21
**Phase:** 14-bot-multi-page-routing
**Areas discussed:** Token fetch cadence, Per-page cache key scheme, Content endpoint page-scoping, Fallback UX when FastAPI down, Messenger profile installation

---

## Token fetch cadence

| Option | Description | Selected |
|--------|-------------|----------|
| Every webhook event | Simple, always fresh. One extra HTTP hop per event (~5–20ms latency). | ✓ |
| Short TTL cache (~60s) | In-memory Map<pageFbId, {token, expiresAt}>. Amortizes fetches for bursty conversations. Small window where a rotated token is still cached. | |
| Long-lived cache + explicit invalidation | Cache indefinitely. Invalidate on OAuth reconnect (requires FastAPI → bot notification or bot polling). Most complex. | |
| Load-on-first-use, cache forever | First webhook per Page fetches token, reused until process restart. Simplest cache; requires restart to pick up rotated token. | |

**User's choice:** Every webhook event.
**Notes:** Simplicity and correctness-on-token-rotation prioritized over per-event latency.

---

## Per-page cache key scheme

| Option | Description | Selected |
|--------|-------------|----------|
| Composite string key `${pageFbId}:${psid}` | Single Map, keys look like "1234:5678". Simplest change to existing code — just build key at read/write sites. | ✓ |
| Nested Map<pageFbId, Map<psid, X>> | Groups per-page. Easier to enumerate/clear all state for one Page (e.g., on disconnect). Slightly more code to touch. | |
| Store PageId alongside value: Map<psid, {pageFbId, value}> | PSID stays the key, add pageFbId check on read. Risky — same PSID across Pages would overwrite. | |

**User's choice:** Composite string key.
**Notes:** Minimal diff to existing Maps.

---

## Content endpoint page-scoping

| Option | Description | Selected |
|--------|-------------|----------|
| Query parameter — `/content?type=category&page_id=X` | Preserves existing path shape. Reads as "another filter param, like type/category". | ✓ |
| Path segment — `/content/{page_fb_id}?type=category` | Page is part of resource identity. Cleaner REST semantics. Breaking change vs current /content contract. | |
| Header — `X-Page-FB-ID: X` | URLs unchanged. Less discoverable/testable via curl. | |

**User's choice:** Query parameter.
**Notes:** Phase 13 must accept `page_id` as a required query param on all content endpoints.

---

## Fallback UX when FastAPI down

| Option | Description | Selected |
|--------|-------------|----------|
| Generic apology, no menu | "Sorry, we're having trouble right now." No menu buttons (we don't know Page menu). Server-side log. | |
| Generic apology + retry-once-with-backoff | Silent retry (~500ms), then apology on second failure. Better on transient blips. | ✓ |
| Silent drop (log only) | User sees nothing. Confusing. | |
| Last-known-good cached fallback | Serve stale token/content. Incompatible with fetch-every-event decision. | |

**User's choice:** Generic apology + retry-once-with-backoff.
**Notes:** ~500ms backoff; process must not crash; errors logged server-side.

---

## Messenger profile installation

| Option | Description | Selected |
|--------|-------------|----------|
| FastAPI, at OAuth completion | The OAuth callback installs persistent menu/greeting/Get Started per Page. Bot doesn't need it. | ✓ |
| Bot, loop over all active Pages at startup | Bot fetches list of active Pages on boot, installs profile for each. Re-runs on every restart; needs new internal endpoint. | |
| Defer to Phase 13 / new phase | Delete setupMessengerProfile() from bot and capture as follow-up. | |

**User's choice:** FastAPI, at OAuth completion.
**Notes:** Phase 14 removes the bot's `setupMessengerProfile()` call. FastAPI-side installation is captured as a deferred follow-up (belongs in a hot-patch to Phase 12 or its own small phase).

---

## Claude's Discretion

- Exact wording of the fallback apology message.
- Exact retry mechanism (inline await vs helper).
- Whether to thread `pageFbId` alone or a small `pageContext` object through `handleWebhookEvent`.

## Deferred Ideas

- FastAPI-side per-Page Messenger profile installation on OAuth completion.
- Revisit token caching if per-event latency becomes a production concern.
- Revisit cache key scheme if a "disconnect Page → clear all its state" feature is ever needed.
