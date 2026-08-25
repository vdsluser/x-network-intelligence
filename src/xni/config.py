from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    database_path: Path = Path("data/x_network.db")
    host: str = "127.0.0.1"
    port: int = 8000

    def ensure_directories(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    return Settings()
