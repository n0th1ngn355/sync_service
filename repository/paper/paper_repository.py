"""
Paper repository.

## Traceability
Feature: F003
Scenarios: SC010, SC011, SC012, SC013, SC014
"""

from collections import Counter
from typing import Any

from sqlalchemy import Float, String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from model.paper.paper_content_model import PaperContentModel
from model.paper.paper_model import PaperModel
from model.paper.paper_source_meta_model import PaperSourceMetaModel


class PaperRepository:
    def __init__(self):
        self.model = PaperModel

    def _apply_filters(
        self,
        stmt,
        *,
        source: str | None,
        status: str | None,
        material: str | None,
        tc_k_min: float | None,
        tc_k_max: float | None,
        paper_type: str | None,
        dimensionality: str | None,
    ):
        if source:
            stmt = stmt.where(self.model.source == source)

        if status:
            stmt = stmt.where(self.model.status == status)

        if material:
            stmt = stmt.where(
                cast(self.model.payload["material"], String).ilike(f"%{material}%")
            )

        tc_k_expr = cast(self.model.payload["tc_K"].as_string(), Float)
        if tc_k_min is not None:
            stmt = stmt.where(tc_k_expr >= tc_k_min)

        if tc_k_max is not None:
            stmt = stmt.where(tc_k_expr <= tc_k_max)

        if paper_type:
            stmt = stmt.where(self.model.payload["type"].as_string() == paper_type)

        if dimensionality:
            stmt = stmt.where(self.model.payload["dimensionality"].as_string() == dimensionality)

        return stmt

    async def get_list(
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
    ) -> tuple[list[PaperModel], int]:
        base_stmt = select(self.model)
        base_stmt = self._apply_filters(
            base_stmt,
            source=source,
            status=status,
            material=material,
            tc_k_min=tc_k_min,
            tc_k_max=tc_k_max,
            paper_type=paper_type,
            dimensionality=dimensionality,
        )

        total_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await session.execute(total_stmt)).scalar_one())

        items_stmt = base_stmt.order_by(self.model.id.desc()).offset(offset).limit(limit)
        items = list((await session.execute(items_stmt)).scalars().all())

        return items, total

    async def get_by_id(self, session: AsyncSession, paper_id: int) -> PaperModel | None:
        stmt = select(self.model).where(self.model.id == paper_id)
        return (await session.execute(stmt)).scalar_one_or_none()

    async def get_source_meta(self, session: AsyncSession, paper_id: int) -> dict[str, Any]:
        stmt = select(PaperSourceMetaModel).where(PaperSourceMetaModel.paper_id == paper_id)
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None or row.source_meta is None:
            return {}
        return dict(row.source_meta)

    async def get_content(self, session: AsyncSession, paper_id: int) -> PaperContentModel | None:
        stmt = select(PaperContentModel).where(PaperContentModel.paper_id == paper_id)
        return (await session.execute(stmt)).scalar_one_or_none()

    async def get_stats(
        self,
        session: AsyncSession,
    ) -> tuple[int, list[tuple[str, int]], list[tuple[str, int]], list[tuple[str, int]], list[tuple[str, int]]]:
        total_count = int((await session.execute(select(func.count()).select_from(self.model))).scalar_one())

        by_source_stmt = (
            select(self.model.source, func.count())
            .group_by(self.model.source)
            .order_by(func.count().desc(), self.model.source.asc())
        )
        by_source = [(str(k), int(v)) for k, v in (await session.execute(by_source_stmt)).all()]

        by_status_stmt = (
            select(self.model.status, func.count())
            .group_by(self.model.status)
            .order_by(func.count().desc(), self.model.status.asc())
        )
        by_status = [(str(k), int(v)) for k, v in (await session.execute(by_status_stmt)).all()]

        by_type_stmt = (
            select(self.model.payload["type"].as_string().label("type_key"), func.count())
            .group_by("type_key")
            .order_by(func.count().desc())
        )
        by_type_rows = (await session.execute(by_type_stmt)).all()
        by_type = [(str(k or "UNKNOWN"), int(v)) for k, v in by_type_rows]

        payload_stmt = select(self.model.payload)
        payload_rows = (await session.execute(payload_stmt)).scalars().all()
        material_counter = Counter()

        for payload in payload_rows:
            if not isinstance(payload, dict):
                continue

            materials = payload.get("material")
            material_names: set[str] = set()

            if isinstance(materials, dict):
                material_names = {str(name) for name in materials.keys() if str(name).strip()}
            elif isinstance(materials, list):
                material_names = {str(name) for name in materials if str(name).strip()}
            elif isinstance(materials, str) and materials.strip():
                material_names = {materials.strip()}

            material_counter.update(material_names)

        top_materials = sorted(
            material_counter.items(),
            key=lambda item: (-item[1], item[0]),
        )[:10]

        return total_count, by_source, by_status, by_type, top_materials
