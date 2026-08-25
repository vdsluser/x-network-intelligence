from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException

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

    return application


app = create_app()
