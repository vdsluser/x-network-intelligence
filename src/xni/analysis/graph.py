from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import networkx as nx
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    Account,
    AccountClassification,
    AccountTopic,
    Target,
    TargetRelationship,
)
from .classification.taxonomy import CLASSIFIER_VERSIONS


class GraphNode(BaseModel):
    data: dict[str, Any]


class GraphEdge(BaseModel):
    data: dict[str, Any]


class GraphMeta(BaseModel):
    target_count: int
    account_count: int
    edge_count: int
    candidate_account_count: int
    truncated: bool
    metrics_scope: str = "displayed_subgraph"
    classifier_version: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    meta: GraphMeta


class GraphOptions(BaseModel):
    targets: list[str]
    topics: list[str]
    account_types: list[str]
    classifier_version: str


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _age_days(account: Account, as_of: datetime) -> int | None:
    if account.created_at is None:
        return None
    delta = _aware(as_of) - _aware(account.created_at)
    return max(0, int(delta.total_seconds() // 86400))


def _validate_common(
    *,
    classifier_version: str,
    new_account_days: int,
    min_target_coverage: float,
    max_accounts: int,
) -> None:
    if classifier_version not in CLASSIFIER_VERSIONS:
        raise ValueError(f"unsupported classifier_version: {classifier_version}")
    if new_account_days < 0:
        raise ValueError("new_account_days must be non-negative")
    if not 0 <= min_target_coverage <= 1:
        raise ValueError("min_target_coverage must be between 0 and 1")
    if not 1 <= max_accounts <= 2000:
        raise ValueError("max_accounts must be between 1 and 2000")


def build_graph_options(
    session: Session,
    *,
    classifier_version: str = "rule-v1",
) -> GraphOptions:
    if classifier_version not in CLASSIFIER_VERSIONS:
        raise ValueError(f"unsupported classifier_version: {classifier_version}")

    targets = list(
        session.scalars(
            select(Target.username)
            .where(Target.is_active.is_(True))
            .order_by(func.lower(Target.username), Target.username)
        ).all()
    )
    topics = list(
        session.scalars(
            select(AccountTopic.topic)
            .where(AccountTopic.classifier_version == classifier_version)
            .distinct()
            .order_by(AccountTopic.topic)
        ).all()
    )
    account_types = list(
        session.scalars(
            select(AccountClassification.account_type)
            .where(AccountClassification.classifier_version == classifier_version)
            .distinct()
            .order_by(AccountClassification.account_type)
        ).all()
    )
    return GraphOptions(
        targets=targets,
        topics=topics,
        account_types=account_types,
        classifier_version=classifier_version,
    )


def build_graph(
    session: Session,
    *,
    target: str | None = None,
    topic: str | None = None,
    account_type: str | None = None,
    new_only: bool = False,
    new_account_days: int = 90,
    min_target_coverage: float = 0.0,
    max_accounts: int = 500,
    classifier_version: str = "rule-v1",
    as_of: datetime | None = None,
) -> GraphResponse:
    _validate_common(
        classifier_version=classifier_version,
        new_account_days=new_account_days,
        min_target_coverage=min_target_coverage,
        max_accounts=max_accounts,
    )
    now = as_of or datetime.now(timezone.utc)

    active_targets = list(
        session.scalars(
            select(Target)
            .where(Target.is_active.is_(True))
            .order_by(func.lower(Target.username), Target.id)
        ).all()
    )
    target_by_id = {item.id: item for item in active_targets}
    global_target_count = len(active_targets)

    selected_target: Target | None = None
    if target is not None:
        normalized = target.strip().lstrip("@")
        selected_target = next(
            (item for item in active_targets if item.username.lower() == normalized.lower()),
            None,
        )
        if selected_target is None:
            raise ValueError(f"target not found: {normalized}")

    if topic is not None:
        valid_topics = set(
            session.scalars(
                select(AccountTopic.topic)
                .where(AccountTopic.classifier_version == classifier_version)
                .distinct()
            ).all()
        )
        if topic not in valid_topics:
            raise ValueError(f"topic not found: {topic}")

    if account_type is not None:
        valid_types = set(
            session.scalars(
                select(AccountClassification.account_type)
                .where(AccountClassification.classifier_version == classifier_version)
                .distinct()
            ).all()
        )
        if account_type not in valid_types:
            raise ValueError(f"account type not found: {account_type}")

    relation_rows = session.execute(
        select(TargetRelationship, Account)
        .join(Target, Target.id == TargetRelationship.target_id)
        .join(Account, Account.id == TargetRelationship.account_id)
        .where(Target.is_active.is_(True), TargetRelationship.is_active.is_(True))
    ).all()

    if not relation_rows:
        nodes: list[GraphNode] = []
        if selected_target is not None:
            nodes.append(
                GraphNode(
                    data={
                        "id": f"target:{selected_target.id}",
                        "kind": "target",
                        "target_id": selected_target.id,
                        "username": selected_target.username,
                        "display_name": selected_target.display_name,
                        "following_count": 0,
                    }
                )
            )
        return GraphResponse(
            nodes=nodes,
            edges=[],
            meta=GraphMeta(
                target_count=len(nodes),
                account_count=0,
                edge_count=0,
                candidate_account_count=0,
                truncated=False,
                classifier_version=classifier_version,
            ),
        )

    account_by_id: dict[int, Account] = {}
    followed_by: dict[int, set[int]] = {}
    following_count_by_target: dict[int, int] = {}
    relationship_pairs: list[tuple[int, int]] = []
    selected_target_account_ids: set[int] = set()

    for relationship, acct in relation_rows:
        account_by_id[acct.id] = acct
        followed_by.setdefault(acct.id, set()).add(relationship.target_id)
        following_count_by_target[relationship.target_id] = (
            following_count_by_target.get(relationship.target_id, 0) + 1
        )
        relationship_pairs.append((relationship.target_id, acct.id))
        if selected_target is not None and relationship.target_id == selected_target.id:
            selected_target_account_ids.add(acct.id)

    candidate_ids = (
        set(selected_target_account_ids)
        if selected_target is not None
        else set(account_by_id)
    )

    if topic is not None:
        topic_ids = set(
            session.scalars(
                select(AccountTopic.account_id).where(
                    AccountTopic.classifier_version == classifier_version,
                    AccountTopic.topic == topic,
                )
            ).all()
        )
        candidate_ids &= topic_ids

    if account_type is not None:
        type_ids = set(
            session.scalars(
                select(AccountClassification.account_id).where(
                    AccountClassification.classifier_version == classifier_version,
                    AccountClassification.account_type == account_type,
                )
            ).all()
        )
        candidate_ids &= type_ids

    if new_only:
        candidate_ids = {
            account_id
            for account_id in candidate_ids
            if (
                (age := _age_days(account_by_id[account_id], now)) is not None
                and age <= new_account_days
            )
        }

    if global_target_count:
        candidate_ids = {
            account_id
            for account_id in candidate_ids
            if len(followed_by.get(account_id, set())) / global_target_count
            >= min_target_coverage
        }
    else:
        candidate_ids = set()

    ranked_candidate_ids = sorted(
        candidate_ids,
        key=lambda account_id: (
            -len(followed_by.get(account_id, set())),
            -(len(followed_by.get(account_id, set())) / global_target_count if global_target_count else 0.0),
            account_by_id[account_id].username.lower(),
            account_id,
        ),
    )
    candidate_account_count = len(ranked_candidate_ids)
    kept_account_ids = set(ranked_candidate_ids[:max_accounts])
    truncated = candidate_account_count > max_accounts

    included_target_ids = {
        target_id
        for target_id, account_id in relationship_pairs
        if account_id in kept_account_ids
    }
    if selected_target is not None:
        included_target_ids.add(selected_target.id)

    displayed_pairs = [
        (target_id, account_id)
        for target_id, account_id in relationship_pairs
        if target_id in included_target_ids and account_id in kept_account_ids
    ]

    graph = nx.Graph()
    for target_id in included_target_ids:
        graph.add_node(f"target:{target_id}", kind="target")
    for account_id in kept_account_ids:
        graph.add_node(f"account:{account_id}", kind="account")
    for target_id, account_id in displayed_pairs:
        graph.add_edge(f"target:{target_id}", f"account:{account_id}")

    betweenness = nx.betweenness_centrality(graph, normalized=True) if graph else {}

    central_ids = {
        account_id
        for account_id in ranked_candidate_ids[:20]
        if account_id in kept_account_ids and len(followed_by.get(account_id, set())) >= 2
    }

    positive_bridge_values = sorted(
        [
            (account_id, betweenness.get(f"account:{account_id}", 0.0))
            for account_id in kept_account_ids
            if betweenness.get(f"account:{account_id}", 0.0) > 0
        ],
        key=lambda item: (-item[1], account_by_id[item[0]].username.lower(), item[0]),
    )
    bridge_count = max(1, math.ceil(len(positive_bridge_values) * 0.10)) if positive_bridge_values else 0
    bridge_ids = {account_id for account_id, _ in positive_bridge_values[:bridge_count]}

    topic_rows = session.execute(
        select(AccountTopic.account_id, AccountTopic.topic).where(
            AccountTopic.classifier_version == classifier_version,
            AccountTopic.account_id.in_(kept_account_ids) if kept_account_ids else False,
        )
    ).all() if kept_account_ids else []
    topics_by_account: dict[int, list[str]] = {}
    for account_id, topic_name in topic_rows:
        if topic_name != "Unknown":
            topics_by_account.setdefault(account_id, []).append(topic_name)
    for values in topics_by_account.values():
        values.sort()

    classification_rows = session.execute(
        select(AccountClassification.account_id, AccountClassification.account_type).where(
            AccountClassification.classifier_version == classifier_version,
            AccountClassification.account_id.in_(kept_account_ids) if kept_account_ids else False,
        )
    ).all() if kept_account_ids else []
    type_by_account = {account_id: type_name for account_id, type_name in classification_rows}

    nodes: list[GraphNode] = []
    for target_id in sorted(
        included_target_ids,
        key=lambda item: (target_by_id[item].username.lower(), item),
    ):
        target_model = target_by_id[target_id]
        nodes.append(
            GraphNode(
                data={
                    "id": f"target:{target_id}",
                    "kind": "target",
                    "target_id": target_id,
                    "username": target_model.username,
                    "display_name": target_model.display_name,
                    "following_count": following_count_by_target.get(target_id, 0),
                }
            )
        )

    for account_id in ranked_candidate_ids[:max_accounts]:
        acct = account_by_id[account_id]
        target_connections = len(followed_by.get(account_id, set()))
        coverage = target_connections / global_target_count if global_target_count else 0.0
        age_days = _age_days(acct, now)
        nodes.append(
            GraphNode(
                data={
                    "id": f"account:{account_id}",
                    "kind": "account",
                    "account_id": account_id,
                    "external_user_id": acct.external_user_id,
                    "username": acct.username,
                    "display_name": acct.display_name,
                    "account_type": type_by_account.get(account_id, "Unknown"),
                    "topics": topics_by_account.get(account_id, []),
                    "followers_count": acct.followers_count,
                    "following_count": acct.following_count,
                    "age_days": age_days,
                    "is_new": age_days is not None and age_days <= new_account_days,
                    "followed_by_targets": target_connections,
                    "target_coverage": coverage,
                    "view_betweenness": betweenness.get(f"account:{account_id}", 0.0),
                    "is_central": account_id in central_ids,
                    "is_bridge": account_id in bridge_ids,
                }
            )
        )

    edges = [
        GraphEdge(
            data={
                "id": f"follows:{target_id}:{account_id}",
                "source": f"target:{target_id}",
                "target": f"account:{account_id}",
                "kind": "follows",
            }
        )
        for target_id, account_id in sorted(displayed_pairs)
    ]

    return GraphResponse(
        nodes=nodes,
        edges=edges,
        meta=GraphMeta(
            target_count=len(included_target_ids),
            account_count=len(kept_account_ids),
            edge_count=len(edges),
            candidate_account_count=candidate_account_count,
            truncated=truncated,
            classifier_version=classifier_version,
        ),
    )
