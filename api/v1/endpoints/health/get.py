"""
Health endpoints.

## Traceability
Feature: F005
Scenarios: SC019, SC020, SC021, SC022
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core import db_connect
from schema import HealthCheckResponseSchema
from service import HealthService

router = APIRouter(prefix="/health", tags=["Health"])
service = HealthService()


@router.get("", response_model=HealthCheckResponseSchema)
async def health_check(session: AsyncSession = Depends(db_connect.get_session)) -> HealthCheckResponseSchema:
    """
    Return full health diagnostics for operators.

    Includes:
    - database connectivity
    - storage availability
    - last synchronization summary
    """
    return await service.check_health(session)


@router.get("/live")
async def liveness() -> dict[str, str]:
    """Liveness probe: process is up."""
    return {"status": "alive"}


@router.get("/ready", response_model=HealthCheckResponseSchema)
async def readiness(session: AsyncSession = Depends(db_connect.get_session)) -> HealthCheckResponseSchema | JSONResponse:
    """
    Readiness probe: dependencies are available.

    Returns:
    - `200` when DB and storage are healthy
    - `503` when at least one dependency is unavailable
    """
    result = await service.check_health(session)

    if result.database != "connected" or result.storage != "available":
        return JSONResponse(status_code=503, content=result.model_dump(mode="json"))

    return result
