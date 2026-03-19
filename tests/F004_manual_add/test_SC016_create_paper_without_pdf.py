"""
Test T012 / SC016.

Given: User sends JSON metadata only.
When: POST /api/v1/papers.
Then: 201 Created, status DONE and default payload.
"""

import pytest
from httpx import AsyncClient

from api.v1.endpoints.papers import post as papers_post
from schema import PaperCreateResponseSchema


@pytest.mark.asyncio
async def test_create_manual_paper_without_pdf(client: AsyncClient, monkeypatch):
    async def fake_create_paper(
        _session,
        payload,
        *,
        pdf_bytes=None,
        pdf_filename=None,
        pdf_mime_type=None,
    ):
        assert payload.title == "Manual Paper"
        assert payload.source == "manual"
        assert pdf_bytes is None
        assert pdf_filename is None
        assert pdf_mime_type is None

        return PaperCreateResponseSchema(
            id=2,
            source=payload.source,
            external_id=None,
            title=payload.title,
            status="DONE",
            payload={},
            created_at="2026-03-19T00:00:00",
        )

    monkeypatch.setattr(papers_post.service, "create_paper", fake_create_paper)

    response = await client.post(
        "/api/v1/papers",
        json={
            "title": "Manual Paper",
            "source": "manual",
            "authors": "Author A",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "DONE"
    assert body["payload"] == {}
