"""
Fixtures for F003 papers read API tests.

## Traceability
Feature: F003
Scenarios: SC010, SC011, SC012, SC013, SC014
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api import app
from core import db_connect


@pytest.fixture(autouse=True)
def clear_overrides():
    async def fake_get_session():
        yield object()

    app.dependency_overrides[db_connect.get_session] = fake_get_session

    yield

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
