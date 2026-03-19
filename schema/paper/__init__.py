"""Paper schema exports."""

from .paper_schema import (
    PaperContentResponseSchema,
    PaperDetailResponseSchema,
    PaperListItemSchema,
    PaperListResponseSchema,
    PaperStatsResponseSchema,
    StatsBucketSchema,
    TopMaterialSchema,
)

__all__ = [
    "PaperListItemSchema",
    "PaperListResponseSchema",
    "PaperDetailResponseSchema",
    "PaperContentResponseSchema",
    "StatsBucketSchema",
    "TopMaterialSchema",
    "PaperStatsResponseSchema",
]
