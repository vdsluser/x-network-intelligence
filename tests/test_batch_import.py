import asyncio

from xni.db import create_engine_for_path, init_database
from xni.services.batch import import_manual_batch


def _user(account_id: str, username: str) -> dict:
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


def _payload(target: str, users: list[dict]) -> dict:
    return {"users": users, "targetLabel": target, "mode": "following"}


def test_batch_import_refreshes_queue_and_network_summary(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db")
    init_database(engine)
    payloads = [
        _payload("alpha", [_user("1", "shared"), _user("2", "only_alpha")]),
        _payload("beta", [_user("1", "shared"), _user("3", "only_beta")]),
    ]

    result = asyncio.run(
        import_manual_batch(
            engine,
            payloads,
            new_account_days=90,
            low_following_max=100,
            min_jaccard=0.0,
            min_shared=1,
            central_limit=5,
        )
    )

    assert [item.target for item in result.imports] == ["alpha", "beta"]
    assert result.queue.added == 3
    assert result.analysis.targets == 2
    assert result.analysis.active_relationships == 4
    assert result.analysis.pending_expansion_candidates == 3
    assert result.analysis.similarity_pairs == 1
    assert result.analysis.central_nodes[0].username == "shared"
    assert result.analysis.central_nodes[0].target_coverage == 1.0
    engine.dispose()
