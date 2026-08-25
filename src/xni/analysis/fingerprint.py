from __future__ import annotations

import math
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    Account,
    AccountAssociation,
    AccountClassification,
    AccountTopic,
    Target,
    TargetRelationship,
)
from .centrality import CentralNodeScore, rank_central_nodes
from .classification.taxonomy import CLASSIFIER_VERSIONS
from .network import (
    find_new_account_cohort_pairs,
    find_similarity_pairs,
    get_active_following_sets,
)
from .profiles import analyze_account_profile


class TopicDistributionItem(BaseModel):
    topic: str
    account_count: int
    share: float


class AccountTypeDistributionItem(BaseModel):
    account_type: str
    account_count: int
    share: float


class PublicAssociationSummary(BaseModel):
    association_type: str
    value: str
    normalized_value: str
    account_count: int


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
    topic_distribution: list[TopicDistributionItem]
    account_type_distribution: list[AccountTypeDistributionItem]
    top_topics: list[TopicDistributionItem]
    topic_concentration: float
    topic_diversity: float
    public_associations: list[PublicAssociationSummary]
    classified_account_count: int
    unclassified_account_count: int
    unclassified_ratio: float
    classifier_version: str


def _topic_metrics(counts: list[int]) -> tuple[float, float]:
    positive = [count for count in counts if count > 0]
    total = sum(positive)
    if total == 0:
        return 0.0, 0.0
    probabilities = [count / total for count in positive]
    concentration = sum(p * p for p in probabilities)
    if len(probabilities) < 2:
        diversity = 0.0
    else:
        entropy = -sum(p * math.log(p) for p in probabilities)
        diversity = entropy / math.log(len(probabilities))
    return concentration, diversity


def _semantic_fields(
    session: Session,
    followed_account_ids: list[int],
    following_count: int,
    classifier_version: str,
) -> dict:
    if classifier_version not in CLASSIFIER_VERSIONS:
        raise ValueError(f"unsupported classifier_version: {classifier_version}")
    if not followed_account_ids:
        return {
            "topic_distribution": [],
            "account_type_distribution": [],
            "top_topics": [],
            "topic_concentration": 0.0,
            "topic_diversity": 0.0,
            "public_associations": [],
            "classified_account_count": 0,
            "unclassified_account_count": 0,
            "unclassified_ratio": 0.0,
            "classifier_version": classifier_version,
        }

    topic_rows = session.execute(
        select(AccountTopic.topic, func.count(func.distinct(AccountTopic.account_id)))
        .where(
            AccountTopic.account_id.in_(followed_account_ids),
            AccountTopic.classifier_version == classifier_version,
        )
        .group_by(AccountTopic.topic)
        .order_by(func.count(func.distinct(AccountTopic.account_id)).desc(), AccountTopic.topic)
    ).all()
    topic_distribution = [
        TopicDistributionItem(
            topic=topic,
            account_count=count,
            share=(count / following_count if following_count else 0.0),
        )
        for topic, count in topic_rows
    ]
    concentration, diversity = _topic_metrics([row.account_count for row in topic_distribution])

    classified_account_count = session.scalar(
        select(func.count(func.distinct(AccountTopic.account_id))).where(
            AccountTopic.account_id.in_(followed_account_ids),
            AccountTopic.classifier_version == classifier_version,
        )
    ) or 0
    unclassified_account_count = max(0, following_count - classified_account_count)

    type_rows = session.execute(
        select(AccountClassification.account_type, func.count(func.distinct(AccountClassification.account_id)))
        .where(
            AccountClassification.account_id.in_(followed_account_ids),
            AccountClassification.classifier_version == classifier_version,
        )
        .group_by(AccountClassification.account_type)
        .order_by(func.count(func.distinct(AccountClassification.account_id)).desc(), AccountClassification.account_type)
    ).all()
    typed_total = sum(count for _, count in type_rows)
    account_type_distribution = [
        AccountTypeDistributionItem(
            account_type=account_type,
            account_count=count,
            share=(count / typed_total if typed_total else 0.0),
        )
        for account_type, count in type_rows
    ]

    association_rows = session.execute(
        select(
            AccountAssociation.association_type,
            AccountAssociation.normalized_value,
            func.min(AccountAssociation.value),
            func.count(func.distinct(AccountAssociation.account_id)),
        )
        .where(
            AccountAssociation.account_id.in_(followed_account_ids),
            AccountAssociation.classifier_version == classifier_version,
        )
        .group_by(AccountAssociation.association_type, AccountAssociation.normalized_value)
        .order_by(
            func.count(func.distinct(AccountAssociation.account_id)).desc(),
            AccountAssociation.association_type,
            AccountAssociation.normalized_value,
        )
        .limit(10)
    ).all()
    public_associations = [
        PublicAssociationSummary(
            association_type=association_type,
            value=value,
            normalized_value=normalized_value,
            account_count=account_count,
        )
        for association_type, normalized_value, value, account_count in association_rows
    ]

    return {
        "topic_distribution": topic_distribution,
        "account_type_distribution": account_type_distribution,
        "top_topics": topic_distribution[:5],
        "topic_concentration": concentration,
        "topic_diversity": diversity,
        "public_associations": public_associations,
        "classified_account_count": classified_account_count,
        "unclassified_account_count": unclassified_account_count,
        "unclassified_ratio": (
            unclassified_account_count / following_count if following_count else 0.0
        ),
        "classifier_version": classifier_version,
    }


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
    classifier_version: str = "rule-v1",
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
    other_sets = [values for username, values in following_sets.items() if username != normalized_target]
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
    own_central_scores = [score for score in central_scores if score.external_user_id in own_set][
        :top_node_limit
    ]

    semantic = _semantic_fields(
        session,
        [account.id for account in followed_accounts],
        following_count,
        classifier_version,
    )

    return FollowingFingerprint(
        target=normalized_target,
        following_count=following_count,
        new_account_count=new_account_count,
        new_account_ratio=(new_account_count / following_count if following_count else 0.0),
        new_low_following_count=new_low_following_count,
        new_low_following_ratio=(new_low_following_count / following_count if following_count else 0.0),
        shared_following_count=shared_following_count,
        shared_network_concentration=(shared_following_count / following_count if following_count else 0.0),
        most_similar_target=most_similar_target,
        similarity_jaccard=similarity_jaccard,
        similarity_shared_count=similarity_shared_count,
        cohort_peer_count=len(cohort_peers),
        cohort_peers=cohort_peers,
        top_central_nodes=own_central_scores,
        **semantic,
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
    classifier_version: str = "rule-v1",
) -> list[FollowingFingerprint]:
    usernames = session.scalars(
        select(Target.username).where(Target.is_active.is_(True)).order_by(Target.username)
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
            classifier_version=classifier_version,
        )
        for username in usernames
    ]
