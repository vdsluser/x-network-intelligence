import base64
import gzip
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from functools import cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .analysis.centrality import CentralNodeScore, rank_central_nodes
from .analysis.classification.service import (
    AccountClassificationDetail,
    AssociationAggregate,
    ClassificationRunRequest,
    ClassificationRunSummary,
    TopicAggregate,
    get_account_classification_detail,
    list_association_aggregates,
    list_topic_aggregates,
    run_classification,
)
from .analysis.fingerprint import (
    FollowingFingerprint,
    build_following_fingerprint,
    build_following_fingerprints,
)
from .analysis.graph import GraphOptions, GraphResponse, build_graph, build_graph_options
from .analysis.network import (
    FollowingSimilarity,
    find_new_account_cohort_pairs,
    find_similarity_pairs,
)
from .analysis.profiles import AccountProfileSignal, find_new_account_candidates
from .config import Settings, get_settings
from .db import create_engine_for_path, init_database
from .services.batch import BatchImportRequest, BatchImportResult, import_manual_batch
from .services.expansion import (
    ExpansionQueueItem,
    ExpansionQueueRefresh,
    list_expansion_queue,
    promote_expansion_candidate,
    refresh_expansion_queue,
)
from .services.snapshots import ImportSummary, import_manual_snapshot

WEB_DIR = Path(__file__).with_name("web")


