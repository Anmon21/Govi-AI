# Phase 12: Page Connection API + Facebook OAuth - Research

**Researched:** 2026-05-28
**Domain:** Facebook OAuth 2.0, Graph API token exchange, FastAPI redirect flows, Fernet encryption
**Confidence:** HIGH (core token exchange flow), MEDIUM (App Review timelines and permission availability)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PAGE-01 | Client can connect a Facebook Page via OAuth — full 3-step token exchange with webhook subscription | 3-step exchange flow verified via official docs; webhook subscription via POST /{page-id}/subscribed_apps confirmed |
| PAGE-02 | Client can view connected Pages with status badge (active / token revoked) | GET /pages endpoint with lazy token health check via debug_token confirmed |
| PAGE-03 | Client can disconnect a Page (removes token + webhook subscription) | DELETE /pages/{id} pattern confirmed; webhook unsubscription via DELETE /{page-id}/subscribed_apps |
| PAGE-04 | Client can see token health indicator and trigger reconnect for revoked token | debug_token `is_valid` field confirmed; reconnect re-runs OAuth flow for same page |
</phase_requirements>

---

## Summary

Phase 12 implements the full Facebook Page connection lifecycle: OAuth initiation, 3-step token exchange, webhook subscription, token health monitoring, and disconnection. It builds directly on Phase 11's JWT auth and Phase 10's SQLite schema and Fernet encryption helpers.

The Facebook token exchange is a server-side 3-step process: (1) redirect user to Facebook's authorization dialog to receive an authorization code, (2) exchange the code for a short-lived user access token via `GET /oauth/access_token`, (3) exchange that for a long-lived user token (60-day) via `fb_exchange_token`, then (4) call `GET /{user-id}/accounts` to get the Page access token — which has no expiry and only invalidates on password change or app deauthorization. All Graph API calls go to v25.0 (current stable as of Feb 2026). [VERIFIED: developers.facebook.com/docs/graph-api/changelog/versions/]

The CSRF state parameter for the OAuth flow embeds a signed JWT containing the `tenant_id` — this makes the flow stateless (no session store needed) while still being tamper-resistant, using the existing `JWT_SECRET` from Settings. `httpx` (already in requirements.txt at 0.28.1) handles all Graph API HTTP calls synchronously via `httpx.get()` inside FastAPI route handlers.

Token health checking uses lazy evaluation only (on GET /pages request time) via the Graph API `GET /debug_token` endpoint — no background job, consistent with the REQUIREMENTS.md deferral of automated health-check to v1.3.

**Primary recommendation:** New router `app/routers/pages.py` with five endpoints: GET /auth/facebook/start, GET /auth/facebook/callback, GET /pages, DELETE /pages/{id}, and GET /pages/{id}/health. All Graph API calls use `httpx` (already installed). No new pip packages needed for Phase 12 beyond what's already in requirements.txt.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| OAuth redirect initiation | API / Backend (`GET /auth/facebook/start`) | Browser | Backend constructs auth URL; browser follows the redirect |
| OAuth callback + token exchange | API / Backend (`GET /auth/facebook/callback`) | — | Code exchange uses app_secret — server-only; never client-side |
| CSRF state validation | API / Backend | — | State JWT signed with `JWT_SECRET`; validated before any DB write |
| Page access token encryption | API / Backend (`app/crypto.py`) | Database / Storage | Fernet encrypt before INSERT to `pages.access_token_enc` |
| Webhook subscription | API / Backend | Facebook Platform | POST to `/{page-id}/subscribed_apps` using Page access token |
| Pages list + token health | API / Backend (`GET /pages`) | Database / Storage | `pages` table join + lazy debug_token call per page |
| Page disconnection | API / Backend (`DELETE /pages/{id}`) | Facebook Platform | DB row deactivated + webhook unsubscription via Graph API |
| Token revocation detection | API / Backend (lazy, on GET /pages) | — | `GET /debug_token` is_valid field; no background job in Phase 12 |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `httpx` | 0.28.1 (installed) | Synchronous HTTP calls to Facebook Graph API | Already in requirements.txt; project uses it; no new install |
| `cryptography` (Fernet) | 48.0.0 (installed) | Encrypt/decrypt Page access tokens at rest | Already in use via `app/crypto.py`; Phase 12 calls `encrypt_token()` / `decrypt_token()` |
| `PyJWT` | 2.13.0 (installed) | Sign/verify the OAuth state parameter to carry tenant_id without session storage | Already installed in Phase 11; reuse existing `JWT_SECRET` |
| `secrets` (stdlib) | Python stdlib | Generate nonce component of OAuth state parameter | Built-in; no install |
| `sqlite3` (stdlib) | Python stdlib | Read/write the `pages` table | Project convention; raw SQL with `?` placeholders |

[VERIFIED: pip3 show httpx — 0.28.1 installed; pip3 show cryptography — 48.0.0; PyJWT — 2.13.0 installed]

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `fastapi.responses.RedirectResponse` | (in fastapi 0.128.8) | Redirect browser to Facebook OAuth dialog and back | `GET /auth/facebook/start` returns this; callback returns it after completion |
| `urllib.parse.urlencode` | Python stdlib | Construct Facebook authorization URL query string | In `GET /auth/facebook/start` handler |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `httpx.get()` synchronous calls | `httpx.AsyncClient` async | Async requires `await` and context manager; synchronous is simpler for one-off Graph API calls in FastAPI route handlers; async is better for high-concurrency (acceptable for Phase 12 admin tool traffic) |
| JWT-signed state | `itsdangerous.TimestampSigner` | Both work; JWT reuses existing PyJWT dependency already imported in `app/auth.py` |
| `secrets` nonce in state | Session cookie | No session middleware in FastAPI by default; stateless JWT state is simpler for this project's pattern |

