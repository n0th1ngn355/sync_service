"""
Application configuration.

## Traceability
Infrastructure.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Configs:
    MODE_DEBUG: bool = os.getenv("MODE_DEBUG", "False") == "True"

    SERVICE_NAME: str = os.getenv("SERVICE_NAME", "ArXiv Superconductor Papers Sync Service")
    SERVICE_VERSION: str = os.getenv("SERVICE_VERSION", "0.1.0")

    STORAGE_PATH: str = os.getenv("STORAGE_PATH", "storage")
    SCHEDULER_DEFAULT_CRON: str = os.getenv("SCHEDULER_DEFAULT_CRON", "0 * * * *")
    SCHEDULER_JOB_NAME: str = os.getenv("SCHEDULER_JOB_NAME", "sync_pipeline")

    DB_ENGINE: str = os.getenv("DB_ENGINE", "postgresql")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "")
    DB_USER: str = os.getenv("DB_USER", "")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    def _sqlite_path(self) -> str:
        db_name = self.DB_NAME or "sync_service.db"
        return Path(db_name).as_posix()

    @property
    def database_url(self) -> str:
        if self.DB_ENGINE.startswith("sqlite"):
            db_path = self._sqlite_path()
            if "+aiosqlite" in self.DB_ENGINE:
                return f"{self.DB_ENGINE}:///{db_path}"
            return f"sqlite+aiosqlite:///{db_path}"

        return (
            f"{self.DB_ENGINE}+asyncpg://"
            f"{self.DB_USER}:{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def database_url_sync(self) -> str:
        if self.DB_ENGINE.startswith("sqlite"):
            return f"sqlite:///{self._sqlite_path()}"

        return (
            f"{self.DB_ENGINE}://"
            f"{self.DB_USER}:{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


configs = Configs()
