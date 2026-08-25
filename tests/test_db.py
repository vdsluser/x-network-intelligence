from pathlib import Path

from sqlalchemy import inspect

from xni.db import create_engine_for_path, init_database


def test_init_database_creates_targets_table(tmp_path: Path) -> None:
    db_path = tmp_path / "x_network.db"
    engine = create_engine_for_path(db_path)
    init_database(engine)
    assert "targets" in inspect(engine).get_table_names()
