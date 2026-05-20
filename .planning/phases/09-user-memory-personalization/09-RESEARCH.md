# Phase 9: User Memory & Personalization - Research

**Researched:** 2026-05-20
**Domain:** Facebook Graph API user profile fetch, in-memory Map state, TypeScript Node.js bot
**Confidence:** HIGH (architecture and implementation pattern fully determined by UI-SPEC and codebase; Graph API contract verified via official docs)

---

## Summary

Phase 9 adds personalized greetings to the Govi Messenger bot. When a PSID is first seen, the bot fetches the user's `first_name` from the Facebook Graph API and stores it in a module-level `Map<string, string>`. On subsequent `GET_STARTED` postbacks or `MENU_MAIN` quick replies, `sendWelcomeMessage` checks the Map and uses the name if present and non-empty. If the Graph API call fails or returns no name, an empty string sentinel `""` is stored so no retry occurs, and the generic greeting is shown. The user never sees any error indication.

The implementation is a targeted four-touch change to `messenger-bot/src/index.ts`: (1) declare `userNameCache` Map, (2) add `fetchUserName` helper, (3) add a name-fetch call at the top of `handleWebhookEvent` for unknown PSIDs, and (4) modify `sendWelcomeMessage` to branch on the cached name. No new dependencies, no new environment variables, no new postback payloads.

The only open risk is whether the deployed Facebook app has the **Business Asset User Profile Access** feature approved. Without it the Graph API returns an empty object rather than an error — the bot's fallback logic handles this gracefully, but the personalization feature will silently not work. The UI-SPEC anticipates this by treating an empty response identically to a network failure.

**Primary recommendation:** Implement as a single plan touching only `index.ts` and adding `memory.test.ts`. The UI-SPEC copy and Graph API contract are fully locked — no design decisions remain open.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UX-06 | Bot fetches user's first name via Graph API on first interaction and stores it per PSID in an in-memory Map | Graph API endpoint verified: `GET /{GRAPH_API_VERSION}/{psid}?fields=first_name&access_token={PAGE_ACCESS_TOKEN}`. `userNameCache` Map pattern confirmed by UI-SPEC State Contract. |
| UX-07 | Returning user is greeted by name in the welcome / Get Started message | `sendWelcomeMessage` branch logic and exact copy strings specified verbatim in UI-SPEC Conversational Copy Contract. |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| PSID-keyed user name storage | Messenger Bot (Node.js) | — | State lives in the bot process; Facebook sends PSIDs only to the bot tier |
| Graph API user profile fetch | Messenger Bot (Node.js) | — | Bot already holds `PAGE_ACCESS_TOKEN` and `GRAPH_API_VERSION`; no reason to proxy via FastAPI backend |
| Personalized greeting copy | Messenger Bot (Node.js) | — | `sendWelcomeMessage` is already in `index.ts`; greeting is bot output, not API response |
| Fallback to generic greeting | Messenger Bot (Node.js) | — | Handled entirely within `sendWelcomeMessage` after Map lookup |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| axios | 1.16.1 (installed) | HTTP GET to Graph API for user profile | Already in `dependencies`; used for all existing Graph API calls |
| Node.js built-in `Map` | N/A (language built-in) | In-memory PSID→name store | Zero-dependency, fits the "no persistent storage" constraint from REQUIREMENTS.md |

[VERIFIED: npm view axios version — 1.16.1]
[VERIFIED: messenger-bot/src/index.ts — axios already imported and used for all Graph API calls]

### No New Dependencies

This phase adds zero npm packages. [VERIFIED: 09-UI-SPEC.md "Registry Safety" section confirms "This phase adds no npm packages."]

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Module-level `Map` | Redis, SQLite | Deferred to PERS-01 (v2+). In-memory sufficient for v1.1 per locked decision in STATE.md |
| Fetching on first event | Fetching every GET_STARTED | Sentinel pattern avoids redundant API calls; fetch-once-per-PSID is simpler |

