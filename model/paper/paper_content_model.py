"""
Paper content model.

## Traceability
Feature: F001, F003, F004
Scenarios: SC002, SC010, SC016
"""

from sqlalchemy import Column, ForeignKey, Integer, Text

from model.base_model import Base, BaseModel


class PaperContentModel(Base, BaseModel):
    __tablename__ = "paper_content"

    paper_id = Column(Integer, ForeignKey("paper.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)
    full_text = Column(Text, nullable=False)
