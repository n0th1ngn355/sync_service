"""
Test T011 / SC015.

Given: User sends multipart metadata + PDF.
When: POST /api/v1/papers.
Then: 201 Created and initial status is PROCESSING.
"""

import json

import pytest
from httpx import AsyncClient

from api.v1.endpoints.papers import post as papers_post
from schema import PaperCreateResponseSchema


@pytest.mark.asyncio
async def test_create_manual_paper_with_pdf(client: AsyncClient, monkeypatch):
    async def fake_create_paper(
        _session,
        payload,
        *,
        pdf_bytes=None,
        pdf_filename=None,
        pdf_mime_type=None,
    ):
        assert payload.title == "Test Paper"
        assert payload.source == "manual"
        assert pdf_filename == "test.pdf"
        assert pdf_mime_type == "application/pdf"
        assert pdf_bytes.startswith(b"%PDF")

        return PaperCreateResponseSchema(
            id=1,
            source=payload.source,
            external_id=None,
            title=payload.title,
            status="PROCESSING",
            payload={},
            created_at="2026-03-19T00:00:00",
        )

    monkeypatch.setattr(papers_post.service, "create_paper", fake_create_paper)

    metadata = {
        "title": "Test Paper",
        "source": "manual",
        "authors": "Author A",
    }
    files = {"file": ("test.pdf", b"%PDF-1.4\nstub-content", "application/pdf")}
    data = {"metadata": json.dumps(metadata)}

    response = await client.post("/api/v1/papers", data=data, files=files)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PROCESSING"
    assert body["title"] == "Test Paper"