---

## Architecture Patterns

### System Architecture Diagram

```
Inbound webhook event (PSID: X)
         |
         v
handleWebhookEvent(event)
         |
         +--[PSID in userNameCache?]--YES--> skip fetch, route to handler
         |
        NO
         |
         v
fetchUserName(psid)
  GET graph.facebook.com/{GRAPH_API_VERSION}/{psid}?fields=first_name
         |
    +----+----+
    |         |
  success   failure (network / 4xx / no field / phone account)
    |         |
  store      store "" sentinel
  first_name |
    |         |
    +---------+
         |
         v
route event to handler (sendWelcomeMessage / other)
         |
    [sendWelcomeMessage called]
         |
    userNameCache.get(psid) -> non-empty string?
         |
    +----+----+
    |         |
   YES        NO
    |         |
"Welcome    "Welcome to Govi!..."
 back, X!..."
    |         |
    +---------+
         |
      sendMessage with MAIN_MENU_QUICK_REPLIES
```

### Recommended Project Structure

No structural changes. All changes land in the single existing entry point:

```
messenger-bot/src/
├── index.ts          # +userNameCache Map, +fetchUserName(), modified handleWebhookEvent, modified sendWelcomeMessage
└── tests/
    └── memory.test.ts  # NEW — covers UX-06, UX-07
```

### Pattern 1: Module-Level Map as In-Memory Cache

**What:** Declare `export const userNameCache = new Map<string, string>()` at module scope, parallel to the existing `lastMessageCache` pattern.

**When to use:** Any per-PSID state that must survive across multiple events in a single process lifetime but need not persist across restarts.

**Example:**
```typescript
// Source: existing pattern in messenger-bot/src/index.ts (lastMessageCache)
export const lastMessageCache = new Map<string, string>();

// New — same pattern for user names
export const userNameCache = new Map<string, string>();
```

[VERIFIED: index.ts line 119 — `lastMessageCache` is already a module-level exported Map using this exact pattern]

### Pattern 2: fetchUserName Helper with Sentinel

**What:** Async helper that calls the Graph API and writes either the name or `""` to the Map. Never throws — swallows failures silently.

**When to use:** Any external API call whose failure must be invisible to the end user.

