"""
Database connection manager.

## Traceability
Infrastructure.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import configs


class DatabaseConnection:
    def __init__(self):
        self.engine = None
        self.async_session = None

    def _ensure_initialized(self) -> None:
        if self.engine is not None and self.async_session is not None:
            return

        self.engine = create_async_engine(
            configs.database_url,
            echo=configs.MODE_DEBUG,
            pool_pre_ping=True,
        )
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        self._ensure_initialized()

        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
