"""
Include API routers.

## Traceability
Infrastructure.
"""

from core import app
from .endpoints import health_router, papers_router, scheduler_router, users_router

app.include_router(health_router)

API_V1_PREFIX = "/api/v1"

app.include_router(users_router, prefix=API_V1_PREFIX)
app.include_router(papers_router, prefix=API_V1_PREFIX)
app.include_router(scheduler_router, prefix=API_V1_PREFIX)
