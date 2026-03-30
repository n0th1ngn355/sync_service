"""
Application runtime configuration.

## Traceability
Infrastructure.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Configs:
    """
    Centralized environment-backed settings.

    Notes:
    - Values are parsed once at import time.
    - Boolean flags use explicit `"True"` string checks.
    - PostgreSQL is the default database backend.
    """

    # Service runtime.
    MODE_DEBUG: bool = os.getenv("MODE_DEBUG", "False") == "True"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Public API metadata.
    SERVICE_NAME: str = os.getenv("SERVICE_NAME", "ArXiv Superconductor Papers Sync Service")
    SERVICE_VERSION: str = os.getenv("SERVICE_VERSION", "0.1.0")

    # Local storage and scheduler defaults.
    STORAGE_PATH: str = os.getenv("STORAGE_PATH", "storage")
    SCHEDULER_DEFAULT_CRON: str = os.getenv("SCHEDULER_DEFAULT_CRON", "0 * * * *")
    SCHEDULER_JOB_NAME: str = os.getenv("SCHEDULER_JOB_NAME", "sync_pipeline")

    # Sync pipeline tuning.
    SYNC_OVERLAP_DAYS: int = int(os.getenv("SYNC_OVERLAP_DAYS", "2"))
    SYNC_PROCESS_BATCH_SIZE: int = int(os.getenv("SYNC_PROCESS_BATCH_SIZE", "300"))

    # arXiv upstream endpoints.
    ARXIV_OAI_BASE_URL: str = os.getenv("ARXIV_OAI_BASE_URL", "https://oaipmh.arxiv.org/oai")
    ARXIV_OAI_SET: str = os.getenv("ARXIV_OAI_SET", "physics:cond-mat")
    ARXIV_MANIFEST_URL: str = os.getenv("ARXIV_MANIFEST_URL", "")
    ARXIV_PDF_BASE_URL: str = os.getenv("ARXIV_PDF_BASE_URL", "https://arxiv.org/pdf")
    ARXIV_HTTP_TIMEOUT_SECONDS: float = float(os.getenv("ARXIV_HTTP_TIMEOUT_SECONDS", "60"))

    # Optional arXiv S3 TAR mode.
    ARXIV_PDF_USE_S3: bool = os.getenv("ARXIV_PDF_USE_S3", "False") == "True"
    ARXIV_S3_BUCKET: str = os.getenv("ARXIV_S3_BUCKET", "arxiv")
    ARXIV_S3_REGION: str = os.getenv("ARXIV_S3_REGION", "us-east-1")
    ARXIV_S3_REQUEST_PAYER: bool = os.getenv("ARXIV_S3_REQUEST_PAYER", "True") == "True"

    # Database connection.
    DB_ENGINE: str = os.getenv("DB_ENGINE", "postgresql")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "")
    DB_USER: str = os.getenv("DB_USER", "")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    def _sqlite_path(self) -> str:
        """Return normalized local SQLite database path."""
        db_name = self.DB_NAME or "sync_service.db"
        return Path(db_name).as_posix()

    @property
    def database_url(self) -> str:
        """Build async SQLAlchemy URL for app runtime."""
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
        """Build sync SQLAlchemy URL for Alembic migrations."""
        if self.DB_ENGINE.startswith("sqlite"):
            return f"sqlite:///{self._sqlite_path()}"

        return (
            f"{self.DB_ENGINE}://"
            f"{self.DB_USER}:{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


configs = Configs()
