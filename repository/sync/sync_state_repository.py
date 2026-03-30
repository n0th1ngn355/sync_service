"""
Sync state repository.

## Traceability
Feature: F001
Business Rules: BR004, BR005, BR007
Scenarios: SC001, SC003, SC004
"""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from model.enums import SyncStatusEnum
from model.sync.sync_state_model import SyncStateModel


class SyncStateRepository:
    """Persistence operations for incremental sync state snapshots."""

    def __init__(self):
        self.model = SyncStateModel

    async def get_by_source(
        self,
        session: AsyncSession,
        *,
        source: str,
    ) -> SyncStateModel | None:
        """Return sync state row by source key."""
        stmt = select(self.model).where(self.model.source == source)
        return (await session.execute(stmt)).scalar_one_or_none()

    async def get_or_create(
        self,
        session: AsyncSession,
        *,
        source: str,
    ) -> SyncStateModel:
        """Return source state or create initial OK state."""
        state = await self.get_by_source(session, source=source)
        if state is not None:
            return state

        state = self.model(source=source, last_status=SyncStatusEnum.OK.value)
        session.add(state)
        await session.flush()
        await session.refresh(state)
        return state

    async def save(self, session: AsyncSession, state: SyncStateModel) -> SyncStateModel:
        """Persist sync state row."""
        session.add(state)
        await session.flush()
        await session.refresh(state)
        return state

    async def mark_running(
        self,
        session: AsyncSession,
        *,
        state: SyncStateModel,
        started_at: datetime,
        note: str | None,
    ) -> SyncStateModel:
        """Mark sync pipeline as running."""
        state.last_status = SyncStatusEnum.RUNNING.value
        state.last_error = None
        state.last_run_started_at = started_at
        state.last_run_finished_at = None
        state.note = note
        return await self.save(session, state)

    async def mark_success(
        self,
        session: AsyncSession,
        *,
        state: SyncStateModel,
        finished_at: datetime,
        rows_written: int,
        checkpoint_datestamp: date | None,
        note: str | None,
    ) -> SyncStateModel:
        """Persist successful sync run metrics."""
        state.last_status = SyncStatusEnum.OK.value
        state.last_error = None
        state.last_run_finished_at = finished_at
        state.last_success_at = finished_at
        if checkpoint_datestamp is not None:
            state.last_success_datestamp = checkpoint_datestamp
        state.last_rows = rows_written
        state.total_rows = int(state.total_rows or 0) + rows_written
        state.note = note
        return await self.save(session, state)

    async def mark_error(
        self,
        session: AsyncSession,
        *,
        state: SyncStateModel,
        finished_at: datetime,
        error_text: str,
        note: str | None,
    ) -> SyncStateModel:
        """Persist failed sync run status and error details."""
        state.last_status = SyncStatusEnum.ERROR.value
        state.last_error = error_text[:8000]
        state.last_run_finished_at = finished_at
        state.last_rows = 0
        state.note = note
        return await self.save(session, state)
