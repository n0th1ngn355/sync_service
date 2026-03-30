"""
Sync pipeline orchestrator.

## Traceability
Feature: F001
Business Rules: BR001-BR009
Scenarios: SC001, SC002, SC003, SC004
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import configs
from model.enums import FileTypeEnum, PaperStatusEnum
from repository.paper.paper_repository import PaperRepository
from repository.sync.sync_state_repository import SyncStateRepository
from .providers import (
    ArxivManifestIndexProvider,
    ArxivOaiMetadataProvider,
    ArxivPdfFetcher,
    DefaultPdfProcessor,
    ManifestIndexProvider,
    OaiMetadataProvider,
    PdfFetcher,
    PdfProcessor,
)
from .types import FullSyncResult, MetadataSyncResult, OaiPaperRecord, ProcessingResult

logger = logging.getLogger(__name__)


class SyncPipelineService:
    """
    Full synchronization orchestrator for feature F001.

    Pipeline stages:
    1. Metadata sync via OAI-PMH.
    2. PDF fetch (S3 TAR or HTTP fallback).
    3. PDF to text + payload extraction.
    4. Status bookkeeping in sync_state and paper tables.
    """

    SOURCE_NAME = "arxiv"
    SYNC_STATE_SOURCE_KEY = "arxiv:oai_suprcon_sync"
    PROGRESS_LOG_EVERY = 10

    def __init__(
        self,
        *,
        paper_repo: PaperRepository | None = None,
        sync_state_repo: SyncStateRepository | None = None,
        oai_provider: OaiMetadataProvider | None = None,
        manifest_provider: ManifestIndexProvider | None = None,
        pdf_fetcher: PdfFetcher | None = None,
        pdf_processor: PdfProcessor | None = None,
    ):
        self._paper_repo = paper_repo or PaperRepository()
        self._sync_state_repo = sync_state_repo or SyncStateRepository()
        self._oai_provider = oai_provider or ArxivOaiMetadataProvider()
        self._manifest_provider = manifest_provider or ArxivManifestIndexProvider()
        self._pdf_fetcher = pdf_fetcher or ArxivPdfFetcher()
        self._pdf_processor = pdf_processor or DefaultPdfProcessor()
        self._overlap_days = int(configs.SYNC_OVERLAP_DAYS)

    async def run_once(self, session: AsyncSession) -> FullSyncResult:
        """Run metadata + processing stages in one transaction scope."""
        logger.info(
            "Sync run started source_key=%s overlap_days=%s batch_size=%s",
            self.SYNC_STATE_SOURCE_KEY,
            self._overlap_days,
            configs.SYNC_PROCESS_BATCH_SIZE,
        )
        state = await self._sync_state_repo.get_or_create(
            session,
            source=self.SYNC_STATE_SOURCE_KEY,
        )
        await self._sync_state_repo.mark_running(
            session,
            state=state,
            started_at=datetime.utcnow(),
            note=f"pipeline=full; overlap_days={self._overlap_days}",
        )

        try:
            metadata = await self._sync_metadata_core(session, state)
            processing = await self.run_download_and_process(session)
            await self._sync_state_repo.mark_success(
                session,
                state=state,
                finished_at=datetime.utcnow(),
                rows_written=metadata.inserted_count,
                checkpoint_datestamp=metadata.checkpoint_datestamp,
                note=(
                    f"metadata_inserted={metadata.inserted_count}; "
                    f"processed={processing.processed_count}; "
                    f"done={processing.done_count}; "
                    f"filtered={processing.filtered_count}; "
                    f"errors={processing.error_count}; "
                    f"skipped={processing.skipped_count}"
                ),
            )
            logger.info(
                "Sync run finished metadata_inserted=%s processed=%s done=%s filtered=%s errors=%s skipped=%s checkpoint=%s",
                metadata.inserted_count,
                processing.processed_count,
                processing.done_count,
                processing.filtered_count,
                processing.error_count,
                processing.skipped_count,
                metadata.checkpoint_datestamp,
            )
            return FullSyncResult(
                metadata_inserted=metadata.inserted_count,
                metadata_checkpoint=metadata.checkpoint_datestamp,
                processed_count=processing.processed_count,
                done_count=processing.done_count,
                filtered_count=processing.filtered_count,
                error_count=processing.error_count,
                skipped_count=processing.skipped_count,
            )
        except Exception as exc:
            await self._sync_state_repo.mark_error(
                session,
                state=state,
                finished_at=datetime.utcnow(),
                error_text=str(exc),
                note="pipeline=full",
            )
            logger.exception("Sync run failed source_key=%s", self.SYNC_STATE_SOURCE_KEY)
            raise

    async def run_sync_metadata(self, session: AsyncSession) -> MetadataSyncResult:
        """Run only metadata synchronization stage."""
        state = await self._sync_state_repo.get_or_create(
            session,
            source=self.SYNC_STATE_SOURCE_KEY,
        )
        await self._sync_state_repo.mark_running(
            session,
            state=state,
            started_at=datetime.utcnow(),
            note=f"pipeline=metadata; overlap_days={self._overlap_days}",
        )

        try:
            result = await self._sync_metadata_core(session, state)
            await self._sync_state_repo.mark_success(
                session,
                state=state,
                finished_at=datetime.utcnow(),
                rows_written=result.inserted_count,
                checkpoint_datestamp=result.checkpoint_datestamp,
                note=f"pipeline=metadata; inserted={result.inserted_count}",
            )
            return result
        except Exception as exc:
            await self._sync_state_repo.mark_error(
                session,
                state=state,
                finished_at=datetime.utcnow(),
                error_text=str(exc),
                note="pipeline=metadata",
            )
            raise

    async def run_download_and_process(self, session: AsyncSession) -> ProcessingResult:
        """Process queued papers: download PDF, parse text, persist payload."""
        papers = await self._paper_repo.list_processable_papers(
            session,
            source=self.SOURCE_NAME,
            limit=int(configs.SYNC_PROCESS_BATCH_SIZE),
        )
        logger.info("Processing step: selected papers=%s", len(papers))
        if not papers:
            return ProcessingResult(
                processed_count=0,
                done_count=0,
                filtered_count=0,
                error_count=0,
                skipped_count=0,
            )

        tar_index = await self._manifest_provider.resolve(
            [paper.external_id for paper in papers if paper.external_id]
        )
        logger.info("Processing step: tar index resolved entries=%s", len(tar_index))

        processed = 0
        done = 0
        filtered = 0
        errors = 0
        skipped = 0

        for paper in papers:
            if paper.status in (PaperStatusEnum.DONE.value, PaperStatusEnum.COMPLETED.value):
                skipped += 1
                continue

            if not paper.external_id:
                logger.warning("Paper id=%s has no external_id; marking ERROR", paper.id)
                await self._paper_repo.mark_status(
                    session,
                    paper=paper,
                    status=PaperStatusEnum.ERROR.value,
                    last_error="Missing external_id for arxiv paper",
                    increment_attempts=True,
                )
                processed += 1
                errors += 1
                continue

            processed += 1
            await self._paper_repo.mark_status(
                session,
                paper=paper,
                status=PaperStatusEnum.DOWNLOADING.value,
                last_error=None,
                increment_attempts=True,
            )

            try:
                pdf_bytes = await self._pdf_fetcher.fetch_pdf(
                    arxiv_id=paper.external_id,
                    tar_key=tar_index.get(paper.external_id),
                )
                if not pdf_bytes:
                    logger.warning(
                        "PDF not found paper_id=%s external_id=%s tar_key=%s",
                        paper.id,
                        paper.external_id,
                        tar_index.get(paper.external_id),
                    )
                    await self._paper_repo.mark_status(
                        session,
                        paper=paper,
                        status=PaperStatusEnum.NOT_FOUND.value,
                        last_error="PDF not found",
                    )
                    continue

                pdf_path, pdf_size, pdf_checksum = self._save_binary(
                    paper_id=paper.id,
                    content=pdf_bytes,
                    extension="pdf",
                    filename_hint=paper.external_id,
                )
                await self._paper_repo.upsert_paper_file(
                    session,
                    paper_id=paper.id,
                    file_type=FileTypeEnum.PDF.value,
                    storage_path=pdf_path,
                    mime_type="application/pdf",
                    size_bytes=pdf_size,
                    checksum=pdf_checksum,
                )

                await self._paper_repo.mark_status(
                    session,
                    paper=paper,
                    status=PaperStatusEnum.PROCESSING.value,
                    last_error=None,
                )

                parsed = await self._pdf_processor.process(pdf_bytes)
                txt_bytes = parsed.full_text.encode("utf-8", errors="ignore")
                txt_path, txt_size, txt_checksum = self._save_binary(
                    paper_id=paper.id,
                    content=txt_bytes,
                    extension="txt",
                    filename_hint=paper.external_id,
                )
                await self._paper_repo.upsert_paper_file(
                    session,
                    paper_id=paper.id,
                    file_type=FileTypeEnum.TXT.value,
                    storage_path=txt_path,
                    mime_type="text/plain; charset=utf-8",
                    size_bytes=txt_size,
                    checksum=txt_checksum,
                )
                await self._paper_repo.upsert_paper_content(
                    session,
                    paper_id=paper.id,
                    full_text=parsed.full_text,
                )

                final_status = PaperStatusEnum.FILTERED.value if parsed.is_filtered else PaperStatusEnum.DONE.value
                await self._paper_repo.mark_status(
                    session,
                    paper=paper,
                    status=final_status,
                    last_error=parsed.filter_reason if parsed.is_filtered else None,
                    payload=parsed.payload,
                )
                if parsed.is_filtered:
                    filtered += 1
                else:
                    done += 1
            except Exception as exc:
                logger.exception(
                    "Failed to process paper_id=%s external_id=%s",
                    paper.id,
                    paper.external_id,
                )
                await self._paper_repo.mark_status(
                    session,
                    paper=paper,
                    status=PaperStatusEnum.ERROR.value,
                    last_error=str(exc)[:4000],
                )
                errors += 1
            finally:
                handled = processed + skipped
                if processed % self.PROGRESS_LOG_EVERY == 0 or handled == len(papers):
                    logger.info(
                        "Processing progress %s/%s done=%s filtered=%s errors=%s skipped=%s",
                        processed,
                        len(papers),
                        done,
                        filtered,
                        errors,
                        skipped,
                    )

        return ProcessingResult(
            processed_count=processed,
            done_count=done,
            filtered_count=filtered,
            error_count=errors,
            skipped_count=skipped,
        )

    async def _sync_metadata_core(
        self,
        session: AsyncSession,
        state,
    ) -> MetadataSyncResult:
        """Fetch OAI records and insert new target papers."""
        from_date = None
        if state.last_success_datestamp is not None:
            from_date = state.last_success_datestamp - timedelta(days=self._overlap_days)

        logger.info("Metadata step: fetch started from_date=%s", from_date)
        records, checkpoint_datestamp = await self._oai_provider.fetch_records(from_date=from_date)
        logger.info(
            "Metadata step: fetched records=%s checkpoint=%s",
            len(records),
            checkpoint_datestamp,
        )
        inserted_count = 0
        target_records = 0

        for record in records:
            if not self._is_target_record(record):
                continue
            target_records += 1

            existing = await self._paper_repo.get_by_source_external_id(
                session,
                source=self.SOURCE_NAME,
                external_id=record.external_id,
            )
            if existing is not None:
                continue

            paper = await self._paper_repo.create_paper(
                session,
                source=self.SOURCE_NAME,
                external_id=record.external_id,
                title=record.title.strip() or record.external_id,
                authors=record.authors,
                abstract=record.abstract,
                categories=record.categories,
                published_at=record.published_at,
                status=PaperStatusEnum.NEW.value,
                payload={},
            )
            await self._paper_repo.upsert_paper_source_meta(
                session,
                paper_id=paper.id,
                source_meta=record.source_meta or {},
            )
            inserted_count += 1

        logger.info(
            "Metadata step: target_records=%s inserted=%s duplicates_skipped=%s",
            target_records,
            inserted_count,
            max(target_records - inserted_count, 0),
        )
        return MetadataSyncResult(
            inserted_count=inserted_count,
            checkpoint_datestamp=checkpoint_datestamp,
        )

    def _is_target_record(self, record: OaiPaperRecord) -> bool:
        """Check whether OAI record belongs to cond-mat.supr-con subset."""
        categories = [token.strip().lower() for token in (record.categories or "").split() if token.strip()]
        return "cond-mat.supr-con" in categories

    def _save_binary(
        self,
        *,
        paper_id: int,
        content: bytes,
        extension: str,
        filename_hint: str,
    ) -> tuple[str, int, str]:
        """Save binary artifact and return `(path, size_bytes, sha256)` tuple."""
        storage_dir = Path(configs.STORAGE_PATH) / "papers" / str(paper_id)
        storage_dir.mkdir(parents=True, exist_ok=True)

        safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "_", filename_hint).strip("._")
        if not safe_name:
            safe_name = f"paper_{paper_id}"

        final_name = f"{uuid4().hex}_{safe_name}.{extension}"
        final_path = storage_dir / final_name
        final_path.write_bytes(content)
        return final_path.as_posix(), len(content), sha256(content).hexdigest()


sync_pipeline_service = SyncPipelineService()