**Installation:** No new packages required. All dependencies already in `requirements.txt`.

**Version verification:**
- `httpx`: `pip3 show httpx` → 0.28.1 [VERIFIED 2026-05-28]
- `cryptography`: `pip3 show cryptography` → 48.0.0 [VERIFIED]
- `PyJWT`: `pip3 show PyJWT` (installed in Phase 11) [VERIFIED]

---

## Architecture Patterns

### System Architecture Diagram

```
Browser (React SPA / curl)
    |
    | GET /auth/facebook/start
    |  (authenticated: requires JWT Bearer token from Phase 11)
    v
FastAPI: /auth/facebook/start
    |-- generates state = jwt.encode({tenant_id, nonce, exp=+10min}, JWT_SECRET)
    |-- constructs FB dialog URL
    v
RedirectResponse(302)
    |
    v
https://www.facebook.com/v25.0/dialog/oauth
    ?client_id=FB_APP_ID
    &redirect_uri=FB_REDIRECT_URI
    &state=<signed-state-jwt>
    &scope=pages_show_list,pages_manage_metadata,pages_messaging
    &response_type=code
    |
    | (user grants permission)
    v
https://yourapi.com/auth/facebook/callback
    ?code=<auth_code>
    &state=<signed-state-jwt>
    |
    v
FastAPI: /auth/facebook/callback
    |
    +-- 1. Verify state JWT (tenant_id, exp) -> raise 400 if invalid
    |
    +-- 2. GET graph.facebook.com/v25.0/oauth/access_token
    |       ?client_id=FB_APP_ID
    |       &redirect_uri=FB_REDIRECT_URI
    |       &client_secret=FB_APP_SECRET
    |       &code=<auth_code>
    |    -> short-lived user token (1-2 hours)
    |
    +-- 3. GET graph.facebook.com/v25.0/oauth/access_token
    |       ?grant_type=fb_exchange_token
    |       &client_id=FB_APP_ID
    |       &client_secret=FB_APP_SECRET
    |       &fb_exchange_token=<short-lived-token>
    |    -> long-lived user token (~60 days)
    |
    +-- 4. GET graph.facebook.com/v25.0/me/accounts
    |       ?access_token=<long-lived-user-token>
    |    -> list of pages [{id, name, access_token, tasks}]
    |    (each page's access_token is a non-expiring Page Access Token)
    |
    +-- 5. For each page returned:
    |    a. encrypt_token(page_access_token) via app/crypto.py
    |    b. UPSERT into pages table (page_fb_id, page_name, access_token_enc, tenant_id)
    |    c. POST graph.facebook.com/v25.0/{page_fb_id}/subscribed_apps
    |          ?subscribed_fields=messages,messaging_postbacks,messaging_referrals
    |          &access_token=<page-access-token>
    |       -> {"success": true}
    |    (all steps in one SQLite transaction; if subscribed_apps fails, rollback DB insert)
    |
    +-- 6. RedirectResponse to frontend /pages (or return JSON 200)
    |
    v
GET /pages (authenticated: requires JWT Bearer)
    |-- SELECT pages WHERE tenant_id = current_tenant AND is_active = 1
    |-- for each page: call GET /debug_token to check is_valid (lazy health check)
    |-- return [{page_fb_id, page_name, status: "active"|"revoked"}]
    |
    v
DELETE /pages/{id} (authenticated: JWT Bearer)
    |-- verify page.tenant_id == current JWT sub
    |-- DELETE /{page_fb_id}/subscribed_apps (Graph API) — best-effort
    |-- UPDATE pages SET is_active=0
    |-- return 200
    |
    v
GET /pages/{id}/health (authenticated: JWT Bearer)
    |-- SELECT page WHERE id AND tenant_id match
    |-- GET /debug_token for page token
    |-- return {is_valid: bool, expires_at: optional}
```

### Recommended Project Structure

```
app/
├── routers/
│   ├── pages.py         # new: all page connection endpoints
│   ├── auth.py          # unchanged
│   ├── tenants.py       # unchanged
│   ├── health.py        # unchanged
│   ├── ai.py            # unchanged
│   └── content.py       # unchanged
├── fb_client.py         # new: thin helpers for Graph API calls (exchange_code, exchange_long_lived, get_user_pages, subscribe_webhook, unsubscribe_webhook, check_token_health)
├── auth.py              # unchanged
├── config.py            # add: fb_app_id, fb_app_secret, fb_redirect_uri
├── db.py                # unchanged
├── crypto.py            # unchanged
└── main.py              # add: app.include_router(pages.router)

tests/
└── test_pages.py        # new: covers PAGE-01 through PAGE-04
```

### Pattern 1: OAuth Start — Signed State + Redirect

**What:** Generate a short-lived signed state JWT carrying `tenant_id` and a nonce, redirect browser to Facebook dialog.
**When to use:** `GET /auth/facebook/start` (requires valid JWT from Phase 11 auth).

```python
# Source: Facebook Login Manual Flow docs + PyJWT pattern from Phase 11
import secrets
import jwt
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from app.auth import get_current_tenant
from app.config import settings

@router.get("/auth/facebook/start")
async def facebook_oauth_start(current: dict = Depends(get_current_tenant)) -> RedirectResponse:
    tenant_id = current["sub"]
    state_payload = {
        "tenant_id": tenant_id,
        "nonce": secrets.token_hex(16),
        "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=10),
    }
    state = jwt.encode(state_payload, settings.jwt_secret, algorithm="HS256")
    params = urlencode({
        "client_id": settings.fb_app_id,
        "redirect_uri": settings.fb_redirect_uri,
        "scope": "pages_show_list,pages_manage_metadata,pages_messaging",
        "state": state,
        "response_type": "code",
    })
    return RedirectResponse(
        url=f"https://www.facebook.com/v25.0/dialog/oauth?{params}"
    )
```

