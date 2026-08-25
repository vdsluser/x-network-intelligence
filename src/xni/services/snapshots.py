from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from ..models import Account, FollowingSnapshot, RelationshipEvent, SnapshotMember, Target, TargetRelationship
from ..providers.manual import ManualImportProvider


class ImportSummary(BaseModel):
    target: str
    snapshot_id: int
    total: int
    added: int
    removed: int
    unchanged: int


async def import_manual_snapshot(engine: Engine, payload: dict[str, Any]) -> ImportSummary:
    provider = ManualImportProvider(payload)
    accounts = await provider.get_following(provider.target_label)
    now = datetime.now(timezone.utc)

    with Session(engine) as session, session.begin():
        target = session.scalar(select(Target).where(Target.username == provider.target_label))
        if target is None:
            target = Target(username=provider.target_label, first_tracked_at=now)
            session.add(target)
            session.flush()
        target.last_collected_at = now

        previous_rows = session.execute(
            select(Account.external_user_id, Account.id)
            .join(TargetRelationship, TargetRelationship.account_id == Account.id)
            .where(TargetRelationship.target_id == target.id, TargetRelationship.is_active.is_(True))
        ).all()
        previous_by_external_id = {row.external_user_id: row.id for row in previous_rows}
        previous_ids = set(previous_by_external_id)

        snapshot = FollowingSnapshot(
            target_id=target.id,
            provider="manual",
            collected_at=now,
            raw_json=provider.raw_payload,
        )
        session.add(snapshot)
        session.flush()

        current_by_external_id: dict[str, Account] = {}
        for position, normalized in enumerate(accounts):
            db_account = session.scalar(select(Account).where(Account.external_user_id == normalized.id))
            if db_account is None:
                db_account = Account(
                    external_user_id=normalized.id,
                    username=normalized.username,
                    first_seen_at=now,
                    last_seen_at=now,
                )
                session.add(db_account)
                session.flush()

            _apply_account_fields(db_account, normalized.model_dump())
            db_account.last_seen_at = now
            current_by_external_id[normalized.id] = db_account

            session.add(
                SnapshotMember(
                    snapshot_id=snapshot.id,
                    account_id=db_account.id,
                    position=position,
                    raw_json=provider.raw_user(normalized.id),
                )
            )

        current_ids = set(current_by_external_id)
        added_ids = current_ids - previous_ids
        removed_ids = previous_ids - current_ids
        unchanged_ids = current_ids & previous_ids

        for external_id, db_account in current_by_external_id.items():
            relationship = session.scalar(
                select(TargetRelationship).where(
                    TargetRelationship.target_id == target.id,
                    TargetRelationship.account_id == db_account.id,
                )
            )
            if relationship is None:
                relationship = TargetRelationship(
                    target_id=target.id,
                    account_id=db_account.id,
                    first_seen_at=now,
                    last_seen_at=now,
                    is_active=True,
                )
                session.add(relationship)
            else:
                relationship.is_active = True
                relationship.last_seen_at = now
                relationship.removed_at = None

            if external_id in added_ids:
                session.add(
                    RelationshipEvent(
                        target_id=target.id,
                        account_id=db_account.id,
                        snapshot_id=snapshot.id,
                        event_type="added",
                        observed_at=now,
                    )
                )

        for external_id in removed_ids:
            account_id = previous_by_external_id[external_id]
            relationship = session.scalar(
                select(TargetRelationship).where(
                    TargetRelationship.target_id == target.id,
                    TargetRelationship.account_id == account_id,
                )
            )
            if relationship is None:
                continue
            relationship.is_active = False
            relationship.removed_at = now
            session.add(
                RelationshipEvent(
                    target_id=target.id,
                    account_id=account_id,
                    snapshot_id=snapshot.id,
                    event_type="removed",
                    observed_at=now,
                )
            )

        snapshot_id = snapshot.id

    return ImportSummary(
        target=provider.target_label,
        snapshot_id=snapshot_id,
        total=len(current_ids),
        added=len(added_ids),
        removed=len(removed_ids),
        unchanged=len(unchanged_ids),
    )


def _apply_account_fields(account: Account, values: dict[str, Any]) -> None:
    account.username = values["username"]
    account.display_name = values.get("display_name")
    account.description = values.get("description")
    account.followers_count = values.get("followers_count")
    account.following_count = values.get("following_count")
    account.tweets_count = values.get("tweets_count")
    account.created_at = values.get("created_at")
    account.verified = bool(values.get("verified", False))
    account.protected = bool(values.get("protected", False))
    account.profile_image_url = values.get("profile_image_url")
