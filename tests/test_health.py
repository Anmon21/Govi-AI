import app.routers.content as content_module
import app.config as config_module
from fastapi.testclient import TestClient
from app.main import app


def test_health_includes_vault_stats(monkeypatch):
    """VAULT-01: GET /health response includes status, vault_loaded, and content_count."""
    monkeypatch.setattr(config_module.settings, "vault_path", "")
    content_module._vault.clear()
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "vault_loaded" in data
        assert "content_count" in data
        assert data["status"] == "ok"
        assert data["vault_loaded"] is False
        assert data["content_count"] == 0


def test_health_vault_loaded_true_when_vault_reachable(tmp_path, monkeypatch):
    """VAULT-01: vault_loaded is True and content_count is 1 when vault has a valid enabled file."""
    (tmp_path / "q.md").write_text(
        "---\nid: q1\ntype: faq\ntitle: T\nenabled: true\n---\nBody",
        encoding="utf-8",
    )
    monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
    content_module._vault.clear()
    content_module._vault.update(content_module.load_vault())
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.json()["vault_loaded"] is True
        assert resp.json()["content_count"] == 1
