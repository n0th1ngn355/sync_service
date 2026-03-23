"""
Scheduler action endpoints.

## Traceability
Feature: F002
Scenarios: SC007, SC008, SC009
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core import db_connect
from schema import SchedulerRunResponseSchema, SchedulerStatusResponseSchema
from service.scheduler.scheduler_service import scheduler_service

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


@router.post("/run", response_model=SchedulerRunResponseSchema, status_code=status.HTTP_202_ACCEPTED)
async def run_scheduler_now(
    session: AsyncSession = Depends(db_connect.get_session),
) -> SchedulerRunResponseSchema:
    return await scheduler_service.run_now(session)


@router.post("/pause", response_model=SchedulerStatusResponseSchema)
async def pause_scheduler(
    session: AsyncSession = Depends(db_connect.get_session),
) -> SchedulerStatusResponseSchema:
    return await scheduler_service.pause(session)


@router.post("/resume", response_model=SchedulerStatusResponseSchema)
async def resume_scheduler(
    session: AsyncSession = Depends(db_connect.get_session),
) -> SchedulerStatusResponseSchema:
    return await scheduler_service.resume(session)
