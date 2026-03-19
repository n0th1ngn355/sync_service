"""Papers router."""

from fastapi import APIRouter

from .get import router as get_router
from .post import router as post_router

router = APIRouter()
router.include_router(get_router)
router.include_router(post_router)

__all__ = ["router"]
