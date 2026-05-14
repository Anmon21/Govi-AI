import pytest
from fastapi.testclient import TestClient

import app.config as config_module
import app.routers.content as content_module
from app.main import app


def write_md(path, frontmatter_block: str, body: str = "Body"):
    """Write a .md file with given frontmatter block and body."""
    path.write_text(f"---\n{frontmatter_block}\n---\n{body}", encoding="utf-8")


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient with vault_path pointing to a controlled tmp directory."""
    monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
    content_module._vault.clear()
    content_module._vault.update(content_module.load_vault())
    with TestClient(app) as c:
        yield c
    content_module._vault.clear()


@pytest.fixture
def vault_dir(tmp_path):
    """Return tmp_path for tests that need to write vault files directly."""
    return tmp_path
