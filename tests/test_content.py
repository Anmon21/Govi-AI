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


def test_list_categories_only(tmp_path, monkeypatch):
    """QA-01: GET /content?type=category lists only category-type items, sorted by id."""
    write_md(tmp_path / "cat-shipping.md",
             "id: cat-shipping\ntype: category\ntitle: Shipping\nenabled: true")
    write_md(tmp_path / "cat-products.md",
             "id: cat-products\ntype: category\ntitle: Products\nenabled: true")
    write_md(tmp_path / "q-1.md",
             "id: q-1\ntype: question\ntitle: Q1\ncategory: cat-shipping\nenabled: true",
             "Answer A")
    monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
    content_module._vault.clear()
    content_module._vault.update(content_module.load_vault())
    with TestClient(app) as client:
        resp = client.get("/content?type=category")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        ids = [item["id"] for item in data["items"]]
        assert ids == ["cat-products", "cat-shipping"]  # sorted ascending
        assert all(item["type"] == "category" for item in data["items"])
        assert all(set(item.keys()) == {"id", "type", "title"} for item in data["items"])


def test_list_questions_filtered_by_category(tmp_path, monkeypatch):
    """QA-02: GET /content?type=question&category=X returns only questions tagged with that category."""
    write_md(tmp_path / "cat-shipping.md",
             "id: cat-shipping\ntype: category\ntitle: Shipping\nenabled: true")
    write_md(tmp_path / "cat-products.md",
             "id: cat-products\ntype: category\ntitle: Products\nenabled: true")
    write_md(tmp_path / "q-ship-1.md",
             "id: q-ship-1\ntype: question\ntitle: Q ship 1\ncategory: cat-shipping\nenabled: true",
             "ship answer 1")
    write_md(tmp_path / "q-ship-2.md",
             "id: q-ship-2\ntype: question\ntitle: Q ship 2\ncategory: cat-shipping\nenabled: true",
             "ship answer 2")
    write_md(tmp_path / "q-prod-1.md",
             "id: q-prod-1\ntype: question\ntitle: Q prod 1\ncategory: cat-products\nenabled: true",
             "prod answer 1")
    monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
    content_module._vault.clear()
    content_module._vault.update(content_module.load_vault())
    with TestClient(app) as client:
        resp = client.get("/content?type=question&category=cat-shipping")
        assert resp.status_code == 200
        ids = sorted(item["id"] for item in resp.json()["items"])
        assert ids == ["q-ship-1", "q-ship-2"]


def test_list_unknown_category_returns_empty(tmp_path, monkeypatch):
    """QA-02: Unknown category -> 200 with empty items, not 404."""
    write_md(tmp_path / "cat-shipping.md",
             "id: cat-shipping\ntype: category\ntitle: Shipping\nenabled: true")
    monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
    content_module._vault.clear()
    content_module._vault.update(content_module.load_vault())
    with TestClient(app) as client:
        resp = client.get("/content?type=question&category=does-not-exist")
        assert resp.status_code == 200
        assert resp.json() == {"items": []}


def test_list_missing_type_returns_400(tmp_path, monkeypatch):
    """Listing endpoint requires `type` query parameter; empty or missing -> 400 with our detail."""
    monkeypatch.setattr(config_module.settings, "vault_path", str(tmp_path))
    content_module._vault.clear()
    with TestClient(app) as client:
        # Empty type=
        resp = client.get("/content?type=")
        assert resp.status_code == 400
        assert resp.json() == {"detail": "type query parameter is required"}
        # No query string at all — must reach the same handler (route ordering)
        resp = client.get("/content")
        assert resp.status_code == 400
        assert resp.json() == {"detail": "type query parameter is required"}