@cache
def _cytoscape_vendor_bytes() -> bytes:
    vendor_dir = WEB_DIR / "vendor"
    parts = sorted(vendor_dir.glob("cytoscape.min.js.gz.b64.part*"))
    if not parts:
        raise RuntimeError("Cytoscape vendor asset is missing")
    encoded = "".join(part.read_text(encoding="ascii") for part in parts)
    return gzip.decompress(base64.b64decode(encoded))


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

    @application.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @application.get("/static/vendor/cytoscape.min.js", include_in_schema=False)
    def cytoscape_vendor() -> Response:
        return Response(
            content=_cytoscape_vendor_bytes(),
            media_type="text/javascript",
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    @application.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "database": str(resolved_settings.database_path)}

    @application.post("/api/import/manual", response_model=ImportSummary)
    async def manual_import(payload: dict[str, Any]) -> ImportSummary:
        try:
            return await import_manual_snapshot(engine, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.post("/api/import/manual/batch", response_model=BatchImportResult)
    async def manual_batch(request: BatchImportRequest) -> BatchImportResult:
        try:
            return await import_manual_batch(
                engine,
                request.payloads,
                new_account_days=request.new_account_days,
                low_following_max=request.low_following_max,
                min_jaccard=request.min_jaccard,
                min_shared=request.min_shared,
                central_limit=request.central_limit,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.post("/api/expansion/queue/refresh", response_model=ExpansionQueueRefresh)
    def expansion_refresh(
        new_account_days: int = Query(default=90, ge=0),
        low_following_max: int = Query(default=100, ge=0),
    ) -> ExpansionQueueRefresh:
        with Session(engine) as session:
            return refresh_expansion_queue(
                session,
                as_of=datetime.now(timezone.utc),
                new_account_days=new_account_days,
                low_following_max=low_following_max,
            )

    @application.get("/api/expansion/queue", response_model=list[ExpansionQueueItem])
    def expansion_queue(
        status: str = Query(default="pending", pattern="^(pending|promoted)$"),
    ) -> list[ExpansionQueueItem]:
        with Session(engine) as session:
            return list_expansion_queue(session, status=status)

    @application.post(
        "/api/expansion/queue/{candidate_id}/promote",
        response_model=ExpansionQueueItem,
    )
    def expansion_promote(candidate_id: int) -> ExpansionQueueItem:
        with Session(engine) as session:
            try:
                return promote_expansion_candidate(session, candidate_id)
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.post("/api/analysis/classify", response_model=ClassificationRunSummary)
    def classify(request: ClassificationRunRequest) -> ClassificationRunSummary:
        with Session(engine) as session:
            try:
                return run_classification(session, request)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.get("/api/analysis/topics", response_model=list[TopicAggregate])
    def topic_aggregates(
        classifier_version: str = Query(default="rule-v1"),
    ) -> list[TopicAggregate]:
        with Session(engine) as session:
            try:
                return list_topic_aggregates(
                    session, classifier_version=classifier_version
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.get(
        "/api/analysis/associations", response_model=list[AssociationAggregate]
    )
    def association_aggregates(
        association_type: str | None = Query(default=None, alias="type"),
        limit: int = Query(default=50, ge=1, le=500),
        classifier_version: str = Query(default="rule-v1"),
    ) -> list[AssociationAggregate]:
        with Session(engine) as session:
            try:
                return list_association_aggregates(
                    session,
                    association_type=association_type,
                    limit=limit,
                    classifier_version=classifier_version,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.get(
        "/api/accounts/{account_id}/classification",
        response_model=AccountClassificationDetail,
    )
    def account_classification(
        account_id: int,
        classifier_version: str = Query(default="rule-v1"),
    ) -> AccountClassificationDetail:
        with Session(engine) as session:
            try:
                return get_account_classification_detail(
                    session, account_id, classifier_version=classifier_version
                )
            except ValueError as exc:
                status_code = 404 if str(exc) == "account not found" else 400
                raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    @application.get(
        "/api/analysis/new-accounts", response_model=list[AccountProfileSignal]
    )
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

    @application.get(
        "/api/analysis/similarity", response_model=list[FollowingSimilarity]
    )
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

    @application.get(
        "/api/analysis/central-nodes", response_model=list[CentralNodeScore]
    )
    def central_nodes(
        limit: int = Query(default=20, ge=1, le=500),
    ) -> list[CentralNodeScore]:
        with Session(engine) as session:
            return rank_central_nodes(session, limit=limit)

    @application.get(
        "/api/analysis/fingerprints", response_model=list[FollowingFingerprint]
    )
    def fingerprints(
        new_account_days: int = Query(default=90, ge=0),
        low_following_max: int = Query(default=100, ge=0),
        min_cohort_jaccard: float = Query(default=0.2, ge=0, le=1),
        min_cohort_shared: int = Query(default=2, ge=0),
        top_node_limit: int = Query(default=5, ge=1, le=50),
        classifier_version: str = Query(default="rule-v1"),
    ) -> list[FollowingFingerprint]:
        with Session(engine) as session:
            try:
                return build_following_fingerprints(
                    session,
                    as_of=datetime.now(timezone.utc),
                    new_account_days=new_account_days,
                    low_following_max=low_following_max,
                    min_cohort_jaccard=min_cohort_jaccard,
                    min_cohort_shared=min_cohort_shared,
                    top_node_limit=top_node_limit,
                    classifier_version=classifier_version,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.get(
        "/api/analysis/fingerprints/{target_username}",
        response_model=FollowingFingerprint,
    )
    def fingerprint(
        target_username: str,
        new_account_days: int = Query(default=90, ge=0),
        low_following_max: int = Query(default=100, ge=0),
        min_cohort_jaccard: float = Query(default=0.2, ge=0, le=1),
        min_cohort_shared: int = Query(default=2, ge=0),
        top_node_limit: int = Query(default=5, ge=1, le=50),
        classifier_version: str = Query(default="rule-v1"),
    ) -> FollowingFingerprint:
        with Session(engine) as session:
            try:
                return build_following_fingerprint(
                    session,
                    target_username,
                    as_of=datetime.now(timezone.utc),
                    new_account_days=new_account_days,
                    low_following_max=low_following_max,
                    min_cohort_jaccard=min_cohort_jaccard,
                    min_cohort_shared=min_cohort_shared,
                    top_node_limit=top_node_limit,
                    classifier_version=classifier_version,
                )
            except ValueError as exc:
                status_code = 404 if str(exc).startswith("active target") else 400
                raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    @application.get("/api/graph/options", response_model=GraphOptions)
    def graph_options(
        classifier_version: str = Query(default="rule-v1"),
    ) -> GraphOptions:
        with Session(engine) as session:
            try:
                return build_graph_options(
                    session, classifier_version=classifier_version
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.get("/api/graph", response_model=GraphResponse)
    def graph_view(
        target: str | None = Query(default=None),
        topic: str | None = Query(default=None),
        account_type: str | None = Query(default=None),
        new_only: bool = Query(default=False),
        new_account_days: int = Query(default=90, ge=0),
        min_target_coverage: float = Query(default=0.0, ge=0, le=1),
        max_accounts: int = Query(default=500, ge=1, le=2000),
        classifier_version: str = Query(default="rule-v1"),
    ) -> GraphResponse:
        with Session(engine) as session:
            try:
                return build_graph(
                    session,
                    target=target,
                    topic=topic,
                    account_type=account_type,
                    new_only=new_only,
                    new_account_days=new_account_days,
                    min_target_coverage=min_target_coverage,
                    max_accounts=max_accounts,
                    classifier_version=classifier_version,
                    as_of=datetime.now(timezone.utc),
                )
            except ValueError as exc:
                message = str(exc)
                status_code = 404 if message.startswith("target not found:") else 400
                raise HTTPException(status_code=status_code, detail=message) from exc

    application.mount(
        "/static",
        StaticFiles(directory=WEB_DIR, check_dir=True),
        name="static",
    )
    return application


app = create_app()
