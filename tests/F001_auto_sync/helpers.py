"""Test doubles for F001 tests."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from service.sync.types import OaiPaperRecord, PdfProcessResult


class FakeOaiProvider:
    def __init__(self, records: list[OaiPaperRecord], checkpoint: date | None):
        self.records = records
        self.checkpoint = checkpoint
        self.calls: list[date | None] = []

    async def fetch_records(self, *, from_date: date | None):
        self.calls.append(from_date)
        return self.records, self.checkpoint


class FakeManifestProvider:
    def __init__(self, mapping: dict[str, str] | None = None):
        self.mapping = mapping or {}
        self.calls: list[list[str]] = []

    async def resolve(self, arxiv_ids: Sequence[str]):
        self.calls.append(list(arxiv_ids))
        return {key: value for key, value in self.mapping.items() if key in set(arxiv_ids)}


class FakePdfFetcher:
    def __init__(self, pdf_map: dict[str, bytes | None]):
        self.pdf_map = pdf_map
        self.calls: list[tuple[str, str | None]] = []

    async def fetch_pdf(self, *, arxiv_id: str, tar_key: str | None = None):
        self.calls.append((arxiv_id, tar_key))
        return self.pdf_map.get(arxiv_id)


class FakePdfProcessor:
    def __init__(self, outputs: dict[bytes, PdfProcessResult], error_payloads: set[bytes] | None = None):
        self.outputs = outputs
        self.error_payloads = error_payloads or set()
        self.calls: list[bytes] = []

    async def process(self, pdf_bytes: bytes) -> PdfProcessResult:
        self.calls.append(pdf_bytes)
        if pdf_bytes in self.error_payloads:
            raise RuntimeError("broken pdf")
        if pdf_bytes in self.outputs:
            return self.outputs[pdf_bytes]
        raise RuntimeError("unexpected pdf payload")

