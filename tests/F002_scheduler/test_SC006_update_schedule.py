"""
Test T006 / SC006.

Given: Scheduler is configured.
When: PUT /api/v1/scheduler/schedule with cron or preset.
Then: 200 and updated cron; invalid cron returns 422.
"""

import pytest
from httpx import AsyncClient

from api.v1.endpoints.scheduler import put as scheduler_put
from schema import SchedulerStatusResponseSchema


@pytest.mark.asyncio
async def test_update_schedule_with_cron_expression(client: AsyncClient, monkeypatch):
    async def fake_update_schedule(_session, body):
        assert body.cron_expression == "0 3 * * *"
        return SchedulerStatusResponseSchema(
            job_name="sync_pipeline",
            cron_expression="0 3 * * *",
            is_active=True,
            last_run_at=None,
            last_status="IDLE",
            next_run_at=None,
        )

    monkeypatch.setattr(scheduler_put.scheduler_service, "update_schedule", fake_update_schedule)

    response = await client.put(
        "/api/v1/scheduler/schedule",
        json={"cron_expression": "0 3 * * *"},
    )

    assert response.status_code == 200
    assert response.json()["cron_expression"] == "0 3 * * *"


@pytest.mark.asyncio
async def test_update_schedule_with_preset(client: AsyncClient, monkeypatch):
    async def fake_update_schedule(_session, body):
        assert body.preset == "weekly"
        return SchedulerStatusResponseSchema(
            job_name="sync_pipeline",
            cron_expression="0 3 * * 1",
            is_active=True,
            last_run_at=None,
            last_status="IDLE",
            next_run_at=None,
        )

    monkeypatch.setattr(scheduler_put.scheduler_service, "update_schedule", fake_update_schedule)

    response = await client.put(
        "/api/v1/scheduler/schedule",
        json={"preset": "weekly"},
    )

    assert response.status_code == 200
    assert response.json()["cron_expression"] == "0 3 * * 1"


@pytest.mark.asyncio
async def test_update_schedule_with_invalid_cron_returns_422(client: AsyncClient):
    response = await client.put(
        "/api/v1/scheduler/schedule",
        json={"cron_expression": "invalid"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_schedule_with_slash_only_invalid_cron_returns_422(client: AsyncClient):
    response = await client.put(
        "/api/v1/scheduler/schedule",
        json={"cron_expression": "/1 * * * *"},
    )
    assert response.status_code == 422
