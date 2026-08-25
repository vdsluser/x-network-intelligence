from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..analysis.profiles import find_new_account_candidates
from ..models import Account, ExpansionCandidate, Target


class ExpansionQueueRefresh(BaseModel):
    added: int
    existing: int
    total_pending: int


class ExpansionQueueItem(BaseModel):
    id: int
    account_id: int
    external_user_id: str
    username: str
    display_name: str | None
    age_days: int | None
    following_count: int | None
    status: str
    reason: str
    promoted_target_id: int | None
    target_username: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_item(candidate: ExpansionCandidate, account: Account, target: Target | None = None) -> ExpansionQueueItem:
    return ExpansionQueueItem(
        id=candidate.id,
        account_id=account.id,
        external_user_id=account.external_user_id,
        username=account.username,
        display_name=account.display_name,
        age_days=candidate.age_days,
        following_count=candidate.following_count,
        status=candidate.status,
        reason=candidate.reason,
        promoted_target_id=candidate.promoted_target_id,
        target_username=target.username if target is not None else None,
    )


def refresh_expansion_queue(
    session: Session,
    *,
    as_of: datetime,
    new_account_days: int,
    low_following_max: int,
) -> ExpansionQueueRefresh:
    candidates = find_new_account_candidates(
        session,
        as_of=as_of,
        new_account_days=new_account_days,
        low_following_max=low_following_max,
    )
    tracked = set(session.scalars(select(Target.username)).all())
    existing_by_account = {
        row.account_id: row for row in session.scalars(select(ExpansionCandidate)).all()
    }
    added = 0
    existing = 0
    now = _now()

    for signal in candidates:
        if signal.account_id is None or signal.username in tracked:
            continue
        row = existing_by_account.get(signal.account_id)
        if row is None:
            row = ExpansionCandidate(
                account_id=signal.account_id,
                status="pending",
                reason="new_low_following",
                age_days=signal.age_days,
                following_count=signal.following_count,
                new_account_days=new_account_days,
                low_following_max=low_following_max,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            existing_by_account[signal.account_id] = row
            added += 1
        else:
            row.age_days = signal.age_days
            row.following_count = signal.following_count
            row.new_account_days = new_account_days
            row.low_following_max = low_following_max
            row.updated_at = now
            existing += 1

    session.commit()
    total_pending = session.scalar(
        select(func.count()).select_from(ExpansionCandidate).where(ExpansionCandidate.status == "pending")
    ) or 0
    return ExpansionQueueRefresh(added=added, existing=existing, total_pending=total_pending)


def list_expansion_queue(session: Session, *, status: str | None = "pending") -> list[ExpansionQueueItem]:
    statement = (
        select(ExpansionCandidate, Account, Target)
        .join(Account, Account.id == ExpansionCandidate.account_id)
        .outerjoin(Target, Target.id == ExpansionCandidate.promoted_target_id)
    )
    if status is not None:
        statement = statement.where(ExpansionCandidate.status == status)
    rows = session.execute(statement.order_by(ExpansionCandidate.id)).all()
    return [_to_item(candidate, account, target) for candidate, account, target in rows]


def promote_expansion_candidate(session: Session, candidate_id: int) -> ExpansionQueueItem:
    row = session.execute(
        select(ExpansionCandidate, Account)
        .join(Account, Account.id == ExpansionCandidate.account_id)
        .where(ExpansionCandidate.id == candidate_id)
    ).one_or_none()
    if row is None:
        raise ValueError("expansion candidate not found")
    candidate, account = row

    target = session.scalar(
        select(Target).where(
            or_(
                Target.external_user_id == account.external_user_id,
                Target.username == account.username,
            )
        )
    )
    now = _now()
    if target is None:
        target = Target(
            username=account.username,
            external_user_id=account.external_user_id,
            display_name=account.display_name,
            is_active=True,
            first_tracked_at=now,
        )
        session.add(target)
        session.flush()
    else:
        target.username = account.username
        target.external_user_id = account.external_user_id
        target.display_name = account.display_name
        target.is_active = True

    candidate.status = "promoted"
    candidate.promoted_at = now
    candidate.promoted_target_id = target.id
    candidate.updated_at = now
    session.commit()
    return _to_item(candidate, account, target)
