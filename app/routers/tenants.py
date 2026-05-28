from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from passlib.context import CryptContext

from app.auth import get_current_tenant, require_super_admin
from app.config import settings
from app.db import get_connection

# No global prefix — router serves both /admin/tenants/* and /tenants/me
router = APIRouter(tags=["tenants"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class CreateTenantRequest(BaseModel):
    email: str
    password: str


class TenantResponse(BaseModel):
    id: int
    email: str
    is_active: bool
    is_super_admin: bool
    created_at: str


class TenantListItem(BaseModel):
    id: int
    email: str
    is_active: bool
    created_at: str
    page_count: int


class DeleteResponse(BaseModel):
    detail: str
    pages_deactivated: int


@router.post("/admin/tenants", response_model=TenantResponse, status_code=201)
async def create_tenant(
    request: CreateTenantRequest,
    current: dict = Depends(require_super_admin),
) -> TenantResponse:
    conn = get_connection(settings.db_path)
    try:
        existing = conn.execute(
            "SELECT id FROM tenants WHERE email = ?", (request.email,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Email already exists")
        cur = conn.execute(
            "INSERT INTO tenants (email, password_hash, is_super_admin) VALUES (?, ?, 0)",
            (request.email, pwd_context.hash(request.password)),
        )
        conn.commit()
        new_id = cur.lastrowid
        row = conn.execute(
            "SELECT id, email, is_active, is_super_admin, created_at FROM tenants WHERE id = ?",
            (new_id,),
        ).fetchone()
    finally:
        conn.close()
    return TenantResponse(
        id=row["id"],
        email=row["email"],
        is_active=bool(row["is_active"]),
        is_super_admin=bool(row["is_super_admin"]),
        created_at=row["created_at"],
    )


@router.get("/admin/tenants", response_model=list[TenantListItem])
async def list_tenants(
    current: dict = Depends(require_super_admin),
) -> list[TenantListItem]:
    conn = get_connection(settings.db_path)
    try:
        rows = conn.execute(
            """
            SELECT t.id, t.email, t.is_active, t.created_at,
                   COUNT(p.id) AS page_count
            FROM tenants t
            LEFT JOIN pages p ON p.tenant_id = t.id AND p.is_active = 1
            WHERE t.is_super_admin = 0
            GROUP BY t.id
            """
        ).fetchall()
    finally:
        conn.close()
    return [
        TenantListItem(
            id=r["id"],
            email=r["email"],
            is_active=bool(r["is_active"]),
            created_at=r["created_at"],
            page_count=r["page_count"],
        )
        for r in rows
    ]


@router.delete("/admin/tenants/{tenant_id}", response_model=DeleteResponse)
async def delete_tenant(
    tenant_id: int,
    current: dict = Depends(require_super_admin),
) -> DeleteResponse:
    # Self-delete guard (Pitfall 5) — check before opening conn
    if tenant_id == int(current["sub"]):
        raise HTTPException(status_code=403, detail="Cannot delete your own account")
    conn = get_connection(settings.db_path)
    try:
        existing = conn.execute(
            "SELECT id FROM tenants WHERE id = ? AND is_active = 1 AND is_super_admin = 0",
            (tenant_id,),
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Tenant not found or already inactive")
        conn.execute("UPDATE tenants SET is_active = 0 WHERE id = ?", (tenant_id,))
        pages_cur = conn.execute(
            "UPDATE pages SET is_active = 0 WHERE tenant_id = ?", (tenant_id,)
        )
        pages_deactivated = pages_cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return DeleteResponse(
        detail=f"Tenant {tenant_id} deactivated",
        pages_deactivated=pages_deactivated,
    )


@router.get("/tenants/me", response_model=TenantResponse)
async def get_my_tenant(
    current: dict = Depends(get_current_tenant),
) -> TenantResponse:
    conn = get_connection(settings.db_path)
    try:
        row = conn.execute(
            "SELECT id, email, is_active, is_super_admin, created_at FROM tenants WHERE id = ?",
            (int(current["sub"]),),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return TenantResponse(
        id=row["id"],
        email=row["email"],
        is_active=bool(row["is_active"]),
        is_super_admin=bool(row["is_super_admin"]),
        created_at=row["created_at"],
    )
