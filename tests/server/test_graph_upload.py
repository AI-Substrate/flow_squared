"""Tests for graph upload and management endpoints.

Uses httpx.AsyncClient with FakeDatabase for fast unit tests.
Integration tests (slow) use real PostgreSQL.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from fs2.server.app import create_app
from tests.server.test_ingestion import make_test_graph, write_pickle


@pytest.fixture
def test_pickle(tmp_path) -> Path:
    """Create a valid test pickle file."""
    metadata, graph = make_test_graph(3)
    path = tmp_path / "test.pickle"
    write_pickle(metadata, graph, path)
    return path


async def test_list_graphs_empty():
    """GET /api/v1/graphs returns empty list on fresh server."""
    from tests.server.test_health import FakeDatabase

    db = FakeDatabase()
    db._connected = True

    # Override connection to return empty list for graphs query
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_conn():
        conn = AsyncMock()

        async def fake_execute(sql, *args, **kwargs):
            result = MagicMock()
            if "FROM graphs" in sql and "SELECT" in sql:
                result.fetchall = AsyncMock(return_value=[])
                result.fetchone = AsyncMock(return_value=None)
            elif "SELECT 1" in sql:
                result.fetchone = AsyncMock(return_value=(1,))
            elif "count(*)" in sql:
                result.fetchone = AsyncMock(return_value=(0,))
            else:
                result.fetchall = AsyncMock(return_value=[])
                result.fetchone = AsyncMock(return_value=None)
            return result

        conn.execute = fake_execute
        yield conn

    db.connection = fake_conn

    app = create_app(database=db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/graphs")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["graphs"] == []


async def test_openapi_has_graph_endpoints():
    """OpenAPI spec includes graph endpoints."""
    from tests.server.test_health import FakeDatabase

    db = FakeDatabase()
    db._connected = True
    app = create_app(database=db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/openapi.json")
        data = response.json()
        paths = data["paths"]
        assert "/api/v1/graphs" in paths
        assert "/api/v1/graphs/{graph_id}/status" in paths
