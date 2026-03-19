"""
Test T016 / SC022.

Given: Service is running, DB is unavailable.
When: GET /health/ready.
Then: 503 Service Unavailable and database=disconnected.
"""

import pytest
from httpx import AsyncClient

from .conftest import BrokenDatabaseSession, override_with_session


@pytest.mark.asyncio
async def test_readiness_returns_503_when_database_is_unavailable(
    client: AsyncClient,
    storage_path,
):
    override_with_session(BrokenDatabaseSession())

    response = await client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["database"] == "disconnected"
