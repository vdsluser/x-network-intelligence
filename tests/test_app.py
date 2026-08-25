from pathlib import Path

from fastapi.testclient import TestClient

from xni.app import create_app
from xni.config import Settings


def test_health_endpoint(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "x_network.db")
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