**Why stateless state JWT:** No session middleware required; `jwt_secret` already in Settings from Phase 11; 10-minute expiry limits replay window; `nonce` adds per-request entropy. [ASSUMED — stateless pattern well-supported by auth0.com CSRF docs; CSRF risk is low for admin-only internal tool]

### Pattern 2: Token Exchange — Full 3-Step Flow

**What:** Exchange auth code for short-lived user token, exchange for long-lived user token, get page tokens via /me/accounts.
**When to use:** `GET /auth/facebook/callback` handler. All calls use `httpx.get()` (synchronous, already installed).

```python
# Source: developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived/ [VERIFIED]
import httpx

GRAPH_BASE = "https://graph.facebook.com/v25.0"

def exchange_code_for_short_token(code: str) -> str:
    """Step 1: code -> short-lived user token."""
    resp = httpx.get(f"{GRAPH_BASE}/oauth/access_token", params={
        "client_id": settings.fb_app_id,
        "redirect_uri": settings.fb_redirect_uri,
        "client_secret": settings.fb_app_secret,
        "code": code,
    })
    resp.raise_for_status()
    return resp.json()["access_token"]  # short-lived (1-2 hours)

def exchange_for_long_lived_token(short_token: str) -> str:
    """Step 2: short-lived user token -> long-lived user token (~60 days)."""
    resp = httpx.get(f"{GRAPH_BASE}/oauth/access_token", params={
        "grant_type": "fb_exchange_token",
        "client_id": settings.fb_app_id,
        "client_secret": settings.fb_app_secret,
        "fb_exchange_token": short_token,
    })
    resp.raise_for_status()
    return resp.json()["access_token"]  # long-lived (~60 days)

def get_user_pages(long_lived_token: str) -> list[dict]:
    """Step 3: long-lived user token -> list of Page tokens (non-expiring)."""
    resp = httpx.get(f"{GRAPH_BASE}/me/accounts", params={
        "access_token": long_lived_token,
    })
    resp.raise_for_status()
    return resp.json().get("data", [])
    # Each item: {"id": page_fb_id, "name": page_name, "access_token": page_token, ...}
```

### Pattern 3: Webhook Subscription

**What:** Subscribe a Facebook Page to receive messages/postbacks via the app webhook.
**When to use:** After storing the Page access token in Phase 12 callback.

```python
# Source: developers.facebook.com/docs/graph-api/reference/page/subscribed_apps/ [VERIFIED]

def subscribe_page_webhook(page_fb_id: str, page_access_token: str) -> None:
    """Subscribe page to receive messages and postbacks via webhook."""
    resp = httpx.post(
        f"{GRAPH_BASE}/{page_fb_id}/subscribed_apps",
        params={
            "subscribed_fields": "messages,messaging_postbacks,messaging_referrals",
            "access_token": page_access_token,
        }
    )
    resp.raise_for_status()
    # Response: {"success": true}

def unsubscribe_page_webhook(page_fb_id: str, page_access_token: str) -> None:
    """Unsubscribe page webhook — best-effort, swallow errors."""
    try:
        httpx.delete(
            f"{GRAPH_BASE}/{page_fb_id}/subscribed_apps",
            params={"access_token": page_access_token},
        )
    except Exception:
        pass  # best-effort on disconnect; log but don't fail
```

**Required permissions:** `pages_manage_metadata` (confirmed required) + user must have MANAGE/MODERATE task on the Page. [VERIFIED: developers.facebook.com/docs/graph-api/webhooks/getting-started/webhooks-for-pages/]

### Pattern 4: Token Health Check (Lazy)

**What:** Call `GET /debug_token` to determine if a stored Page access token is still valid.
**When to use:** On each `GET /pages` request — check each active page's token.

```python
# Source: developers.facebook.com/docs/graph-api/reference/debug_token/ [VERIFIED]

def check_token_health(page_access_token: str) -> bool:
    """Return True if the token is valid, False if revoked/invalid."""
    # App access token format: {app_id}|{app_secret}
    app_token = f"{settings.fb_app_id}|{settings.fb_app_secret}"
    try:
        resp = httpx.get(f"{GRAPH_BASE}/debug_token", params={
            "input_token": page_access_token,
            "access_token": app_token,
        })
        resp.raise_for_status()
        data = resp.json().get("data", {})
        return bool(data.get("is_valid", False))
    except Exception:
        return False  # treat HTTP failure as unhealthy
```

**App access token format:** `{app_id}|{app_secret}` is the standard pattern for constructing an app access token without a separate API call. [CITED: developers.facebook.com/docs/graph-api/reference/debug_token/ — "app access token or an app developer's user access token"]

### Pattern 5: Atomic Callback — Token Store + Webhook Subscribe

**What:** Ensure the DB INSERT and webhook subscription succeed together; rollback if subscription fails.
**When to use:** In the callback handler after successful 3-step token exchange.