**Example:**
```typescript
// Source: UI-SPEC Graph API Contract + SEC-03 error logging convention from index.ts
export async function fetchUserName(psid: string): Promise<void> {
  try {
    const response = await axios.get(
      `https://graph.facebook.com/${GRAPH_API_VERSION}/${psid}`,
      { params: { fields: "first_name", access_token: PAGE_ACCESS_TOKEN } }
    );
    const firstName: string = response.data?.first_name ?? "";
    userNameCache.set(psid, firstName);
  } catch (err: unknown) {
    // SEC-03: never log full axios error (config.url contains PAGE_ACCESS_TOKEN)
    if (axios.isAxiosError(err)) {
      console.error("fetchUserName failed:", err.message, err.response?.data);
    } else {
      console.error("fetchUserName failed (unexpected):", err instanceof Error ? err.message : String(err));
    }
    userNameCache.set(psid, "");
  }
}
```

[CITED: developers.facebook.com/docs/messenger-platform/identity/user-profile — endpoint URL and response shape]
[VERIFIED: index.ts SEC-03 error logging pattern applied consistently across sendMessage, passThreadControl, sendTypingIndicator]

### Pattern 3: Fetch-Once Guard in handleWebhookEvent

**What:** At the top of `handleWebhookEvent`, before any routing, check if the PSID is in `userNameCache`. If not, call `fetchUserName` and await it. This ensures the name is populated before `sendWelcomeMessage` runs.

**When to use:** Any per-PSID initialization that must complete before the event is handled.

**Example:**
```typescript
export async function handleWebhookEvent(event: any): Promise<void> {
  const senderId: string = event.sender?.id;
  if (!senderId) return;

  // UX-06: fetch name on first interaction, store sentinel on failure
  if (!userNameCache.has(senderId)) {
    await fetchUserName(senderId);
  }

  // ... existing routing logic unchanged ...
}
```

[CITED: 09-UI-SPEC.md — "Name Fetch Timing" section specifies this exact ordering]

### Pattern 4: Modified sendWelcomeMessage

**What:** `sendWelcomeMessage` reads `userNameCache` and branches on whether the name is a non-empty string.

**Exact copy strings (from UI-SPEC — executor MUST use these verbatim):**

- Returning user: `"Welcome back, {firstName}! How can I help you today?"`
- Generic (first-time or fallback): `"Welcome to Govi! I can help with product questions or connect you with a human."`

**Example:**
```typescript
export async function sendWelcomeMessage(recipientId: string): Promise<void> {
  const firstName = userNameCache.get(recipientId);
  const text = firstName
    ? `Welcome back, ${firstName}! How can I help you today?`
    : "Welcome to Govi! I can help with product questions or connect you with a human.";
  await sendMessage(recipientId, text, MAIN_MENU_QUICK_REPLIES);
}
```

[CITED: 09-UI-SPEC.md — Conversational Copy Contract, "Returning user welcome" and "First-time welcome" sections]

### Anti-Patterns to Avoid

- **Retry on every event:** Using `if (!firstName)` rather than `if (!userNameCache.has(psid))` would retry the Graph API on every message from a user whose name lookup failed. The sentinel `""` (stored by `fetchUserName` on failure) means `userNameCache.has(psid)` returns `true` and the fetch is correctly skipped. `!firstName` would also trigger retry for users whose name IS empty string, which is the same as the failure state. **Use `userNameCache.has(psid)` as the guard, not truthiness of the value.**

- **Throwing from fetchUserName:** If `fetchUserName` throws, `handleWebhookEvent` will catch it in the outer try/catch (added in Phase 6 DEBT-02), log it, and silently drop the event. The sentinel must be written in the catch block inside `fetchUserName` to ensure the Map is always populated after the function completes.

- **Logging the PAGE_ACCESS_TOKEN:** The Graph API URL includes `access_token=PAGE_ACCESS_TOKEN` as a query param. Following SEC-03, never log the full axios error object — log only `err.message` and `err.response?.data`. [VERIFIED: all existing catch blocks in index.ts follow this pattern]

- **Modifying setupMessengerProfile:** The static greeting in `setupMessengerProfile` (the Messenger Profile greeting shown before a conversation starts) is set once at startup and cannot be personalized per-user. Per UI-SPEC: "Static greeting text in setupMessengerProfile" must remain byte-for-byte identical after this phase.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PSID-keyed name storage | Custom class, LRU cache, or file-backed store | `Map<string, string>` (built-in) | Requirements explicitly scope to in-memory; Map is the standard tool |
| Graph API HTTP call | Custom fetch wrapper | `axios.get(...)` (already imported) | axios is already the project's HTTP client; consistent error handling pattern |

**Key insight:** Both the storage mechanism and the HTTP client are already in the codebase. This phase wires them together; it does not introduce new infrastructure.

---

## Common Pitfalls

### Pitfall 1: Empty-object response treated as success with name

**What goes wrong:** `response.data?.first_name` evaluates to `undefined` when the app lacks Business Asset User Profile Access (Graph API returns `{}`). If `userNameCache.set(psid, undefined as any)` is called, a later truthiness check could behave unexpectedly.

**Why it happens:** The `??` nullish coalescing operator (`response.data?.first_name ?? ""`) correctly collapses `undefined` to `""`. Using optional chaining without the fallback risks storing `undefined`.

**How to avoid:** Always use `const firstName: string = response.data?.first_name ?? "";` — the explicit `string` type annotation plus `??` guarantees a string is stored.

**Warning signs:** TypeScript strict mode will flag `string | undefined` assignment to `Map<string, string>` at compile time if the type annotation is present.

### Pitfall 2: Race condition on concurrent first events

**What goes wrong:** Two events from the same new PSID arrive nearly simultaneously. Both pass the `!userNameCache.has(psid)` check before either `fetchUserName` writes to the Map, causing two redundant Graph API calls.

**Why it happens:** Node.js is single-threaded but `await fetchUserName(senderId)` yields to the event loop. If two events are processed in the same tick (unlikely for webhook delivery but theoretically possible with the current `for...of` loop), the second event could start before the first `fetchUserName` resolves.

**How to avoid:** This is acceptable for v1.1. The worst case is two Graph API calls for the same PSID, both writing the same name. The idempotent `Map.set` makes this safe. Do not over-engineer a promise deduplication mechanism.

**Warning signs:** None visible in production; this is a theoretical edge case.

### Pitfall 3: sendWelcomeMessage called before userNameCache is populated

**What goes wrong:** If `fetchUserName` is not awaited before routing, `sendWelcomeMessage` runs while the Map still lacks the PSID entry, always showing the generic greeting even when a name is available.

**Why it happens:** Forgetting `await` on `fetchUserName(senderId)` makes it fire-and-forget.

**How to avoid:** The guard in `handleWebhookEvent` must be `await fetchUserName(senderId)`. The `sendWelcomeMessage` call is downstream in the same `handleWebhookEvent` execution, so awaiting the fetch guarantees ordering.

### Pitfall 4: Phone-number Messenger accounts returning error code 2018218

**What goes wrong:** For users who created their Messenger account with a phone number (not Facebook), the Graph API returns an error rather than an empty object. If `fetchUserName`'s catch block doesn't handle this, it still writes `""` sentinel — which is correct behavior.

**Why it happens:** Meta explicitly documents this case: "The User Profile API does not support retrieving profile information for Messenger accounts that were created using a phone number."

**How to avoid:** The sentinel-on-error pattern in `fetchUserName` already handles this correctly. No special-casing needed.

[CITED: developers.facebook.com/docs/messenger-platform/identity/user-profile — phone-number account restriction]

### Pitfall 5: Existing handlers.test.ts tests for sendWelcomeMessage will require stub for GET

**What goes wrong:** After this phase, `handleWebhookEvent` calls `fetchUserName` (a GET to Graph API) before routing. Any existing test that fires `handleWebhookEvent` without stubbing `axios.get` will make a real HTTP call to Facebook (which fails in unit test context).

**Why it happens:** `fetchUserName` is called unconditionally for unknown PSIDs.

**How to avoid:** All existing tests use a fresh `require("../index")` module — each test file imports the module once. The `withAxiosStubs` helper in existing tests stubs `axios.get`. New `memory.test.ts` tests must stub `axios.get` to return `{ data: { first_name: "Alice" } }` or `{ data: {} }`. Existing tests that use different PSIDs across tests need their `axios.get` stub to handle the Graph API URL (anything matching `graph.facebook.com/{GRAPH_API_VERSION}/{psid}`) in addition to Govi AI vault URLs.

**Warning signs:** Test failures in `handlers.test.ts`, `feedback.test.ts`, or `truncation.test.ts` with network errors or timeout after this phase lands.

---

## Runtime State Inventory

> Not a rename/migration phase. Omit this section.

Step 2.5: SKIPPED — this is a feature addition phase, not a rename/refactor/migration.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Test runner, bot runtime | Yes | v26.0.0 | — |
| axios | Graph API GET call | Yes (installed) | 1.16.1 | — |
| Facebook Graph API | UX-06 name fetch | External — not verifiable locally | v21.0 (GRAPH_API_VERSION in index.ts) | Empty-object response → generic greeting |
| Business Asset User Profile Access | UX-06 returning non-empty name | Unknown — requires app review | — | Returns `{}` → fallback to generic greeting (handled) |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:**
- Business Asset User Profile Access: If the app lacks this feature, Graph API returns `{}`. `fetchUserName` stores `""` sentinel. `sendWelcomeMessage` shows the generic greeting. The feature degrades silently — personalization does not work but the bot does not break. This is by design per UI-SPEC.

[CITED: developers.facebook.com/docs/messenger-platform/identity/user-profile — "an empty object is returned" when app lacks access]
[CITED: developers.facebook.com/docs/features-reference/business-asset-user-profile-access — feature requires App Review]

---

## Graph API Contract (Verified)

| Property | Value |
|----------|-------|
| Endpoint | `GET https://graph.facebook.com/{GRAPH_API_VERSION}/{psid}` |
| Query params | `fields=first_name&access_token={PAGE_ACCESS_TOKEN}` |
| `GRAPH_API_VERSION` constant | `"v21.0"` (already in index.ts line 117) |
| Success response shape | `{ "first_name": "Alice" }` |
| No-access response shape | `{}` (empty object, not an error) |
| Phone-number account response | Error code `2018218` — caught by catch block |
| Token exposure risk | `config.url` in axios error contains `access_token` — must follow SEC-03 |

