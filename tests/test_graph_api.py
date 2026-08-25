from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from xni.app import create_app
from xni.config import Settings
from xni.db import create_engine_for_path, init_database
from xni.models import Account, AccountClassification, AccountTopic, Target, TargetRelationship

NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)


def seed(db_path):
    engine = create_engine_for_path(db_path)
    init_database(engine)
    with Session(engine) as session:
        a = Account(external_user_id="1", username="shared", first_seen_at=NOW, last_seen_at=NOW)
        session.add(a); session.flush()
        alpha = Target(username="alpha", first_tracked_at=NOW)
        beta = Target(username="beta", first_tracked_at=NOW)
        session.add_all([alpha,beta]); session.flush()
        session.add_all([
            TargetRelationship(target_id=alpha.id, account_id=a.id, first_seen_at=NOW, last_seen_at=NOW, is_active=True),
            TargetRelationship(target_id=beta.id, account_id=a.id, first_seen_at=NOW, last_seen_at=NOW, is_active=True),
            AccountTopic(account_id=a.id, topic="AI", source="bio_rule", evidence="AI", confidence=.9, classifier_version="rule-v1", analyzed_at=NOW),
            AccountClassification(account_id=a.id, account_type="Company", source="bio_rule", evidence="company", confidence=.9, classifier_version="rule-v1", analyzed_at=NOW),
        ])
        session.commit()
    engine.dispose()


def test_graph_and_options_endpoints(tmp_path):
    db = tmp_path / "xni.db"; seed(db)
    with TestClient(create_app(Settings(database_path=db))) as client:
        graph = client.get("/api/graph")
        options = client.get("/api/graph/options")
    assert graph.status_code == 200
    assert graph.json()["meta"]["account_count"] == 1
    assert options.status_code == 200
    assert options.json()["targets"] == ["alpha", "beta"]
    assert options.json()["topics"] == ["AI"]
    assert options.json()["account_types"] == ["Company"]


def test_graph_endpoint_validation_statuses(tmp_path):
    db = tmp_path / "xni.db"; seed(db)
    with TestClient(create_app(Settings(database_path=db))) as client:
        bad_version = client.get("/api/graph", params={"classifier_version":"bad"})
        missing_target = client.get("/api/graph", params={"target":"missing"})
        bad_topic = client.get("/api/graph", params={"topic":"Missing"})
        bad_type = client.get("/api/graph", params={"account_type":"Missing"})
    assert bad_version.status_code == 400
    assert missing_target.status_code == 404
    assert bad_topic.status_code == 400
    assert bad_type.status_code == 400


def test_empty_graph_endpoint_is_valid(tmp_path):
    db = tmp_path / "xni.db"
    with TestClient(create_app(Settings(database_path=db))) as client:
        graph = client.get("/api/graph")
    assert graph.status_code == 200
    assert graph.json()["nodes"] == []
    assert graph.json()["edges"] == []
