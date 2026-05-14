import app.routers.content as content_module
import app.config as config_module
from fastapi.testclient import TestClient
from app.main import app


def write_md(path, frontmatter: str, body: str = "Body text"):
    """Helper: write a .md file with given frontmatter block."""
    path.write_text(f"---\n{frontmatter}\n---\n{body}", encoding="utf-8")


def test_vault_loads_at_startup(tmp_path, monkeypatch):
    """VAULT-01: Vault loads at startup; health shows content_count reflects loaded files."""
    write_md(tmp_path / "q1.md", "id: q1\ntype: faq\ntitle: T\nenabled: true")
    monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
    content_module._vault.clear()
    content_module._vault.update(content_module.load_vault())
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.json()["content_count"] == 1


def test_get_content_by_id(tmp_path, monkeypatch):
    """VAULT-02: GET /content/{id} returns matching item by frontmatter id."""
    write_md(tmp_path / "q1.md", "id: q1\ntype: faq\ntitle: Test Title\nenabled: true", "Answer body")
    monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
    content_module._vault.clear()
    content_module._vault.update(content_module.load_vault())
    with TestClient(app) as client:
        resp = client.get("/content/q1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "q1"
        assert data["title"] == "Test Title"
        assert data["body"] == "Answer body"


def test_get_content_missing_returns_404(tmp_path, monkeypatch):
    """VAULT-02: GET /content/{unknown_id} returns 404."""
    monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
    content_module._vault.clear()
    with TestClient(app) as client:
        resp = client.get("/content/nonexistent")
        assert resp.status_code == 404


def test_missing_vault_soft_fails(monkeypatch):
    """VAULT-01 D-03: Missing VAULT_PATH causes soft-fail — server starts, content_count = 0."""
    monkeypatch.setattr(config_module.settings, "vault_path", "/does/not/exist")
    content_module._vault.clear()
    content_module._vault.update(content_module.load_vault())
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["content_count"] == 0
        assert resp.json()["vault_loaded"] is False


def test_disabled_files_excluded(tmp_path, monkeypatch):
    """VAULT-03: Files with enabled: false are not served; enabled files are."""
    write_md(tmp_path / "enabled.md", "id: e1\ntype: faq\ntitle: E\nenabled: true")
    write_md(tmp_path / "disabled.md", "id: d1\ntype: faq\ntitle: D\nenabled: false")
    monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
    content_module._vault.clear()
    content_module._vault.update(content_module.load_vault())
    with TestClient(app) as client:
        assert client.get("/content/e1").status_code == 200
        assert client.get("/content/d1").status_code == 404


def test_malformed_frontmatter_skipped(tmp_path, monkeypatch):
    """VAULT-03: Files missing required fields are silently skipped — server does not crash."""
    write_md(tmp_path / "ok.md", "id: ok1\ntype: faq\ntitle: OK\nenabled: true")
    write_md(tmp_path / "bad.md", "enabled: true")  # missing id, type, title
    monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
    content_module._vault.clear()
    content_module._vault.update(content_module.load_vault())
    with TestClient(app) as client:
        assert len(content_module._vault) == 1


def test_enabled_string_true_rejected(tmp_path, monkeypatch):
    """VAULT-03 Pitfall 3: enabled: "true" (quoted string) must NOT be served — strict bool check."""
    write_md(tmp_path / "strEnabled.md", 'id: s1\ntype: faq\ntitle: S\nenabled: "true"')
    monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
    content_module._vault.clear()
    content_module._vault.update(content_module.load_vault())
    with TestClient(app) as client:
        assert client.get("/content/s1").status_code == 404


def test_reload_endpoint(tmp_path, monkeypatch):
    """QA-04: POST /content/reload hot-reloads vault without restart."""
    monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
    content_module._vault.clear()
    with TestClient(app) as client:
        assert client.get("/health").json()["content_count"] == 0
        write_md(tmp_path / "new.md", "id: n1\ntype: faq\ntitle: New\nenabled: true")
        resp = client.post("/content/reload")
        assert resp.status_code == 200
        assert resp.json()["reloaded"] is True
        assert resp.json()["content_count"] == 1
        assert client.get("/content/n1").status_code == 200
