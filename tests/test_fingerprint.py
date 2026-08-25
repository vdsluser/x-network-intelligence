from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from xni.analysis.fingerprint import build_following_fingerprint
from xni.db import create_engine_for_path, init_database
from xni.models import Account, Target, TargetRelationship


NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)


def _account(
    external_user_id: str,
    username: str,
    *,
    age_days: int,
    following_count: int,
) -> Account:
    return Account(
        external_user_id=external_user_id,
        username=username,
        created_at=NOW - timedelta(days=age_days),
        following_count=following_count,
        first_seen_at=NOW,
        last_seen_at=NOW,
    )


def _rel(target: Target, account: Account) -> TargetRelationship:
    return TargetRelationship(
        target_id=target.id,
        account_id=account.id,
        first_seen_at=NOW,
        last_seen_at=NOW,
        is_active=True,
    )


def test_following_fingerprint_combines_target_network_metrics(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db")
    init_database(engine)

    with Session(engine) as session:
        shared_one = _account("1", "shared_one", age_days=1000, following_count=500)
        shared_two = _account("2", "shared_two", age_days=1000, following_count=500)
        young_sparse = _account("3", "young_sparse", age_days=12, following_count=20)
        beta_only = _account("4", "beta_only", age_days=1000, following_count=500)
        gamma_only = _account("5", "gamma_only", age_days=1000, following_count=500)
        alpha_profile = _account("ta", "alpha", age_days=15, following_count=30)
        beta_profile = _account("tb", "beta", age_days=18, following_count=25)
        session.add_all([
            shared_one,
            shared_two,
            young_sparse,
            beta_only,
            gamma_only,
            alpha_profile,
            beta_profile,
        ])
        session.flush()

        alpha = Target(username="alpha", first_tracked_at=NOW)
        beta = Target(username="beta", first_tracked_at=NOW)
        gamma = Target(username="gamma", first_tracked_at=NOW)
        session.add_all([alpha, beta, gamma])
        session.flush()

        session.add_all([
            _rel(alpha, shared_one),
            _rel(alpha, shared_two),
            _rel(alpha, young_sparse),
            _rel(beta, shared_one),
            _rel(beta, shared_two),
            _rel(beta, beta_only),
            _rel(gamma, shared_one),
            _rel(gamma, gamma_only),
        ])
        session.commit()

        fingerprint = build_following_fingerprint(
            session,
            "alpha",
            as_of=NOW,
            new_account_days=90,
            low_following_max=100,
            min_cohort_jaccard=0.5,
            min_cohort_shared=2,
            top_node_limit=3,
        )

    assert fingerprint.target == "alpha"
    assert fingerprint.following_count == 3
    assert fingerprint.new_account_count == 1
    assert fingerprint.new_account_ratio == 1 / 3
    assert fingerprint.new_low_following_count == 1
    assert fingerprint.new_low_following_ratio == 1 / 3
    assert fingerprint.shared_following_count == 2
    assert fingerprint.shared_network_concentration == 2 / 3
    assert fingerprint.most_similar_target == "beta"
    assert fingerprint.similarity_jaccard == 0.5
    assert fingerprint.similarity_shared_count == 2
    assert fingerprint.cohort_peers == ["beta"]
    assert fingerprint.cohort_peer_count == 1
    assert fingerprint.top_central_nodes[0].username == "shared_one"
    assert fingerprint.top_central_nodes[0].followed_by_targets == 3

    engine.dispose()


def test_fingerprint_api_returns_profile_after_manual_batch_import(tmp_path):
    from fastapi.testclient import TestClient

    from xni.app import create_app
    from xni.config import Settings

    def payload(target: str, users: list[dict]) -> dict:
        return {"targetLabel": target, "mode": "following", "users": users}

    def user(account_id: str, username: str) -> dict:
        return {
            "id": account_id,
            "username": username,
            "display_name": username.title(),
            "description": "",
            "followers_count": 100,
            "followings_count": 500,
            "created_at": "Sun Nov 05 08:05:40 +0000 2023",
            "tweets_count": 20,
            "verified": False,
            "protected": False,
            "profile_image_url": None,
        }

    settings = Settings(database_path=tmp_path / "x_network.db")
    request = {
        "payloads": [
            payload("alpha", [user("1", "shared"), user("2", "alpha_only")]),
            payload("beta", [user("1", "shared"), user("3", "beta_only")]),
        ],
        "new_account_days": 90,
        "low_following_max": 100,
        "min_jaccard": 0.2,
        "min_shared": 1,
        "central_limit": 10,
    }

    with TestClient(create_app(settings)) as client:
        imported = client.post("/api/import/manual/batch", json=request)
        single = client.get("/api/analysis/fingerprints/alpha")
        all_fingerprints = client.get("/api/analysis/fingerprints")

    assert imported.status_code == 200
    assert single.status_code == 200
    body = single.json()
    assert body["target"] == "alpha"
    assert body["following_count"] == 2
    assert body["shared_following_count"] == 1
    assert body["shared_network_concentration"] == 0.5
    assert body["most_similar_target"] == "beta"
    assert body["similarity_shared_count"] == 1
    assert body["top_central_nodes"][0]["username"] == "shared"

    assert all_fingerprints.status_code == 200
    assert [item["target"] for item in all_fingerprints.json()] == ["alpha", "beta"]
