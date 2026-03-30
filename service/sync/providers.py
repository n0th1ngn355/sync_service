"""
External providers and processors for sync pipeline.

## Traceability
Feature: F001
Business Rules: BR001, BR002, BR003, BR004, BR008
"""

from __future__ import annotations

import io
import re
import tarfile
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path
from typing import Any, Protocol, Sequence

import httpx

from core.config import configs
from .types import OaiPaperRecord, PdfProcessResult


_OAI_NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "arxiv": "http://arxiv.org/OAI/arXiv/",
}

_FORBIDDEN_FIRST_PAGE_KEYWORDS = (
    "qubit",
    "josephson",
    "transmon",
    "fluxon",
    "squid",
    "majorana",
    "diode",
    "duality",
    "ads-cft",
)
_PRESSURE_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:gpa|kbar|bar)\b", re.IGNORECASE)
_TEMPERATURE_K_RE = re.compile(
    r"(?:~|≈|about|around|above|below|over|nearly|roughly)?\s*(\d+(?:\.\d+)?)\s*K\b",
    re.IGNORECASE,
)
_MATERIAL_RE = re.compile(r"\b(?:[A-Z][a-z]?\d*){2,}\b")
_DEBYE_RE = re.compile(r"(?:debye\s+frequenc(?:y|ies)|ω[_\s-]?d)\D*(\d+(?:\.\d+)?)", re.IGNORECASE)
_ARXIV_VERSION_RE = re.compile(r"v\d+$", re.IGNORECASE)


class OaiMetadataProvider(Protocol):
    async def fetch_records(self, *, from_date: date | None) -> tuple[list[OaiPaperRecord], date | None]:
        """Fetch OAI records."""


class ManifestIndexProvider(Protocol):
    async def resolve(self, arxiv_ids: Sequence[str]) -> dict[str, str]:
        """Resolve arxiv_id -> tar key mapping."""


class PdfFetcher(Protocol):
    async def fetch_pdf(self, *, arxiv_id: str, tar_key: str | None = None) -> bytes | None:
        """Fetch PDF bytes."""


class PdfProcessor(Protocol):
    async def process(self, pdf_bytes: bytes) -> PdfProcessResult:
        """Convert PDF bytes into text and payload."""


