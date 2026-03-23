"""
Tests T007 / SC007 / SC008.

Given: Scheduler can be running or idle.
When: POST /api/v1/scheduler/run.
Then: 202 Accepted for idle, 409 Conflict when already running.
"""

import pytest
from httpx import AsyncClient

from api.v1.endpoints.scheduler import post as scheduler_post
from core.exceptions import ConflictError
from schema import SchedulerRunResponseSchema


@pytest.mark.asyncio
async def test_manual_run_returns_202_when_pipeline_is_idle(client: AsyncClient, monkeypatch):
    async def fake_run_now(_session):
        return SchedulerRunResponseSchema(
            run_id="run-123",
            status="RUNNING",
            started_at="2026-03-23T10:00:00",
        )

    monkeypatch.setattr(scheduler_post.scheduler_service, "run_now", fake_run_now)

    response = await client.post("/api/v1/scheduler/run")

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "RUNNING"
    assert body["run_id"] == "run-123"


@pytest.mark.asyncio
async def test_manual_run_returns_409_when_pipeline_already_running(client: AsyncClient, monkeypatch):
    async def fake_run_now(_session):
        raise ConflictError("Pipeline is already running")

    monkeypatch.setattr(scheduler_post.scheduler_service, "run_now", fake_run_now)

    response = await client.post("/api/v1/scheduler/run")

    assert response.status_code == 409
