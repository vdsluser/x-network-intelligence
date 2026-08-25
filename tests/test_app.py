from pathlib import Path
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from xni.app import create_app
from xni.config import Settings
from xni.db import create_engine_for_path, init_database
from xni.models import Account, Target, TargetRelationship


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


ANALYSIS_NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)


def _seed_analysis_database(db_path: Path) -> None:
    engine = create_engine_for_path(db_path)
    init_database(engine)
    with Session(engine) as session:
        accounts = {}
        for external_id, username, age, following in [
            ("1", "one", 1000, 500),
            ("2", "two", 1000, 500),
            ("3", "three", 1000, 500),
            ("ta", "alpha", 15, 30),
            ("tb", "beta", 18, 25),
        ]:
            account = Account(
                external_user_id=external_id,
                username=username,
                created_at=ANALYSIS_NOW - timedelta(days=age),
                following_count=following,
                first_seen_at=ANALYSIS_NOW,
                last_seen_at=ANALYSIS_NOW,
            )
            session.add(account)
            accounts[username] = account
        session.flush()
        alpha = Target(username="alpha", first_tracked_at=ANALYSIS_NOW)
        beta = Target(username="beta", first_tracked_at=ANALYSIS_NOW)
        session.add_all([alpha, beta])
        session.flush()
        for target, names in [(alpha, ["one", "two", "three"]), (beta, ["two", "three"])]:
            for name in names:
                session.add(TargetRelationship(
                    target_id=target.id,
                    account_id=accounts[name].id,
                    first_seen_at=ANALYSIS_NOW,
                    last_seen_at=ANALYSIS_NOW,
                    is_active=True,
                ))
        session.commit()
    engine.dispose()


def test_analysis_endpoints_return_observable_network_metrics(tmp_path: Path) -> None:
    db_path = tmp_path / "x_network.db"
    _seed_analysis_database(db_path)
    settings = Settings(database_path=db_path)
    with TestClient(create_app(settings)) as client:
        new_accounts = client.get("/api/analysis/new-accounts?new_account_days=90&low_following_max=100")
        similarity = client.get("/api/analysis/similarity?min_jaccard=0.5&min_shared=2")
        cohorts = client.get("/api/analysis/cohorts?new_account_days=90&low_following_max=100&min_jaccard=0.5&min_shared=2")
        central = client.get("/api/analysis/central-nodes?limit=5")

    assert new_accounts.status_code == 200
    assert [item["username"] for item in new_accounts.json()] == ["alpha", "beta"]
    assert similarity.status_code == 200
    assert similarity.json()[0]["shared_count"] == 2
    assert cohorts.status_code == 200
    assert [(item["target_a"], item["target_b"]) for item in cohorts.json()] == [("alpha", "beta")]
    assert central.status_code == 200
    assert central.json()[0]["username"] in {"two", "three"}
    assert central.json()[0]["target_coverage"] == 1.0


def _batch_user(account_id: str, username: str) -> dict:
    return {
        "id": account_id,
        "username": username,
        "display_name": username.title(),
        "description": "candidate",
        "followers_count": 10,
        "followings_count": 20,
        "created_at": "Mon Aug 24 00:00:00 +0000 2026",
        "tweets_count": 20,
        "verified": False,
        "protected": False,
        "profile_image_url": None,
    }


def test_expansion_queue_workflow_and_batch_import_endpoints(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "x_network.db")
    body = {
        "payloads": [
            {"users": [_batch_user("1", "shared")], "targetLabel": "alpha", "mode": "following"},
            {"users": [_batch_user("1", "shared"), _batch_user("2", "candidate")], "targetLabel": "beta", "mode": "following"},
        ],
        "new_account_days": 90,
        "low_following_max": 100,
        "min_jaccard": 0.0,
        "min_shared": 1,
        "central_limit": 5,
    }

    with TestClient(create_app(settings)) as client:
        batch = client.post("/api/import/manual/batch", json=body)
        queue = client.get("/api/expansion/queue")
        candidate_id = next(item["id"] for item in queue.json() if item["username"] == "candidate")
        promoted = client.post(f"/api/expansion/queue/{candidate_id}/promote")
        promoted_queue = client.get("/api/expansion/queue", params={"status": "promoted"})

    assert batch.status_code == 200
    assert batch.json()["analysis"]["targets"] == 2
    assert batch.json()["analysis"]["central_nodes"][0]["username"] == "shared"
    assert queue.status_code == 200
    assert {item["username"] for item in queue.json()} == {"shared", "candidate"}
    assert promoted.status_code == 200
    assert promoted.json()["target_username"] == "candidate"
    assert {item["username"] for item in promoted_queue.json()} == {"candidate"}
