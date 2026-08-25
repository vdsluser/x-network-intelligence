from __future__ import annotations

from datetime import datetime
from itertools import combinations

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account, Target, TargetRelationship
from .profiles import find_new_account_candidates


class FollowingSimilarity(BaseModel):
    target_a: str
    target_b: str
    shared_count: int
    union_count: int
    jaccard: float
    overlap_a: float
    overlap_b: float


def get_active_following_sets(session: Session) -> dict[str, set[str]]:
    targets = session.scalars(select(Target).where(Target.is_active.is_(True))).all()
    result = {target.username: set() for target in targets}
    rows = session.execute(
        select(Target.username, Account.external_user_id)
        .join(TargetRelationship, TargetRelationship.target_id == Target.id)
        .join(Account, Account.id == TargetRelationship.account_id)
        .where(TargetRelationship.is_active.is_(True), Target.is_active.is_(True))
    ).all()
    for username, external_user_id in rows:
        result.setdefault(username, set()).add(external_user_id)
    return result


def compare_following_sets(
    target_a: str,
    following_a: set[str],
    target_b: str,
    following_b: set[str],
) -> FollowingSimilarity:
    shared = following_a & following_b
    union = following_a | following_b
    shared_count = len(shared)
    union_count = len(union)
    return FollowingSimilarity(
        target_a=target_a,
        target_b=target_b,
        shared_count=shared_count,
        union_count=union_count,
        jaccard=(shared_count / union_count) if union_count else 0.0,
        overlap_a=(shared_count / len(following_a)) if following_a else 0.0,
        overlap_b=(shared_count / len(following_b)) if following_b else 0.0,
    )


def find_similarity_pairs(
    session: Session,
    *,
    min_jaccard: float = 0.0,
    min_shared: int = 1,
) -> list[FollowingSimilarity]:
    if not 0 <= min_jaccard <= 1:
        raise ValueError("min_jaccard must be between 0 and 1")
    if min_shared < 0:
        raise ValueError("min_shared must be non-negative")
    following_sets = get_active_following_sets(session)
    pairs = []
    for target_a, target_b in combinations(sorted(following_sets), 2):
        result = compare_following_sets(
            target_a, following_sets[target_a], target_b, following_sets[target_b]
        )
        if result.shared_count >= min_shared and result.jaccard >= min_jaccard:
            pairs.append(result)
    return sorted(
        pairs,
        key=lambda item: (-item.jaccard, -item.shared_count, item.target_a, item.target_b),
    )


def find_new_account_cohort_pairs(
    session: Session,
    *,
    as_of: datetime,
    new_account_days: int,
    low_following_max: int,
    min_jaccard: float = 0.0,
    min_shared: int = 1,
) -> list[FollowingSimilarity]:
    candidate_usernames = {
        candidate.username
        for candidate in find_new_account_candidates(
            session,
            as_of=as_of,
            new_account_days=new_account_days,
            low_following_max=low_following_max,
        )
    }
    return [
        pair
        for pair in find_similarity_pairs(
            session, min_jaccard=min_jaccard, min_shared=min_shared
        )
        if pair.target_a in candidate_usernames and pair.target_b in candidate_usernames
    ]
