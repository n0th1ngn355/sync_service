"""
Health service.

## Traceability
Feature: F005
Scenarios: SC019, SC020, SC021, SC022
"""

from pathlib import Path
import tempfile

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import configs
from core.loader import VERSION
from schema import HealthCheckResponseSchema, LastSyncSchema


class HealthService:
    async def check_health(self, session: AsyncSession) -> HealthCheckResponseSchema:
        db_ok, db_error = await self._check_database(session)
        storage_ok, storage_error = self._check_storage()

        errors: list[str] = []
        if db_error:
            errors.append(f"database: {db_error}")
        if storage_error:
            errors.append(f"storage: {storage_error}")

        last_sync = LastSyncSchema()
        if db_ok:
            last_sync = await self._fetch_last_sync(session)

        return HealthCheckResponseSchema(
            status="healthy" if db_ok and storage_ok else "unhealthy",
            version=VERSION,
            database="connected" if db_ok else "disconnected",
            storage="available" if storage_ok else "unavailable",
            last_sync=last_sync,
            error="; ".join(errors) if errors else None,
        )

    async def _check_database(self, session: AsyncSession) -> tuple[bool, str | None]:
        try:
            await session.execute(text("SELECT 1"))
            return True, None
        except Exception as exc:
            return False, str(exc)

    def _check_storage(self) -> tuple[bool, str | None]:
        try:
            storage_dir = Path(configs.STORAGE_PATH)
            storage_dir.mkdir(parents=True, exist_ok=True)

            with tempfile.NamedTemporaryFile(dir=storage_dir, prefix=".healthcheck_", delete=True) as handle:
                handle.write(b"ok")
                handle.flush()

            return True, None
        except Exception as exc:
            return False, str(exc)

    async def _fetch_last_sync(self, session: AsyncSession) -> LastSyncSchema:
        try:
            result = await session.execute(
                text(
                    """
                    SELECT
                        last_status,
                        COALESCE(last_success_at, last_run_finished_at, last_run_started_at) AS last_time,
                        COALESCE(last_rows, 0) AS last_rows
                    FROM sync_state
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """
                )
            )
            row = result.first()
            if row is None:
                return LastSyncSchema()

            mapping = getattr(row, "_mapping", None)
            if mapping is not None:
                return LastSyncSchema(
                    status=mapping.get("last_status") or "UNKNOWN",
                    time=mapping.get("last_time"),
                    papers=int(mapping.get("last_rows") or 0),
                )

            return LastSyncSchema(
                status=row[0] or "UNKNOWN",
                time=row[1],
                papers=int(row[2] or 0),
            )
        except Exception:
            return LastSyncSchema()
