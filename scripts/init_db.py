import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import init_schema
from app.config import settings

if __name__ == "__main__":
    init_schema(settings.db_path)
    print(f"Schema initialized at {settings.db_path}")
