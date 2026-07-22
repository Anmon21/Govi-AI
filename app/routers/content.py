import hmac
from typing import Annotated, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from app.config import settings
from app.db import get_connection

router = APIRouter(prefix="/content", tags=["content"])


class ContentResponse(BaseModel):
    id: str
    type: str
    title: str
    body: str


class ContentListItem(BaseModel):
    id: str
    type: str
    title: str


class ContentListResponse(BaseModel):
    items: list[ContentListItem]


def _check_internal_key(x_internal_key: Optional[str]) -> None:
    if not settings.internal_secret:
        raise HTTPException(status_code=500, detail="INTERNAL_SECRET not configured")

    provided = (x_internal_key or "").encode()
    expected = settings.internal_secret.encode()
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="Forbidden")


def _resolve_page_id(conn, page_fb_id: str) -> int:
    """Resolve a Facebook page_fb_id to the internal pages.id; 404 if not an active page."""
    row = conn.execute(
        "SELECT id FROM pages WHERE page_fb_id = ? AND is_active = 1",
        (page_fb_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Page not found")
    return row["id"]


@router.get("", response_model=ContentListResponse)
async def list_content(
    page_id: str = Query(..., description="Required. The Facebook page_fb_id (not the internal pages.id)."),
    type: str = Query("", description="Required. Filter by item type, e.g. 'category' or 'question'."),
    category: Optional[str] = Query(None, description="Optional. When type='question', restrict to a category id."),
    x_internal_key: Annotated[Optional[str], Header()] = None,
):
    _check_internal_key(x_internal_key)
    if not type:
        raise HTTPException(status_code=400, detail="type query parameter is required")

    conn = get_connection(settings.db_path)
    try:
        internal_page_id = _resolve_page_id(conn, page_id)

        category_id: Optional[int] = None
        if category is not None:
            try:
                category_id = int(category)
            except ValueError:
                return ContentListResponse(items=[])

        if category_id is not None:
            rows = conn.execute(
                "SELECT id, type, title FROM qa_items "
                "WHERE page_id = ? AND type = ? AND enabled = 1 AND category_id = ? "
                "ORDER BY id ASC",
                (internal_page_id, type, category_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, type, title FROM qa_items "
                "WHERE page_id = ? AND type = ? AND enabled = 1 "
                "ORDER BY id ASC",
                (internal_page_id, type),
            ).fetchall()
    finally:
        conn.close()

    items = [
        ContentListItem(id=str(row["id"]), type=row["type"], title=row["title"])
        for row in rows
    ]
    return ContentListResponse(items=items)


@router.get("/{content_id}", response_model=ContentResponse)
async def get_content(
    content_id: str,
    page_id: str = Query(..., description="Required. The Facebook page_fb_id (not the internal pages.id)."),
    x_internal_key: Annotated[Optional[str], Header()] = None,
):
    _check_internal_key(x_internal_key)

    try:
        item_id = int(content_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Content not found")

    conn = get_connection(settings.db_path)
    try:
        internal_page_id = _resolve_page_id(conn, page_id)
        row = conn.execute(
            "SELECT id, type, title, body FROM qa_items "
            "WHERE id = ? AND page_id = ? AND enabled = 1",
            (item_id, internal_page_id),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Content not found")
    return ContentResponse(id=str(row["id"]), type=row["type"], title=row["title"], body=row["body"])
