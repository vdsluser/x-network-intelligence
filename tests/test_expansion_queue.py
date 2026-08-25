import asyncio
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from xni.db import create_engine_for_path, init_database
from xni.services.expansion import (
    list_expansion_queue,
    promote_expansion_candidate,
    refresh_expansion_queue,
)
from xni.services.snapshots import import_manual_snapshot


def _user(account_id: str, username: str, *, created_at: str, followings: int) -> dict:
    return {
        "id": account_id,
        "username": username,
        "display_name": username.title(),
        "description": "candidate",
        "followers_count": 10,
        "followings_count": followings,
        "created_at": created_at,
        "tweets_count": 20,
        "verified": False,
        "protected": False,
        "profile_image_url": None,
    }


def test_refresh_expansion_queue_adds_and_deduplicates_candidates(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db")
    init_database(engine)
    payload = {
        "users": [
            _user("1", "new_small", created_at="Mon Aug 24 00:00:00 +0000 2026", followings=20),
            _user("2", "old_large", created_at="Sun Nov 05 08:05:40 +0000 2023", followings=500),
        ],
        "targetLabel": "seed",
        "mode": "following",
    }
    asyncio.run(import_manual_snapshot(engine, payload))

    with Session(engine) as session:
        first = refresh_expansion_queue(
            session,
            as_of=datetime(2026, 8, 25, tzinfo=timezone.utc),
            new_account_days=90,
            low_following_max=100,
        )
        second = refresh_expansion_queue(
            session,
            as_of=datetime(2026, 8, 25, tzinfo=timezone.utc),
            new_account_days=90,
            low_following_max=100,
        )
        items = list_expansion_queue(session, status="pending")

    assert first.added == 1
    assert first.existing == 0
    assert second.added == 0
    assert second.existing == 1
    assert [item.username for item in items] == ["new_small"]
    engine.dispose()


def test_promote_expansion_candidate_creates_local_target(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db")
    init_database(engine)
    payload = {
        "users": [_user("1", "new_small", created_at="Mon Aug 24 00:00:00 +0000 2026", followings=20)],
        "targetLabel": "seed",
        "mode": "following",
    }
    asyncio.run(import_manual_snapshot(engine, payload))

    with Session(engine) as session:
        refresh_expansion_queue(
            session,
            as_of=datetime(2026, 8, 25, tzinfo=timezone.utc),
            new_account_days=90,
            low_following_max=100,
        )
        candidate = list_expansion_queue(session, status="pending")[0]
        promoted = promote_expansion_candidate(session, candidate.id)
        queue_after = list_expansion_queue(session, status="promoted")

    assert promoted.status == "promoted"
    assert promoted.target_username == "new_small"
    assert queue_after[0].promoted_target_id is not None
    engine.dispose()