class ArxivOaiMetadataProvider:
    """HTTP client for arXiv OAI-PMH metadata extraction."""

    def __init__(self):
        self._base_url = configs.ARXIV_OAI_BASE_URL
        self._set_spec = configs.ARXIV_OAI_SET
        self._timeout = float(configs.ARXIV_HTTP_TIMEOUT_SECONDS)

    async def fetch_records(self, *, from_date: date | None) -> tuple[list[OaiPaperRecord], date | None]:
        """Fetch and parse OAI pages until resumption token is exhausted."""
        records: list[OaiPaperRecord] = []
        max_datestamp: date | None = None
        token: str | None = None

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            while True:
                if token:
                    params = {"verb": "ListRecords", "resumptionToken": token}
                else:
                    params = {
                        "verb": "ListRecords",
                        "metadataPrefix": "arXiv",
                        "set": self._set_spec,
                    }
                    if from_date is not None:
                        params["from"] = from_date.isoformat()

                response = await client.get(self._base_url, params=params)
                response.raise_for_status()

                page_records, token, page_max_datestamp = self._parse_page(response.text)
                records.extend(page_records)
                if page_max_datestamp is not None:
                    if max_datestamp is None or page_max_datestamp > max_datestamp:
                        max_datestamp = page_max_datestamp

                if not token:
                    break

        return records, max_datestamp

    def _parse_page(self, xml_text: str) -> tuple[list[OaiPaperRecord], str | None, date | None]:
        """Parse one OAI XML page into normalized record DTOs."""
        root = ET.fromstring(xml_text)
        records: list[OaiPaperRecord] = []
        max_datestamp: date | None = None

        for rec in root.findall(".//oai:record", _OAI_NS):
            header = rec.find("oai:header", _OAI_NS)
            if header is None:
                continue
            if header.get("status") == "deleted":
                continue

            datestamp_text = self._safe_text(header.find("oai:datestamp", _OAI_NS))
            datestamp = self._parse_date(datestamp_text)
            if datestamp is not None and (max_datestamp is None or datestamp > max_datestamp):
                max_datestamp = datestamp

            meta = rec.find("oai:metadata/arxiv:arXiv", _OAI_NS)
            if meta is None:
                continue

            arxiv_id = self._safe_text(meta.find("arxiv:id", _OAI_NS))
            if not arxiv_id:
                continue

            categories = self._safe_text(meta.find("arxiv:categories", _OAI_NS))
            title = self._normalize_ws(self._safe_text(meta.find("arxiv:title", _OAI_NS)))
            abstract = self._normalize_ws(self._safe_text(meta.find("arxiv:abstract", _OAI_NS))) or None
            published_at = self._parse_datetime(self._safe_text(meta.find("arxiv:created", _OAI_NS)))

            records.append(
                OaiPaperRecord(
                    external_id=arxiv_id,
                    title=title or arxiv_id,
                    categories=categories,
                    authors=self._parse_authors(meta),
                    abstract=abstract,
                    published_at=published_at,
                    datestamp=datestamp,
                    source_meta={
                        "oai_datestamp": datestamp.isoformat() if datestamp else None,
                        "categories": categories,
                    },
                )
            )

        token_node = root.find(".//oai:resumptionToken", _OAI_NS)
        token = token_node.text.strip() if token_node is not None and token_node.text else None
        return records, token, max_datestamp

    @staticmethod
    def _safe_text(node: ET.Element | None) -> str:
        if node is None or node.text is None:
            return ""
        return node.text.strip()

    @staticmethod
    def _normalize_ws(value: str) -> str:
        return " ".join((value or "").split())

    @staticmethod
    def _parse_date(value: str) -> date | None:
        if not value:
            return None
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None

    @staticmethod
    def _parse_datetime(value: str) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            try:
                return datetime.fromisoformat(f"{value[:10]}T00:00:00")
            except ValueError:
                return None

    def _parse_authors(self, meta: ET.Element) -> str | None:
        """Build comma-separated author list from arXiv metadata node."""
        names: list[str] = []
        for author in meta.findall("arxiv:authors/arxiv:author", _OAI_NS):
            keyname = self._safe_text(author.find("arxiv:keyname", _OAI_NS))
            forenames = self._safe_text(author.find("arxiv:forenames", _OAI_NS))
            full_name = " ".join(part for part in (forenames, keyname) if part)
            if full_name:
                names.append(full_name)
        if not names:
            return None
        return ", ".join(names)


class ArxivManifestIndexProvider:
    """Resolver for mapping arXiv IDs to TAR keys via manifest XML."""

    def __init__(self):
        self._manifest_url = configs.ARXIV_MANIFEST_URL
        self._timeout = float(configs.ARXIV_HTTP_TIMEOUT_SECONDS)

    async def resolve(self, arxiv_ids: Sequence[str]) -> dict[str, str]:
        """Return `arxiv_id -> tar_key` mapping for provided identifiers."""
        if not self._manifest_url:
            return {}
        if not arxiv_ids:
            return {}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(self._manifest_url)
            response.raise_for_status()
            manifest_entries = self._parse_manifest(response.content)

        indexed: dict[str, str] = {}
        for arxiv_id in arxiv_ids:
            yymm, lookup_key = to_lookup_key(arxiv_id)
            if not lookup_key:
                continue
            for entry in manifest_entries:
                if entry["yymm"] != yymm:
                    continue
                if entry["first_item"] and entry["last_item"]:
                    if entry["first_item"] <= lookup_key <= entry["last_item"]:
                        indexed[arxiv_id] = entry["tar_key"]
                        break
        return indexed

    @staticmethod
    def _parse_manifest(content: bytes) -> list[dict[str, str]]:
        """Parse manifest XML into comparable ranges."""
        entries: list[dict[str, str]] = []
        context = ET.iterparse(io.BytesIO(content), events=("end",))
        for _, elem in context:
            if elem.tag != "file":
                continue

            tar_key = manifest_text(elem, "filename")
            yymm = manifest_text(elem, "yymm")
            first_item = manifest_text(elem, "first_item")
            last_item = manifest_text(elem, "last_item")

            if tar_key and yymm:
                entries.append(
                    {
                        "tar_key": tar_key,
                        "yymm": yymm,
                        "first_item": first_item,
                        "last_item": last_item,
                    }
                )
            elem.clear()

        return entries


