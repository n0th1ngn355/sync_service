"""
Scheduler service behavior tests.
"""

from dataclasses import dataclass

import pytest

from service.scheduler.scheduler_service import SchedulerService


@dataclass
class _Config:
    job_name: str = "sync_pipeline"
    cron_expression: str = "* * * * *"
    is_active: bool = True
    last_run_at: object | None = None
    last_status: str = "IDLE"


class _Repo:
    def __init__(self):
        self.config = _Config()

    async def get_or_create(self, _session, **kwargs):
        _ = kwargs
        return self.config

    async def save(self, _session, config):
        self.config = config
        return self.config

    async def mark_running(self, _session, *, config, started_at, note):
        _ = started_at, note
        config.last_status = "RUNNING"
        return config

    async def mark_finished(self, _session, *, config, status, note):
        _ = note
        config.last_status = status.value
        return config


class _Runtime:
    def __init__(self):
        self._configured = False
        self.configure_calls = 0

    def is_configured(self):
        return self._configured

    def configure_job(self, **kwargs):
        _ = kwargs
        self.configure_calls += 1
        self._configured = True

    def get_next_run_at(self):
        return None

    def shutdown(self):
        self._configured = False


@pytest.mark.asyncio
async def test_get_status_configures_runtime_only_once():
    service = SchedulerService(repo=_Repo(), runtime=_Runtime())

    await service.get_status(object())
    await service.get_status(object())

    assert service._runtime.configure_calls == 1
