"""
Fixtures for F002 scheduler API tests.

## Traceability
Feature: F002
Scenarios: SC005, SC006, SC007, SC008, SC009
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
