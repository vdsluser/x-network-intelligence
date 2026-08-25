from pathlib import Path

from xni.config import Settings


def test_settings_creates_parent_directory(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "x_network.db"
    settings = Settings(database_path=db_path)
    settings.ensure_directories()
    assert db_path.parent.exists()