```python
# Project convention: raw SQL + explicit conn.commit() / conn.close() (from app/db.py)

async def _store_pages_and_subscribe(pages: list[dict], tenant_id: int) -> int:
    """Store page tokens and subscribe webhooks. Returns count of pages stored."""
    conn = get_connection(settings.db_path)
    stored = 0
    try:
        for page in pages:
            page_fb_id = page["id"]
            page_name = page["name"]
            page_token = page["access_token"]
            encrypted = encrypt_token(page_token)

            # UPSERT: update if page already exists for this tenant, else insert
            existing = conn.execute(
                "SELECT id FROM pages WHERE page_fb_id = ? AND tenant_id = ?",
                (page_fb_id, tenant_id),
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE pages SET access_token_enc = ?, page_name = ?, is_active = 1 "
                    "WHERE page_fb_id = ? AND tenant_id = ?",
                    (encrypted, page_name, page_fb_id, tenant_id),
                )
            else:
                conn.execute(
                    "INSERT INTO pages (tenant_id, page_fb_id, page_name, access_token_enc) "
                    "VALUES (?, ?, ?, ?)",
                    (tenant_id, page_fb_id, page_name, encrypted),
                )

            # Webhook subscription — must succeed for this page to be considered connected
            subscribe_page_webhook(page_fb_id, page_token)
            stored += 1

        conn.commit()
    except Exception:
        conn.rollback()  # Don't commit partial state
        raise
    finally:
        conn.close()
    return stored
```

**Atomicity note:** `conn.rollback()` undoes the DB INSERT if `subscribe_page_webhook()` raises. The inverse (webhook subscribed but DB not committed) is handled by the `try/except` — if `conn.commit()` fails after a successful subscription, the subscription is orphaned. This is acceptable for MVP: the next OAuth reconnect will re-subscribe and overwrite. True two-phase commit would require compensating transactions (out of scope). [ASSUMED — acceptable for v1.2 MVP; noted for v1.3]

### Pattern 6: Settings Extension

**What:** Add Facebook app credentials to `app/config.py` Settings.

```python
# Extend existing Settings — snake_case, consistent with existing fields
class Settings(BaseSettings):
    # ... existing fields ...
    fb_app_id: str = ""           # FACEBOOK_APP_ID env var
    fb_app_secret: str = ""       # FACEBOOK_APP_SECRET env var
    fb_redirect_uri: str = ""     # FACEBOOK_REDIRECT_URI env var
                                  # e.g., "https://yourapi.com/auth/facebook/callback"
```

**New env vars for `.env.example`:**
```
FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret
FACEBOOK_REDIRECT_URI=https://yourapi.com/auth/facebook/callback
```

**Note:** `FACEBOOK_APP_SECRET` already appears in `messenger-bot/.env.example` for webhook signature verification. The Python side needs its own copy in the root `.env`. These are the same credential.

### Anti-Patterns to Avoid

- **Calling Graph API from the browser:** The `client_secret` must never leave the server. All three token exchange steps happen in FastAPI. [CITED: developers.facebook.com/docs/facebook-login/guides/advanced/manual-flow/]
- **Storing the short-lived or long-lived user token:** Only the Page access token needs to be persisted. The user token is a transient intermediate.
- **Using a non-expiring state token:** The state JWT must have a short expiry (10 minutes). A long-lived state token allows cross-site request forgery to be replayed indefinitely.
- **Plaintext Page access token in DB:** Always call `encrypt_token()` before INSERT. The `access_token_enc` column name signals this requirement.
- **Skipping `raise_for_status()` on Graph API responses:** Facebook returns HTTP 200 with an `error` key in the JSON for auth errors. Check both `raise_for_status()` and parse the response for `error` keys.
- **Hardcoding Graph API version:** Always use `v25.0` (current stable). Do not use unversioned calls — they route to a version that may be deprecated. [VERIFIED: v25.0 is latest as of Feb 2026]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Token encryption at rest | Custom base64 / XOR | `app/crypto.py encrypt_token()` (Fernet) | Already implemented in Phase 10; Fernet is AES-128-CBC + HMAC |
| CSRF state parameter | Random string in DB | JWT-signed state with `tenant_id` + nonce + 10-min expiry | Stateless, tamper-proof, no session storage needed |
| HTTP calls to Graph API | Low-level socket or `requests` | `httpx.get()` (already installed) | Already in requirements.txt; project uses it |
| Token health background job | Celery / APScheduler | Lazy check on GET /pages via `debug_token` | Background jobs deferred to v1.3 per REQUIREMENTS.md |
| App access token generation | Separate API call | `f"{fb_app_id}|{fb_app_secret}"` inline string | Facebook's documented shorthand; eliminates an extra HTTP round-trip |

**Key insight:** Nearly all the infrastructure (crypto, HTTP, JWT, SQLite) already exists from Phases 10 and 11. Phase 12 is primarily wiring these together with Facebook's 3-step exchange protocol.

---

## Common Pitfalls

### Pitfall 1: `redirect_uri` Must Exactly Match App Dashboard Registration
**What goes wrong:** Facebook returns `Error: redirect_uri does not match` even with minor differences (trailing slash, http vs https).
**Why it happens:** Facebook compares the `redirect_uri` in the callback against the registered Valid OAuth Redirect URIs character-by-character.
**How to avoid:** Register the exact value of `FB_REDIRECT_URI` in Facebook App Dashboard → Products → Facebook Login → Settings → Valid OAuth Redirect URIs. Store it as `FACEBOOK_REDIRECT_URI` env var and always read from `settings.fb_redirect_uri`.
**Warning signs:** `OAuthException: (#100) redirect_uri` error in callback.

### Pitfall 2: Graph API Returns HTTP 200 With Error JSON
**What goes wrong:** `httpx.get().raise_for_status()` passes, but the response contains `{"error": {"code": 190, "message": "Invalid OAuth access token"}}`.
**Why it happens:** Facebook's Graph API uses HTTP 200 for many error conditions; only network-level errors get non-200 status codes.
**How to avoid:** After `raise_for_status()`, always check `if "error" in resp.json(): raise HTTPException(...)`. Pattern:
```python
data = resp.json()
if "error" in data:
    raise HTTPException(status_code=400, detail=data["error"]["message"])
```
**Warning signs:** Callback appears to succeed (no exception) but no pages are stored.

