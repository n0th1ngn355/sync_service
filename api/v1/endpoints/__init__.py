"""
Endpoints exports.

## Traceability
Infrastructure.
"""

from .health import router as health_router
from .papers import router as papers_router
from .users import router as users_router

__all__ = [
    "health_router",
    "papers_router",
    "users_router",
]
