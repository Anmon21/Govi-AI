import httpx
from fastapi import HTTPException

from app.config import settings


GRAPH_BASE = "https://graph.facebook.com/v25.0"


def _require_fb_settings() -> None:
    if not settings.fb_app_id or not settings.fb_app_secret or not settings.fb_redirect_uri:
        raise RuntimeError(
            "FACEBOOK_APP_ID / FACEBOOK_APP_SECRET / FACEBOOK_REDIRECT_URI not configured."
        )


def exchange_code_for_short_token(code: str) -> str:
    _require_fb_settings()
    resp = httpx.get(
        f"{GRAPH_BASE}/oauth/access_token",
        params={
            "client_id": settings.fb_app_id,
            "redirect_uri": settings.fb_redirect_uri,
            "client_secret": settings.fb_app_secret,
            "code": code,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"]["message"])
    return data["access_token"]


def exchange_for_long_lived_token(short_token: str) -> str:
    _require_fb_settings()
    resp = httpx.get(
        f"{GRAPH_BASE}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": settings.fb_app_id,
            "client_secret": settings.fb_app_secret,
            "fb_exchange_token": short_token,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"]["message"])
    return data["access_token"]


def get_user_pages(long_lived_token: str) -> list[dict]:
    _require_fb_settings()
    resp = httpx.get(
        f"{GRAPH_BASE}/me/accounts",
        params={"access_token": long_lived_token},
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"]["message"])
    return data.get("data", [])


def subscribe_page_webhook(page_fb_id: str, page_access_token: str) -> None:
    resp = httpx.post(
        f"{GRAPH_BASE}/{page_fb_id}/subscribed_apps",
        params={
            "subscribed_fields": "messages,messaging_postbacks,messaging_referrals",
            "access_token": page_access_token,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"]["message"])


def unsubscribe_page_webhook(page_fb_id: str, page_access_token: str) -> None:
    try:
        httpx.delete(
            f"{GRAPH_BASE}/{page_fb_id}/subscribed_apps",
            params={"access_token": page_access_token},
        )
    except Exception:
        pass


def check_token_health(page_access_token: str) -> bool:
    app_token = f"{settings.fb_app_id}|{settings.fb_app_secret}"
    try:
        resp = httpx.get(
            f"{GRAPH_BASE}/debug_token",
            params={
                "input_token": page_access_token,
                "access_token": app_token,
            },
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        return bool(data.get("is_valid", False))
    except Exception:
        return False
