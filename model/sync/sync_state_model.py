"""
Sync state model.

## Traceability
Feature: F001, F005
Scenarios: SC001-SC004, SC019-SC022
"""

from sqlalchemy import BigInteger, Column, Date, DateTime, String, Text, UniqueConstraint

from model.base_model import Base, BaseModel
from model.enums import SyncStatusEnum


class SyncStateModel(Base, BaseModel):
    __tablename__ = "sync_state"

    source = Column(String(128), nullable=False)

    last_status = Column(String(32), nullable=True, default=SyncStatusEnum.OK.value)
    last_error = Column(Text, nullable=True)

    last_run_started_at = Column(DateTime, nullable=True)
    last_run_finished_at = Column(DateTime, nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    last_success_datestamp = Column(Date, nullable=True)

    last_rows = Column(BigInteger, nullable=False, default=0)
    total_rows = Column(BigInteger, nullable=False, default=0)
    note = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("source", name="uq_sync_state_source"),
    )