### Pitfall 3: State JWT Expiry Too Long Allows Replay
**What goes wrong:** An attacker intercepts a state token and uses it hours or days later.
**Why it happens:** If `exp` is not set or is too long, old states remain valid.
**How to avoid:** Set `exp = datetime.now(tz=timezone.utc) + timedelta(minutes=10)` for the state JWT. Catch `jwt.ExpiredSignatureError` in the callback and return 400. [ASSUMED — security best practice; 10 minutes is standard OAuth state window]

### Pitfall 4: Page Access Token Is For the Page, Not the User
**What goes wrong:** Using the long-lived user token for webhook subscription calls returns 403.
**Why it happens:** `POST /{page-id}/subscribed_apps` requires a Page access token, not a user access token.
**How to avoid:** Use each page's `access_token` from the `/me/accounts` response for webhook calls. [VERIFIED: developers.facebook.com/docs/graph-api/reference/page/subscribed_apps/]
**Warning signs:** `OAuthException: (#200) The user hasn't authorized the application to perform this action` on subscribed_apps POST.

### Pitfall 5: Development Mode Limits OAuth to App Admins/Developers Only
**What goes wrong:** A client tenant tries to connect their Facebook Page but gets `Error: You are not authorized to use this app`.
**Why it happens:** In Development mode, only the app's admins, developers, and testers can log in via OAuth.
**How to avoid:** In development/testing, add all test accounts as Testers or Developers in the Facebook App Dashboard. Only in Live mode (after App Review) can arbitrary users connect. [CITED: developers.facebook.com/docs/permissions/]
**Warning signs:** Works for your own account but fails for any other user.

### Pitfall 6: `pages_messaging` Requires App Review for Production Use
**What goes wrong:** The webhook subscription appears to work but messages sent by end users are not delivered to the webhook in Live mode.
**Why it happens:** `pages_messaging` requires Advanced Access (App Review) to receive messages from users who are not admins/testers of the app.
**How to avoid:** Submit App Review during Phase 12. In Development mode, only app testers can trigger the bot — acceptable for integration testing. Submit for review before Phase 14 goes live. [MEDIUM confidence — based on multiple independent community sources; CITED: respond.io/blog/skip-facebook-bot-verification]
**Warning signs:** Bot works for developers in Development mode but silently ignores messages from real users in Live mode.

### Pitfall 7: `db.py` `get_connection()` Does Not Set WAL Mode
**What goes wrong:** Concurrent page connection callbacks hit SQLite lock errors.
**Why it happens:** Per Phase 10 research, WAL mode is set once in `init_schema()` and persists at the file level. `get_connection()` does NOT set WAL. The `busy_timeout=5000` in `get_connection()` is the concurrency protection.
**How to avoid:** Do not add WAL to `get_connection()`; the 5-second timeout already handles concurrent writes. [VERIFIED: Phase 10 research, `app/db.py` confirmed]

### Pitfall 8: `httpx.get()` Is Synchronous — Blocks the FastAPI Event Loop
**What goes wrong:** Under load, the 3 sequential Graph API calls in the callback block the event loop.
**Why it happens:** `httpx.get()` is synchronous; FastAPI is async.
**How to avoid:** For v1.2 (low-traffic admin tool), synchronous is acceptable. Use `httpx.AsyncClient` and `await` if traffic grows. The existing pattern in `app/routers/ai.py` has the same characteristic (synchronous Anthropic SDK call). [ASSUMED — acceptable for MVP; same trade-off accepted in Phase 11]

---

## Code Examples

### State Parameter — Create and Verify

```python
# Source: JWT pattern from Phase 11 (app/auth.py) + secrets stdlib
import secrets, jwt
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException

def create_oauth_state(tenant_id: str) -> str:
    """Generate a short-lived signed state token for OAuth CSRF protection."""
    payload = {
        "tenant_id": tenant_id,
        "nonce": secrets.token_hex(16),
        "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=10),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

def verify_oauth_state(state: str) -> str:
    """Verify state token and return tenant_id. Raises 400 on failure."""
    try:
        decoded = jwt.decode(state, settings.jwt_secret, algorithms=["HS256"])
        return decoded["tenant_id"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="OAuth state expired — please try again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid OAuth state — possible CSRF attack")
```

### debug_token Response Shape

```json
// Source: developers.facebook.com/docs/graph-api/reference/debug_token/ [VERIFIED]
{
  "data": {
    "app_id": "123456",
    "is_valid": true,
    "expires_at": 0,
    "scopes": ["pages_messaging", "pages_manage_metadata"],
    "error": null
  }
}
// When revoked:
{
  "data": {
    "app_id": "123456",
    "is_valid": false,
    "error": {
      "code": 190,
      "message": "The access token could not be decrypted"
    }
  }
}
```

### Pages Response Model

```python
# Project convention: inline Pydantic models per router file
from pydantic import BaseModel
from typing import Literal

class PageResponse(BaseModel):
    id: int
    page_fb_id: str
    page_name: str
    status: Literal["active", "revoked"]
    created_at: str
```

### Callback Endpoint Skeleton

```python
# Source: Facebook Manual Flow docs + project conventions
@router.get("/auth/facebook/callback")
async def facebook_oauth_callback(code: str, state: str) -> dict:
    # Step 1: verify CSRF state
    tenant_id = verify_oauth_state(state)

    # Steps 2-4: 3-step token exchange
    short_token = exchange_code_for_short_token(code)
    long_token = exchange_for_long_lived_token(short_token)
    pages = get_user_pages(long_token)

    if not pages:
        raise HTTPException(status_code=400, detail="No Facebook Pages found for this account")

    # Step 5: store + subscribe (atomic)
    count = await _store_pages_and_subscribe(pages, int(tenant_id))
    return {"pages_connected": count}
```

