import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

import app.config as config_module
from app.db import init_schema, get_connection
from scripts.seed_qa import seed

VAULT_SAMPLE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vault-sample"
)


@pytest.fixture
def seed_db(tmp_path, monkeypatch):
    """tmp-path SQLite DB with a tenant + page row; vault_path points at vault-sample/."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(config_module.settings, "db_path", db_path)
    monkeypatch.setattr(config_module.settings, "vault_path", VAULT_SAMPLE_DIR)
    init_schema(db_path)

    page_fb_id = "fb-seed-test-page"
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO tenants (email, password_hash) VALUES (?, ?)",
            ("seed-tenant@test.local", "hash"),
        )
        conn.commit()
        tenant_id = conn.execute("SELECT id FROM tenants").fetchone()["id"]
        conn.execute(
            "INSERT INTO pages (tenant_id, page_fb_id, page_name) VALUES (?, ?, ?)",
            (tenant_id, page_fb_id, "Seed Test Page"),
        )
        conn.commit()
        page_id = conn.execute(
            "SELECT id FROM pages WHERE page_fb_id = ?", (page_fb_id,)
        ).fetchone()["id"]
    finally:
        conn.close()

    return SimpleNamespace(db_path=db_path, page_fb_id=page_fb_id, page_id=page_id)


def test_seed_migrates_categories_and_questions(seed_db):
    seed(seed_db.page_fb_id)
    conn = get_connection(seed_db.db_path)
    try:
        categories = conn.execute(
            "SELECT id FROM qa_items WHERE page_id = ? AND type = 'category'",
            (seed_db.page_id,),
        ).fetchall()
        questions = conn.execute(
            "SELECT id FROM qa_items WHERE page_id = ? AND type = 'question'",
            (seed_db.page_id,),
        ).fetchall()
    finally:
        conn.close()
    # vault-sample/ fixtures: cat-products, cat-shipping (2 categories)
    # q-products-01, q-shipping-01, q-shipping-02 (3 questions)
    assert len(categories) == 2
    assert len(questions) == 3


def test_seed_resolves_category_fk(seed_db):
    seed(seed_db.page_fb_id)
    conn = get_connection(seed_db.db_path)
    try:
        category_ids = {
            row["id"]
            for row in conn.execute(
                "SELECT id FROM qa_items WHERE page_id = ? AND type = 'category'",
                (seed_db.page_id,),
            ).fetchall()
        }
        questions = conn.execute(
            "SELECT category_id, page_id FROM qa_items WHERE page_id = ? AND type = 'question'",
            (seed_db.page_id,),
        ).fetchall()
    finally:
        conn.close()
    assert len(questions) == 3
    for question in questions:
        assert question["category_id"] in category_ids
        assert question["page_id"] == seed_db.page_id


def test_seed_is_idempotent(seed_db):
    seed(seed_db.page_fb_id)
    conn = get_connection(seed_db.db_path)
    try:
        first_count = conn.execute(
            "SELECT COUNT(*) AS c FROM qa_items WHERE page_id = ?", (seed_db.page_id,)
        ).fetchone()["c"]
    finally:
        conn.close()

    seed(seed_db.page_fb_id)
    conn = get_connection(seed_db.db_path)
    try:
        second_count = conn.execute(
            "SELECT COUNT(*) AS c FROM qa_items WHERE page_id = ?", (seed_db.page_id,)
        ).fetchone()["c"]
    finally:
        conn.close()

    assert first_count == second_count == 5


def test_seed_creates_page_configs_row(seed_db):
    seed(seed_db.page_fb_id)
    conn = get_connection(seed_db.db_path)
    try:
        row = conn.execute(
            "SELECT welcome_text, menu_json FROM page_configs WHERE page_id = ?",
            (seed_db.page_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row["welcome_text"] == ""
    assert row["menu_json"] == "[]"


def test_seed_unknown_page_fb_id_exits(seed_db):
    with pytest.raises(SystemExit):
        seed("no-such-page-fb-id")
    conn = get_connection(seed_db.db_path)
    try:
        count = conn.execute("SELECT COUNT(*) AS c FROM qa_items").fetchone()["c"]
    finally:
        conn.close()
    assert count == 0


# DB-02 — fail-closed on empty/misconfigured vault (13-REVIEW.md CR-01)


@pytest.mark.parametrize("bad_vault_kind", ["unset", "missing_dir", "empty_dir"])
def test_seed_refuses_and_preserves_content_when_vault_yields_nothing(
    seed_db, monkeypatch, tmp_path, capsys, bad_vault_kind
):
    """Expected RED behaviour before the Task 2 fix: the `pytest.raises(SystemExit)`
    block below fails because today seed() returns normally after wiping the rows
    instead of raising."""
    # Precondition: seed with the valid vault first so the page has real content to lose.
    seed(seed_db.page_fb_id)
    conn = get_connection(seed_db.db_path)
    try:
        categories = conn.execute(
            "SELECT id FROM qa_items WHERE page_id = ? AND type = 'category'",
            (seed_db.page_id,),
        ).fetchall()
        questions = conn.execute(
            "SELECT id FROM qa_items WHERE page_id = ? AND type = 'question'",
            (seed_db.page_id,),
        ).fetchall()
    finally:
        conn.close()
    assert len(categories) == 2
    assert len(questions) == 3

    # capsys accumulates until read — drain the precondition's success output here
    # so it cannot pollute the "Seeded" not in out assertion below.
    capsys.readouterr()

    if bad_vault_kind == "unset":
        bad_path = ""
    elif bad_vault_kind == "missing_dir":
        bad_path = str(tmp_path / "no-such-vault-dir")
    else:
        empty_dir = tmp_path / "empty-vault-dir"
        empty_dir.mkdir()
        bad_path = str(empty_dir)
    monkeypatch.setattr(config_module.settings, "vault_path", bad_path)

    with pytest.raises(SystemExit) as exc:
        seed(seed_db.page_fb_id)
    assert exc.value.code == 1

    conn = get_connection(seed_db.db_path)
    try:
        categories = conn.execute(
            "SELECT id FROM qa_items WHERE page_id = ? AND type = 'category'",
            (seed_db.page_id,),
        ).fetchall()
        questions = conn.execute(
            "SELECT id FROM qa_items WHERE page_id = ? AND type = 'question'",
            (seed_db.page_id,),
        ).fetchall()
    finally:
        conn.close()
    assert len(categories) == 2
    assert len(questions) == 3

    out = capsys.readouterr().out
    assert "Refusing to seed" in out
    assert "Seeded" not in out


def test_seed_cli_exits_non_zero_and_preserves_content_on_bad_vault_path(seed_db, tmp_path):
    """Expected RED behaviour before the Task 2 fix: fails on
    `assert proc.returncode != 0` because today the script exits 0."""
    repo_root = os.path.dirname(VAULT_SAMPLE_DIR)

    # Precondition: seed with the valid vault first, then close every connection
    # before the subprocess starts (it opens the same SQLite file).
    seed(seed_db.page_fb_id)
    conn = get_connection(seed_db.db_path)
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM qa_items WHERE page_id = ?", (seed_db.page_id,)
        ).fetchone()["c"]
    finally:
        conn.close()
    assert count == 5

    proc = subprocess.run(
        [
            sys.executable,
            os.path.join(repo_root, "scripts", "seed_qa.py"),
            "--page-fb-id",
            seed_db.page_fb_id,
        ],
        cwd=repo_root,
        env={
            **os.environ,
            "DB_PATH": seed_db.db_path,
            "VAULT_PATH": str(tmp_path / "no-such-vault-dir"),
        },
        capture_output=True,
        text=True,
    )

    assert proc.returncode != 0
    assert "Refusing to seed" in proc.stdout
    assert "Seeded" not in proc.stdout

    conn = get_connection(seed_db.db_path)
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM qa_items WHERE page_id = ?", (seed_db.page_id,)
        ).fetchone()["c"]
    finally:
        conn.close()
    assert count == 5
