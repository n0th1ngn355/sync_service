"""
Paper create endpoint.

## Traceability
Feature: F004
Scenarios: SC015, SC016, SC017, SC018
"""

import json
from json import JSONDecodeError
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import FormData, UploadFile

from core import db_connect
from schema import PaperCreateResponseSchema, PaperCreateSchema
from service import PaperService

router = APIRouter(prefix="/papers", tags=["Papers"])
service = PaperService()


@router.post("", response_model=PaperCreateResponseSchema, status_code=201)
async def create_paper(
    request: Request,
    session: AsyncSession = Depends(db_connect.get_session),
) -> PaperCreateResponseSchema:
    """
    Create a paper manually (F004).

    Supported content types:
    - `application/json` for metadata-only create
    - `multipart/form-data` for metadata + PDF upload
    """
    content_type = request.headers.get("content-type", "")
    media_type = content_type.split(";", 1)[0].strip().lower()

    if media_type == "application/json":
        body = await _parse_json_body(request)
        payload = _validate_paper_payload(body)
        return await service.create_paper(session, payload)

    if media_type == "multipart/form-data":
        form = await request.form()
        payload = _parse_payload_from_form(form)
        upload_file = _extract_upload(form)

        if upload_file is None:
            return await service.create_paper(session, payload)

        file_bytes = await upload_file.read()
        return await service.create_paper(
            session,
            payload,
            pdf_bytes=file_bytes,
            pdf_filename=upload_file.filename,
            pdf_mime_type=upload_file.content_type,
        )

    raise HTTPException(
        status_code=415,
        detail="Unsupported content type. Use application/json or multipart/form-data",
    )


async def _parse_json_body(request: Request) -> dict[str, Any]:
    """Parse and validate JSON request body as an object."""
    try:
        body = await request.json()
    except JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="Invalid JSON body") from exc

    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object")

    return body


def _parse_payload_from_form(form: FormData) -> PaperCreateSchema:
    """Build `PaperCreateSchema` from multipart form data."""
    metadata_raw = form.get("metadata")
    if metadata_raw is not None:
        if not isinstance(metadata_raw, str):
            raise HTTPException(status_code=422, detail="metadata must be a JSON string")

        try:
            metadata = json.loads(metadata_raw)
        except JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="metadata is not valid JSON") from exc

        if not isinstance(metadata, dict):
            raise HTTPException(status_code=422, detail="metadata must decode to JSON object")

        return _validate_paper_payload(metadata)

    raw_source_meta = form.get("source_meta")
    source_meta: dict[str, Any] = {}
    if isinstance(raw_source_meta, str) and raw_source_meta.strip():
        try:
            source_meta = json.loads(raw_source_meta)
        except JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="source_meta is not valid JSON") from exc

        if not isinstance(source_meta, dict):
            raise HTTPException(status_code=422, detail="source_meta must decode to JSON object")

    payload = {
        "title": form.get("title"),
        "source": form.get("source"),
        "authors": form.get("authors"),
        "abstract": form.get("abstract"),
        "categories": form.get("categories"),
        "external_id": form.get("external_id"),
        "source_meta": source_meta,
    }
    return _validate_paper_payload(payload)


def _extract_upload(form: FormData) -> UploadFile | None:
    """Extract uploaded PDF file from supported multipart keys."""
    for key in ("file", "pdf", "paper_pdf"):
        candidate = form.get(key)
        if isinstance(candidate, UploadFile):
            return candidate
    return None


def _validate_paper_payload(payload: dict[str, Any]) -> PaperCreateSchema:
    """Validate payload via Pydantic and normalize validation errors."""
    try:
        return PaperCreateSchema.model_validate(payload)
    except PydanticValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
