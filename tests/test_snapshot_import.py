import asyncio

from sqlalchemy import select
from sqlalchemy.orm import Session

from xni.db import create_engine_for_path, init_database
from xni.models import Account, FollowingSnapshot, RelationshipEvent, SnapshotMember, TargetRelationship
from xni.services.snapshots import import_manual_snapshot


def _user(account_id: str, username: str, following_count: int = 5) -> dict:
    return {
        "id": account_id,
        "username": username,
        "display_name": username.title(),
        "description": f"bio-{username}",
        "followers_count": 10,
        "followings_count": following_count,
        "created_at": "Sun Nov 05 08:05:40 +0000 2023",
        "tweets_count": 20,
        "verified": False,
        "protected": False,
        "profile_image_url": f"https://example.com/{username}.jpg",
    }


def _payload(users: list[dict]) -> dict:
    return {"users": users, "targetLabel": "target_user", "mode": "following"}


def test_first_manual_snapshot_persists_raw_data_and_relationships(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db")
    init_database(engine)
    payload = _payload([_user("1", "alice", 4), _user("2", "bob", 7)])

    summary = asyncio.run(import_manual_snapshot(engine, payload))

    assert summary.model_dump(exclude={"snapshot_id"}) == {
        "target": "target_user",
        "total": 2,
        "added": 2,
        "removed": 0,
        "unchanged": 0,
    }

    with Session(engine) as session:
        accounts = session.scalars(select(Account).order_by(Account.external_user_id)).all()
        snapshot = session.scalars(select(FollowingSnapshot)).one()
        members = session.scalars(select(SnapshotMember)).all()
        relationships = session.scalars(select(TargetRelationship)).all()
        events = session.scalars(select(RelationshipEvent)).all()

        assert [account.username for account in accounts] == ["alice", "bob"]
        assert accounts[0].following_count == 4
        assert snapshot.raw_json["targetLabel"] == "target_user"
        assert len(members) == 2
        assert members[0].raw_json["id"] in {"1", "2"}
        assert all(relationship.is_active for relationship in relationships)
        assert sorted(event.event_type for event in events) == ["added", "added"]

    engine.dispose()


def test_second_snapshot_reports_added_removed_and_unchanged(tmp_path):
    engine = create_engine_for_path(tmp_path / "xni.db")
    init_database(engine)

    asyncio.run(import_manual_snapshot(engine, _payload([_user("1", "alice"), _user("2", "bob")])))
    summary = asyncio.run(import_manual_snapshot(engine, _payload([_user("2", "bob"), _user("3", "carol")])))

    assert summary.total == 2
    assert summary.added == 1
    assert summary.removed == 1
    assert summary.unchanged == 1

    with Session(engine) as session:
        accounts = {a.external_user_id: a for a in session.scalars(select(Account)).all()}
        relationships = {r.account_id: r for r in session.scalars(select(TargetRelationship)).all()}
        events = session.scalars(select(RelationshipEvent).order_by(RelationshipEvent.id)).all()

        assert relationships[accounts["1"].id].is_active is False
        assert relationships[accounts["1"].id].removed_at is not None
        assert relationships[accounts["2"].id].is_active is True
        assert relationships[accounts["3"].id].is_active is True
        assert [event.event_type for event in events] == ["added", "added", "added", "removed"]

    engine.dispose()
