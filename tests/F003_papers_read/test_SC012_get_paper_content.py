"""
Test T009 / SC012.

Given: Paper content may exist or be missing.
When: GET /api/v1/papers/{id}/content.
Then: 200 with full_text or 404 if content is missing.
"""

import pytest
from httpx import AsyncClient

from core.exceptions import NotFoundError
from schema import PaperContentResponseSchema
from api.v1.endpoints.papers import get as papers_get


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "has_content, expected_status",
    [
        (True, 200),
        (False, 404),
    ],
)
async def test_get_paper_content(
    client: AsyncClient,
    monkeypatch,
    has_content: bool,
    expected_status: int,
):
    async def fake_get_paper_content(_session, paper_id: int):
        if not has_content:
            raise NotFoundError("paper_content", paper_id)

        return PaperContentResponseSchema(
            paper_id=paper_id,
            full_text="Full paper text",
        )

    monkeypatch.setattr(papers_get.service, "get_paper_content", fake_get_paper_content)

    response = await client.get("/api/v1/papers/1/content")

    assert response.status_code == expected_status
    if expected_status == 200:
        body = response.json()
        assert bool(body["full_text"].strip()) is True
