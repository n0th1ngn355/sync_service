"""
Test SC009.

Given: Scheduler is active.
When: POST /api/v1/scheduler/pause then /resume.
Then: is_active toggles false/true.
"""

import pytest
from httpx import AsyncClient

from api.v1.endpoints.scheduler import post as scheduler_post
from schema import SchedulerStatusResponseSchema


@pytest.mark.asyncio
async def test_pause_and_resume_scheduler(client: AsyncClient, monkeypatch):
    async def fake_pause(_session):
        return SchedulerStatusResponseSchema(
            job_name="sync_pipeline",
            cron_expression="0 * * * *",
            is_active=False,
            last_run_at=None,
            last_status="IDLE",
            next_run_at=None,
        )

    async def fake_resume(_session):
        return SchedulerStatusResponseSchema(
            job_name="sync_pipeline",
            cron_expression="0 * * * *",
            is_active=True,
            last_run_at=None,
            last_status="IDLE",
            next_run_at=None,
        )

    monkeypatch.setattr(scheduler_post.scheduler_service, "pause", fake_pause)
    monkeypatch.setattr(scheduler_post.scheduler_service, "resume", fake_resume)

    paused = await client.post("/api/v1/scheduler/pause")
    resumed = await client.post("/api/v1/scheduler/resume")

    assert paused.status_code == 200
    assert paused.json()["is_active"] is False

    assert resumed.status_code == 200
    assert resumed.json()["is_active"] is True