---

## Facebook OAuth — 3-Step Exchange Summary

| Step | Endpoint | Method | Input | Output |
|------|----------|--------|-------|--------|
| 1. Authorization | `https://www.facebook.com/v25.0/dialog/oauth` | GET (redirect) | client_id, redirect_uri, scope, state | Authorization code via redirect |
| 2. Code → Short Token | `https://graph.facebook.com/v25.0/oauth/access_token` | GET | client_id, client_secret, redirect_uri, code | Short-lived user token (1-2h) |
| 3. Short → Long Token | `https://graph.facebook.com/v25.0/oauth/access_token` | GET | grant_type=fb_exchange_token, client_id, client_secret, fb_exchange_token | Long-lived user token (~60 days) |
| 4. Long Token → Page Tokens | `https://graph.facebook.com/v25.0/me/accounts` | GET | access_token (long-lived user) | List of Page tokens (non-expiring) |

[VERIFIED: developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived/]

---

## App Review Implications

| Permission | Available in Dev Mode | Requires App Review (Live Mode) |
|------------|----------------------|--------------------------------|
| `pages_show_list` | Yes (own pages only) | Yes for arbitrary users |
| `pages_manage_metadata` | Yes (own pages only) | Yes for arbitrary users |
| `pages_messaging` | Yes (app admins/testers only) | Yes — Advanced Access required |
| `pages_read_engagement` | Yes (own pages only) | Yes for arbitrary users |

**Critical path:** In Development mode, Phase 12 can be fully tested with the developer's own Facebook Pages and test accounts added to the app. The App Review submission should be initiated during Phase 12 execution (not after) because review turnaround is days to weeks — it is on the critical path to any production launch. [MEDIUM confidence — CITED: respond.io/blog/skip-facebook-bot-verification + STATE.md blocker note]

**What to submit in review:**
- Use case description per permission (why the bot needs it)
- Screen recording demonstrating each permission in use
- Test user credentials for the Facebook review team to verify
- `pages_messaging` is the highest-impact review; submit it first

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Graph API v21.0 (referenced in STATE.md open questions) | v25.0 (current stable) | Feb 2026 | Use v25.0 in all API calls; v21.0 still works but will be deprecated Sep 2026 |
| `manage_pages` permission (older SDKs) | `pages_manage_metadata` | ~2021 (FB Platform overhaul) | `manage_pages` is removed; use `pages_manage_metadata` |
| Separate API call for app access token | `f"{app_id}|{app_secret}"` inline | N/A | Graph API accepts this format directly; saves one HTTP round-trip |
| Long-lived user token stored for recurring use | Only Page access token stored | N/A | Page tokens are non-expiring; user tokens expire in 60 days — only store what you use |

**Deprecated/outdated:**
- `manage_pages` permission: replaced by `pages_manage_metadata` and `pages_read_engagement`. [ASSUMED — based on training knowledge; should be verified in Facebook App Dashboard]
- Graph API unversioned calls: route to a deprecated version; always specify version explicitly.

---

## Runtime State Inventory

> Not a rename/refactor phase. No runtime state migration required.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | `pages` table exists in `govi.db` (created by Phase 10 init_schema) — currently zero rows | No migration; Phase 12 writes first rows via OAuth callback |
| Live service config | `messenger-bot/.env` has `FACEBOOK_APP_SECRET` — same value needed in root `.env` as `FACEBOOK_APP_SECRET` | Copy existing value; add `FACEBOOK_APP_ID` and `FACEBOOK_REDIRECT_URI` |
| OS-registered state | None | None |
| Secrets/env vars | `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_REDIRECT_URI` not yet in root `.env` or `app/config.py` | Add to Settings + `.env.example` |
| Build artifacts | None | None |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.x | All backend code | Yes | 3.9.6 | — |
| `httpx` | Graph API HTTP calls | Yes | 0.28.1 | — |
| `cryptography` (Fernet) | Token encryption | Yes | 48.0.0 | — |
| `PyJWT` | OAuth state JWT | Yes | 2.13.0 | — |
| `secrets` (stdlib) | State nonce | Yes | stdlib | — |
| `sqlite3` (stdlib) | DB writes | Yes | 3.51.0 | — |
| `pytest` | Test suite | Yes | installed | — |
| Facebook App credentials | OAuth flow | NOT YET CONFIGURED | — | Dev-mode test with own Pages |
| Internet access to graph.facebook.com | All token exchange | Required at runtime | — | Tests must mock httpx |

**Missing dependencies with no fallback:** None pip-installable. Facebook App credentials must be manually configured in the developer dashboard and added to `.env`.

