from pathlib import Path

from sqlalchemy import Engine, create_engine

from .models import Base


def create_engine_for_path(database_path: Path) -> Engine:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{database_path}", future=True)


def init_database(engine: Engine) -> None:
    Base.metadata.create_all(engine)
