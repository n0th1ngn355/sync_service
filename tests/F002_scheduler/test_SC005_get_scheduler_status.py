"""
Test T005 / SC005.

Given: Scheduler config exists.
When: GET /api/v1/scheduler/status.
Then: 200 and response has schedule/status fields.
"""

import pytest
from httpx import AsyncClient

from api.v1.endpoints.scheduler import get as scheduler_get
from schema import SchedulerStatusResponseSchema


@pytest.mark.asyncio
async def test_get_scheduler_status(client: AsyncClient, monkeypatch):
    async def fake_get_status(_session):
        return SchedulerStatusResponseSchema(
            job_name="sync_pipeline",
            cron_expression="0 * * * *",
            is_active=True,
            last_run_at=None,
            last_status="IDLE",
            next_run_at=None,
        )

    monkeypatch.setattr(scheduler_get.scheduler_service, "get_status", fake_get_status)

    response = await client.get("/api/v1/scheduler/status")

    assert response.status_code == 200
    body = response.json()
    assert "cron_expression" in body
    assert "is_active" in body
    assert "last_run_at" in body
    assert "last_status" in body
    assert "next_run_at" in body