**Missing dependencies with fallback:** Facebook App credentials — tests mock the `httpx` calls; dev testing uses own Pages in Development mode.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (installed) |
| Config file | none — pytest discovers `tests/` by convention |
| Quick run command | `python3 -m pytest tests/test_pages.py -x -q` |
| Full suite command | `python3 -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PAGE-01 | `GET /auth/facebook/start` returns 302 redirect to Facebook dialog with correct params | unit | `pytest tests/test_pages.py -k "test_oauth_start" -x` | No — Wave 0 |
| PAGE-01 | State JWT in redirect URL is verifiable and contains tenant_id | unit | `pytest tests/test_pages.py -k "test_state_jwt" -x` | No — Wave 0 |
| PAGE-01 | `GET /auth/facebook/callback` with valid code+state: calls 3 Graph API steps, stores pages, subscribes webhooks | integration (mocked httpx) | `pytest tests/test_pages.py -k "test_callback_success" -x` | No — Wave 0 |
| PAGE-01 | Callback with invalid state returns 400 | unit | `pytest tests/test_pages.py -k "test_callback_invalid_state" -x` | No — Wave 0 |
| PAGE-01 | Callback with expired state returns 400 | unit | `pytest tests/test_pages.py -k "test_callback_expired_state" -x` | No — Wave 0 |
| PAGE-01 | If subscribe_page_webhook raises, DB insert is rolled back | integration (mocked httpx) | `pytest tests/test_pages.py -k "test_callback_webhook_failure_rollback" -x` | No — Wave 0 |
| PAGE-02 | `GET /pages` returns active pages with status=active for valid tokens | integration (mocked httpx) | `pytest tests/test_pages.py -k "test_list_pages" -x` | No — Wave 0 |
| PAGE-02 | `GET /pages` returns status=revoked for pages whose debug_token returns is_valid=false | integration (mocked httpx) | `pytest tests/test_pages.py -k "test_list_pages_revoked" -x` | No — Wave 0 |
| PAGE-02 | `GET /pages` excludes pages belonging to other tenants | integration | `pytest tests/test_pages.py -k "test_pages_isolation" -x` | No — Wave 0 |
| PAGE-03 | `DELETE /pages/{id}` deactivates page in DB and calls unsubscribed_apps | integration (mocked httpx) | `pytest tests/test_pages.py -k "test_disconnect_page" -x` | No — Wave 0 |
| PAGE-03 | `DELETE /pages/{id}` returns 404 for unknown or other tenant's page | unit | `pytest tests/test_pages.py -k "test_disconnect_not_found" -x` | No — Wave 0 |
| PAGE-04 | `GET /pages/{id}/health` returns is_valid=true/false per debug_token response | unit (mocked httpx) | `pytest tests/test_pages.py -k "test_token_health" -x` | No — Wave 0 |

**httpx mocking approach:** Use `pytest-monkeypatch` or `unittest.mock.patch("app.fb_client.httpx.get")` to mock all Graph API calls. Tests should not make real HTTP calls. [ASSUMED — standard pattern for httpx mocking in pytest; monkeypatch already established in conftest.py]

### Sampling Rate

- **Per task commit:** `python3 -m pytest tests/test_pages.py -x -q`
- **Per wave merge:** `python3 -m pytest tests/ -q`
- **Phase gate:** Full suite green (37 existing + new page tests) before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_pages.py` — covers all PAGE-01 through PAGE-04 success criteria (new file)
- [ ] `app/fb_client.py` — stub with `httpx.get()` wrappers (needed before tests can import)
- [ ] `app/routers/pages.py` — stub with empty route skeletons (needed for TestClient routing)
- [ ] `app/config.py` — add `fb_app_id`, `fb_app_secret`, `fb_redirect_uri` fields
- [ ] `app/main.py` — add `app.include_router(pages.router)`
- [ ] `.env.example` — add `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_REDIRECT_URI`
- [ ] Update `tests/conftest.py` `db_client` fixture — add monkeypatch for `fb_app_id`, `fb_app_secret`, `fb_redirect_uri` settings fields

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes | Phase 11 JWT required on all page endpoints; `get_current_tenant()` Depends |
| V3 Session Management | Yes | OAuth state JWT: 10-min expiry, HS256 signed, nonce — no server-side session |
| V4 Access Control | Yes | Page endpoints verify `page.tenant_id == current JWT sub`; no cross-tenant access |
| V5 Input Validation | Yes | `code` and `state` params validated at callback; page_id from DB never from user |
| V6 Cryptography | Yes | Fernet for token storage (AES-128-CBC + HMAC); HS256 for state JWT — never hand-roll |

### Known Threat Patterns for Facebook OAuth + SQLite

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| CSRF via crafted callback URL | Spoofing | State JWT with tenant_id + nonce + 10-min expiry; verify before any action |
| Authorization code interception / replay | Spoofing | Code can only be exchanged once; `redirect_uri` must match exactly; HTTPS required |
| State JWT replay after expiry | Elevation of Privilege | `exp` claim with 10-minute window; `jwt.ExpiredSignatureError` → 400 |
| Plaintext Page access token in DB | Information Disclosure | Fernet encryption via `app/crypto.py encrypt_token()` before INSERT |
| Cross-tenant page access | Information Disclosure | All page queries include `WHERE tenant_id = current_tenant_id` |
| `fb_app_secret` in logs or responses | Information Disclosure | Never log `fb_app_secret`; never include in API response body |
| SQL injection via page_fb_id or code | Tampering | Raw SQL uses `?` placeholders throughout (project convention) |
| Webhook subscription with wrong token type | Spoofing | Verify: subscribed_apps requires Page access token, not user token — use `page["access_token"]` from /me/accounts response |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | JWT-signed stateless state parameter (no server-side session) is sufficient CSRF protection for this admin-only internal tool | Architecture Patterns (Pattern 1) | Low — admin-only tool; if wrong, add Starlette session middleware in v1.3 |
| A2 | `httpx.get()` (synchronous) is acceptable for Graph API calls given v1.2 is a low-traffic admin tool | Common Pitfalls (Pitfall 8) | Low — same trade-off already accepted for Anthropic SDK calls |
| A3 | Orphaned webhook subscription (DB rollback but subscription succeeded) can be resolved by reconnect in next OAuth flow | Architecture Patterns (Pattern 5) | Medium — if Page is subscribed but not in DB, the old token routes messages to no handler; resolved by reconnect |
| A4 | `manage_pages` permission is deprecated; `pages_manage_metadata` is the replacement | State of the Art | Medium — if wrong, webhook subscription may fail; verify in Facebook App Dashboard |
| A5 | App Review turnaround is days to weeks — initiate during Phase 12 not after | App Review section | High if launch is time-sensitive — this is on the critical path |
| A6 | `httpx` mock via `unittest.mock.patch("app.fb_client.httpx.get")` is the correct test pattern | Validation Architecture | Low — monkeypatch works for module-level imports; alternatively use `respx` library |
| A7 | Long-lived Page access tokens have no expiry and only invalidate on password change or app deauthorization | Architecture Patterns | Medium — if wrong, tokens expire silently; the lazy health check via debug_token mitigates this |

