"""
Scheduler repository.

## Traceability
Feature: F002
Scenarios: SC005, SC006, SC007, SC008, SC009
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from model.sync.scheduler_config_model import SchedulerConfigModel
from model.enums import SchedulerStatusEnum


class SchedulerRepository:
    def __init__(self):
        self.model = SchedulerConfigModel

    async def get_by_job_name(
        self,
        session: AsyncSession,
        *,
        job_name: str,
    ) -> SchedulerConfigModel | None:
        stmt = select(self.model).where(self.model.job_name == job_name)
        return (await session.execute(stmt)).scalar_one_or_none()

    async def get_or_create(
        self,
        session: AsyncSession,
        *,
        job_name: str,
        cron_expression: str,
        is_active: bool,
    ) -> SchedulerConfigModel:
        config = await self.get_by_job_name(session, job_name=job_name)
        if config is not None:
            return config

        config = self.model(
            job_name=job_name,
            cron_expression=cron_expression,
            is_active=is_active,
            last_status=SchedulerStatusEnum.IDLE.value,
        )
        session.add(config)
        await session.flush()
        await session.refresh(config)
        return config

    async def save(self, session: AsyncSession, config: SchedulerConfigModel) -> SchedulerConfigModel:
        session.add(config)
        await session.flush()
        await session.refresh(config)
        return config

    async def mark_running(
        self,
        session: AsyncSession,
        *,
        config: SchedulerConfigModel,
        started_at: datetime,
        note: str | None,
    ) -> SchedulerConfigModel:
        config.last_run_at = started_at
        config.last_status = SchedulerStatusEnum.RUNNING.value
        config.note = note
        return await self.save(session, config)

    async def mark_finished(
        self,
        session: AsyncSession,
        *,
        config: SchedulerConfigModel,
        status: SchedulerStatusEnum,
        note: str | None,
    ) -> SchedulerConfigModel:
        config.last_status = status.value
        config.note = note
        return await self.save(session, config)
