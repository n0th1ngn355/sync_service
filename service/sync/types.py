"""Sync pipeline DTOs."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(slots=True)
class OaiPaperRecord:
    """Normalized metadata record fetched from OAI-PMH."""

    external_id: str
    title: str
    categories: str
    authors: str | None = None
    abstract: str | None = None
    published_at: datetime | None = None
    datestamp: date | None = None
    source_meta: dict[str, Any] | None = None


@dataclass(slots=True)
class MetadataSyncResult:
    """Result of metadata-only synchronization stage."""

    inserted_count: int
    checkpoint_datestamp: date | None


@dataclass(slots=True)
class PdfProcessResult:
    """Result of PDF parsing and payload extraction."""

    full_text: str
    payload: dict[str, Any]
    is_filtered: bool
    filter_reason: str | None = None


@dataclass(slots=True)
class ProcessingResult:
    """Counters for download/process stage outcome."""

    processed_count: int
    done_count: int
    filtered_count: int
    error_count: int
    skipped_count: int


@dataclass(slots=True)
class FullSyncResult:
    """Combined result for full pipeline run."""

    metadata_inserted: int
    metadata_checkpoint: date | None
    processed_count: int
    done_count: int
    filtered_count: int
    error_count: int
    skipped_count: int
