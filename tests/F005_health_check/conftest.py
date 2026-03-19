"""
Fixtures for F005 health checks.

## Traceability
Feature: F005
Scenarios: SC019, SC022
"""

from pathlib import Path
import shutil
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api import app
from core import configs, db_connect


class _FakeResult:
    def __init__(self, row=None):
        self._row = row

    def first(self):
        return self._row


class HealthySession:
    async def execute(self, statement):
        sql = str(statement)
        if "FROM sync_state" in sql:
            return _FakeResult(("OK", None, 3))
        return _FakeResult()


class BrokenDatabaseSession:
    async def execute(self, statement):
        raise RuntimeError("database disconnected")


@pytest.fixture(autouse=True)
def cleanup_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def storage_path(monkeypatch):
    root = Path("tests") / ".tmp-storage"
    path = root / str(uuid.uuid4())
    path.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(configs, "STORAGE_PATH", str(path))
    yield path

    shutil.rmtree(root, ignore_errors=True)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def override_with_session(session_obj):
    async def _override_get_session():
        yield session_obj

    app.dependency_overrides[db_connect.get_session] = _override_get_session
