from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from ..analysis.summary import NetworkAnalysisSummary, build_network_summary
from .expansion import ExpansionQueueRefresh, refresh_expansion_queue
from .snapshots import ImportSummary, import_manual_snapshot


class BatchImportRequest(BaseModel):
    payloads: list[dict[str, Any]]
    new_account_days: int = Field(default=90, ge=0)
    low_following_max: int = Field(default=100, ge=0)
    min_jaccard: float = Field(default=0.2, ge=0, le=1)
    min_shared: int = Field(default=2, ge=0)
    central_limit: int = Field(default=20, ge=1, le=500)


class BatchImportResult(BaseModel):
    imports: list[ImportSummary]
    queue: ExpansionQueueRefresh
    analysis: NetworkAnalysisSummary


async def import_manual_batch(
    engine: Engine,
    payloads: list[dict[str, Any]],
    *,
    new_account_days: int = 90,
    low_following_max: int = 100,
    min_jaccard: float = 0.2,
    min_shared: int = 2,
    central_limit: int = 20,
) -> BatchImportResult:
    if not payloads:
        raise ValueError("batch import requires at least one payload")

    imports = []
    for payload in payloads:
        imports.append(await import_manual_snapshot(engine, payload))

    as_of = datetime.now(timezone.utc)
    with Session(engine) as session:
        queue = refresh_expansion_queue(
            session,
            as_of=as_of,
            new_account_days=new_account_days,
            low_following_max=low_following_max,
        )
        analysis = build_network_summary(
            session,
            as_of=as_of,
            new_account_days=new_account_days,
            low_following_max=low_following_max,
            min_jaccard=min_jaccard,
            min_shared=min_shared,
            central_limit=central_limit,
        )

    return BatchImportResult(imports=imports, queue=queue, analysis=analysis)
