import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal, Optional
from urllib.parse import urlencode

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app import fb_client
from app.auth import get_current_tenant
from app.config import settings
from app.crypto import encrypt_token, decrypt_token
from app.db import get_connection


router = APIRouter(tags=["pages"])


class PageResponse(BaseModel):
    id: int
    page_fb_id: str
    page_name: str
    status: Literal["active", "revoked"]
    created_at: str


class HealthResponse(BaseModel):
    is_valid: bool
    expires_at: int | None


class MenuItem(BaseModel):
    model_config = {"extra": "forbid"}

    title: str
    payload: str


class PageConfigRequest(BaseModel):
    welcome_text: str
    menu_json: list[MenuItem]
    escalation_psid: Optional[str] = None
    escalation_message: Optional[str] = None


class PageConfigResponse(BaseModel):
    page_id: int
    welcome_text: str
    menu_json: list[MenuItem]
    escalation_psid: Optional[str]
    escalation_message: Optional[str]
    updated_at: str


class InternalPageConfigResponse(BaseModel):
    welcome_text: str
    menu_json: list[MenuItem]
    escalation_psid: Optional[str]
    escalation_message: Optional[str]


class QAItemCreateRequest(BaseModel):
    type: Literal["category", "question"]
    title: str
    body: str = ""
    category_id: Optional[int] = None
    enabled: bool = True


class QAItemUpdateRequest(BaseModel):
    type: Literal["category", "question"]
    title: str
    body: str = ""
    category_id: Optional[int] = None
    enabled: bool = True


class QAItemResponse(BaseModel):
    id: int
    page_id: int
    type: str
    title: str
    body: str
    category_id: Optional[int]
    enabled: bool
    created_at: str


def create_oauth_state(tenant_id: str) -> str:
    """Generate a short-lived signed state token for OAuth CSRF protection."""
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is not configured. Set it in .env.")
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
        raise HTTPException(status_code=400, detail="Invalid OAuth state")


def _store_pages_and_subscribe(pages: list[dict], tenant_id: int) -> int:
    """Store page tokens and subscribe webhooks — atomic. Returns count stored."""
    conn = get_connection(settings.db_path)
    stored = 0
    try:
        for page in pages:
            page_fb_id = page["id"]
            page_name = page["name"]
            page_token = page["access_token"]
            encrypted = encrypt_token(page_token)

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

            fb_client.subscribe_page_webhook(page_fb_id, page_token)
            stored += 1

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return stored


@router.get("/auth/facebook/start")
async def facebook_oauth_start(
    current: dict = Depends(get_current_tenant),
) -> RedirectResponse:
    tenant_id = current["sub"]
    state = create_oauth_state(tenant_id)
    params = {
        "client_id": settings.fb_app_id,
        "redirect_uri": settings.fb_redirect_uri,
        "scope": "pages_show_list,pages_manage_metadata,pages_messaging",
        "state": state,
        "response_type": "code",
    }
    url = f"https://www.facebook.com/v25.0/dialog/oauth?{urlencode(params)}"
    return RedirectResponse(url=url, status_code=302)


@router.get("/auth/facebook/callback")
async def facebook_oauth_callback(code: str, state: str) -> dict:
    tenant_id_str = verify_oauth_state(state)
    short_token = fb_client.exchange_code_for_short_token(code)
    long_token = fb_client.exchange_for_long_lived_token(short_token)
    pages_data = fb_client.get_user_pages(long_token)
    if not pages_data:
        raise HTTPException(status_code=400, detail="No Facebook Pages found for this account")
    count = _store_pages_and_subscribe(pages_data, int(tenant_id_str))
    return {"pages_connected": count}


@router.get("/pages", response_model=list[PageResponse])
async def list_pages(current: dict = Depends(get_current_tenant)) -> list[PageResponse]:
    tenant_id = int(current["sub"])
    conn = get_connection(settings.db_path)
    try:
        rows = conn.execute(
            "SELECT id, page_fb_id, page_name, access_token_enc, created_at "
            "FROM pages WHERE tenant_id = ? AND is_active = 1 ORDER BY id ASC",
            (tenant_id,),
        ).fetchall()
    finally:
        conn.close()

    result: list[PageResponse] = []
    for r in rows:
        enc = r["access_token_enc"]
        if enc:
            try:
                page_token = decrypt_token(enc)
            except ValueError:
                page_token = None
        else:
            page_token = None
        is_valid = fb_client.check_token_health(page_token) if page_token else False
        result.append(
            PageResponse(
                id=r["id"],
                page_fb_id=r["page_fb_id"],
                page_name=r["page_name"],
                status="active" if is_valid else "revoked",
                created_at=r["created_at"],
            )
        )
    return result


