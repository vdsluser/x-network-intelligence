from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from sqlalchemy.orm import Session

from .analysis.centrality import CentralNodeScore, rank_central_nodes
from .analysis.network import FollowingSimilarity, find_new_account_cohort_pairs, find_similarity_pairs
from .analysis.profiles import AccountProfileSignal, find_new_account_candidates
from .config import Settings, get_settings
from .db import create_engine_for_path, init_database
from .services.snapshots import ImportSummary, import_manual_snapshot


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    engine = create_engine_for_path(resolved_settings.database_path)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        resolved_settings.ensure_directories()
        init_database(engine)
        yield
        engine.dispose()

    application = FastAPI(title="X Network Intelligence", lifespan=lifespan)

    @application.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "database": str(resolved_settings.database_path)}

    @application.post("/api/import/manual", response_model=ImportSummary)
    async def manual_import(payload: dict[str, Any]) -> ImportSummary:
        try:
            return await import_manual_snapshot(engine, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.get("/api/analysis/new-accounts", response_model=list[AccountProfileSignal])
    def new_accounts(
        new_account_days: int = Query(default=90, ge=0),
        low_following_max: int = Query(default=100, ge=0),
    ) -> list[AccountProfileSignal]:
        with Session(engine) as session:
            return find_new_account_candidates(
                session,
                as_of=datetime.now(timezone.utc),
                new_account_days=new_account_days,
                low_following_max=low_following_max,
            )

    @application.get("/api/analysis/similarity", response_model=list[FollowingSimilarity])
    def similarity(
        min_jaccard: float = Query(default=0.2, ge=0, le=1),
        min_shared: int = Query(default=2, ge=0),
    ) -> list[FollowingSimilarity]:
        with Session(engine) as session:
            return find_similarity_pairs(
                session, min_jaccard=min_jaccard, min_shared=min_shared
            )

    @application.get("/api/analysis/cohorts", response_model=list[FollowingSimilarity])
    def cohorts(
        new_account_days: int = Query(default=90, ge=0),
        low_following_max: int = Query(default=100, ge=0),
        min_jaccard: float = Query(default=0.2, ge=0, le=1),
        min_shared: int = Query(default=2, ge=0),
    ) -> list[FollowingSimilarity]:
        with Session(engine) as session:
            return find_new_account_cohort_pairs(
                session,
                as_of=datetime.now(timezone.utc),
                new_account_days=new_account_days,
                low_following_max=low_following_max,
                min_jaccard=min_jaccard,
                min_shared=min_shared,
            )

    @application.get("/api/analysis/central-nodes", response_model=list[CentralNodeScore])
    def central_nodes(
        limit: int = Query(default=20, ge=1, le=500),
    ) -> list[CentralNodeScore]:
        with Session(engine) as session:
            return rank_central_nodes(session, limit=limit)

    return application


app = create_app()
