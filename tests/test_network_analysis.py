from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from xni.analysis.network import compare_following_sets, find_new_account_cohort_pairs, find_similarity_pairs
from xni.db import create_engine_for_path, init_database
from xni.models import Account, Target, TargetRelationship

NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)


def _seed(session: Session):
    accounts = {}
    for external_id, username, age, following in [
        ("1", "one", 10, 20), ("2", "two", 10, 20), ("3", "three", 10, 20),
        ("4", "four", 1000, 500), ("5", "five", 1000, 500),
        ("ta", "alpha", 15, 30), ("tb", "beta", 18, 25), ("tc", "gamma", 300, 30),
    ]:
        account = Account(
            external_user_id=external_id, username=username,
            created_at=NOW - timedelta(days=age), following_count=following,
            first_seen_at=NOW, last_seen_at=NOW,
        )
        session.add(account); accounts[username] = account
    session.flush()
    targets = {}
    for username in ["alpha", "beta", "gamma"]:
        target = Target(username=username, first_tracked_at=NOW)
        session.add(target); targets[username] = target
    session.flush()
    edges = {
        "alpha": ["one", "two", "three"],
        "beta": ["two", "three", "four"],
        "gamma": ["five"],
    }
    for target_name, followed_names in edges.items():
        for followed_name in followed_names:
            session.add(TargetRelationship(
                target_id=targets[target_name].id,
                account_id=accounts[followed_name].id,
                first_seen_at=NOW, last_seen_at=NOW, is_active=True,
            ))
    session.commit()


def test_compare_following_sets_returns_evidence():
    result = compare_following_sets("alpha", {"1", "2", "3"}, "beta", {"2", "3", "4"})
    assert result.shared_count == 2
    assert result.union_count == 4
    assert result.jaccard == 0.5
    assert round(result.overlap_a, 3) == 0.667
    assert round(result.overlap_b, 3) == 0.667


def test_similarity_and_new_account_cohort_pairs(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db"); init_database(engine)
    with Session(engine) as session:
        _seed(session)
        pairs = find_similarity_pairs(session, min_jaccard=0.4, min_shared=2)
        cohorts = find_new_account_cohort_pairs(
            session, as_of=NOW, new_account_days=90, low_following_max=100,
            min_jaccard=0.4, min_shared=2,
        )
    assert [(p.target_a, p.target_b) for p in pairs] == [("alpha", "beta")]
    assert [(p.target_a, p.target_b) for p in cohorts] == [("alpha", "beta")]
