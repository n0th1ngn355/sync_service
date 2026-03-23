"""
API package.

Exports FastAPI app.
"""

from core import app
from service.scheduler.scheduler_service import scheduler_service
from .v1 import include_router  # noqa: F401
from .v1.exception_handlers import register_exception_handlers

register_exception_handlers(app)


@app.on_event("startup")
async def startup_scheduler_runtime() -> None:
    await scheduler_service.bootstrap()


@app.on_event("shutdown")
async def shutdown_scheduler_runtime() -> None:
    scheduler_service.shutdown()


__all__ = ["app"]
