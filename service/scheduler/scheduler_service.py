"""
Scheduler service.

## Traceability
Feature: F002
Scenarios: SC005, SC006, SC007, SC008, SC009
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from core import db_connect
from core.config import configs
from core.exceptions import ConflictError, ValidationError
from model.enums import SchedulerStatusEnum
from model.sync.scheduler_config_model import SchedulerConfigModel
from repository.scheduler.scheduler_repository import SchedulerRepository
from schema import (
    SchedulerRunResponseSchema,
    SchedulerScheduleUpdateSchema,
    SchedulerStatusResponseSchema,
)
from service.sync.pipeline_service import sync_pipeline_service
from .apscheduler_compat import CronTrigger
from .runtime import SchedulerRuntime, scheduler_runtime

logger = logging.getLogger(__name__)


class SchedulerService:
    PRESET_TO_CRON = {
        "hourly": "0 * * * *",
        "daily": "0 3 * * *",
        "weekly": "0 3 * * 1",
    }

    def __init__(
        self,
        repo: SchedulerRepository | None = None,
        runtime: SchedulerRuntime | None = None,
    ):
        self._repo = repo or SchedulerRepository()
        self._runtime = runtime or scheduler_runtime

    async def get_status(self, session: AsyncSession) -> SchedulerStatusResponseSchema:
        config = await self._ensure_config(session)
        if not self._runtime.is_configured():
            self._runtime.configure_job(
                cron_expression=config.cron_expression,
                is_active=config.is_active,
                callback=self._run_from_scheduler,
            )
        return self._build_status_response(config)

    async def bootstrap(self) -> None:
        try:
            async with self._session_scope() as session:
                config = await self._ensure_config(session)
                self._runtime.configure_job(
                    cron_expression=config.cron_expression,
                    is_active=config.is_active,
                    callback=self._run_from_scheduler,
                )
                logger.info(
                    "Scheduler bootstrapped job=%s cron=%s active=%s",
                    config.job_name,
                    config.cron_expression,
                    config.is_active,
                )
        except Exception:
            logger.exception("Failed to bootstrap scheduler runtime")
            return

    async def update_schedule(
        self,
        session: AsyncSession,
        body: SchedulerScheduleUpdateSchema,
    ) -> SchedulerStatusResponseSchema:
        config = await self._ensure_config(session)
        cron_expression = self._resolve_cron_expression(body)
        self._validate_cron_expression(cron_expression)

        config.cron_expression = cron_expression
        config = await self._repo.save(session, config)

        self._runtime.configure_job(
            cron_expression=config.cron_expression,
            is_active=config.is_active,
            callback=self._run_from_scheduler,
        )
        return self._build_status_response(config)

    async def run_now(self, session: AsyncSession) -> SchedulerRunResponseSchema:
        config = await self._ensure_config(session)
        self._runtime.configure_job(
            cron_expression=config.cron_expression,
            is_active=config.is_active,
            callback=self._run_from_scheduler,
        )

        acquired = await self._runtime.acquire_run_lock()
        if not acquired:
            raise ConflictError("Pipeline is already running")

        run_id = uuid4().hex
        started_at = datetime.utcnow()
        await self._repo.mark_running(
            session,
            config=config,
            started_at=started_at,
            note=f"run_id={run_id}",
        )

        asyncio.create_task(self._run_pipeline(run_id))
        logger.info("Manual scheduler run requested run_id=%s", run_id)
        return SchedulerRunResponseSchema(
            run_id=run_id,
            status=SchedulerStatusEnum.RUNNING.value,
            started_at=started_at,
        )

    async def pause(self, session: AsyncSession) -> SchedulerStatusResponseSchema:
        config = await self._ensure_config(session)
        config.is_active = False
        config = await self._repo.save(session, config)
        self._runtime.configure_job(
            cron_expression=config.cron_expression,
            is_active=config.is_active,
            callback=self._run_from_scheduler,
        )
        return self._build_status_response(config)

    async def resume(self, session: AsyncSession) -> SchedulerStatusResponseSchema:
        config = await self._ensure_config(session)
        config.is_active = True
        config = await self._repo.save(session, config)
        self._runtime.configure_job(
            cron_expression=config.cron_expression,
            is_active=config.is_active,
            callback=self._run_from_scheduler,
        )
        return self._build_status_response(config)

    def shutdown(self) -> None:
        self._runtime.shutdown()

    async def _run_from_scheduler(self) -> None:
        acquired = await self._runtime.acquire_run_lock()
        if not acquired:
            logger.info("Scheduled tick skipped: run is already in progress")
            return

        run_id = uuid4().hex
        started_at = datetime.utcnow()
        logger.info("Scheduled run triggered run_id=%s", run_id)
        async with self._session_scope() as session:
            config = await self._ensure_config(session)
            await self._repo.mark_running(
                session,
                config=config,
                started_at=started_at,
                note=f"run_id={run_id}",
            )
        await self._run_pipeline(run_id)

    async def _run_pipeline(self, run_id: str) -> None:
        status = SchedulerStatusEnum.OK
        note = f"run_id={run_id}; status=OK"
        logger.info("Pipeline execution started run_id=%s", run_id)

        try:
            async with self._session_scope() as session:
                result = await sync_pipeline_service.run_once(session)
                note = (
                    f"run_id={run_id}; status=OK; "
                    f"metadata_inserted={result.metadata_inserted}; "
                    f"processed={result.processed_count}; "
                    f"done={result.done_count}; "
                    f"filtered={result.filtered_count}; "
                    f"errors={result.error_count}; "
                    f"skipped={result.skipped_count}"
                )
                logger.info("Pipeline execution finished run_id=%s %s", run_id, note)
        except Exception as exc:
            status = SchedulerStatusEnum.ERROR
            note = f"run_id={run_id}; error={exc}"
            logger.exception("Pipeline execution failed run_id=%s", run_id)
        finally:
            try:
                async with self._session_scope() as session:
                    config = await self._ensure_config(session)
                    await self._repo.mark_finished(
                        session,
                        config=config,
                        status=status,
                        note=note,
                    )
            finally:
                self._runtime.release_run_lock()
                logger.info("Pipeline execution finalized run_id=%s status=%s", run_id, status.value)

    async def _ensure_config(self, session: AsyncSession) -> SchedulerConfigModel:
        config = await self._repo.get_or_create(
            session,
            job_name=configs.SCHEDULER_JOB_NAME,
            cron_expression=configs.SCHEDULER_DEFAULT_CRON,
            is_active=True,
        )
        return config

    def _resolve_cron_expression(self, body: SchedulerScheduleUpdateSchema) -> str:
        if body.cron_expression:
            return body.cron_expression
        if body.preset:
            return self.PRESET_TO_CRON[body.preset]
        raise ValidationError("Either cron_expression or preset is required")

    def _validate_cron_expression(self, cron_expression: str) -> None:
        try:
            CronTrigger.from_crontab(cron_expression)
        except ValueError as exc:
            raise ValidationError(f"Invalid cron_expression: {cron_expression}") from exc

    def _build_status_response(
        self,
        config: SchedulerConfigModel,
    ) -> SchedulerStatusResponseSchema:
        return SchedulerStatusResponseSchema(
            job_name=config.job_name,
            cron_expression=config.cron_expression,
            is_active=config.is_active,
            last_run_at=config.last_run_at,
            last_status=config.last_status,
            next_run_at=self._runtime.get_next_run_at(),
        )

    @asynccontextmanager
    async def _session_scope(self):
        db_connect._ensure_initialized()
        async with db_connect.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


scheduler_service = SchedulerService()
