"""
Fixtures for F001 automatic sync tests.

## Traceability
Feature: F001
Scenarios: SC001, SC002, SC003, SC004
"""

from pathlib import Path
import shutil
import uuid

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import model  # noqa: F401
from core.config import configs
from model.base_model import Base


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    root = Path("tests") / ".tmp-f001"
    test_dir = root / str(uuid.uuid4())
    storage_dir = test_dir / "storage"

    storage_dir.mkdir(parents=True, exist_ok=True)
    configs.STORAGE_PATH = str(storage_dir)

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with factory() as db_session:
        yield db_session

    await engine.dispose()
    shutil.rmtree(test_dir, ignore_errors=True)
