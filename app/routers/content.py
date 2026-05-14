import logging
import os
import yaml
import frontmatter
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content", tags=["content"])

_vault: dict[str, dict] = {}


class ContentResponse(BaseModel):
    id: str
    type: str
    title: str
    body: str


def load_vault() -> dict[str, dict]:
    vault_path = settings.vault_path
    if not vault_path or not os.path.isdir(vault_path):
        logger.warning("VAULT_PATH not set or directory missing — starting with empty content")
        return {}

    result: dict[str, dict] = {}
    for entry in os.scandir(vault_path):
        if not entry.is_file() or not entry.name.endswith(".md"):
            continue
        try:
            with open(entry.path, encoding="utf-8") as f:
                post = frontmatter.load(f)
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
            logger.warning("Skipping %s: %s", entry.name, e)
            continue

        meta = post.metadata
        if not isinstance(meta.get("enabled"), bool) or not meta["enabled"]:
            continue

        content_id = meta.get("id")
        if not isinstance(content_id, str) or not content_id:
            logger.warning("Skipping %s: missing or non-string 'id'", entry.name)
            continue

        if content_id in result:
            logger.warning("ID collision: '%s' from %s (skipping duplicate)", content_id, entry.name)
            continue

        if not all(isinstance(meta.get(k), str) and meta.get(k) for k in ("type", "title")):
            logger.warning("Skipping %s: missing required string fields (type, title)", entry.name)
            continue

        result[content_id] = {
            "id": content_id,
            "type": meta["type"],
            "title": meta["title"],
            "body": post.content,
        }

    return result


@router.get("/{content_id}", response_model=ContentResponse)
async def get_content(content_id: str):
    item = _vault.get(content_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Content not found")
    return ContentResponse(**item)


@router.post("/reload")
async def reload_vault():
    global _vault
    new_vault = load_vault()
    _vault = new_vault
    return {"reloaded": True, "content_count": len(_vault)}