class ArxivPdfFetcher:
    """PDF fetcher with S3 TAR-first strategy and HTTP fallback."""

    def __init__(self):
        self._timeout = float(configs.ARXIV_HTTP_TIMEOUT_SECONDS)
        self._pdf_base_url = configs.ARXIV_PDF_BASE_URL.rstrip("/")

    async def fetch_pdf(self, *, arxiv_id: str, tar_key: str | None = None) -> bytes | None:
        """Fetch one PDF from S3 TAR (optional) or arXiv HTTP endpoint."""
        if configs.ARXIV_PDF_USE_S3 and tar_key:
            pdf_from_s3 = await self._fetch_from_s3_tar(arxiv_id=arxiv_id, tar_key=tar_key)
            if pdf_from_s3 is not None:
                return pdf_from_s3

        return await self._fetch_from_arxiv_http(arxiv_id)

    async def _fetch_from_arxiv_http(self, arxiv_id: str) -> bytes | None:
        """Fetch PDF directly from `ARXIV_PDF_BASE_URL`."""
        url = f"{self._pdf_base_url}/{arxiv_id}.pdf"
        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
            response = await client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.content or None

    async def _fetch_from_s3_tar(self, *, arxiv_id: str, tar_key: str) -> bytes | None:
        """Extract PDF bytes from one TAR object in S3 bucket."""
        try:
            import boto3  # type: ignore
        except Exception:
            return None

        request_kwargs: dict[str, Any] = {
            "Bucket": configs.ARXIV_S3_BUCKET,
            "Key": tar_key,
        }
        if configs.ARXIV_S3_REQUEST_PAYER:
            request_kwargs["RequestPayer"] = "requester"

        client = boto3.client("s3", region_name=configs.ARXIV_S3_REGION)
        response = await to_thread(client.get_object, **request_kwargs)
        body = response.get("Body")
        if body is None:
            return None

        tar_bytes = await to_thread(body.read)
        if not tar_bytes:
            return None

        wanted = build_pdf_basename_candidates(arxiv_id)
        with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:*") as tf:
            for member in tf:
                if not member.isfile():
                    continue
                base = Path(member.name).name
                if not base.lower().endswith(".pdf"):
                    continue
                if base[:-4] not in wanted:
                    continue
                handle = tf.extractfile(member)
                if handle is None:
                    continue
                return handle.read()
        return None


