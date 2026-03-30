"""
Compatibility layer for APScheduler.

Uses real APScheduler when available.
Falls back to lightweight in-memory implementations for offline environments.
"""

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Callable

try:
    from apscheduler.jobstores.base import JobLookupError  # type: ignore
    from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
    from apscheduler.triggers.cron import CronTrigger  # type: ignore

    APSCHEDULER_AVAILABLE = True
except Exception:
    APSCHEDULER_AVAILABLE = False

    class JobLookupError(Exception):
        """Fallback APScheduler-compatible lookup exception."""

        pass

    class CronTrigger:
        """Minimal cron trigger validator used in fallback mode."""

        def __init__(self, expression: str):
            self.expression = expression

        @classmethod
        def from_crontab(cls, expression: str) -> "CronTrigger":
            parts = expression.strip().split()
            if len(parts) != 5:
                raise ValueError("Cron expression must have 5 fields")

            token_re = re.compile(r"^[\d\*/,\-]+$")
            for token in parts:
                if not token_re.fullmatch(token):
                    raise ValueError(f"Invalid cron token: {token}")

            return cls(expression=expression)

    @dataclass
    class _FallbackJob:
        id: str
        func: Callable[..., Any]
        trigger: CronTrigger
        paused: bool = False
        next_run_time: datetime | None = None

    class AsyncIOScheduler:
        """In-memory scheduler fallback for environments without APScheduler."""

        def __init__(self, timezone: str = "UTC"):
            self.timezone = timezone
            self._started = False
            self._jobs: dict[str, _FallbackJob] = {}

        def start(self) -> None:
            self._started = True

        def shutdown(self, wait: bool = False) -> None:
            _ = wait
            self._started = False

        def add_job(
            self,
            func: Callable[..., Any],
            *,
            id: str,
            trigger: CronTrigger,
            replace_existing: bool = True,
            max_instances: int = 1,
            coalesce: bool = True,
        ) -> None:
            _ = replace_existing, max_instances, coalesce
            self._jobs[id] = _FallbackJob(
                id=id,
                func=func,
                trigger=trigger,
                paused=False,
                next_run_time=datetime.utcnow(),
            )

        def get_job(self, job_id: str) -> _FallbackJob | None:
            return self._jobs.get(job_id)

        def reschedule_job(self, job_id: str, *, trigger: CronTrigger) -> None:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobLookupError(job_id)
            job.trigger = trigger
            if not job.paused:
                job.next_run_time = datetime.utcnow()

        def modify_job(self, job_id: str, *, func: Callable[..., Any]) -> None:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobLookupError(job_id)
            job.func = func

        def pause_job(self, job_id: str) -> None:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobLookupError(job_id)
            job.paused = True
            job.next_run_time = None

        def resume_job(self, job_id: str) -> None:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobLookupError(job_id)
            job.paused = False
            job.next_run_time = datetime.utcnow()
