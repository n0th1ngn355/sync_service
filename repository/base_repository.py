"""
Generic repository primitives.

## Traceability
Infrastructure.
"""

from typing import Generic, Optional, Type, TypeVar

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from model.base_model import Base


ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base CRUD repository for one SQLAlchemy model."""

    def __init__(self, model: Type[ModelType]):
        self.model = model

    async def get_by_id(
        self,
        id: int,
        session: AsyncSession,
    ) -> Optional[ModelType]:
        """Return one entity by primary key or `None` when missing."""
        result = await session.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_all(
        self,
        session: AsyncSession,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ModelType]:
        """Return paginated list of entities."""
        result = await session.execute(select(self.model).limit(limit).offset(offset))
        return list(result.scalars().all())

    async def create(
        self,
        session: AsyncSession,
        **kwargs,
    ) -> ModelType:
        """Create and flush one entity instance."""
        instance = self.model(**kwargs)
        session.add(instance)
        await session.flush()
        await session.refresh(instance)
        return instance

    async def delete(
        self,
        id: int,
        session: AsyncSession,
    ) -> bool:
        """Delete by primary key. Returns `True` when row was affected."""
        result = await session.execute(delete(self.model).where(self.model.id == id))
        return result.rowcount > 0
