# Phase 11: Auth & Tenant Management API - Context

**Gathered:** 2026-05-27
**Status:** Ready for planning

<domain>
## Phase Boundary

FastAPI authentication + JWT session management + super-admin CRUD for client (tenant) accounts. Deliverables:
- `POST /auth/login` — single endpoint for both super-admin and client login, returns a signed JWT
- `GET /admin/tenants`, `POST /admin/tenants`, `DELETE /admin/tenants/{id}` — super-admin-only CRUD
- `GET /tenants/me` — client self-info; enforces tenant-scoped token isolation (SC-5)
- `app/auth.py` — reusable `get_current_tenant()` FastAPI dependency
- Schema update: `is_super_admin` column added to `tenants` table; super-admin seed in `init_db.py`

**Out of scope:** Refresh tokens, Facebook OAuth (Phase 12), content endpoints (Phase 13), admin panel UI (Phase 15).

</domain>

<decisions>
## Implementation Decisions

### Super-admin Identity
- **D-01:** Super-admin is stored as a special row in the `tenants` table with `is_super_admin = 1`. No separate table.
- **D-02:** Schema reset — add `is_super_admin INTEGER NOT NULL DEFAULT 0` to `CREATE TABLE tenants` in `app/db.py`. Re-run `scripts/init_db.py` (dev-only DB, no migration needed for v1.2).
- **D-03:** Super-admin row is seeded by `scripts/init_db.py` reading `SUPER_ADMIN_EMAIL` and `SUPER_ADMIN_PASSWORD` env vars; password stored as bcrypt hash. No hardcoded credentials.
- **D-04:** Admin-only endpoints (`/admin/tenants/*`) check `role == "super_admin"` in the JWT. Non-super-admin tokens receive **403 Forbidden**.

### Client Auth Scope
- **D-05:** Single `POST /auth/login` endpoint handles both roles. Returns a JWT with `role: "super_admin"` or `role: "client"` based on the `is_super_admin` flag of the matching tenant row.
- **D-06:** Client JWT payload: `{ "sub": "<tenant_id as string>", "role": "client", "exp": <timestamp> }`
- **D-07:** Super-admin JWT payload: `{ "sub": "<tenant_id of super-admin row>", "role": "super_admin", "exp": <timestamp> }`
- **D-08:** `GET /tenants/me` added to Phase 11 — returns the calling client's own tenant record. Directly enforces and tests SC-5 (tenant-scoped token isolation).
- **D-09:** Auth via FastAPI `Depends()` — reusable `get_current_tenant(token: str = Depends(oauth2_scheme))` dependency. Protected routes declare `current = Depends(get_current_tenant)`. Public routes (e.g. `/auth/login`) use no dependency.

### JWT Library & Secret
- **D-10:** PyJWT library — `pip install PyJWT`; add `PyJWT>=2.8.0` to `requirements.txt`.
- **D-11:** JWT signing secret in `JWT_SECRET` env var — add `jwt_secret: str = ""` to `Settings` in `app/config.py`. Guard: raise `RuntimeError` at token creation time if empty (same pattern as `_fernet()` in `app/crypto.py`).
- **D-12:** Token expiry: **7 days fixed** (`exp = datetime.utcnow() + timedelta(days=7)`). No refresh tokens.
- **D-13:** Password hashing: `passlib` with bcrypt — `pip install passlib[bcrypt]`; add `passlib[bcrypt]>=1.7.4` to `requirements.txt`.

### Claude's Discretion
- **Deactivation vs. deletion:** `DELETE /admin/tenants/{id}` performs a **soft delete** (`is_active = 0`). The `tenants` table already has `is_active`. Soft delete is safer and reversible — aligns with TENANT-03 "delete or deactivate." Hard delete is not in scope for this phase.
- **New module layout:**
  - `app/auth.py` — `create_access_token()`, `verify_token()`, `get_current_tenant()` Depends, `require_super_admin()` Depends
  - `app/routers/auth.py` — `POST /auth/login` (prefix `/auth`, tags `["auth"]`)
  - `app/routers/tenants.py` — super-admin CRUD (`/admin/tenants`) + client self-info (`/tenants/me`) (prefix in route declarations, tags `["tenants"]`)
