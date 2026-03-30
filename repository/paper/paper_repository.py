"""
Paper repository.

## Traceability
Feature: F003, F004
Scenarios: SC010, SC011, SC012, SC013, SC014, SC015, SC016, SC017, SC018
"""

from collections import Counter
from datetime import datetime
from typing import Any

from sqlalchemy import Float, String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from model.paper.paper_content_model import PaperContentModel
from model.paper.paper_file_model import PaperFileModel
from model.paper.paper_model import PaperModel
from model.paper.paper_source_meta_model import PaperSourceMetaModel
from model.enums import PaperStatusEnum


class PaperRepository:
    """Persistence layer for paper entities and related artifacts."""

    def __init__(self):
        self.model = PaperModel

    @staticmethod
    def _sanitize_text(value: str) -> str:
        # PostgreSQL TEXT does not allow NUL bytes.
        return value.replace("\x00", "")

    async def get_by_source_external_id(
        self,
        session: AsyncSession,
        source: str,
        external_id: str,
    ) -> PaperModel | None:
        """Return paper by unique `(source, external_id)` pair."""
        stmt = select(self.model).where(
            self.model.source == source,
            self.model.external_id == external_id,
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_processable_papers(
        self,
        session: AsyncSession,
        *,
        source: str | None = None,
        limit: int = 500,
    ) -> list[PaperModel]:
        """Return papers eligible for processing stage."""
        stmt = select(self.model).where(
            self.model.status.in_(
                [
                    PaperStatusEnum.NEW.value,
                    PaperStatusEnum.DOWNLOADING.value,
                    PaperStatusEnum.PROCESSING.value,
                ]
            )
        )
        if source:
            stmt = stmt.where(self.model.source == source)

        stmt = stmt.order_by(self.model.id.asc()).limit(limit)
        return list((await session.execute(stmt)).scalars().all())

    async def create_paper(self, session: AsyncSession, **kwargs) -> PaperModel:
        """Create `paper` row and return persisted model."""
        paper = self.model(**kwargs)
        session.add(paper)
        await session.flush()
        await session.refresh(paper)
        return paper

    async def create_paper_content(
        self,
        session: AsyncSession,
        *,
        paper_id: int,
        full_text: str,
    ) -> PaperContentModel:
        """Create `paper_content` row for a paper."""
        content = PaperContentModel(
            paper_id=paper_id,
            full_text=self._sanitize_text(full_text),
        )
        session.add(content)
        await session.flush()
        await session.refresh(content)
        return content

    async def create_paper_file(
        self,
        session: AsyncSession,
        *,
        paper_id: int,
        file_type: str,
        storage_path: str,
        mime_type: str | None,
        size_bytes: int | None,
        checksum: str | None,
    ) -> PaperFileModel:
        """Create `paper_file` artifact row."""
        paper_file = PaperFileModel(
            paper_id=paper_id,
            file_type=file_type,
            storage_path=storage_path,
            mime_type=mime_type,
            size_bytes=size_bytes,
            checksum=checksum,
        )
        session.add(paper_file)
        await session.flush()
        await session.refresh(paper_file)
        return paper_file

    async def create_paper_source_meta(
        self,
        session: AsyncSession,
        *,
        paper_id: int,
        source_meta: dict[str, Any],
    ) -> PaperSourceMetaModel:
        """Create `paper_source_meta` row."""
        source_meta_model = PaperSourceMetaModel(
            paper_id=paper_id,
            source_meta=source_meta,
        )
        session.add(source_meta_model)
        await session.flush()
        await session.refresh(source_meta_model)
        return source_meta_model

    async def upsert_paper_source_meta(
        self,
        session: AsyncSession,
        *,
        paper_id: int,
        source_meta: dict[str, Any],
    ) -> PaperSourceMetaModel:
        """Insert or update source metadata for a paper."""
        stmt = select(PaperSourceMetaModel).where(PaperSourceMetaModel.paper_id == paper_id)
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is None:
            return await self.create_paper_source_meta(
                session,
                paper_id=paper_id,
                source_meta=source_meta,
            )

        existing.source_meta = source_meta
        session.add(existing)
        await session.flush()
        await session.refresh(existing)
        return existing

    async def upsert_paper_content(
        self,
        session: AsyncSession,
        *,
        paper_id: int,
        full_text: str,
    ) -> PaperContentModel:
        """Insert or update extracted full text for a paper."""
        sanitized_text = self._sanitize_text(full_text)
        stmt = select(PaperContentModel).where(PaperContentModel.paper_id == paper_id)
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is None:
            return await self.create_paper_content(
                session,
                paper_id=paper_id,
                full_text=sanitized_text,
            )

        existing.full_text = sanitized_text
        session.add(existing)
        await session.flush()
        await session.refresh(existing)
        return existing

    async def upsert_paper_file(
        self,
        session: AsyncSession,
        *,
        paper_id: int,
        file_type: str,
        storage_path: str,
        mime_type: str | None,
        size_bytes: int | None,
        checksum: str | None,
    ) -> PaperFileModel:
        """Insert or update artifact file metadata by `(paper_id, file_type)`."""
        stmt = select(PaperFileModel).where(
            PaperFileModel.paper_id == paper_id,
            PaperFileModel.file_type == file_type,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is None:
            return await self.create_paper_file(
                session,
                paper_id=paper_id,
                file_type=file_type,
                storage_path=storage_path,
                mime_type=mime_type,
                size_bytes=size_bytes,
                checksum=checksum,
            )

        existing.storage_path = storage_path
        existing.mime_type = mime_type
        existing.size_bytes = size_bytes
        existing.checksum = checksum
        session.add(existing)
        await session.flush()
        await session.refresh(existing)
        return existing

    async def mark_status(
        self,
        session: AsyncSession,
        *,
        paper: PaperModel,
        status: str,
        last_error: str | None = None,
        increment_attempts: bool = False,
        payload: dict[str, Any] | None = None,
    ) -> PaperModel:
        """Update processing status and optional payload/error metadata."""
        paper.status = status
        paper.last_error = self._sanitize_text(last_error) if last_error else None
        if increment_attempts:
            paper.attempts = int(paper.attempts or 0) + 1
        if payload is not None:
            paper.payload = payload
        paper.updated_at = datetime.utcnow()
        session.add(paper)
        await session.flush()
        await session.refresh(paper)
        return paper

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
        """Apply API filter set to selectable statement."""
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
        """Return filtered page of papers and total count."""
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
        """Return paper by internal ID."""
        stmt = select(self.model).where(self.model.id == paper_id)
        return (await session.execute(stmt)).scalar_one_or_none()

    async def get_source_meta(self, session: AsyncSession, paper_id: int) -> dict[str, Any]:
        """Return paper source metadata as plain dict."""
        stmt = select(PaperSourceMetaModel).where(PaperSourceMetaModel.paper_id == paper_id)
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None or row.source_meta is None:
            return {}
        return dict(row.source_meta)

    async def get_content(self, session: AsyncSession, paper_id: int) -> PaperContentModel | None:
        """Return extracted content row by paper ID."""
        stmt = select(PaperContentModel).where(PaperContentModel.paper_id == paper_id)
        return (await session.execute(stmt)).scalar_one_or_none()

    async def get_stats(
        self,
        session: AsyncSession,
    ) -> tuple[int, list[tuple[str, int]], list[tuple[str, int]], list[tuple[str, int]], list[tuple[str, int]]]:
        """Build aggregate counters for stats endpoint."""
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
