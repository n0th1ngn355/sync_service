"""
Test T013 / SC017.

Given: Paper with same source+external_id already exists.
When: POST /api/v1/papers with same source+external_id.
Then: 409 Conflict.
"""

import pytest
from httpx import AsyncClient

from api.v1.endpoints.papers import post as papers_post
from core.exceptions import ConflictError


@pytest.mark.asyncio
async def test_create_paper_duplicate_returns_conflict(client: AsyncClient, monkeypatch):
    async def fake_create_paper(_session, payload, **kwargs):
        _ = payload, kwargs
        raise ConflictError("Paper already exists")

    monkeypatch.setattr(papers_post.service, "create_paper", fake_create_paper)

    response = await client.post(
        "/api/v1/papers",
        json={
            "title": "Duplicate",
            "source": "scopus",
            "external_id": "10.1038/test",
        },
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "CONFLICT"
