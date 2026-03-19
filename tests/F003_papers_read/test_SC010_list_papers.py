"""
Test T008 / SC010.

Given: DB has papers with mixed source/type/tc_K.
When: GET /api/v1/papers with filters and pagination.
Then: Returns filtered items and total count.
"""

import pytest
from httpx import AsyncClient

from schema import PaperListItemSchema, PaperListResponseSchema
from api.v1.endpoints.papers import get as papers_get


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query, expected_source, expected_type, expected_min, expected_max",
    [
        (
            "/api/v1/papers?source=arxiv&type=experiment&offset=0&limit=10",
            "arxiv",
            "experiment",
            None,
            None,
        ),
        (
            "/api/v1/papers?tc_K_min=30&tc_K_max=100&offset=0&limit=10",
            None,
            None,
            30.0,
            100.0,
        ),
    ],
)
async def test_list_papers_with_filters_and_pagination(
    client: AsyncClient,
    monkeypatch,
    query: str,
    expected_source: str | None,
    expected_type: str | None,
    expected_min: float | None,
    expected_max: float | None,
):
    async def fake_get_papers(
        _session,
        **kwargs,
    ):
        assert kwargs["source"] == expected_source
        assert kwargs["paper_type"] == expected_type
        assert kwargs["tc_k_min"] == expected_min
        assert kwargs["tc_k_max"] == expected_max

        items = [
            PaperListItemSchema(
                id=1,
                external_id="2311.05538",
                source=kwargs["source"] or "arxiv",
                title="Paper A",
                authors="Author A",
                categories="cond-mat.supr-con",
                payload={"type": kwargs["paper_type"] or "experiment", "tc_K": 42.0},
                status="DONE",
                published_at=None,
            )
        ]

        return PaperListResponseSchema(
            items=items,
            total=37,
            offset=kwargs["offset"],
            limit=kwargs["limit"],
        )

    monkeypatch.setattr(papers_get.service, "get_papers", fake_get_papers)

    response = await client.get(query)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 37
    assert len(body["items"]) <= 10

    if expected_source is not None:
        assert all(item["source"] == expected_source for item in body["items"])

    if expected_type is not None:
        assert all(item["payload"].get("type") == expected_type for item in body["items"])

    if expected_min is not None and expected_max is not None:
        assert all(expected_min <= float(item["payload"].get("tc_K", 0)) <= expected_max for item in body["items"])
