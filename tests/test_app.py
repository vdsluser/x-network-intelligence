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


def test_manual_import_endpoint_persists_snapshot(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "x_network.db")
    payload = {
        "users": [{
            "id": "1",
            "username": "alice",
            "display_name": "Alice",
            "description": "AI",
            "followers_count": 10,
            "followings_count": 2,
            "created_at": "Sun Nov 05 08:05:40 +0000 2023",
            "tweets_count": 20,
            "verified": False,
            "protected": False,
            "profile_image_url": "https://example.com/alice.jpg",
        }],
        "targetLabel": "target_user",
        "mode": "following",
    }

    with TestClient(create_app(settings)) as client:
        response = client.post("/api/import/manual", json=payload)

    assert response.status_code == 200
    assert response.json() == {
        "target": "target_user",
        "snapshot_id": 1,
        "total": 1,
        "added": 1,
        "removed": 0,
        "unchanged": 0,
    }
