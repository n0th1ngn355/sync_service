"""
Paper file model.

## Traceability
Feature: F001, F004
Scenarios: SC002, SC015
"""

from sqlalchemy import BigInteger, Column, ForeignKey, Integer, String, Text, UniqueConstraint

from model.base_model import Base, BaseModel
from model.enums import FileTypeEnum


class PaperFileModel(Base, BaseModel):
    __tablename__ = "paper_file"

    paper_id = Column(Integer, ForeignKey("paper.id", ondelete="CASCADE"), nullable=False, index=True)
    file_type = Column(String(16), nullable=False, default=FileTypeEnum.PDF.value)
    storage_path = Column(Text, nullable=False)
    mime_type = Column(String(128), nullable=True)
    size_bytes = Column(BigInteger, nullable=True)
    checksum = Column(String(128), nullable=True)

    __table_args__ = (
        UniqueConstraint("paper_id", "file_type", name="uq_paper_file_type"),
    )
