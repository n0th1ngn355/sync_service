"""
Health schemas.

## Traceability
Feature: F005
Scenarios: SC019, SC020, SC021, SC022
"""

from datetime import datetime
from pydantic import BaseModel, Field


class LastSyncSchema(BaseModel):
    status: str = Field(default="UNKNOWN", description="Last sync status")
    time: datetime | None = Field(default=None, description="Last sync time")
    papers: int = Field(default=0, description="Processed papers in last run")


class HealthCheckResponseSchema(BaseModel):
    status: str = Field(..., description="Overall service status")
    version: str = Field(..., description="Service version")

    database: str = Field(..., description="Database status", examples=["connected", "disconnected"])
    storage: str = Field(..., description="Storage status", examples=["available", "unavailable"])

    last_sync: LastSyncSchema = Field(..., description="Last successful/finished sync data")
    error: str | None = Field(default=None, description="Health check error details")
