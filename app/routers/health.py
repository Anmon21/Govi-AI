import os

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings
from app.routers import content

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    vault_loaded: bool
    content_count: int


@router.get("", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="ok",
        vault_loaded=bool(settings.vault_path) and os.path.isdir(settings.vault_path),
        content_count=len(content._vault),
    )
