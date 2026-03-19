"""
Scheduler config model.

## Traceability
Feature: F002
Scenarios: SC005-SC007
"""

from sqlalchemy import Boolean, Column, DateTime, String, Text, UniqueConstraint

from model.base_model import Base, BaseModel
from model.enums import SchedulerStatusEnum


class SchedulerConfigModel(Base, BaseModel):
    __tablename__ = "scheduler_config"

    job_name = Column(String(128), nullable=False)
    cron_expression = Column(String(64), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    last_run_at = Column(DateTime, nullable=True)
    last_status = Column(String(32), nullable=False, default=SchedulerStatusEnum.IDLE.value)
    note = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("job_name", name="uq_scheduler_config_job_name"),
    )
