from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import Settings, get_settings
from .db import create_engine_for_path, init_database


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        resolved_settings.ensure_directories()
        engine = create_engine_for_path(resolved_settings.database_path)
        init_database(engine)
        yield
        engine.dispose()

    application = FastAPI(title="X Network Intelligence", lifespan=lifespan)

    @application.get("/api/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "database": str(resolved_settings.database_path),
        }

    return application


app = create_app()
