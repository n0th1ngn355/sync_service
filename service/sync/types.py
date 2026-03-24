"""Sync pipeline DTOs."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(slots=True)
class OaiPaperRecord:
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
    inserted_count: int
    checkpoint_datestamp: date | None


@dataclass(slots=True)
class PdfProcessResult:
    full_text: str
    payload: dict[str, Any]
    is_filtered: bool
    filter_reason: str | None = None


@dataclass(slots=True)
class ProcessingResult:
    processed_count: int
    done_count: int
    filtered_count: int
    error_count: int
    skipped_count: int


@dataclass(slots=True)
class FullSyncResult:
    metadata_inserted: int
    metadata_checkpoint: date | None
    processed_count: int
    done_count: int
    filtered_count: int
    error_count: int
    skipped_count: int

