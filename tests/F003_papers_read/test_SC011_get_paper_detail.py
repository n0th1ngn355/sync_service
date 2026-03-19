"""
Test SC011.

Given: Paper with id=42 exists.
When: GET /api/v1/papers/42.
Then: Returns full paper details including source_meta.
"""

import pytest
from httpx import AsyncClient

from schema import PaperDetailResponseSchema
from api.v1.endpoints.papers import get as papers_get


@pytest.mark.asyncio
async def test_get_paper_details(client: AsyncClient, monkeypatch):
    async def fake_get_paper_by_id(_session, paper_id: int):
        assert paper_id == 42
        return PaperDetailResponseSchema(
            id=42,
            source="arxiv",
            external_id="2311.05538",
            title="Superconductor paper",
            authors="A. Author",
            abstract="Abstract",
            categories="cond-mat.supr-con",
            published_at=None,
            status="DONE",
            attempts=1,
            last_error=None,
            payload={"material": {"HgBa2Ca2Cu3O8": 2}, "tc_K": 135.0, "type": "experiment"},
            source_meta={"doi": "10.1000/example"},
            created_at="2026-03-19T00:00:00",
            updated_at="2026-03-19T00:00:00",
        )

    monkeypatch.setattr(papers_get.service, "get_paper_by_id", fake_get_paper_by_id)

    response = await client.get("/api/v1/papers/42")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 42
    assert "payload" in body
    assert "source_meta" in body