[CITED: developers.facebook.com/docs/messenger-platform/identity/user-profile]
[VERIFIED: index.ts line 117 — `export const GRAPH_API_VERSION = "v21.0"`]
[VERIFIED: index.ts line 13 — `const PAGE_ACCESS_TOKEN = process.env.FACEBOOK_PAGE_ACCESS_TOKEN!`]

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Node.js built-in test runner (`node:test`) |
| Config file | none — tests run via `npm test` script |
| Quick run command | `npm test` (runs all `src/tests/*.test.ts` via ts-node) |
| Full suite command | `npm test` |

[VERIFIED: messenger-bot/package.json — `"test": "node --test-force-exit --test --require ts-node/register src/tests/*.test.ts"`]

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UX-06 | First event from new PSID triggers `fetchUserName` Graph API GET | unit | `npm test` | No — Wave 0: `memory.test.ts` |
| UX-06 | Graph API success stores `first_name` in `userNameCache` | unit | `npm test` | No — Wave 0: `memory.test.ts` |
| UX-06 | Graph API returns empty object — stores `""` sentinel | unit | `npm test` | No — Wave 0: `memory.test.ts` |
| UX-06 | Graph API throws (network error) — stores `""` sentinel | unit | `npm test` | No — Wave 0: `memory.test.ts` |
| UX-06 | Second event from same PSID skips Graph API call entirely | unit | `npm test` | No — Wave 0: `memory.test.ts` |
| UX-07 | `sendWelcomeMessage` with non-empty name sends personalized greeting | unit | `npm test` | No — Wave 0: `memory.test.ts` |
| UX-07 | `sendWelcomeMessage` with `""` sentinel sends generic greeting | unit | `npm test` | No — Wave 0: `memory.test.ts` |
| UX-07 | `sendWelcomeMessage` for PSID not in Map sends generic greeting | unit | `npm test` | No — Wave 0: `memory.test.ts` |
| Regression | Existing tests (handlers, feedback, truncation) pass without network calls | regression | `npm test` | Yes — existing suite |