class DefaultPdfProcessor:
    """PDF processor: extract full text and build structured payload."""

    async def process(self, pdf_bytes: bytes) -> PdfProcessResult:
        """Parse PDF bytes, apply filters and return extraction result."""
        full_text = await to_thread(self._extract_text, pdf_bytes)
        if not full_text.strip():
            raise RuntimeError("Failed to extract text from PDF")

        payload = self._build_payload(full_text)
        if self._first_page_contains_forbidden(full_text):
            return PdfProcessResult(
                full_text=full_text,
                payload=payload,
                is_filtered=True,
                filter_reason="filtered_by_first_page_keywords",
            )
        if _PRESSURE_RE.search(full_text):
            return PdfProcessResult(
                full_text=full_text,
                payload=payload,
                is_filtered=True,
                filter_reason="filtered_by_pressure",
            )
        return PdfProcessResult(full_text=full_text, payload=payload, is_filtered=False)

    def _extract_text(self, pdf_bytes: bytes) -> str:
        """Extract text with PyMuPDF, then pypdf fallback, then raw decode."""
        try:
            import fitz  # type: ignore

            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            try:
                pages = [page.get_text() for page in doc]
            finally:
                doc.close()
            return "\f".join(pages).strip()
        except Exception:
            pass

        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(io.BytesIO(pdf_bytes))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\f".join(pages).strip()
        except Exception:
            pass

        return pdf_bytes.decode("utf-8", errors="ignore").strip()

    def _first_page_contains_forbidden(self, text: str) -> bool:
        """Apply BR002 keyword filter against first page only."""
        if "\f" in text:
            first_page = text.split("\f", 1)[0].lower()
        else:
            first_page = text.split("\n\n", 1)[0].lower()
        return any(word in first_page for word in _FORBIDDEN_FIRST_PAGE_KEYWORDS)

    def _build_payload(self, text: str) -> dict[str, Any]:
        """Build payload fields required by BR008."""
        lowered = text.lower()
        return {
            "material": self._extract_materials(text),
            "tc_K": self._extract_tc_k(text),
            "type": self._extract_type(lowered),
            "dimensionality": self._extract_dimensionality(lowered),
            "unconventional": bool(
                re.search(r"\b(antiferromagnet|mott\s+insulator|unconventional)\b", lowered)
            ),
            "debye_frequency": self._extract_debye(text),
        }

    def _extract_tc_k(self, text: str) -> float | None:
        """Extract max observed Tc value in Kelvin from free text."""
        values: list[float] = []
        for raw in _TEMPERATURE_K_RE.findall(text):
            try:
                values.append(float(raw))
            except ValueError:
                continue
        return max(values) if values else None

    def _extract_type(self, lowered: str) -> str:
        """Classify paper as experiment, theory or hybrid."""
        has_exp = bool(
            re.search(
                r"\b(experiment|experimental|measured?|observation|transport|arpes|stm|sample)\b",
                lowered,
            )
        )
        has_theory = bool(
            re.search(
                r"\b(theory|theoretical|model|calculation|dft|ab initio|simulation|hamiltonian)\b",
                lowered,
            )
        )
        if has_exp and has_theory:
            return "hybrid"
        if has_exp:
            return "experiment"
        if has_theory:
            return "theory"
        return ""

    def _extract_dimensionality(self, lowered: str) -> str:
        """Classify dimensionality into 2D, Bulk or unknown."""
        has_2d = bool(
            re.search(r"\b(2d|two-dimensional|monolayer|single-layer|thin film|ultrathin)\b", lowered)
        )
        has_bulk = bool(re.search(r"\b(bulk|3d|three-dimensional|single crystal)\b", lowered))
        if has_2d and has_bulk:
            return ""
        if has_2d:
            return "2D"
        if has_bulk:
            return "Bulk"
        return ""

    def _extract_materials(self, text: str) -> dict[str, int]:
        """Extract formula-like material tokens with context validation."""
        materials: dict[str, int] = {}
        lowered = text.lower()
        for match in _MATERIAL_RE.findall(text):
            if len(match) < 3:
                continue
            if not re.search(r"[A-Z]", match):
                continue
            if not re.search(r"[a-zA-Z]\d", match) and len(re.findall(r"[A-Z][a-z]?", match)) < 2:
                continue
            for occurrence in re.finditer(re.escape(match), text):
                start = max(0, occurrence.start() - 80)
                end = min(len(text), occurrence.end() + 80)
                window = lowered[start:end]
                if any(word in window for word in ("superconduct", "tc", "pairing", "critical temperature")):
                    materials[match] = materials.get(match, 0) + 1
        return materials

    def _extract_debye(self, text: str) -> list[float]:
        """Extract Debye frequency-like numeric values."""
        values: list[float] = []
        for raw in _DEBYE_RE.findall(text):
            try:
                values.append(float(raw))
            except ValueError:
                continue
        return values


def manifest_text(element: ET.Element, tag: str) -> str:
    """Return stripped child text for XML tag, or empty string."""
    child = element.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def to_lookup_key(arxiv_id: str) -> tuple[str, str]:
    """Normalize arXiv ID into `(yymm, comparable_key)` for manifest lookup."""
    raw = (arxiv_id or "").strip()
    if not raw:
        return "", ""

    raw = _ARXIV_VERSION_RE.sub("", raw)
    if "/" in raw:
        category, rest = raw.split("/", 1)
        yymm = rest[:4] if len(rest) >= 4 else "0000"
        return yymm, f"{category}{rest}"

    if "." in raw:
        try:
            year, tail = raw.split(".", 1)
            return f"{year[2:4]}{tail[:2]}", raw
        except Exception:
            pass

    return "0000", raw.replace("/", "")


def build_pdf_basename_candidates(arxiv_id: str) -> set[str]:
    """Build acceptable basename variants used while scanning TAR members."""
    normalized = (arxiv_id or "").strip()
    base = normalized[6:] if normalized.lower().startswith("arxiv:") else normalized
    without_version = _ARXIV_VERSION_RE.sub("", base)
    variants = {
        base,
        without_version,
        base.replace("/", ""),
        without_version.replace("/", ""),
        base.replace("/", "_"),
        without_version.replace("/", "_"),
    }
    return {value for value in variants if value}


async def to_thread(func, *args, **kwargs):
    """Run sync callable in thread pool and await result."""
    import asyncio

    return await asyncio.to_thread(func, *args, **kwargs)
