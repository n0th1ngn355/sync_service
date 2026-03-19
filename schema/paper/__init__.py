"""Paper schema exports."""

from .paper_schema import (
    PaperCreateResponseSchema,
    PaperCreateSchema,
    PaperContentResponseSchema,
    PaperDetailResponseSchema,
    PaperListItemSchema,
    PaperListResponseSchema,
    PaperStatsResponseSchema,
    StatsBucketSchema,
    TopMaterialSchema,
)

__all__ = [
    "PaperCreateSchema",
    "PaperCreateResponseSchema",
    "PaperListItemSchema",
    "PaperListResponseSchema",
    "PaperDetailResponseSchema",
    "PaperContentResponseSchema",
    "StatsBucketSchema",
    "TopMaterialSchema",
    "PaperStatsResponseSchema",
]
