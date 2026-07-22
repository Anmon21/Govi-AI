from fastapi.testclient import TestClient
from app.main import app


def test_health_ok():
    """GET /health returns 200 with only the status field — legacy fields are gone."""
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
