"""
Paper source metadata model.

## Traceability
Feature: F003, F004
Scenarios: SC009, SC014, SC017
"""

from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy import JSON

from model.base_model import Base, BaseModel


class PaperSourceMetaModel(Base, BaseModel):
    __tablename__ = "paper_source_meta"

    paper_id = Column(Integer, ForeignKey("paper.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)
    source_meta = Column(JSON, nullable=False, default=dict)
