"""Scheduler router."""

from fastapi import APIRouter

from .get import router as get_router
from .post import router as post_router
from .put import router as put_router

router = APIRouter()
router.include_router(get_router)
router.include_router(put_router)
router.include_router(post_router)

__all__ = ["router"]
