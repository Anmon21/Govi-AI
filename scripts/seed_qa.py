import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml
import frontmatter

from app.config import settings
from app.db import get_connection


def load_vault_items() -> list[dict]:
    """Scan settings.vault_path for enabled *.md items with valid frontmatter.

    Reproduces the vault frontmatter-parsing logic (load_vault) locally so
    this script has no dependency on the retired content router module.
    """
    vault_path = settings.vault_path
    items: list[dict] = []
    if not vault_path or not os.path.isdir(vault_path):
        print(f"VAULT_PATH not set or directory missing: {vault_path!r}")
        return items

    for entry in os.scandir(vault_path):
        if not entry.is_file() or not entry.name.endswith(".md"):
            continue
        try:
            with open(entry.path, encoding="utf-8") as f:
                post = frontmatter.load(f)
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
            print(f"Skipping {entry.name}: {e}")
            continue

        meta = post.metadata
        if not isinstance(meta.get("enabled"), bool) or not meta["enabled"]:
            continue

        content_id = meta.get("id")
        if not isinstance(content_id, str) or not content_id:
            print(f"Skipping {entry.name}: missing or non-string 'id'")
            continue

        if not all(isinstance(meta.get(k), str) and meta.get(k) for k in ("type", "title")):
            print(f"Skipping {entry.name}: missing required string fields (type, title)")
            continue

        category_value = meta.get("category")
        if category_value is not None and (not isinstance(category_value, str) or not category_value):
            print(f"Skipping {entry.name}: 'category' present but not a non-empty string")
            continue

        items.append({
            "id": content_id,
            "type": meta["type"],
            "title": meta["title"],
            "category": category_value,
            "body": post.content,
        })

    return items


def seed(page_fb_id: str) -> None:
    """Resolve page_fb_id to pages.id, wipe+reload its qa_items from the
    vault (idempotent), and ensure a default page_configs row exists."""
    conn = get_connection(settings.db_path)
    try:
        row = conn.execute(
            "SELECT id FROM pages WHERE page_fb_id = ?",
            (page_fb_id,),
        ).fetchone()
        if not row:
            print(f"No page found with page_fb_id={page_fb_id!r}")
            sys.exit(1)
        page_id = row["id"]

        items = load_vault_items()

        if not items:
            print(f"Refusing to seed: no valid vault items found under {settings.vault_path!r}. Existing content for {page_fb_id!r} left intact.")
            sys.exit(1)

        conn.execute("DELETE FROM qa_items WHERE page_id = ?", (page_id,))

        category_map: dict[str, int] = {}
        category_count = 0
        for item in items:
            if item["type"] != "category":
                continue
            cur = conn.execute(
                "INSERT INTO qa_items (page_id, type, title, body, enabled) "
                "VALUES (?, 'category', ?, ?, 1)",
                (page_id, item["title"], item["body"]),
            )
            category_map[item["id"]] = cur.lastrowid
            category_count += 1

        question_count = 0
        for item in items:
            if item["type"] != "question":
                continue
            category_id = None
            if item["category"] is not None:
                category_id = category_map.get(item["category"])
                if category_id is None:
                    print(f"Skipping question {item['id']!r}: unknown category {item['category']!r}")
                    continue
            conn.execute(
                "INSERT INTO qa_items (page_id, type, title, body, category_id, enabled) "
                "VALUES (?, 'question', ?, ?, ?, 1)",
                (page_id, item["title"], item["body"], category_id),
            )
            question_count += 1

        conn.execute(
            "INSERT INTO page_configs (page_id, welcome_text, menu_json) "
            "SELECT ?, '', '[]' WHERE NOT EXISTS "
            "(SELECT id FROM page_configs WHERE page_id = ?)",
            (page_id, page_id),
        )

        conn.commit()
        print(f"Seeded {category_count} categories, {question_count} questions for page {page_fb_id}")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="One-time migration of Obsidian vault Q&A content into the DB for a page."
    )
    parser.add_argument("--page-fb-id", required=True, help="Facebook Page ID to seed Q&A content for.")
    args = parser.parse_args()
    seed(args.page_fb_id)
