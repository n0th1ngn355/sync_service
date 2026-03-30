"""
Endpoints exports.

## Traceability
Infrastructure.
"""

from .health import router as health_router
from .papers import router as papers_router
from .scheduler import router as scheduler_router

__all__ = [
    "health_router",
    "papers_router",
    "scheduler_router",
]