---

## Open Questions

1. **Graph API version: v21.0 vs v25.0**
   - What we know: STATE.md open question references v21.0 and v25.0; research confirmed v25.0 is current stable (released Feb 2026)
   - Recommendation: Use v25.0 in all new code. [RESOLVED]

2. **Should the OAuth callback return JSON or a browser redirect?**
   - What we know: The callback is triggered by a browser redirect from Facebook; if the API is called from a SPA the callback must redirect back to the SPA route
   - What's unclear: Phase 15 hasn't been planned yet; the redirect URL target isn't defined
   - Recommendation: Return JSON `{"pages_connected": N}` for Phase 12 (API-only phase); Phase 15 can add the frontend redirect when the SPA exists

3. **What `subscribed_fields` are needed for the bot?**
   - What we know: The bot handles `messages` (text) and `messaging_postbacks` (button taps) — confirmed in Phase 1-9 code
   - Recommendation: Subscribe to `messages,messaging_postbacks,messaging_referrals`. Keep `messaging_referrals` for the Get Started payload. [ASSUMED — based on existing bot behavior review]

4. **Should `GET /pages` call `debug_token` on every request?**
   - What we know: The requirement says "token health indicator per Page"; deferred background job is in REQUIREMENTS.md future items
   - What's unclear: Calling debug_token for each page on every list request adds N × 1 Graph API call latency
   - Recommendation: Accept the latency for Phase 12 (low page count, admin tool); add caching or background refresh in v1.3

5. **What happens if the Facebook user has no Pages?**
   - Recommendation: `GET /me/accounts` returns empty `data` array; callback should return `400 No Facebook Pages found for this account` (not 200 with empty list)

---

## Project Constraints (from CLAUDE.md)

| Directive | Impact on Phase 12 |
|-----------|-------------------|
| Tech stack: Python/FastAPI for backend; Node.js for bot | All OAuth and Graph API code goes in `app/`; no Node.js involvement |
| No containerization | `FACEBOOK_REDIRECT_URI` must be manually configured to match current deployment URL |
| Surgical changes | Only `app/config.py` (3 new fields), `app/main.py` (1 new router include), and new files; no existing files restructured |
| Simplicity first | No oauth library (authlib, fastapi-sso) — raw httpx calls are simpler and match project's no-ORM/no-framework ethos |
| Match existing style | snake_case files, 4-space indent, inline Pydantic models per router, raw SQL with `?` placeholders, `settings` singleton |
| No features beyond asked | No token rotation, no refresh of long-lived user tokens, no background health job (deferred) |

---

## Sources

### Primary (HIGH confidence)
- [Generate Long-Lived User and Page Access Tokens — Meta for Developers](https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived/) — 3-step exchange flow, /me/accounts endpoint, Page token non-expiry [VERIFIED via WebFetch]
- [Manually Build a Login Flow — Meta for Developers](https://developers.facebook.com/docs/facebook-login/guides/advanced/manual-flow/) — authorization dialog URL, code exchange endpoint, state parameter, redirect_uri requirements [VERIFIED via WebFetch]
- [Open Graph Page Subscribed Apps — Meta for Developers](https://developers.facebook.com/docs/graph-api/reference/page/subscribed_apps/) — subscribed_fields, required permissions, Page access token requirement [VERIFIED via WebFetch]
- [Webhooks for Pages — Meta for Developers](https://developers.facebook.com/docs/graph-api/webhooks/getting-started/webhooks-for-pages/) — pages_manage_metadata + pages_messaging permissions, webhook setup steps [VERIFIED via WebFetch]
- [Debug Token — Graph API — Meta for Developers](https://developers.facebook.com/docs/graph-api/reference/debug_token/) — is_valid field, app access token format, response shape [VERIFIED via WebFetch]
- [Graph API Versions — Meta for Developers](https://developers.facebook.com/docs/graph-api/changelog/versions/) — v25.0 is current stable (Feb 2026) [VERIFIED via WebFetch]
- Phase 10 and Phase 11 RESEARCH.md — established patterns for crypto, JWT, SQLite, conftest [VERIFIED via direct read]
- `app/db.py`, `app/config.py`, `app/crypto.py`, `app/routers/tenants.py`, `app/auth.py`, `requirements.txt` — current codebase [VERIFIED via direct read]

### Secondary (MEDIUM confidence)
- [Facebook App Approval Process — respond.io](https://respond.io/blog/skip-facebook-bot-verification) — pages_messaging requires App Review in Live mode; development mode allows admin/tester accounts only
- [Auth0 OAuth State Parameters](https://auth0.com/docs/secure/attack-protection/state-parameters) — stateless JWT-signed state pattern

### Tertiary (LOW confidence)
- None.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed and verified; no new packages
- Architecture: HIGH — 3-step exchange flow verified via official Meta docs; JWT state pattern verified via Phase 11 patterns
- Pitfalls: HIGH — redirect_uri mismatch, HTTP 200 with error JSON, Dev mode limitations are well-documented; App Review requirement is MEDIUM (community sources)
- App Review: MEDIUM — timelines are not officially documented; community consensus is days to weeks

**Research date:** 2026-05-28
**Valid until:** 2026-06-28 (Graph API stable; token exchange flow does not change frequently)
