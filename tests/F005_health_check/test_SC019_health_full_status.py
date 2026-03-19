"""
Test T015 / SC019.

Given: Service is running, DB and storage are available.
When: GET /health.
Then: 200 OK and healthy dependency states.
"""

import pytest
from httpx import AsyncClient

from .conftest import HealthySession, override_with_session


@pytest.mark.asyncio
async def test_health_returns_full_status_when_dependencies_are_available(
    client: AsyncClient,
    storage_path,
):
    override_with_session(HealthySession())

    response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["database"] == "connected"
    assert body["storage"] == "available"
    assert "last_sync" in body
    assert "version" in body
