from __future__ import annotations

import networkx as nx
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account, Target, TargetRelationship


class CentralNodeScore(BaseModel):
    account_id: int
    external_user_id: str
    username: str
    followed_by_targets: int
    target_coverage: float
    betweenness: float


def rank_central_nodes(session: Session, *, limit: int = 20) -> list[CentralNodeScore]:
    if limit < 1:
        raise ValueError("limit must be at least 1")

    active_targets = session.scalars(
        select(Target).where(Target.is_active.is_(True))
    ).all()
    target_count = len(active_targets)
    if target_count == 0:
        return []

    graph = nx.Graph()
    account_by_id: dict[int, Account] = {}
    followed_by: dict[int, set[int]] = {}

    for target in active_targets:
        graph.add_node(f"t:{target.id}", kind="target")

    rows = session.execute(
        select(TargetRelationship, Account)
        .join(Account, Account.id == TargetRelationship.account_id)
        .join(Target, Target.id == TargetRelationship.target_id)
        .where(TargetRelationship.is_active.is_(True), Target.is_active.is_(True))
    ).all()

    for relationship, account in rows:
        account_by_id[account.id] = account
        followed_by.setdefault(account.id, set()).add(relationship.target_id)
        target_node = f"t:{relationship.target_id}"
        account_node = f"a:{account.id}"
        graph.add_node(account_node, kind="account")
        graph.add_edge(target_node, account_node)

    if not account_by_id:
        return []

    betweenness = nx.betweenness_centrality(graph, normalized=True)
    scores = []
    for account_id, account in account_by_id.items():
        target_ids = followed_by[account_id]
        scores.append(
            CentralNodeScore(
                account_id=account.id,
                external_user_id=account.external_user_id,
                username=account.username,
                followed_by_targets=len(target_ids),
                target_coverage=len(target_ids) / target_count,
                betweenness=betweenness.get(f"a:{account.id}", 0.0),
            )
        )

    return sorted(
        scores,
        key=lambda item: (
            -item.target_coverage,
            -item.betweenness,
            -item.followed_by_targets,
            item.username.lower(),
        ),
    )[:limit]
