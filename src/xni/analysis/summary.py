from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import ExpansionCandidate, Target, TargetRelationship
from .centrality import CentralNodeScore, rank_central_nodes
from .network import find_new_account_cohort_pairs, find_similarity_pairs
from .profiles import find_new_account_candidates


class NetworkAnalysisSummary(BaseModel):
    targets: int
    active_relationships: int
    pending_expansion_candidates: int
    promoted_expansion_candidates: int
    new_account_candidates: int
    similarity_pairs: int
    cohort_pairs: int
    central_nodes: list[CentralNodeScore]


def build_network_summary(
    session: Session,
    *,
    as_of: datetime,
    new_account_days: int,
    low_following_max: int,
    min_jaccard: float,
    min_shared: int,
    central_limit: int,
) -> NetworkAnalysisSummary:
    target_count = session.scalar(
        select(func.count()).select_from(Target).where(Target.is_active.is_(True))
    ) or 0
    relationship_count = session.scalar(
        select(func.count())
        .select_from(TargetRelationship)
        .join(Target, Target.id == TargetRelationship.target_id)
        .where(TargetRelationship.is_active.is_(True), Target.is_active.is_(True))
    ) or 0
    pending = session.scalar(
        select(func.count())
        .select_from(ExpansionCandidate)
        .where(ExpansionCandidate.status == "pending")
    ) or 0
    promoted = session.scalar(
        select(func.count())
        .select_from(ExpansionCandidate)
        .where(ExpansionCandidate.status == "promoted")
    ) or 0
    candidates = find_new_account_candidates(
        session,
        as_of=as_of,
        new_account_days=new_account_days,
        low_following_max=low_following_max,
    )
    similarities = find_similarity_pairs(
        session,
        min_jaccard=min_jaccard,
        min_shared=min_shared,
    )
    cohorts = find_new_account_cohort_pairs(
        session,
        as_of=as_of,
        new_account_days=new_account_days,
        low_following_max=low_following_max,
        min_jaccard=min_jaccard,
        min_shared=min_shared,
    )
    return NetworkAnalysisSummary(
        targets=target_count,
        active_relationships=relationship_count,
        pending_expansion_candidates=pending,
        promoted_expansion_candidates=promoted,
        new_account_candidates=len(candidates),
        similarity_pairs=len(similarities),
        cohort_pairs=len(cohorts),
        central_nodes=rank_central_nodes(session, limit=central_limit),
    )
