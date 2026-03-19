"""
Test T010 / SC013.

Given: DB contains papers from multiple sources and statuses.
When: GET /api/v1/papers/stats.
Then: Returns all aggregation fields.
"""

import pytest
from httpx import AsyncClient

from schema import PaperStatsResponseSchema, StatsBucketSchema, TopMaterialSchema
from api.v1.endpoints.papers import get as papers_get


@pytest.mark.asyncio
async def test_get_paper_stats(client: AsyncClient, monkeypatch):
    async def fake_get_stats(_session):
        return PaperStatsResponseSchema(
            total_count=5,
            by_source=[StatsBucketSchema(key="arxiv", count=3), StatsBucketSchema(key="manual", count=2)],
            by_status=[StatsBucketSchema(key="DONE", count=4), StatsBucketSchema(key="NEW", count=1)],
            by_type=[StatsBucketSchema(key="experiment", count=3), StatsBucketSchema(key="theory", count=2)],
            top_materials=[TopMaterialSchema(material="HgBa2Ca2Cu3O8", count=2)],
        )

    monkeypatch.setattr(papers_get.service, "get_stats", fake_get_stats)

    response = await client.get("/api/v1/papers/stats")

    assert response.status_code == 200
    body = response.json()
    assert "total_count" in body
    assert "by_source" in body
    assert "by_status" in body
    assert "by_type" in body
    assert "top_materials" in body
