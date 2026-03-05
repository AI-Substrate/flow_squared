"""Tests for the health endpoint.

Uses httpx.AsyncClient with FastAPI test transport — no real database needed.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from fs2.config.objects import ServerDatabaseConfig
from fs2.server.app import create_app
from fs2.server.database import Database


class FakeDatabase(Database):
    """Fake database for unit tests — no real PostgreSQL connection.

    Simulates a connected pool that returns canned results.
    """

    def __init__(self) -> None:
        super().__init__(ServerDatabaseConfig())
        self._connected = False
        self._graph_count = 0

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected


class FakeDatabaseDisconnected(FakeDatabase):
    """Simulates a database that is not connected."""

    @property
    def is_connected(self) -> bool:
        return False


@pytest.fixture
def fake_db() -> FakeDatabase:
    db = FakeDatabase()
    db._connected = True
    return db


@pytest.fixture
def app(fake_db: FakeDatabase):
    return create_app(database=fake_db)


@pytest.fixture
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health_returns_200(client: AsyncClient):
    """Health endpoint returns 200 status code."""
    response = await client.get("/health")
    assert response.status_code == 200


async def test_health_json_shape(client: AsyncClient):
    """Health endpoint returns expected JSON keys."""
    response = await client.get("/health")
    data = response.json()
    assert "status" in data
    assert "db" in data
    assert "graphs" in data


async def test_health_disconnected_db():
    """Health endpoint degrades gracefully when DB is not connected."""
    db = FakeDatabaseDisconnected()
    app = create_app(database=db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        data = response.json()
        assert data["status"] == "degraded"
        assert data["db"] == "disconnected"
        assert data["graphs"] is None


async def test_openapi_docs(client: AsyncClient):
    """OpenAPI docs endpoint is available."""
    response = await client.get("/docs")
    assert response.status_code == 200


async def test_app_title(client: AsyncClient):
    """App metadata is set correctly."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "fs2 Server"
