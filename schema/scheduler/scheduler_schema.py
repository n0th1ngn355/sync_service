"""
Scheduler schemas.

## Traceability
Feature: F002
Scenarios: SC005, SC006, SC007, SC008, SC009
"""

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SchedulerStatusResponseSchema(BaseModel):
    job_name: str
    cron_expression: str
    is_active: bool
    last_run_at: datetime | None = None
    last_status: str
    next_run_at: datetime | None = None


class SchedulerScheduleUpdateSchema(BaseModel):
    cron_expression: str | None = Field(default=None, description="Cron expression with 5 fields")
    preset: Literal["hourly", "daily", "weekly"] | None = Field(default=None)

    @model_validator(mode="after")
    def validate_source(self):
        has_cron = bool(self.cron_expression)
        has_preset = bool(self.preset)

        if has_cron == has_preset:
            raise ValueError("Provide exactly one of cron_expression or preset")

        if has_cron:
            expression = self.cron_expression or ""
            parts = expression.strip().split()
            if len(parts) != 5:
                raise ValueError("Invalid cron_expression")

            if not all(_is_valid_cron_part(part) for part in parts):
                raise ValueError("Invalid cron_expression")

        return self


class SchedulerRunResponseSchema(BaseModel):
    run_id: str
    status: str
    started_at: datetime


_DIGIT_RE = re.compile(r"^\d+$")


def _is_valid_cron_part(part: str) -> bool:
    if not part:
        return False

    for item in part.split(","):
        if not item:
            return False
        if item == "*":
            continue
        if item.startswith("/"):
            return False
        if item.startswith("*/"):
            step = item[2:]
            if not _DIGIT_RE.fullmatch(step):
                return False
            if int(step) <= 0:
                return False
            continue

        if "/" in item:
            base, step = item.split("/", 1)
            if not base or not step:
                return False
            if not _DIGIT_RE.fullmatch(step):
                return False
            if int(step) <= 0:
                return False

            if base == "*":
                continue
            if "-" in base:
                start, end = base.split("-", 1)
                if not (_DIGIT_RE.fullmatch(start) and _DIGIT_RE.fullmatch(end)):
                    return False
                continue
            if _DIGIT_RE.fullmatch(base):
                continue
            return False

        if "-" in item:
            start, end = item.split("-", 1)
            if not (_DIGIT_RE.fullmatch(start) and _DIGIT_RE.fullmatch(end)):
                return False
            continue

        if not _DIGIT_RE.fullmatch(item):
            return False

    return True
