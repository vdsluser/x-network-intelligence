from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from xni.app import create_app
from xni.config import Settings
from xni.db import create_engine_for_path, init_database
from xni.models import Account


def _seed(db_path):
    engine = create_engine_for_path(db_path); init_database(engine)
    with Session(engine) as session:
        session.add_all([
            Account(external_user_id="1", username="alice", description="AI researcher | Python | CEO @ExampleAI", first_seen_at=None, last_seen_at=None),
            Account(external_user_id="2", username="reporter", description="경제 전문 기자 | 뉴스룸", first_seen_at=None, last_seen_at=None),
            Account(external_user_id="3", username="plain", description="hello", first_seen_at=None, last_seen_at=None),
        ])
        session.commit()
    engine.dispose()


def test_classification_api_run_aggregates_and_detail(tmp_path):
    db_path = tmp_path / "xni.db"; _seed(db_path)
    with TestClient(create_app(Settings(database_path=db_path))) as client:
        run = client.post("/api/analysis/classify", json={"classifier_version":"rule-v1","replace_version":True})
        assert run.status_code == 200
        assert run.json()["accounts_processed"] == 3
        topics = client.get("/api/analysis/topics?classifier_version=rule-v1")
        assert topics.status_code == 200
        assert any(row["topic"] == "AI" and row["account_count"] == 1 for row in topics.json())
        associations = client.get("/api/analysis/associations?type=organization&limit=20&classifier_version=rule-v1")
        assert associations.status_code == 200
        assert any(row["normalized_value"] == "exampleai" for row in associations.json())
        detail = client.get("/api/accounts/1/classification?classifier_version=rule-v1")
        assert detail.status_code == 200
        assert detail.json()["account_type"] == "Individual"
        assert any(row["topic"] == "AI" for row in detail.json()["topics"])
        assert all("evidence" in row and "confidence" in row for row in detail.json()["topics"])


def test_classification_api_errors(tmp_path):
    db_path = tmp_path / "xni.db"; _seed(db_path)
    with TestClient(create_app(Settings(database_path=db_path))) as client:
        bad = client.post("/api/analysis/classify", json={"classifier_version":"rule-v2","replace_version":True})
        assert bad.status_code == 400
        missing = client.get("/api/accounts/999/classification")
        assert missing.status_code == 404
        invalid_type = client.get("/api/analysis/associations?type=not-real")
        assert invalid_type.status_code == 400