### Sampling Rate

- **Per task commit:** `npm test`
- **Per wave merge:** `npm test`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `messenger-bot/src/tests/memory.test.ts` — covers UX-06 and UX-07 (8 test cases above)
- [ ] Existing test files may need `axios.get` stubs extended to handle Graph API URLs — verify after `fetchUserName` is added

---

## Code Examples

### fetchUserName — complete implementation pattern

```typescript
// Source: 09-UI-SPEC.md Graph API Contract + SEC-03 pattern from index.ts
export async function fetchUserName(psid: string): Promise<void> {
  try {
    const response = await axios.get(
      `https://graph.facebook.com/${GRAPH_API_VERSION}/${psid}`,
      { params: { fields: "first_name", access_token: PAGE_ACCESS_TOKEN } }
    );
    const firstName: string = response.data?.first_name ?? "";
    userNameCache.set(psid, firstName);
  } catch (err: unknown) {
    if (axios.isAxiosError(err)) {
      console.error("fetchUserName failed:", err.message, err.response?.data);
    } else {
      console.error("fetchUserName failed (unexpected):", err instanceof Error ? err.message : String(err));
    }
    userNameCache.set(psid, "");
  }
}
```

### handleWebhookEvent guard — insertion point

```typescript
export async function handleWebhookEvent(event: any): Promise<void> {
  const senderId: string = event.sender?.id;
  if (!senderId) return;

  // UX-06: populate userNameCache on first contact; sentinel "" stored on failure
  if (!userNameCache.has(senderId)) {
    await fetchUserName(senderId);
  }

  // existing routing unchanged from here ...
  if (event.postback?.payload === "GET_STARTED") {
    await sendWelcomeMessage(senderId);
    return;
  }
  // ...
}
```

### sendWelcomeMessage — updated

```typescript
// Source: 09-UI-SPEC.md Conversational Copy Contract (exact strings)
export async function sendWelcomeMessage(recipientId: string): Promise<void> {
  const firstName = userNameCache.get(recipientId);
  const text = firstName
    ? `Welcome back, ${firstName}! How can I help you today?`
    : "Welcome to Govi! I can help with product questions or connect you with a human.";
  await sendMessage(recipientId, text, MAIN_MENU_QUICK_REPLIES);
}
```

### memory.test.ts stub pattern

```typescript
// Pattern follows existing withAxiosStubs in feedback.test.ts / truncation.test.ts
function withAxiosStubs(opts: { onGet?: (url: string) => any; onPost?: (url: string, body: any) => any }) {
  const axios = require("axios");
  const originalPost = axios.post;
  const originalGet = axios.get;
  const getCalls: { url: string }[] = [];
  const postCalls: { url: string; body: any }[] = [];
  axios.get = async (url: string) => {
    getCalls.push({ url });
    if (opts.onGet) return opts.onGet(url);
    return { data: {} };
  };
  axios.post = async (url: string, body: any) => {
    postCalls.push({ url, body });
    if (opts.onPost) return opts.onPost(url, body);
    return { data: {} };
  };
  return { getCalls, postCalls, restore() { axios.post = originalPost; axios.get = originalGet; } };
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fetch user profile including locale, timezone, gender | Only `first_name` field available without extended permissions | Post-2020 privacy changes | Scope to `fields=first_name` only — no extra fields without App Review |

**Deprecated/outdated:**
- Profile picture URLs from user profile: expire over time — not used in this phase
- `locale`, `timezone`, `gender` fields: require additional `pages_user_*` permissions beyond Business Asset User Profile Access — not used in this phase

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The deployed Facebook app may or may not have Business Asset User Profile Access approved | Environment Availability | If not approved, `first_name` fetch silently returns `{}` and personalization never activates — bot still functions normally |
| A2 | Existing tests that stub `axios.get` for Govi AI vault URLs will also intercept the new Graph API GET (since they stub the entire `axios.get` function) | Validation Architecture — Regression | If a test does NOT stub `axios.get` and a new PSID is used, a real HTTP call to Facebook is attempted and fails. Likely causes test failure with ECONNREFUSED. Mitigation: verify existing tests all use `withAxiosStubs` before sending any event from a new PSID. |

---

## Open Questions

1. **Does the deployed app have Business Asset User Profile Access?**
   - What we know: The feature requires App Review. Without it, the Graph API returns `{}` (empty object, not error). The bot handles this gracefully.
   - What's unclear: Whether the current Govi Facebook app has completed App Review for this feature.
   - Recommendation: Document in VERIFICATION.md as a human-UAT step. The feature degrades silently — test by checking whether the greeting includes the name after interacting from a known account.

2. **Do existing tests need `axios.get` stub updates?**
   - What we know: After Phase 9 lands, every `handleWebhookEvent` call for an unknown PSID triggers `fetchUserName` which calls `axios.get`. All existing test files use per-test PSIDs like `"USR_1"`, `"USR_X"`.
   - What's unclear: Whether any test reuses a PSID across `test()` blocks within the same file (which would cause the second invocation to skip the fetch). Given module-level Map state persists within a test file's `require` session, the first test to use a PSID populates the cache for subsequent tests in the same run.
   - Recommendation: The planner should include a task to audit existing test files and ensure their `withAxiosStubs` handlers return `{ data: {} }` for Graph API URLs (the `onGet` default already returns `{ data: {} }` in all existing stubs, which correctly produces empty-object behavior for the name fetch). This is likely already handled but should be verified.

---

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | — |
| V3 Session Management | No | — |
| V4 Access Control | No | — |
| V5 Input Validation | Yes | `response.data?.first_name ?? ""` — nullish coalescing defends against undefined/null; TypeScript `string` annotation prevents wrong types entering the Map |
| V6 Cryptography | No | — |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| PAGE_ACCESS_TOKEN exposure in logs | Information Disclosure | SEC-03: log only `err.message` and `err.response?.data`, never the full axios error object. Already established pattern in index.ts. |
| Malformed `first_name` value (XSS) | Tampering | Messenger sends `first_name` as plain text in a JSON string field; it is interpolated into a message string sent back to Messenger (not rendered as HTML). No XSS risk in this context. |

---

## Project Constraints (from CLAUDE.md)

| Directive | Impact on Phase 9 |
|-----------|-------------------|
| Tech stack: Node.js/TypeScript for the Messenger bot | All changes in `messenger-bot/src/index.ts` (TypeScript) |
| No new features beyond what was asked | Only UX-06 and UX-07 implemented; no persistent storage, no analytics |
| Surgical changes — touch only what you must | Only `index.ts` modified: +`userNameCache`, +`fetchUserName`, modified `handleWebhookEvent` guard, modified `sendWelcomeMessage` |
| Match existing style | Use `export const` for Map (matches `lastMessageCache`); use `export async function` (matches all helpers); SEC-03 error logging (matches all catch blocks) |
| No containerization | No Docker/CI changes |
| Facebook Messenger only — no other channels | Only Messenger Platform Graph API used |

---

## Sources

### Primary (HIGH confidence)
- `messenger-bot/src/index.ts` — full source read; all existing patterns verified directly
- `09-UI-SPEC.md` — exact copy strings, state contract, Graph API contract, interaction flow
- `messenger-bot/package.json` — test command, dependency versions
- `.planning/REQUIREMENTS.md` — UX-06, UX-07 requirement text
- `.planning/STATE.md` — locked decision: in-memory Map for v1.1
- `messenger-bot/src/tests/feedback.test.ts`, `truncation.test.ts`, `handlers.test.ts` — test patterns

### Secondary (MEDIUM confidence)
- [Profile Information - Messenger Platform](https://developers.facebook.com/docs/messenger-platform/identity/user-profile) — endpoint URL, query params, response shape, empty-object behavior, phone-account restriction; fetched directly
- [Business Asset User Profile Access](https://developers.facebook.com/docs/features-reference/business-asset-user-profile-access) — App Review requirement confirmed; fetched directly

### Tertiary (LOW confidence)
- None — all claims are verified or cited.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all libraries verified in package.json
- Architecture: HIGH — fully specified by UI-SPEC; matches existing Map/axios patterns in codebase
- Graph API contract: HIGH — verified against official Meta documentation
- Pitfalls: HIGH — derived from reading the actual source code and official API docs
- Business Asset User Profile Access status: LOW — cannot verify from local environment; documented as open question

**Research date:** 2026-05-20
**Valid until:** 2026-06-20 (Graph API endpoint is stable; Meta API versions deprecate on ~2-year cycles)
