import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from app import fb_client
from app.auth import get_current_tenant
from app.config import settings
from app.crypto import encrypt_token
from app.db import get_connection


router = APIRouter(tags=["pages"])


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
