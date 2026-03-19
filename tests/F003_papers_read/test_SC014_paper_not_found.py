"""
Test SC014.

Given: Paper with id=99999 does not exist.
When: GET /api/v1/papers/99999.
Then: 404 Not Found.
"""

import pytest
from httpx import AsyncClient

from core.exceptions import NotFoundError
from api.v1.endpoints.papers import get as papers_get


@pytest.mark.asyncio
async def test_get_paper_not_found(client: AsyncClient, monkeypatch):
    async def fake_get_paper_by_id(_session, paper_id: int):
        raise NotFoundError("paper", paper_id)

    monkeypatch.setattr(papers_get.service, "get_paper_by_id", fake_get_paper_by_id)

    response = await client.get("/api/v1/papers/99999")

    assert response.status_code == 404
