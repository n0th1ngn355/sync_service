"""
Paper model.

## Traceability
Feature: F001, F003, F004
Scenarios: SC001, SC002, SC008-SC018
"""

from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy import JSON

from model.base_model import Base, BaseModel
from model.enums import PaperStatusEnum


class PaperModel(Base, BaseModel):
    __tablename__ = "paper"

    source = Column(String(64), nullable=False, index=True)
    external_id = Column(String(255), nullable=True)

    title = Column(Text, nullable=False)
    authors = Column(Text, nullable=True)
    abstract = Column(Text, nullable=True)
    categories = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True, index=True)

    status = Column(String(32), nullable=False, default=PaperStatusEnum.NEW.value, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)

    payload = Column(JSON, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_paper_source_external_id"),
    )
