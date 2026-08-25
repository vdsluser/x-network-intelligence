from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account, Target, TargetRelationship
from .centrality import CentralNodeScore, rank_central_nodes
from .network import (
    find_new_account_cohort_pairs,
    find_similarity_pairs,
    get_active_following_sets,
)
from .profiles import analyze_account_profile


class FollowingFingerprint(BaseModel):
    target: str
    following_count: int
    new_account_count: int
    new_account_ratio: float
    new_low_following_count: int
    new_low_following_ratio: float
    shared_following_count: int
    shared_network_concentration: float
    most_similar_target: str | None
    similarity_jaccard: float
    similarity_shared_count: int
    cohort_peer_count: int
    cohort_peers: list[str]
    top_central_nodes: list[CentralNodeScore]


def build_following_fingerprint(
    session: Session,
    target_username: str,
    *,
    as_of: datetime,
    new_account_days: int = 90,
    low_following_max: int = 100,
    min_cohort_jaccard: float = 0.2,
    min_cohort_shared: int = 2,
    top_node_limit: int = 5,
) -> FollowingFingerprint:
    if top_node_limit < 1:
        raise ValueError("top_node_limit must be at least 1")

    normalized_target = target_username.strip().lstrip("@")
    target = session.scalar(
        select(Target).where(
            Target.username == normalized_target,
            Target.is_active.is_(True),
        )
    )
    if target is None:
        raise ValueError(f"active target {normalized_target!r} not found")

    followed_accounts = session.scalars(
        select(Account)
        .join(TargetRelationship, TargetRelationship.account_id == Account.id)
        .where(
            TargetRelationship.target_id == target.id,
            TargetRelationship.is_active.is_(True),
        )
    ).all()
    following_count = len(followed_accounts)

    new_account_count = 0
    new_low_following_count = 0
    for account in followed_accounts:
        signal = analyze_account_profile(
            account,
            as_of=as_of,
            new_account_days=new_account_days,
            low_following_max=low_following_max,
        )
        if signal.is_new_account:
            new_account_count += 1
        if signal.is_new_account and signal.is_low_following:
            new_low_following_count += 1

    following_sets = get_active_following_sets(session)
    own_set = following_sets.get(normalized_target, set())
    other_sets = [
        values for username, values in following_sets.items() if username != normalized_target
    ]
    shared_following_count = sum(
        1 for account_id in own_set if any(account_id in values for values in other_sets)
    )

    similarity_pairs = [
        pair
        for pair in find_similarity_pairs(session, min_jaccard=0.0, min_shared=0)
        if normalized_target in {pair.target_a, pair.target_b}
    ]
    best_similarity = similarity_pairs[0] if similarity_pairs else None
    if best_similarity is None:
        most_similar_target = None
        similarity_jaccard = 0.0
        similarity_shared_count = 0
    else:
        most_similar_target = (
            best_similarity.target_b
            if best_similarity.target_a == normalized_target
            else best_similarity.target_a
        )
        similarity_jaccard = best_similarity.jaccard
        similarity_shared_count = best_similarity.shared_count

    cohort_pairs = find_new_account_cohort_pairs(
        session,
        as_of=as_of,
        new_account_days=new_account_days,
        low_following_max=low_following_max,
        min_jaccard=min_cohort_jaccard,
        min_shared=min_cohort_shared,
    )
    cohort_peers = sorted(
        {
            pair.target_b if pair.target_a == normalized_target else pair.target_a
            for pair in cohort_pairs
            if normalized_target in {pair.target_a, pair.target_b}
        }
    )

    all_followed_ids = set().union(*following_sets.values()) if following_sets else set()
    central_scores = rank_central_nodes(session, limit=max(1, len(all_followed_ids)))
    own_central_scores = [
        score for score in central_scores if score.external_user_id in own_set
    ][:top_node_limit]

    return FollowingFingerprint(
        target=normalized_target,
        following_count=following_count,
        new_account_count=new_account_count,
        new_account_ratio=(new_account_count / following_count if following_count else 0.0),
        new_low_following_count=new_low_following_count,
        new_low_following_ratio=(
            new_low_following_count / following_count if following_count else 0.0
        ),
        shared_following_count=shared_following_count,
        shared_network_concentration=(
            shared_following_count / following_count if following_count else 0.0
        ),
        most_similar_target=most_similar_target,
        similarity_jaccard=similarity_jaccard,
        similarity_shared_count=similarity_shared_count,
        cohort_peer_count=len(cohort_peers),
        cohort_peers=cohort_peers,
        top_central_nodes=own_central_scores,
    )


def build_following_fingerprints(
    session: Session,
    *,
    as_of: datetime,
    new_account_days: int = 90,
    low_following_max: int = 100,
    min_cohort_jaccard: float = 0.2,
    min_cohort_shared: int = 2,
    top_node_limit: int = 5,
) -> list[FollowingFingerprint]:
    usernames = session.scalars(
        select(Target.username)
        .where(Target.is_active.is_(True))
        .order_by(Target.username)
    ).all()
    return [
        build_following_fingerprint(
            session,
            username,
            as_of=as_of,
            new_account_days=new_account_days,
            low_following_max=low_following_max,
            min_cohort_jaccard=min_cohort_jaccard,
            min_cohort_shared=min_cohort_shared,
            top_node_limit=top_node_limit,
        )
        for username in usernames
    ]
