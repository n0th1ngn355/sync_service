"""
Paper schemas.

## Traceability
Feature: F003
Scenarios: SC010, SC011, SC012, SC013, SC014
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PaperListItemSchema(BaseModel):
    id: int
    external_id: str | None = None
    source: str
    title: str
    authors: str | None = None
    categories: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    status: str
    published_at: datetime | None = None

    class Config:
        from_attributes = True


class PaperListResponseSchema(BaseModel):
    items: list[PaperListItemSchema]
    total: int
    offset: int
    limit: int


class PaperDetailResponseSchema(BaseModel):
    id: int
    source: str
    external_id: str | None = None
    title: str
    authors: str | None = None
    abstract: str | None = None
    categories: str | None = None
    published_at: datetime | None = None

    status: str
    attempts: int
    last_error: str | None = None

    payload: dict[str, Any] = Field(default_factory=dict)
    source_meta: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime
    updated_at: datetime | None = None


class PaperContentResponseSchema(BaseModel):
    paper_id: int
    full_text: str


class StatsBucketSchema(BaseModel):
    key: str
    count: int


class TopMaterialSchema(BaseModel):
    material: str
    count: int


class PaperStatsResponseSchema(BaseModel):
    total_count: int
    by_source: list[StatsBucketSchema]
    by_status: list[StatsBucketSchema]
    by_type: list[StatsBucketSchema]
    top_materials: list[TopMaterialSchema]
