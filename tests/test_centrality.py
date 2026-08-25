from datetime import datetime, timezone
from sqlalchemy.orm import Session
from xni.analysis.centrality import rank_central_nodes
from xni.db import create_engine_for_path, init_database
from xni.models import Account, Target, TargetRelationship

NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)


def test_rank_central_nodes_finds_global_hub_and_bridge_score(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db"); init_database(engine)
    with Session(engine) as session:
        hub = Account(external_user_id="hub", username="hub", first_seen_at=NOW, last_seen_at=NOW)
        left = Account(external_user_id="left", username="left", first_seen_at=NOW, last_seen_at=NOW)
        right = Account(external_user_id="right", username="right", first_seen_at=NOW, last_seen_at=NOW)
        session.add_all([hub, left, right]); session.flush()
        targets = [Target(username=name, first_tracked_at=NOW) for name in ["a", "b", "c"]]
        session.add_all(targets); session.flush()
        for target in targets:
            session.add(TargetRelationship(target_id=target.id, account_id=hub.id, first_seen_at=NOW, last_seen_at=NOW, is_active=True))
        session.add(TargetRelationship(target_id=targets[0].id, account_id=left.id, first_seen_at=NOW, last_seen_at=NOW, is_active=True))
        session.add(TargetRelationship(target_id=targets[2].id, account_id=right.id, first_seen_at=NOW, last_seen_at=NOW, is_active=True))
        session.commit()
        scores = rank_central_nodes(session, limit=10)
    assert scores[0].username == "hub"
    assert scores[0].followed_by_targets == 3
    assert scores[0].target_coverage == 1.0
    assert scores[0].betweenness > 0
