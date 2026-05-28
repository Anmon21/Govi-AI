import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passlib.context import CryptContext

from app.db import init_schema, get_connection
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

if __name__ == "__main__":
    init_schema(settings.db_path)
    print(f"Schema initialized at {settings.db_path}")

    if not settings.super_admin_email or not settings.super_admin_password:
        raise RuntimeError("SUPER_ADMIN_EMAIL and SUPER_ADMIN_PASSWORD must be set in .env.")

    conn = get_connection(settings.db_path)
    try:
        existing = conn.execute(
            "SELECT id FROM tenants WHERE is_super_admin = 1"
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO tenants (email, password_hash, is_super_admin)"
                " SELECT ?, ?, 1 WHERE NOT EXISTS"
                " (SELECT id FROM tenants WHERE is_super_admin = 1)",
                (settings.super_admin_email, pwd_context.hash(settings.super_admin_password)),
            )
            conn.commit()
            print(f"Super-admin seeded: {settings.super_admin_email}")
        else:
            print("Super-admin row already present (idempotent skip)")
    finally:
        conn.close()
