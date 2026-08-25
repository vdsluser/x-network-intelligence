from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from sqlalchemy.orm import Session

from .analysis.centrality import CentralNodeScore, rank_central_nodes
from .analysis.fingerprint import FollowingFingerprint, build_following_fingerprint, build_following_fingerprints
from .analysis.network import FollowingSimilarity, find_new_account_cohort_pairs, find_similarity_pairs
from .analysis.profiles import AccountProfileSignal, find_new_account_candidates
from .analysis.classification.service import (
    AccountClassificationDetail, AssociationAggregate, ClassificationRunRequest, ClassificationRunSummary, TopicAggregate,
    get_account_classification_detail, list_association_aggregates, list_topic_aggregates, run_classification,
)
from .config import Settings, get_settings
from .db import create_engine_for_path, init_database
from .services.batch import BatchImportRequest, BatchImportResult, import_manual_batch
from .services.expansion import ExpansionQueueItem, ExpansionQueueRefresh, list_expansion_queue, promote_expansion_candidate, refresh_expansion_queue
from .services.snapshots import ImportSummary, import_manual_snapshot


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    engine = create_engine_for_path(resolved_settings.database_path)
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        resolved_settings.ensure_directories(); init_database(engine); yield; engine.dispose()
    application = FastAPI(title="X Network Intelligence", lifespan=lifespan)
    @application.get("/api/health")
    def health() -> dict[str,str]: return {"status":"ok","database":str(resolved_settings.database_path)}
    @application.post("/api/import/manual", response_model=ImportSummary)
    async def manual_import(payload:dict[str,Any]):
        try:return await import_manual_snapshot(engine,payload)
        except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc
    @application.post("/api/import/manual/batch", response_model=BatchImportResult)
    async def manual_batch(request:BatchImportRequest):
        try:return await import_manual_batch(engine,request.payloads,new_account_days=request.new_account_days,low_following_max=request.low_following_max,min_jaccard=request.min_jaccard,min_shared=request.min_shared,central_limit=request.central_limit)
        except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc
    @application.post("/api/expansion/queue/refresh", response_model=ExpansionQueueRefresh)
    def expansion_refresh(new_account_days:int=Query(default=90,ge=0),low_following_max:int=Query(default=100,ge=0)):
        with Session(engine) as session:return refresh_expansion_queue(session,as_of=datetime.now(timezone.utc),new_account_days=new_account_days,low_following_max=low_following_max)
    @application.get("/api/expansion/queue", response_model=list[ExpansionQueueItem])
    def expansion_queue(status:str=Query(default="pending",pattern="^(pending|promoted)$")):
        with Session(engine) as session:return list_expansion_queue(session,status=status)
    @application.post("/api/expansion/queue/{candidate_id}/promote", response_model=ExpansionQueueItem)
    def expansion_promote(candidate_id:int):
        with Session(engine) as session:
            try:return promote_expansion_candidate(session,candidate_id)
            except ValueError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    @application.post("/api/analysis/classify", response_model=ClassificationRunSummary)
    def classify(request: ClassificationRunRequest) -> ClassificationRunSummary:
        with Session(engine) as session:
            try:
                return run_classification(session, request)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.get("/api/analysis/topics", response_model=list[TopicAggregate])
    def topic_aggregates(classifier_version: str = Query(default="rule-v1")) -> list[TopicAggregate]:
        with Session(engine) as session:
            try:
                return list_topic_aggregates(session, classifier_version=classifier_version)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.get("/api/analysis/associations", response_model=list[AssociationAggregate])
    def association_aggregates(
        association_type: str | None = Query(default=None, alias="type"),
        limit: int = Query(default=50, ge=1, le=500),
        classifier_version: str = Query(default="rule-v1"),
    ) -> list[AssociationAggregate]:
        with Session(engine) as session:
            try:
                return list_association_aggregates(
                    session, association_type=association_type, limit=limit, classifier_version=classifier_version
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.get("/api/accounts/{account_id}/classification", response_model=AccountClassificationDetail)
    def account_classification(
        account_id: int, classifier_version: str = Query(default="rule-v1")
    ) -> AccountClassificationDetail:
        with Session(engine) as session:
            try:
                return get_account_classification_detail(
                    session, account_id, classifier_version=classifier_version
                )
            except ValueError as exc:
                status_code = 404 if str(exc) == "account not found" else 400
                raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    @application.get("/api/analysis/new-accounts", response_model=list[AccountProfileSignal])
    def new_accounts(new_account_days:int=Query(default=90,ge=0),low_following_max:int=Query(default=100,ge=0)):
        with Session(engine) as session:return find_new_account_candidates(session,as_of=datetime.now(timezone.utc),new_account_days=new_account_days,low_following_max=low_following_max)
    @application.get("/api/analysis/similarity", response_model=list[FollowingSimilarity])
    def similarity(min_jaccard:float=Query(default=0.2,ge=0,le=1),min_shared:int=Query(default=2,ge=0)):
        with Session(engine) as session:return find_similarity_pairs(session,min_jaccard=min_jaccard,min_shared=min_shared)
    @application.get("/api/analysis/cohorts", response_model=list[FollowingSimilarity])
    def cohorts(new_account_days:int=Query(default=90,ge=0),low_following_max:int=Query(default=100,ge=0),min_jaccard:float=Query(default=0.2,ge=0,le=1),min_shared:int=Query(default=2,ge=0)):
        with Session(engine) as session:return find_new_account_cohort_pairs(session,as_of=datetime.now(timezone.utc),new_account_days=new_account_days,low_following_max=low_following_max,min_jaccard=min_jaccard,min_shared=min_shared)
    @application.get("/api/analysis/central-nodes", response_model=list[CentralNodeScore])
    def central_nodes(limit:int=Query(default=20,ge=1,le=500)):
        with Session(engine) as session:return rank_central_nodes(session,limit=limit)
    @application.get("/api/analysis/fingerprints", response_model=list[FollowingFingerprint])
    def fingerprints(
        new_account_days:int=Query(default=90,ge=0),
        low_following_max:int=Query(default=100,ge=0),
        min_cohort_jaccard:float=Query(default=0.2,ge=0,le=1),
        min_cohort_shared:int=Query(default=2,ge=0),
        top_node_limit:int=Query(default=5,ge=1,le=50),
        classifier_version:str=Query(default="rule-v1"),
    ):
        with Session(engine) as session:
            try:
                return build_following_fingerprints(
                    session,as_of=datetime.now(timezone.utc),new_account_days=new_account_days,
                    low_following_max=low_following_max,min_cohort_jaccard=min_cohort_jaccard,
                    min_cohort_shared=min_cohort_shared,top_node_limit=top_node_limit,
                    classifier_version=classifier_version,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400,detail=str(exc)) from exc
    @application.get("/api/analysis/fingerprints/{target_username}", response_model=FollowingFingerprint)
    def fingerprint(
        target_username:str,
        new_account_days:int=Query(default=90,ge=0),
        low_following_max:int=Query(default=100,ge=0),
        min_cohort_jaccard:float=Query(default=0.2,ge=0,le=1),
        min_cohort_shared:int=Query(default=2,ge=0),
        top_node_limit:int=Query(default=5,ge=1,le=50),
        classifier_version:str=Query(default="rule-v1"),
    ):
        with Session(engine) as session:
            try:
                return build_following_fingerprint(
                    session,target_username,as_of=datetime.now(timezone.utc),new_account_days=new_account_days,
                    low_following_max=low_following_max,min_cohort_jaccard=min_cohort_jaccard,
                    min_cohort_shared=min_cohort_shared,top_node_limit=top_node_limit,
                    classifier_version=classifier_version,
                )
            except ValueError as exc:
                status_code = 404 if str(exc).startswith("active target") else 400
                raise HTTPException(status_code=status_code,detail=str(exc)) from exc
    return application

app=create_app()
