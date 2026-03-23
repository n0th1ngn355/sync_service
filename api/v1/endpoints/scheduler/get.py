"""
Scheduler read endpoints.

## Traceability
Feature: F002
Scenarios: SC005
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core import db_connect
from schema import SchedulerStatusResponseSchema
from service.scheduler.scheduler_service import scheduler_service

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


@router.get("/status", response_model=SchedulerStatusResponseSchema)
async def get_scheduler_status(
    session: AsyncSession = Depends(db_connect.get_session),
) -> SchedulerStatusResponseSchema:
    return await scheduler_service.get_status(session)
