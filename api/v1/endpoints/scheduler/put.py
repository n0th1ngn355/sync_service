"""
Scheduler update endpoints.

## Traceability
Feature: F002
Scenarios: SC006
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core import db_connect
from schema import SchedulerScheduleUpdateSchema, SchedulerStatusResponseSchema
from service.scheduler.scheduler_service import scheduler_service

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


@router.put("/schedule", response_model=SchedulerStatusResponseSchema)
async def update_schedule(
    body: SchedulerScheduleUpdateSchema,
    session: AsyncSession = Depends(db_connect.get_session),
) -> SchedulerStatusResponseSchema:
    """Update scheduler cron via explicit expression or preset alias."""
    return await scheduler_service.update_schedule(session, body)