@router.delete("/pages/{page_id}", status_code=200)
async def disconnect_page(
    page_id: int, current: dict = Depends(get_current_tenant)
) -> dict:
    tenant_id = int(current["sub"])
    conn = get_connection(settings.db_path)
    try:
        row = conn.execute(
            "SELECT id, page_fb_id, access_token_enc FROM pages "
            "WHERE id = ? AND tenant_id = ? AND is_active = 1",
            (page_id, tenant_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Page not found")

        enc = row["access_token_enc"]
        page_token = None
        if enc:
            try:
                page_token = decrypt_token(enc)
            except ValueError:
                page_token = None
        if page_token:
            fb_client.unsubscribe_page_webhook(row["page_fb_id"], page_token)

        conn.execute(
            "UPDATE pages SET is_active = 0 WHERE id = ? AND tenant_id = ?",
            (page_id, tenant_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"detail": f"Page {page_id} disconnected"}


@router.get("/pages/{page_id}/health", response_model=HealthResponse)
async def page_health(
    page_id: int, current: dict = Depends(get_current_tenant)
) -> HealthResponse:
    tenant_id = int(current["sub"])
    conn = get_connection(settings.db_path)
    try:
        row = conn.execute(
            "SELECT access_token_enc FROM pages "
            "WHERE id = ? AND tenant_id = ? AND is_active = 1",
            (page_id, tenant_id),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Page not found")

    enc = row["access_token_enc"]
    if not enc:
        return HealthResponse(is_valid=False, expires_at=None)
    try:
        page_token = decrypt_token(enc)
    except ValueError:
        return HealthResponse(is_valid=False, expires_at=None)

    app_token = f"{settings.fb_app_id}|{settings.fb_app_secret}"
    try:
        resp = fb_client.httpx.get(
            fb_client.GRAPH_BASE + "/debug_token",
            params={"input_token": page_token, "access_token": app_token},
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
    except Exception:
        return HealthResponse(is_valid=False, expires_at=None)

    is_valid = bool(data.get("is_valid", False))
    expires_raw = data.get("expires_at")
    if isinstance(expires_raw, (int, float)) and expires_raw != 0:
        expires_at = int(expires_raw)
    else:
        expires_at = None
    return HealthResponse(is_valid=is_valid, expires_at=expires_at)


@router.put("/pages/{page_id}/config", response_model=PageConfigResponse)
async def put_page_config(
    page_id: int, request: PageConfigRequest, current: dict = Depends(get_current_tenant)
) -> PageConfigResponse:
    """Whole-row replace of the page_configs row for a tenant-owned page.

    `page_id` here is the INTERNAL `pages.id` (a tenant-scoped resource) —
    contrast with the internal read API below, which is keyed on the
    Facebook `page_fb_id`.
    """
    tenant_id = int(current["sub"])
    conn = get_connection(settings.db_path)
    try:
        row = conn.execute(
            "SELECT id FROM pages WHERE id = ? AND tenant_id = ? AND is_active = 1",
            (page_id, tenant_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Page not found")

        menu_str = json.dumps([m.model_dump() for m in request.menu_json])

        existing = conn.execute(
            "SELECT id FROM page_configs WHERE page_id = ?", (page_id,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE page_configs SET welcome_text = ?, menu_json = ?, "
                "escalation_psid = ?, escalation_message = ?, "
                "updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE page_id = ?",
                (
                    request.welcome_text,
                    menu_str,
                    request.escalation_psid,
                    request.escalation_message,
                    page_id,
                ),
            )
        else:
            conn.execute(
                "INSERT INTO page_configs "
                "(page_id, welcome_text, menu_json, escalation_psid, escalation_message) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    page_id,
                    request.welcome_text,
                    menu_str,
                    request.escalation_psid,
                    request.escalation_message,
                ),
            )
        conn.commit()

        config_row = conn.execute(
            "SELECT welcome_text, menu_json, escalation_psid, escalation_message, updated_at "
            "FROM page_configs WHERE page_id = ?",
            (page_id,),
        ).fetchone()
    finally:
        conn.close()

    return PageConfigResponse(
        page_id=page_id,
        welcome_text=config_row["welcome_text"],
        menu_json=[MenuItem(**item) for item in json.loads(config_row["menu_json"])],
        escalation_psid=config_row["escalation_psid"],
        escalation_message=config_row["escalation_message"],
        updated_at=config_row["updated_at"],
    )


def _require_owned_page(conn, page_id: int, tenant_id: int) -> None:
    """Raise 404 unless page_id is an active page owned by tenant_id."""
    row = conn.execute(
        "SELECT id FROM pages WHERE id = ? AND tenant_id = ? AND is_active = 1",
        (page_id, tenant_id),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Page not found")


def _validate_category_ref(conn, page_id: int, category_id: Optional[int]) -> None:
    """Raise 400 unless category_id references an existing category on page_id."""
    if category_id is None:
        return
    row = conn.execute(
        "SELECT id FROM qa_items WHERE id = ? AND page_id = ? AND type = 'category'",
        (category_id, page_id),
    ).fetchone()
    if not row:
        raise HTTPException(
            status_code=400, detail="category_id must reference a category on this page"
        )


@router.get("/pages/{page_id}/qa", response_model=list[QAItemResponse])
async def list_qa(
    page_id: int, current: dict = Depends(get_current_tenant)
) -> list[QAItemResponse]:
    """List all Q&A items (categories + questions, enabled or not) for a
    tenant-owned page. `page_id` is the INTERNAL `pages.id`."""
    tenant_id = int(current["sub"])
    conn = get_connection(settings.db_path)
    try:
        _require_owned_page(conn, page_id, tenant_id)
        rows = conn.execute(
            "SELECT id, page_id, type, title, body, category_id, enabled, created_at "
            "FROM qa_items WHERE page_id = ? ORDER BY id ASC",
            (page_id,),
        ).fetchall()
    finally:
        conn.close()

    return [
        QAItemResponse(
            id=r["id"],
            page_id=r["page_id"],
            type=r["type"],
            title=r["title"],
            body=r["body"],
            category_id=r["category_id"],
            enabled=bool(r["enabled"]),
            created_at=r["created_at"],
        )
        for r in rows
    ]


@router.post("/pages/{page_id}/qa", response_model=QAItemResponse, status_code=201)
async def create_qa(
    page_id: int, request: QAItemCreateRequest, current: dict = Depends(get_current_tenant)
) -> QAItemResponse:
    """Create a Q&A category or question on a tenant-owned page. `page_id` is
    the INTERNAL `pages.id`."""
    tenant_id = int(current["sub"])
    conn = get_connection(settings.db_path)
    try:
        _require_owned_page(conn, page_id, tenant_id)
        _validate_category_ref(conn, page_id, request.category_id)

        cur = conn.execute(
            "INSERT INTO qa_items (page_id, type, title, body, category_id, enabled) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                page_id,
                request.type,
                request.title,
                request.body,
                request.category_id,
                1 if request.enabled else 0,
            ),
        )
        conn.commit()
        new_id = cur.lastrowid
        row = conn.execute(
            "SELECT id, page_id, type, title, body, category_id, enabled, created_at "
            "FROM qa_items WHERE id = ?",
            (new_id,),
        ).fetchone()
    finally:
        conn.close()

    return QAItemResponse(
        id=row["id"],
        page_id=row["page_id"],
        type=row["type"],
        title=row["title"],
        body=row["body"],
        category_id=row["category_id"],
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
    )


def _require_owned_qa_item(conn, page_id: int, item_id: int) -> None:
    """Raise 404 unless item_id is a qa_items row belonging to page_id."""
    row = conn.execute(
        "SELECT id FROM qa_items WHERE id = ? AND page_id = ?", (item_id, page_id)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Q&A item not found")


@router.put("/pages/{page_id}/qa/{item_id}", response_model=QAItemResponse)
async def update_qa(
    page_id: int,
    item_id: int,
    request: QAItemUpdateRequest,
    current: dict = Depends(get_current_tenant),
) -> QAItemResponse:
    """Whole-row replace of a Q&A item on a tenant-owned page. `page_id` is
    the INTERNAL `pages.id`."""
    tenant_id = int(current["sub"])
    conn = get_connection(settings.db_path)
    try:
        _require_owned_page(conn, page_id, tenant_id)
        _require_owned_qa_item(conn, page_id, item_id)

        if request.category_id is not None and request.category_id == item_id:
            raise HTTPException(
                status_code=400, detail="category_id cannot reference itself"
            )
        _validate_category_ref(conn, page_id, request.category_id)

        conn.execute(
            "UPDATE qa_items SET type = ?, title = ?, body = ?, category_id = ?, "
            "enabled = ? WHERE id = ? AND page_id = ?",
            (
                request.type,
                request.title,
                request.body,
                request.category_id,
                1 if request.enabled else 0,
                item_id,
                page_id,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, page_id, type, title, body, category_id, enabled, created_at "
            "FROM qa_items WHERE id = ?",
            (item_id,),
        ).fetchone()
    finally:
        conn.close()

    return QAItemResponse(
        id=row["id"],
        page_id=row["page_id"],
        type=row["type"],
        title=row["title"],
        body=row["body"],
        category_id=row["category_id"],
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
    )


@router.delete("/pages/{page_id}/qa/{item_id}", status_code=200)
async def delete_qa(
    page_id: int, item_id: int, current: dict = Depends(get_current_tenant)
) -> dict:
    """Delete a Q&A item on a tenant-owned page. `page_id` is the INTERNAL
    `pages.id`."""
    tenant_id = int(current["sub"])
    conn = get_connection(settings.db_path)
    try:
        _require_owned_page(conn, page_id, tenant_id)
        _require_owned_qa_item(conn, page_id, item_id)

        conn.execute(
            "DELETE FROM qa_items WHERE id = ? AND page_id = ?", (item_id, page_id)
        )
        conn.commit()
    finally:
        conn.close()
    return {"detail": f"Q&A item {item_id} deleted"}


@router.get("/internal/pages/{page_fb_id}/access-token", include_in_schema=False)
async def get_internal_page_access_token(
    page_fb_id: str,
    x_internal_key: Annotated[Optional[str], Header()] = None,
) -> dict:
    if not settings.internal_secret:
        raise HTTPException(status_code=500, detail="INTERNAL_SECRET not configured")

    provided = (x_internal_key or "").encode()
    expected = settings.internal_secret.encode()
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="Forbidden")

    conn = get_connection(settings.db_path)
    try:
        row = conn.execute(
            "SELECT access_token_enc FROM pages WHERE page_fb_id = ? AND is_active = 1",
            (page_fb_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row or not row["access_token_enc"]:
        raise HTTPException(status_code=404, detail="Page not found or token not set")

    try:
        plain = decrypt_token(row["access_token_enc"])
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="Token decryption failed") from exc

    return {"access_token": plain}


@router.get(
    "/internal/pages/{page_fb_id}/config",
    include_in_schema=False,
    response_model=InternalPageConfigResponse,
)
async def get_internal_page_config(
    page_fb_id: str,
    x_internal_key: Annotated[Optional[str], Header()] = None,
) -> InternalPageConfigResponse:
    """Bot-facing config read, keyed on the Facebook page_fb_id (mirrors
    get_internal_page_access_token above, not the tenant-scoped write API)."""
    if not settings.internal_secret:
        raise HTTPException(status_code=500, detail="INTERNAL_SECRET not configured")

    provided = (x_internal_key or "").encode()
    expected = settings.internal_secret.encode()
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="Forbidden")

    conn = get_connection(settings.db_path)
    try:
        page_row = conn.execute(
            "SELECT id FROM pages WHERE page_fb_id = ? AND is_active = 1",
            (page_fb_id,),
        ).fetchone()
        if not page_row:
            raise HTTPException(status_code=404, detail="Page not found")

        config_row = conn.execute(
            "SELECT welcome_text, menu_json, escalation_psid, escalation_message "
            "FROM page_configs WHERE page_id = ?",
            (page_row["id"],),
        ).fetchone()
    finally:
        conn.close()

    if not config_row:
        return InternalPageConfigResponse(
            welcome_text="",
            menu_json=[],
            escalation_psid=None,
            escalation_message=None,
        )

    return InternalPageConfigResponse(
        welcome_text=config_row["welcome_text"],
        menu_json=[MenuItem(**item) for item in json.loads(config_row["menu_json"])],
        escalation_psid=config_row["escalation_psid"],
        escalation_message=config_row["escalation_message"],
    )
