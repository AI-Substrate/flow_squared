"""Tests for the structured request logging middleware.

Verifies that AccessLogMiddleware:
- Logs requests with correct fields
- Skips /health to avoid noise
- Captures status codes and timing
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from fs2.config.objects import ServerDatabaseConfig
from fs2.server.app import create_app
from fs2.server.database import Database


class MinimalFakeDatabase(Database):
    """Minimal fake database for middleware tests."""

    def __init__(self) -> None:
        super().__init__(ServerDatabaseConfig())
        self._connected = True

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator:
        conn = AsyncMock()

        async def fake_execute(sql, *args, **kwargs):
            result = MagicMock()
            if "count(*)" in str(sql).lower():
                result.fetchone = AsyncMock(return_value=(0,))
            elif "select 1" in str(sql).lower():
                result.fetchone = AsyncMock(return_value=(1,))
            elif "from graphs" in str(sql).lower():
                result.fetchall = AsyncMock(return_value=[])
            elif "from api_keys" in str(sql).lower():
                result.fetchall = AsyncMock(return_value=[])
            else:
                result.fetchone = AsyncMock(return_value=None)
                result.fetchall = AsyncMock(return_value=[])
            return result

        conn.execute = fake_execute
        conn.commit = AsyncMock()
        yield conn


@pytest.fixture
def fake_db() -> MinimalFakeDatabase:
    return MinimalFakeDatabase()


@pytest.fixture
def app(fake_db: MinimalFakeDatabase):
    return create_app(database=fake_db)


@pytest.fixture
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_middleware_logs_api_request(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
):
    """Middleware logs API requests with status and method."""
    with caplog.at_level(logging.INFO, logger="fs2.server.access"):
        await client.get("/api/v1/graphs")
    assert any("GET" in r.message and "/api/v1/graphs" in r.message for r in caplog.records)


async def test_middleware_logs_dashboard_request(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
):
    """Middleware logs dashboard requests."""
    with caplog.at_level(logging.INFO, logger="fs2.server.access"):
        await client.get("/dashboard/")
    assert any("/dashboard/" in r.message for r in caplog.records)


async def test_middleware_skips_health(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
):
    """Middleware does NOT log /health requests (noise reduction)."""
    with caplog.at_level(logging.INFO, logger="fs2.server.access"):
        await client.get("/health")
    assert not any("/health" in r.message for r in caplog.records)


async def test_middleware_logs_status_code(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
):
    """Middleware log records include status code in extra data."""
    with caplog.at_level(logging.INFO, logger="fs2.server.access"):
        await client.get("/api/v1/graphs")
    access_records = [r for r in caplog.records if r.name == "fs2.server.access"]
    assert len(access_records) > 0
    record = access_records[0]
    assert hasattr(record, "status_code")
    assert record.status_code == 200


async def test_middleware_logs_duration(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
):
    """Middleware log records include duration_ms in extra data."""
    with caplog.at_level(logging.INFO, logger="fs2.server.access"):
        await client.get("/api/v1/graphs")
    access_records = [r for r in caplog.records if r.name == "fs2.server.access"]
    assert len(access_records) > 0
    record = access_records[0]
    assert hasattr(record, "duration_ms")
    assert isinstance(record.duration_ms, float)
    assert record.duration_ms >= 0


async def test_middleware_logs_method(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
):
    """Middleware log records include HTTP method."""
    with caplog.at_level(logging.INFO, logger="fs2.server.access"):
        await client.get("/dashboard/graphs")
    access_records = [r for r in caplog.records if r.name == "fs2.server.access"]
    assert len(access_records) > 0
    assert access_records[0].method == "GET"
