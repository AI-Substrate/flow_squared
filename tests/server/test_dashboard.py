"""Tests for the management dashboard routes.

Uses httpx.AsyncClient + ASGITransport with FakeDatabase — no real PostgreSQL.
Lightweight functional tests: HTML response codes, form handling, HTMX partials.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from fs2.config.objects import ServerDatabaseConfig
from fs2.server.app import create_app
from fs2.server.database import Database


class DashboardFakeDatabase(Database):
    """Fake database for dashboard tests.

    Supports graph list, graph delete, API key queries, and count queries.
    Maintains in-memory graph and API key state for realistic test flows.
    """

    def __init__(self) -> None:
        super().__init__(ServerDatabaseConfig())
        self._connected = True
        self._graphs: list[dict] = []
        self._api_keys: list[dict] = []
        self._tenants_created = False

    def add_graph(
        self,
        graph_id: str = "test-id-1",
        name: str = "test-graph",
        status: str = "ready",
        node_count: int = 100,
        edge_count: int = 50,
    ) -> None:
        """Add a fake graph for list/delete testing."""
        self._graphs.append({
            "id": graph_id,
            "name": name,
            "description": None,
            "status": status,
            "node_count": node_count,
            "edge_count": edge_count,
            "embedding_model": "text-embedding-3-small",
            "updated_at": None,
        })

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

        async def fake_execute(sql, params=None):
            result = MagicMock()
            sql_lower = sql.strip().lower() if isinstance(sql, str) else str(sql).lower()

            if "select 1" in sql_lower:
                result.fetchone = AsyncMock(return_value=(1,))

            elif "count(*)" in sql_lower and "ready" in sql_lower:
                ready = sum(1 for g in self._graphs if g["status"] == "ready")
                result.fetchone = AsyncMock(return_value=(ready,))

            elif "count(*)" in sql_lower and "pending" in sql_lower:
                pending = sum(
                    1 for g in self._graphs
                    if g["status"] in ("pending", "ingesting")
                )
                result.fetchone = AsyncMock(return_value=(pending,))

            elif "from graphs" in sql_lower and "order by" in sql_lower:
                rows = [
                    (
                        g["id"], g["name"], g["description"], g["status"],
                        g["node_count"], g["edge_count"], g["embedding_model"],
                        g["updated_at"],
                    )
                    for g in sorted(self._graphs, key=lambda x: x["name"])
                ]
                result.fetchall = AsyncMock(return_value=rows)

            elif "select name from graphs" in sql_lower:
                graph_id = params[0] if params else None
                found = next(
                    (g for g in self._graphs if g["id"] == graph_id), None
                )
                if found:
                    result.fetchone = AsyncMock(return_value=(found["name"],))
                else:
                    result.fetchone = AsyncMock(return_value=None)

            elif "delete from graphs" in sql_lower:
                graph_id = params[0] if params else None
                self._graphs = [
                    g for g in self._graphs if g["id"] != graph_id
                ]
                result.fetchone = AsyncMock(return_value=None)

            elif "insert into tenants" in sql_lower:
                self._tenants_created = True
                result.fetchone = AsyncMock(return_value=None)

            elif "from api_keys" in sql_lower:
                rows = [
                    (
                        k["id"], k["name"], k["key_prefix"], k["scope"],
                        k["is_active"], k.get("last_used_at"), k["created_at"],
                    )
                    for k in self._api_keys if k["is_active"]
                ]
                result.fetchall = AsyncMock(return_value=rows)

            elif "insert into api_keys" in sql_lower:
                from datetime import datetime, timezone
                key_data = {
                    "id": "key-" + str(len(self._api_keys)),
                    "key_hash": params[1] if params else "hash",
                    "key_prefix": params[2] if params else "fs2_",
                    "name": params[3] if params else "test",
                    "scope": params[4] if params else "read",
                    "is_active": True,
                    "last_used_at": None,
                    "created_at": datetime.now(timezone.utc),
                }
                self._api_keys.append(key_data)

            elif "update api_keys" in sql_lower:
                key_id = params[0] if params else None
                for k in self._api_keys:
                    if k["id"] == key_id:
                        k["is_active"] = False

            else:
                result.fetchone = AsyncMock(return_value=None)
                result.fetchall = AsyncMock(return_value=[])

            conn.commit = AsyncMock()
            return result

        conn.execute = fake_execute
        conn.commit = AsyncMock()
        yield conn


@pytest.fixture
def fake_db() -> DashboardFakeDatabase:
    return DashboardFakeDatabase()


@pytest.fixture
def app(fake_db: DashboardFakeDatabase):
    return create_app(database=fake_db)


@pytest.fixture
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --- Dashboard Home ---


async def test_dashboard_home_returns_html(client: AsyncClient):
    """Dashboard home returns 200 with HTML content type."""
    response = await client.get("/dashboard/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


async def test_dashboard_home_contains_navigation(client: AsyncClient):
    """Dashboard home contains navigation links."""
    response = await client.get("/dashboard/")
    html = response.text
    assert "Graphs" in html
    assert "Upload" in html
    assert "API Keys" in html


async def test_dashboard_home_shows_graph_count(
    fake_db: DashboardFakeDatabase, client: AsyncClient
):
    """Dashboard home shows ready graph count."""
    fake_db.add_graph(status="ready")
    fake_db.add_graph(graph_id="id-2", name="graph-2", status="ready")
    response = await client.get("/dashboard/")
    assert "2" in response.text


# --- Graph List ---


async def test_graph_list_returns_html(client: AsyncClient):
    """Graph list returns 200 with HTML."""
    response = await client.get("/dashboard/graphs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


async def test_graph_list_shows_graphs(
    fake_db: DashboardFakeDatabase, client: AsyncClient
):
    """Graph list shows graph names and status badges."""
    fake_db.add_graph(name="my-repo", status="ready")
    response = await client.get("/dashboard/graphs")
    html = response.text
    assert "my-repo" in html
    assert "badge-ready" in html


async def test_graph_list_empty_state(client: AsyncClient):
    """Graph list shows empty state message when no graphs."""
    response = await client.get("/dashboard/graphs")
    assert "No graphs uploaded" in response.text


async def test_graph_list_shows_ingesting_badge(
    fake_db: DashboardFakeDatabase, client: AsyncClient
):
    """Graph list shows ingesting badge for in-progress graphs."""
    fake_db.add_graph(name="building", status="ingesting")
    response = await client.get("/dashboard/graphs")
    assert "badge-ingesting" in response.text


async def test_graph_table_partial(
    fake_db: DashboardFakeDatabase, client: AsyncClient
):
    """HTMX table partial returns just the table for polling."""
    fake_db.add_graph(name="polled-graph")
    response = await client.get("/dashboard/graphs/table")
    assert response.status_code == 200
    assert "polled-graph" in response.text
    # Should be a table fragment, not a full page
    assert "<html" not in response.text


# --- Graph Upload ---


async def test_upload_form_returns_html(client: AsyncClient):
    """Upload form page returns 200 with HTML."""
    response = await client.get("/dashboard/graphs/upload")
    assert response.status_code == 200
    assert "Upload Graph" in response.text


# --- Graph Delete ---


async def test_graph_delete_removes_graph(
    fake_db: DashboardFakeDatabase, client: AsyncClient
):
    """Delete endpoint removes graph and returns empty response."""
    fake_db.add_graph(graph_id="del-1", name="to-delete")
    response = await client.request("DELETE", "/dashboard/graphs/del-1")
    assert response.status_code == 200
    assert response.text == ""
    assert len(fake_db._graphs) == 0


async def test_graph_delete_not_found(client: AsyncClient):
    """Delete returns 404 for unknown graph."""
    response = await client.request("DELETE", "/dashboard/graphs/nonexistent")
    assert response.status_code == 404


# --- API Keys ---


async def test_api_keys_page_returns_html(client: AsyncClient):
    """API keys page returns 200 with HTML."""
    response = await client.get("/dashboard/settings/keys")
    assert response.status_code == 200
    assert "API Keys" in response.text


async def test_api_keys_shows_warning_banner(client: AsyncClient):
    """API keys page shows auth not active warning (DYK-P6-08)."""
    response = await client.get("/dashboard/settings/keys")
    assert "enforcement not active" in response.text


async def test_api_key_generation(
    fake_db: DashboardFakeDatabase, client: AsyncClient
):
    """Generating an API key returns the full key once."""
    response = await client.post(
        "/dashboard/settings/keys",
        data={"name": "test-key", "scope": "read"},
    )
    assert response.status_code == 200
    html = response.text
    assert "fs2_" in html
    assert "Copy to Clipboard" in html
    assert len(fake_db._api_keys) == 1


async def test_api_key_revoke(
    fake_db: DashboardFakeDatabase, client: AsyncClient
):
    """Revoking an API key returns empty response for HTMX row removal."""
    fake_db._api_keys.append({
        "id": "key-revoke-1",
        "name": "old-key",
        "key_prefix": "fs2_abc",
        "scope": "read",
        "is_active": True,
        "created_at": None,
    })

    response = await client.post("/dashboard/settings/keys/key-revoke-1/revoke")
    assert response.status_code == 200
    assert response.text == ""


# --- Key Generation Logic ---


def test_generate_api_key_format():
    """API key has correct format: fs2_ prefix + 32 hex chars."""
    from fs2.server.dashboard.routes import _generate_api_key

    full_key, prefix, key_hash = _generate_api_key()
    assert full_key.startswith("fs2_")
    assert len(full_key) == 36
    assert prefix == full_key[:12]
    assert len(key_hash) == 64  # SHA-256 hex


def test_generate_api_key_uniqueness():
    """Each generated key is unique."""
    from fs2.server.dashboard.routes import _generate_api_key

    keys = {_generate_api_key()[0] for _ in range(10)}
    assert len(keys) == 10


def test_generate_api_key_hash_is_sha256():
    """Key hash is SHA-256 of the full key (DYK-P6-10)."""
    import hashlib

    from fs2.server.dashboard.routes import _generate_api_key

    full_key, _, key_hash = _generate_api_key()
    expected = hashlib.sha256(full_key.encode()).hexdigest()
    assert key_hash == expected


# --- Polling Stop Condition (FT-001/FT-005) ---


async def test_polling_container_has_htmx_when_pending(
    fake_db: DashboardFakeDatabase, client: AsyncClient
):
    """Table container includes hx-get/trigger when graphs are pending."""
    fake_db.add_graph(name="pending-graph", status="ingesting")
    response = await client.get("/dashboard/graphs/table")
    html = response.text
    assert 'hx-get="/dashboard/graphs/table"' in html
    assert 'hx-trigger="every 5s"' in html


async def test_polling_container_stops_when_settled(
    fake_db: DashboardFakeDatabase, client: AsyncClient
):
    """Table container removes hx-get/trigger when all graphs are ready/error."""
    fake_db.add_graph(name="done-graph", status="ready")
    response = await client.get("/dashboard/graphs/table")
    html = response.text
    assert "hx-get" not in html
    assert "hx-trigger" not in html


# --- Dashboard Home Error Handling (FT-006) ---


async def test_dashboard_home_shows_db_error():
    """Dashboard home shows error message when DB query fails."""
    from contextlib import asynccontextmanager

    from fs2.server.app import create_app

    class FailingDatabase(DashboardFakeDatabase):
        @asynccontextmanager
        async def connection(self):
            raise RuntimeError("DB is down")
            yield  # noqa: unreachable — required for async generator syntax

    db = FailingDatabase()
    app = create_app(database=db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/dashboard/")
        assert response.status_code == 200
        assert "Unable to load dashboard data" in response.text


# --- Shared Helpers (FT-007) ---


def test_shared_default_tenant_id():
    """graph_admin.DEFAULT_TENANT_ID matches across modules."""
    from fs2.server.graph_admin import DEFAULT_TENANT_ID

    assert DEFAULT_TENANT_ID == "00000000-0000-0000-0000-000000000000"
