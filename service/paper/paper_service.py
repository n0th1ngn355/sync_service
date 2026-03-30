"""
Paper service.

## Traceability
Feature: F003, F004
Scenarios: SC010, SC011, SC012, SC013, SC014, SC015, SC016, SC017, SC018
"""

import asyncio
from contextlib import asynccontextmanager
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core import db_connect
from core.config import configs
from core.exceptions import ConflictError, NotFoundError, ValidationError
from model.enums import FileTypeEnum, PaperStatusEnum
from repository.paper.paper_repository import PaperRepository
from service.sync.providers import DefaultPdfProcessor
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
    """
    Business logic for PRD features F003 (read) and F004 (manual add).

    Responsibilities:
    - manual paper creation with optional PDF upload
    - asynchronous PDF processing for manual uploads
    - read endpoints with filters, detail, content and stats views
    """

    _MAX_PDF_SIZE_BYTES = 50 * 1024 * 1024
    _ALLOWED_PDF_MIME_TYPES = {"application/pdf"}

    @staticmethod
    def _sanitize_text(value: str) -> str:
        # PostgreSQL TEXT does not allow NUL bytes.
        return value.replace("\x00", "")

    def __init__(
        self,
        repo: PaperRepository | None = None,
        pdf_processor: DefaultPdfProcessor | None = None,
    ):
        self._repo = repo or PaperRepository()
        self._pdf_processor = pdf_processor or DefaultPdfProcessor()

    async def create_paper(
        self,
        session: AsyncSession,
        payload: PaperCreateSchema,
        *,
        pdf_bytes: bytes | None = None,
        pdf_filename: str | None = None,
        pdf_mime_type: str | None = None,
    ) -> PaperCreateResponseSchema:
        """
        Create manual paper record and optionally schedule PDF extraction.

        Behavior:
        - without PDF: creates DONE paper with empty content
        - with PDF: stores file and starts background processing
        """
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
            await self._enqueue_pdf_processing(
                paper_id=paper.id,
                pdf_bytes=pdf_bytes,
                pdf_filename=pdf_filename,
            )
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
        """Return filtered paper list with validated pagination parameters."""
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
        """Return one paper detail or raise NotFoundError."""
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
        """Return extracted full text for a paper."""
        content = await self._repo.get_content(session, paper_id)
        if content is None:
            raise NotFoundError("paper_content", paper_id)

        return PaperContentResponseSchema(
            paper_id=paper_id,
            full_text=content.full_text,
        )

    async def get_stats(self, session: AsyncSession) -> PaperStatsResponseSchema:
        """Return aggregated metrics used by `/api/v1/papers/stats`."""
        total_count, by_source, by_status, by_type, top_materials = await self._repo.get_stats(session)

        return PaperStatsResponseSchema(
            total_count=total_count,
            by_source=[StatsBucketSchema(key=key, count=count) for key, count in by_source],
            by_status=[StatsBucketSchema(key=key, count=count) for key, count in by_status],
            by_type=[StatsBucketSchema(key=key, count=count) for key, count in by_type],
            top_materials=[TopMaterialSchema(material=material, count=count) for material, count in top_materials],
        )

    def _normalize_create_payload(self, payload: PaperCreateSchema) -> dict:
        """Normalize and validate required metadata fields for create operation."""
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
        """Validate uploaded PDF MIME type and size constraints."""
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
        """Persist uploaded PDF and return storage metadata tuple."""
        storage_dir = Path(configs.STORAGE_PATH) / "papers" / str(paper_id)
        storage_dir.mkdir(parents=True, exist_ok=True)

        original_name = Path(filename or "paper.pdf").name or "paper.pdf"
        if not original_name.lower().endswith(".pdf"):
            original_name = f"{original_name}.pdf"

        saved_name = f"{uuid4().hex}_{original_name}"
        saved_path = storage_dir / saved_name
        saved_path.write_bytes(pdf_bytes)

        return saved_path.as_posix(), len(pdf_bytes), sha256(pdf_bytes).hexdigest()

    async def _enqueue_pdf_processing(
        self,
        *,
        paper_id: int,
        pdf_bytes: bytes,
        pdf_filename: str | None,
    ) -> None:
        """Schedule asynchronous processing task for uploaded PDF."""
        asyncio.create_task(
            self._process_uploaded_pdf_in_background(
                paper_id=paper_id,
                pdf_bytes=pdf_bytes,
                pdf_filename=pdf_filename,
            )
        )

    async def _process_uploaded_pdf_in_background(
        self,
        *,
        paper_id: int,
        pdf_bytes: bytes,
        pdf_filename: str | None,
    ) -> None:
        """Process uploaded PDF in isolated DB sessions and update paper status."""
        # Request transaction can still be open when task starts, so retry briefly.
        for _ in range(20):
            paper_not_visible = False
            async with self._session_scope() as session:
                paper = await self._repo.get_by_id(session, paper_id)
                if paper is None:
                    paper_not_visible = True
                else:
                    if paper.status in (PaperStatusEnum.DONE.value, PaperStatusEnum.COMPLETED.value):
                        return

                    try:
                        parsed = await self._pdf_processor.process(pdf_bytes)
                        clean_text = self._sanitize_text(parsed.full_text)
                        txt_path, txt_size, txt_checksum = self._save_text_file(
                            paper_id=paper_id,
                            full_text=clean_text,
                            filename=pdf_filename,
                        )
                        await self._repo.upsert_paper_file(
                            session,
                            paper_id=paper_id,
                            file_type=FileTypeEnum.TXT.value,
                            storage_path=txt_path,
                            mime_type="text/plain; charset=utf-8",
                            size_bytes=txt_size,
                            checksum=txt_checksum,
                        )
                        await self._repo.upsert_paper_content(
                            session,
                            paper_id=paper_id,
                            full_text=clean_text,
                        )
                        # BR024: manual papers are not filtered by BR002/BR003.
                        await self._repo.mark_status(
                            session,
                            paper=paper,
                            status=PaperStatusEnum.DONE.value,
                            last_error=None,
                            payload=parsed.payload,
                        )
                        return
                    except Exception as exc:
                        await session.rollback()
                        reloaded_paper = await self._repo.get_by_id(session, paper_id)
                        if reloaded_paper is None:
                            return
                        await self._repo.mark_status(
                            session,
                            paper=reloaded_paper,
                            status=PaperStatusEnum.ERROR.value,
                            last_error=str(exc)[:4000],
                            increment_attempts=True,
                        )
                        return

            if paper_not_visible:
                await asyncio.sleep(0.1)

        # If record is still not visible after retries, persist a best-effort error status.
        async with self._session_scope() as session:
            paper = await self._repo.get_by_id(session, paper_id)
            if paper is None:
                return
            await self._repo.mark_status(
                session,
                paper=paper,
                status=PaperStatusEnum.ERROR.value,
                last_error="Background processing timeout waiting for committed paper",
                increment_attempts=True,
            )

    def _save_text_file(
        self,
        *,
        paper_id: int,
        full_text: str,
        filename: str | None,
    ) -> tuple[str, int, str]:
        """Persist extracted text artifact and return storage metadata tuple."""
        storage_dir = Path(configs.STORAGE_PATH) / "papers" / str(paper_id)
        storage_dir.mkdir(parents=True, exist_ok=True)

        original_name = Path(filename or "paper").stem or "paper"
        saved_name = f"{uuid4().hex}_{original_name}.txt"
        saved_path = storage_dir / saved_name
        raw = full_text.encode("utf-8", errors="ignore")
        saved_path.write_bytes(raw)
        return saved_path.as_posix(), len(raw), sha256(raw).hexdigest()

    @asynccontextmanager
    async def _session_scope(self):
        """Provide independent transactional session for background jobs."""
        db_connect._ensure_initialized()
        async with db_connect.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
