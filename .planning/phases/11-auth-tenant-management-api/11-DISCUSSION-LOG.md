# Phase 11: Auth & Tenant Management API - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-27
**Phase:** 11-auth-tenant-management-api
**Areas discussed:** Super-admin identity, Client auth in Phase 11, JWT library & secret

---

## Super-admin identity

### Q1: Where does the super-admin credential live?

| Option | Description | Selected |
|--------|-------------|----------|
| Env vars (SUPER_ADMIN_EMAIL + SUPER_ADMIN_PASSWORD) | Super-admin is NOT in the DB. Login validates against env vars. Simple — no bootstrap problem, no DB row to seed. | |
| Separate `admins` table in DB | Create an `admins` table with one seeded row. More DB-consistent but adds a table and a seed step. | |
| Special row in `tenants` table | Add `is_super_admin` flag to tenants. Single table, but mixes roles and complicates tenant-scoped queries. | ✓ |

**User's choice:** Special row in `tenants` table
**Notes:** User preferred keeping super-admin in the tenants table with a flag.

---

### Q2: How should `is_super_admin` column be added?

| Option | Description | Selected |
|--------|-------------|----------|
| Alter init_schema to add column (with migration) | UPDATE db.py to ADD COLUMN IF NOT EXISTS via ALTER TABLE. Requires schema migration. | |
| Reset schema (ALTER not needed — fresh DB for v1.2) | Update CREATE TABLE to include the column, re-run init_db.py. | ✓ (Claude's decision) |

**User's choice:** "which one is the best solution then pick it" — deferred to Claude
**Notes:** Claude chose schema reset since there is no production data in v1.2 dev environment.

---

### Q3: How is the initial super-admin row seeded?

| Option | Description | Selected |
|--------|-------------|----------|
| New env vars SUPER_ADMIN_EMAIL + SUPER_ADMIN_PASSWORD seed on init_db.py run | init_db.py reads these vars, hashes the password, inserts the super-admin row. | ✓ |
| Hardcoded seed in init_db.py | Fixed default credentials seeded as a comment. | |
| Manual INSERT — documented in README | Developer runs SQL INSERT manually. | |

**User's choice:** New env vars SUPER_ADMIN_EMAIL + SUPER_ADMIN_PASSWORD seed on init_db.py run
**Notes:** Clean approach — credentials in .env, never hardcoded.

---

### Q4: What does a non-super-admin get when hitting admin endpoints?

| Option | Description | Selected |
|--------|-------------|----------|
| 403 Forbidden — check is_super_admin claim in JWT | JWT payload includes a role field. Admin-only endpoints check role=super_admin, return 403 otherwise. | ✓ |
| 404 Not Found — treat admin routes as invisible | Non-super-admin tokens get 404, obscuring that they exist. | |

**User's choice:** 403 Forbidden — check is_super_admin claim in JWT
**Notes:** Explicit 403 is better UX for an admin tool — developers know why access was denied.

---

## Client auth in Phase 11

### Q1: Does Phase 11 include client login?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — one login endpoint handles both roles | POST /auth/login accepts any email+password. Returns role=super_admin or role=client JWT based on is_super_admin flag. | ✓ |
| No — super-admin login only in Phase 11 | Client JWT pattern defined but client login endpoint deferred to Phase 12. | |

**User's choice:** Yes — one login endpoint handles both roles
**Notes:** Makes SC-5 (tenant-scoped isolation) testable within Phase 11.

---

### Q2: What JWT claims does a client token carry?

| Option | Description | Selected |
|--------|-------------|----------|
| sub (tenant_id), role: 'client', exp | Tenant ID as subject claim. Clean and minimal. | ✓ |
| sub (email), tenant_id (custom claim), role, exp | Email as subject, tenant_id as a separate custom claim. | |

**User's choice:** sub (tenant_id), role: 'client', exp
**Notes:** Minimal claims — downstream endpoints use sub as the scoping key.

---

### Q3: Is there a GET /tenants/me endpoint in Phase 11?

| Option | Description | Selected |
|--------|-------------|----------|
| Add GET /tenants/me for client self-info — enforces SC-5 | Client calls GET /tenants/me, gets their own row. SC-5 directly testable. | ✓ |
| Test SC-5 via unit tests only — no client endpoint in Phase 11 | SC-5 validated by auth middleware logic + unit tests only. | |

**User's choice:** Add GET /tenants/me for client self-info — enforces SC-5
**Notes:** Live endpoint makes the isolation guarantee concrete and E2E testable.

---

### Q4: Auth middleware approach?

| Option | Description | Selected |
|--------|-------------|----------|
| FastAPI Depends() — get_current_tenant() dependency | Reusable Depends function; each route declares `current_tenant = Depends(get_current_tenant)`. | ✓ |
| Custom middleware class (BaseHTTPMiddleware) | Runs before every request; harder to exclude public routes. | |

**User's choice:** FastAPI Depends() — get_current_tenant() dependency
**Notes:** Standard FastAPI idiom. Easier to exclude public routes and test in isolation.

---

## JWT library & secret

### Q1: JWT library?

| Option | Description | Selected |
|--------|-------------|----------|
| PyJWT | Minimal, well-maintained, HS256 out of the box. | ✓ |
| python-jose | More features (JWE, multi-algorithm). Heavier. Overkill for HS256. | |
| python-jwt | Less popular, less maintained. | |

**User's choice:** PyJWT
**Notes:** Recommended option selected — simple and sufficient.

---

### Q2: Where does the JWT signing secret live?

| Option | Description | Selected |
|--------|-------------|----------|
| New JWT_SECRET env var in .env + Settings | Dedicated secret, follows pydantic-settings pattern. | ✓ |
| Derive from FERNET_KEY | Reuses existing key. Bad practice (key separation). | |

**User's choice:** New JWT_SECRET env var in .env + Settings
**Notes:** Clean key separation — FERNET_KEY stays for token encryption only.

---

### Q3: Token expiry?

| Option | Description | Selected |
|--------|-------------|----------|
| 24 hours, configurable via JWT_EXPIRES_HOURS env var | Sensible default, adjustable. | |
| 8 hours, fixed | Short window — better security, but expires mid-day. | |
| 7 days, fixed | Long-lived — convenient for admin tool, low-traffic. | ✓ |

**User's choice:** 7 days, fixed
**Notes:** Admin panel is low-traffic; 7-day sessions avoid interruption.

---

### Q4: Password hashing library?

| Option | Description | Selected |
|--------|-------------|----------|
| passlib with bcrypt | Industry standard for FastAPI. CryptContext makes hash/verify one-liners. | ✓ |
| hashlib.sha256 (stdlib) | No extra install, but too fast for passwords — vulnerable to brute-force. | |

**User's choice:** passlib with bcrypt
**Notes:** Correct choice for production password storage.

---

## Claude's Discretion

- **Schema migration approach:** Reset schema (add `is_super_admin` to CREATE TABLE, re-run init_db.py) — user deferred this decision; no production data in v1.2 dev environment makes migration unnecessary
- **Deactivation vs. deletion:** `DELETE /admin/tenants/{id}` performs soft delete (`is_active = 0`) — aligns with existing schema and TENANT-03 "delete or deactivate" wording; not discussed explicitly, hard delete excluded
- **Module layout:** `app/auth.py` for auth helpers, `app/routers/auth.py` and `app/routers/tenants.py` for new routes
- **No refresh tokens:** 7-day tokens + admin tool = no refresh needed in v1.2

## Deferred Ideas

- Refresh tokens — deferred to v1.3 (low-traffic tool, 7-day sessions sufficient)
- Hard delete for tenant accounts — soft delete is sufficient; hard delete can be added later
- Token revocation / blacklist — deferred; soft-deactivation handles the security concern
