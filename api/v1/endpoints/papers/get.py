"""
Paper read endpoints.

## Traceability
Feature: F003
Scenarios: SC010, SC011, SC012, SC013, SC014
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core import db_connect
from schema import (
    PaperContentResponseSchema,
    PaperDetailResponseSchema,
    PaperListResponseSchema,
    PaperStatsResponseSchema,
)
from service import PaperService

router = APIRouter(prefix="/papers", tags=["Papers"])
service = PaperService()


@router.get("", response_model=PaperListResponseSchema)
async def get_papers(
    source: str | None = Query(default=None),
    status: str | None = Query(default=None),
    material: str | None = Query(default=None),
    tc_k_min: float | None = Query(default=None, alias="tc_K_min"),
    tc_k_max: float | None = Query(default=None, alias="tc_K_max"),
    paper_type: str | None = Query(default=None, alias="type"),
    dimensionality: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(db_connect.get_session),
) -> PaperListResponseSchema:
    return await service.get_papers(
        session,
        source=source,
        status=status,
        material=material,
        tc_k_min=tc_k_min,
        tc_k_max=tc_k_max,
        paper_type=paper_type,
        dimensionality=dimensionality,
        offset=offset,
        limit=limit,
    )


@router.get("/stats", response_model=PaperStatsResponseSchema)
async def get_papers_stats(
    session: AsyncSession = Depends(db_connect.get_session),
) -> PaperStatsResponseSchema:
    return await service.get_stats(session)


@router.get("/{paper_id}", response_model=PaperDetailResponseSchema)
async def get_paper_by_id(
    paper_id: int,
    session: AsyncSession = Depends(db_connect.get_session),
) -> PaperDetailResponseSchema:
    return await service.get_paper_by_id(session, paper_id)


@router.get("/{paper_id}/content", response_model=PaperContentResponseSchema)
async def get_paper_content(
    paper_id: int,
    session: AsyncSession = Depends(db_connect.get_session),
) -> PaperContentResponseSchema:
    return await service.get_paper_content(session, paper_id)
