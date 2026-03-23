"""
APScheduler runtime wrapper.

## Traceability
Feature: F002
Business Rules: BR012, BR013, BR014
"""

import asyncio
import inspect
from datetime import datetime
from typing import Awaitable, Callable

from .apscheduler_compat import AsyncIOScheduler, CronTrigger, JobLookupError


SchedulerCallable = Callable[[], Awaitable[None] | None]


class SchedulerRuntime:
    JOB_ID = "sync_pipeline_job"

    def __init__(self):
        self._scheduler = AsyncIOScheduler(timezone="UTC")
        self._is_started = False
        self._is_configured = False
        self._job_callable: SchedulerCallable | None = None
        self._run_lock = asyncio.Lock()

    def ensure_started(self) -> None:
        if self._is_started:
            return

        self._scheduler.start()
        self._is_started = True

    def shutdown(self) -> None:
        if not self._is_started:
            return

        self._scheduler.shutdown(wait=False)
        self._is_started = False
        self._is_configured = False

    def configure_job(
        self,
        *,
        cron_expression: str,
        is_active: bool,
        callback: SchedulerCallable,
    ) -> None:
        self.ensure_started()
        self._job_callable = callback
        trigger = CronTrigger.from_crontab(cron_expression)

        existing = self._scheduler.get_job(self.JOB_ID)
        if existing is None:
            self._scheduler.add_job(
                self._run_callback,
                id=self.JOB_ID,
                trigger=trigger,
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
        else:
            self._scheduler.reschedule_job(self.JOB_ID, trigger=trigger)
            self._scheduler.modify_job(self.JOB_ID, func=self._run_callback)

        if is_active:
            self.resume()
        else:
            self.pause()
        self._is_configured = True

    def is_configured(self) -> bool:
        return self._is_configured

    def pause(self) -> None:
        self.ensure_started()
        try:
            self._scheduler.pause_job(self.JOB_ID)
        except JobLookupError:
            return

    def resume(self) -> None:
        self.ensure_started()
        try:
            self._scheduler.resume_job(self.JOB_ID)
        except JobLookupError:
            return

    def get_next_run_at(self) -> datetime | None:
        if not self._is_started:
            return None

        job = self._scheduler.get_job(self.JOB_ID)
        if job is None:
            return None

        return job.next_run_time

    async def acquire_run_lock(self) -> bool:
        if self._run_lock.locked():
            return False

        await self._run_lock.acquire()
        return True

    def release_run_lock(self) -> None:
        if self._run_lock.locked():
            self._run_lock.release()

    async def _run_callback(self) -> None:
        if self._job_callable is None:
            return

        result = self._job_callable()
        if inspect.isawaitable(result):
            await result


scheduler_runtime = SchedulerRuntime()
