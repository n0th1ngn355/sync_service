"""
Paper service.

## Traceability
Feature: F003
Scenarios: SC010, SC011, SC012, SC013, SC014
"""

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import NotFoundError, ValidationError
from repository.paper.paper_repository import PaperRepository
from schema import (
    PaperContentResponseSchema,
    PaperDetailResponseSchema,
    PaperListItemSchema,
    PaperListResponseSchema,
    PaperStatsResponseSchema,
    StatsBucketSchema,
    TopMaterialSchema,
)


class PaperService:
    def __init__(self, repo: PaperRepository | None = None):
        self._repo = repo or PaperRepository()

    async def get_papers(
        self,
        session: AsyncSession,
        *,
        source: str | None,
        status: str | None,
        material: str | None,
        tc_k_min: float | None,
        tc_k_max: float | None,
        paper_type: str | None,
        dimensionality: str | None,
        offset: int,
        limit: int,
    ) -> PaperListResponseSchema:
        if offset < 0:
            raise ValidationError("offset must be >= 0")

        if limit <= 0:
            raise ValidationError("limit must be > 0")

        if limit > 200:
            raise ValidationError("limit must be <= 200")

        items, total = await self._repo.get_list(
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

        return PaperListResponseSchema(
            items=[
                PaperListItemSchema(
                    id=item.id,
                    external_id=item.external_id,
                    source=item.source,
                    title=item.title,
                    authors=item.authors,
                    categories=item.categories,
                    payload=item.payload or {},
                    status=item.status,
                    published_at=item.published_at,
                )
                for item in items
            ],
            total=total,
            offset=offset,
            limit=limit,
        )

    async def get_paper_by_id(
        self,
        session: AsyncSession,
        paper_id: int,
    ) -> PaperDetailResponseSchema:
        paper = await self._repo.get_by_id(session, paper_id)
        if paper is None:
            raise NotFoundError("paper", paper_id)

        source_meta = await self._repo.get_source_meta(session, paper_id)

        return PaperDetailResponseSchema(
            id=paper.id,
            source=paper.source,
            external_id=paper.external_id,
            title=paper.title,
            authors=paper.authors,
            abstract=paper.abstract,
            categories=paper.categories,
            published_at=paper.published_at,
            status=paper.status,
            attempts=paper.attempts,
            last_error=paper.last_error,
            payload=paper.payload or {},
            source_meta=source_meta,
            created_at=paper.created_at,
            updated_at=paper.updated_at,
        )

    async def get_paper_content(
        self,
        session: AsyncSession,
        paper_id: int,
    ) -> PaperContentResponseSchema:
        content = await self._repo.get_content(session, paper_id)
        if content is None:
            raise NotFoundError("paper_content", paper_id)

        return PaperContentResponseSchema(
            paper_id=paper_id,
            full_text=content.full_text,
        )

    async def get_stats(self, session: AsyncSession) -> PaperStatsResponseSchema:
        total_count, by_source, by_status, by_type, top_materials = await self._repo.get_stats(session)

        return PaperStatsResponseSchema(
            total_count=total_count,
            by_source=[StatsBucketSchema(key=key, count=count) for key, count in by_source],
            by_status=[StatsBucketSchema(key=key, count=count) for key, count in by_status],
            by_type=[StatsBucketSchema(key=key, count=count) for key, count in by_type],
            top_materials=[TopMaterialSchema(material=material, count=count) for material, count in top_materials],
        )
