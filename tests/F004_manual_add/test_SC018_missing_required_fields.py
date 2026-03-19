"""
Test T014 / SC018.

Given: Request payload misses required fields.
When: POST /api/v1/papers without title.
Then: 422 Unprocessable Entity.
"""

import pytest
from httpx import AsyncClient

from api.v1.endpoints.papers import post as papers_post


@pytest.mark.asyncio
async def test_create_paper_without_title_returns_422(client: AsyncClient, monkeypatch):
    async def fake_create_paper(_session, payload, **kwargs):
        _ = payload, kwargs
        raise AssertionError("service.create_paper must not be called for invalid payload")

    monkeypatch.setattr(papers_post.service, "create_paper", fake_create_paper)

    response = await client.post("/api/v1/papers", json={"source": "manual"})

    assert response.status_code == 422
