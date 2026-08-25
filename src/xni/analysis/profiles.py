from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account


class AccountProfileSignal(BaseModel):
    account_id: int | None
    external_user_id: str
    username: str
    age_days: int | None
    following_count: int | None
    followers_count: int | None
    tweets_count: int | None
    is_new_account: bool
    is_low_following: bool
    new_account_days: int
    low_following_max: int


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def analyze_account_profile(
    account: Account,
    *,
    as_of: datetime,
    new_account_days: int,
    low_following_max: int,
) -> AccountProfileSignal:
    if new_account_days < 0 or low_following_max < 0:
        raise ValueError("analysis thresholds must be non-negative")

    age_days: int | None = None
    if account.created_at is not None:
        delta = _aware(as_of) - _aware(account.created_at)
        age_days = max(0, int(delta.total_seconds() // 86400))

    is_new_account = age_days is not None and age_days <= new_account_days
    is_low_following = (
        account.following_count is not None
        and account.following_count <= low_following_max
    )

    return AccountProfileSignal(
        account_id=account.id,
        external_user_id=account.external_user_id,
        username=account.username,
        age_days=age_days,
        following_count=account.following_count,
        followers_count=account.followers_count,
        tweets_count=account.tweets_count,
        is_new_account=is_new_account,
        is_low_following=is_low_following,
        new_account_days=new_account_days,
        low_following_max=low_following_max,
    )


def find_new_account_candidates(
    session: Session,
    *,
    as_of: datetime,
    new_account_days: int,
    low_following_max: int,
) -> list[AccountProfileSignal]:
    accounts = session.scalars(select(Account)).all()
    signals = [
        analyze_account_profile(
            account,
            as_of=as_of,
            new_account_days=new_account_days,
            low_following_max=low_following_max,
        )
        for account in accounts
    ]
    candidates = [s for s in signals if s.is_new_account and s.is_low_following]
    return sorted(
        candidates,
        key=lambda s: (
            s.age_days if s.age_days is not None else 10**9,
            s.following_count if s.following_count is not None else 10**9,
            s.username.lower(),
        ),
    )