- **Tenant list response:** includes connected Page count — requires a `SELECT COUNT(*)` join against the `pages` table per tenant. Return as `page_count: int` in the response model.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope & Requirements
- `.planning/ROADMAP.md` §Phase 11 — goal, success criteria (SC-1 through SC-5)
- `.planning/REQUIREMENTS.md` §TENANT-01, TENANT-02, TENANT-03 — the three requirements this phase satisfies

### Existing DB & Config Patterns (MUST follow)
- `app/db.py` — `get_connection(db_path)` factory, `init_schema(db_path)`, `tenants` table schema (to be updated with `is_super_admin`)
- `app/config.py` — `Settings(BaseSettings)` singleton; add `jwt_secret`, `super_admin_email`, `super_admin_password` following same field pattern
- `scripts/init_db.py` — DB init + seed script; update to seed super-admin row

### Existing Router Patterns (MUST follow)
- `app/routers/health.py` — canonical `APIRouter` + Pydantic inline model pattern
- `app/main.py` — where new routers are registered via `app.include_router(...)`

### Crypto Pattern Reference
- `app/crypto.py` — env-var guard pattern (`if not settings.X: raise RuntimeError(...)`) — use same pattern for `jwt_secret` in `app/auth.py`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/db.py:get_connection(db_path)` — use for all tenant queries; returns `sqlite3.Row` rows (dict-accessible)
- `app/config.py:settings` — extend with 3 new fields: `jwt_secret`, `super_admin_email`, `super_admin_password`
- `app/crypto.py:_fernet()` guard pattern — copy for JWT secret guard in `app/auth.py`

### Established Patterns
- **APIRouter:** `router = APIRouter(prefix="/prefix", tags=["tag"])` — one router per file
- **Pydantic models:** inline in the same router file as the route (`class LoginRequest(BaseModel): ...`)
- **Error responses:** `raise HTTPException(status_code=N, detail="...")` — no try/except in happy path
- **Async routes:** `async def login(request: LoginRequest)` — keep consistent
- **Raw SQL only** — no ORM, no SQLAlchemy. All queries use `?` placeholders with `conn.execute()`
- **Settings singleton:** `from app.config import settings` at module level

### Integration Points
- `app/main.py` — add `from app.routers import auth, tenants` and `app.include_router(auth.router)`, `app.include_router(tenants.router)`
- `app/config.py` — add `jwt_secret: str = ""`, `super_admin_email: str = ""`, `super_admin_password: str = ""`
- `app/db.py` — update `CREATE TABLE tenants` to add `is_super_admin INTEGER NOT NULL DEFAULT 0`
- `.env.example` — document new vars: `JWT_SECRET`, `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD`
- `requirements.txt` — add `PyJWT>=2.8.0` and `passlib[bcrypt]>=1.7.4`

</code_context>

<specifics>
## Specific Ideas

- Seed guard in `init_db.py`: insert super-admin row only if no row with `is_super_admin=1` exists (idempotent).
- `GET /admin/tenants` response: include `page_count` per tenant (COUNT join on `pages.tenant_id`). Excludes the super-admin row itself from the list.
- `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")` — standard FastAPI OAuth2 bearer setup for `get_current_tenant`.

</specifics>

<deferred>
## Deferred Ideas

- Refresh tokens — not needed for v1.2 low-traffic admin tool; revisit in v1.3 if sessions prove too short
- Hard delete for tenant accounts — soft delete (`is_active=0`) is sufficient for Phase 11; hard delete can be added later if needed
- Token revocation / blacklist — deferred; 7-day tokens with soft-deactivation is acceptable for v1.2

</deferred>

---

*Phase: 11-auth-tenant-management-api*
*Context gathered: 2026-05-27*
