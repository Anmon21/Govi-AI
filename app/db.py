import sqlite3


# get_connection — callers MUST use ? placeholders, never f-strings, for SQL parameters
def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(db_path: str) -> None:
    conn = get_connection(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tenants (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            email         TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            is_active     INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        );

        CREATE TABLE IF NOT EXISTS pages (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id        INTEGER NOT NULL REFERENCES tenants(id),
            page_fb_id       TEXT    NOT NULL UNIQUE,
            page_name        TEXT    NOT NULL,
            access_token_enc TEXT,
            is_active        INTEGER NOT NULL DEFAULT 1,
            created_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        );

        CREATE TABLE IF NOT EXISTS page_configs (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            page_id            INTEGER NOT NULL UNIQUE REFERENCES pages(id),
            welcome_text       TEXT    NOT NULL DEFAULT '',
            menu_json          TEXT    NOT NULL DEFAULT '[]',
            escalation_psid    TEXT,
            escalation_message TEXT,
            updated_at         TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        );

        CREATE TABLE IF NOT EXISTS qa_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            page_id     INTEGER NOT NULL REFERENCES pages(id),
            type        TEXT    NOT NULL CHECK(type IN ('category', 'question')),
            title       TEXT    NOT NULL,
            body        TEXT    NOT NULL DEFAULT '',
            category_id INTEGER REFERENCES qa_items(id),
            enabled     INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        );

        CREATE INDEX IF NOT EXISTS idx_pages_tenant_id      ON pages(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_page_configs_page_id ON page_configs(page_id);
        CREATE INDEX IF NOT EXISTS idx_qa_items_page_id     ON qa_items(page_id);
        CREATE INDEX IF NOT EXISTS idx_qa_items_category_id ON qa_items(category_id);
    """)
    conn.commit()
    conn.close()
