"""
Paper service.

## Traceability
Feature: F003, F004
Scenarios: SC010, SC011, SC012, SC013, SC014, SC015, SC016, SC017, SC018
"""

from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import configs
from core.exceptions import ConflictError, NotFoundError, ValidationError
from model.enums import FileTypeEnum, PaperStatusEnum
from repository.paper.paper_repository import PaperRepository
from schema import (
    PaperCreateResponseSchema,
    PaperCreateSchema,
    PaperContentResponseSchema,
    PaperDetailResponseSchema,
    PaperListItemSchema,
    PaperListResponseSchema,
    PaperStatsResponseSchema,
    StatsBucketSchema,
    TopMaterialSchema,
)


class PaperService:
    _MAX_PDF_SIZE_BYTES = 50 * 1024 * 1024
    _ALLOWED_PDF_MIME_TYPES = {"application/pdf"}

    def __init__(self, repo: PaperRepository | None = None):
        self._repo = repo or PaperRepository()

    async def create_paper(
        self,
        session: AsyncSession,
        payload: PaperCreateSchema,
        *,
        pdf_bytes: bytes | None = None,
        pdf_filename: str | None = None,
        pdf_mime_type: str | None = None,
    ) -> PaperCreateResponseSchema:
        normalized = self._normalize_create_payload(payload)
        external_id = normalized["external_id"]

        if external_id:
            existing = await self._repo.get_by_source_external_id(
                session,
                source=normalized["source"],
                external_id=external_id,
            )
            if existing is not None:
                raise ConflictError("Paper already exists")

        has_pdf = pdf_bytes is not None
        if has_pdf:
            self._validate_pdf(
                pdf_bytes=pdf_bytes,
                mime_type=pdf_mime_type,
            )
            initial_status = PaperStatusEnum.PROCESSING.value
        else:
            initial_status = PaperStatusEnum.DONE.value

        try:
            paper = await self._repo.create_paper(
                session,
                source=normalized["source"],
                external_id=external_id,
                title=normalized["title"],
                authors=normalized["authors"],
                abstract=normalized["abstract"],
                categories=normalized["categories"],
                status=initial_status,
                payload={},
            )
        except IntegrityError as exc:
            if external_id:
                raise ConflictError("Paper already exists") from exc
            raise

        await self._repo.create_paper_source_meta(
            session,
            paper_id=paper.id,
            source_meta=normalized["source_meta"],
        )

        if has_pdf:
            storage_path, size_bytes, checksum = self._save_pdf_file(
                paper_id=paper.id,
                pdf_bytes=pdf_bytes,
                filename=pdf_filename,
            )
            await self._repo.create_paper_file(
                session,
                paper_id=paper.id,
                file_type=FileTypeEnum.PDF.value,
                storage_path=storage_path,
                mime_type=pdf_mime_type,
                size_bytes=size_bytes,
                checksum=checksum,
            )
            await self._enqueue_pdf_processing(paper.id)
        else:
            await self._repo.create_paper_content(
                session,
                paper_id=paper.id,
                full_text="",
            )

        return PaperCreateResponseSchema(
            id=paper.id,
            source=paper.source,
            external_id=paper.external_id,
            title=paper.title,
            status=paper.status,
            payload=paper.payload or {},
            created_at=paper.created_at,
        )

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

    def _normalize_create_payload(self, payload: PaperCreateSchema) -> dict:
        title = payload.title.strip()
        source = payload.source.strip()

        if not title:
            raise ValidationError("title must not be empty")
        if not source:
            raise ValidationError("source must not be empty")

        def _opt(value: str | None) -> str | None:
            if value is None:
                return None
            stripped = value.strip()
            return stripped or None

        source_meta = payload.source_meta if isinstance(payload.source_meta, dict) else {}

        return {
            "title": title,
            "source": source,
            "authors": _opt(payload.authors),
            "abstract": _opt(payload.abstract),
            "categories": _opt(payload.categories),
            "external_id": _opt(payload.external_id),
            "source_meta": source_meta,
        }

    def _validate_pdf(self, *, pdf_bytes: bytes | None, mime_type: str | None) -> None:
        if mime_type is None or mime_type.lower() not in self._ALLOWED_PDF_MIME_TYPES:
            raise ValidationError("Invalid PDF MIME type. Expected application/pdf")

        if pdf_bytes is None or len(pdf_bytes) == 0:
            raise ValidationError("PDF file is empty")

        if len(pdf_bytes) > self._MAX_PDF_SIZE_BYTES:
            raise ValidationError("PDF file exceeds 50 MB limit")

    def _save_pdf_file(
        self,
        *,
        paper_id: int,
        pdf_bytes: bytes,
        filename: str | None,
    ) -> tuple[str, int, str]:
        storage_dir = Path(configs.STORAGE_PATH) / "papers" / str(paper_id)
        storage_dir.mkdir(parents=True, exist_ok=True)

        original_name = Path(filename or "paper.pdf").name or "paper.pdf"
        if not original_name.lower().endswith(".pdf"):
            original_name = f"{original_name}.pdf"

        saved_name = f"{uuid4().hex}_{original_name}"
        saved_path = storage_dir / saved_name
        saved_path.write_bytes(pdf_bytes)

        return saved_path.as_posix(), len(pdf_bytes), sha256(pdf_bytes).hexdigest()

    async def _enqueue_pdf_processing(self, paper_id: int) -> None:
        # Queue integration will be added in sync pipeline blocks.
        _ = paper_id
