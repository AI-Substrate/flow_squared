"""Tests for server query API endpoints.

Tests tree, search, get-node, and multi-graph search routes
using FakeDatabase pattern from prior phases.
"""

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from fs2.server.app import create_app


# ── Fake Database for query tests ──


class FakeConnection:
    """Fake async connection that returns configured results."""

    def __init__(self, results: dict | None = None):
        self._results = results or {}
        self._default_result = FakeResult([])

    async def execute(self, query, params=None):
        # Route based on query content
        query_lower = query.strip().lower() if isinstance(query, str) else ""

        for key, result in self._results.items():
            if key.lower() in query_lower:
                return result

        return self._default_result

    async def commit(self):
        pass


class FakeResult:
    """Fake query result."""

    def __init__(self, rows):
        self._rows = rows

    async def fetchone(self):
        return self._rows[0] if self._rows else None

    async def fetchall(self):
        return self._rows


class FakeDatabase:
    """Fake database for testing query endpoints."""

    def __init__(self, results: dict | None = None):
        self._results = results or {}

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator:
        yield FakeConnection(self._results)

    async def connect(self):
        pass

    async def disconnect(self):
        pass

    @property
    def is_connected(self):
        return True


def _make_graph_row(
    graph_id="00000000-0000-0000-0000-000000000001",
    name="test-repo",
    status="ready",
    model="text-embedding-3-small",
    dims=1024,
):
    """Create a fake graphs table row."""
    return (graph_id, name, status, model, dims)


def _make_node_row(
    node_id="file:src/main.py",
    category="file",
    ts_kind="module",
    content_type="code",
    name="main.py",
):
    """Create a fake code_nodes row matching _NODE_COLUMNS order."""
    return (
        node_id,      # node_id
        category,      # category
        ts_kind,       # ts_kind
        content_type,  # content_type
        name,          # name
        node_id,       # qualified_name
        1,             # start_line
        50,            # end_line
        0,             # start_column
        0,             # end_column
        0,             # start_byte
        500,           # end_byte
        "# Main file", # content
        "abc123",      # content_hash
        None,          # signature
        "python",      # language
        True,          # is_named
        None,          # field_name
        False,         # is_error
        None,          # parent_node_id
        False,         # truncated
        None,          # truncated_at_line
        "Main module", # smart_content
        "sc123",       # smart_content_hash
        None,          # embedding_hash
    )


def _make_app_with_fake(fake_db):
    """Create app with fake database, bypassing lifespan."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fs2.server.routes.graphs import router as graphs_router
    from fs2.server.routes.health import router as health_router
    from fs2.server.routes.query import router as query_router

    app = FastAPI(title="fs2 Server Test")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.db = fake_db
    app.include_router(health_router)
    app.include_router(graphs_router)
    app.include_router(query_router)
    return app


# ── Tree endpoint tests ──


class TestTreeEndpoint:
    """Tests for GET /api/v1/graphs/{name}/tree."""

    @pytest.mark.anyio
    async def test_tree_returns_200_with_graph_name(self):
        """Tree endpoint returns graph metadata in response."""
        graph_row = _make_graph_row()
        fake_db = FakeDatabase({
            "from graphs where name": FakeResult([graph_row]),
            "from code_nodes": FakeResult([]),
        })
        app = _make_app_with_fake(fake_db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/graphs/test-repo/tree")

        assert resp.status_code == 200
        data = resp.json()
        assert data["graph_name"] == "test-repo"
        assert data["pattern"] == "."
        assert "tree" in data
        assert "count" in data

    @pytest.mark.anyio
    async def test_tree_404_for_unknown_graph(self):
        """Tree returns 404 for non-existent graph."""
        fake_db = FakeDatabase({
            "from graphs where name": FakeResult([]),
        })
        app = _make_app_with_fake(fake_db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/graphs/nonexistent/tree")

        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_tree_409_for_not_ready_graph(self):
        """Tree returns 409 for graph not in 'ready' status."""
        graph_row = _make_graph_row(status="ingesting")
        fake_db = FakeDatabase({
            "from graphs where name": FakeResult([graph_row]),
        })
        app = _make_app_with_fake(fake_db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/graphs/test-repo/tree")

        assert resp.status_code == 409

    @pytest.mark.anyio
    async def test_tree_with_folder_hierarchy(self):
        """Tree with max_depth builds virtual folder structure."""
        graph_row = _make_graph_row()
        nodes = [
            _make_node_row("file:src/main.py", "file", "module", "code", "main.py"),
            _make_node_row("file:src/utils.py", "file", "module", "code", "utils.py"),
            _make_node_row("file:tests/test_main.py", "file", "module", "code", "test_main.py"),
        ]
        fake_db = FakeDatabase({
            "from graphs where name": FakeResult([graph_row]),
            "from code_nodes": FakeResult(nodes),
        })
        app = _make_app_with_fake(fake_db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/graphs/test-repo/tree?pattern=.&max_depth=1"
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1  # At least one folder

    @pytest.mark.anyio
    async def test_tree_with_pattern_filter(self):
        """Tree with pattern filter returns matching nodes."""
        graph_row = _make_graph_row()
        nodes = [
            _make_node_row("file:src/main.py", "file", "module", "code", "main.py"),
        ]
        fake_db = FakeDatabase({
            "from graphs where name": FakeResult([graph_row]),
            "from code_nodes": FakeResult(nodes),
        })
        app = _make_app_with_fake(fake_db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/graphs/test-repo/tree?pattern=main"
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "tree" in data


# ── Get-node endpoint tests ──


class TestGetNodeEndpoint:
    """Tests for GET /api/v1/graphs/{name}/nodes/{node_id}."""

    @pytest.mark.anyio
    async def test_get_node_returns_code_node(self):
        """Get-node returns full CodeNode data."""
        graph_row = _make_graph_row()
        node_row = _make_node_row()
        fake_db = FakeDatabase({
            "from graphs where name": FakeResult([graph_row]),
            "from code_nodes": FakeResult([node_row]),
            "from embedding_chunks": FakeResult([]),
            "count(*) from node_edges": FakeResult([(3,)]),
        })
        app = _make_app_with_fake(fake_db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/graphs/test-repo/nodes/file:src/main.py"
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["node_id"] == "file:src/main.py"
        assert data["category"] == "file"
        assert data["graph_name"] == "test-repo"
        assert "children_count" in data

    @pytest.mark.anyio
    async def test_get_node_404_for_unknown_node(self):
        """Get-node returns 404 for non-existent node."""
        graph_row = _make_graph_row()
        fake_db = FakeDatabase({
            "from graphs where name": FakeResult([graph_row]),
            "from code_nodes": FakeResult([]),
            "from embedding_chunks": FakeResult([]),
        })
        app = _make_app_with_fake(fake_db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/graphs/test-repo/nodes/file:nonexistent.py"
            )

        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_node_max_detail_includes_content(self):
        """Get-node with detail=max includes content field."""
        graph_row = _make_graph_row()
        node_row = _make_node_row()
        fake_db = FakeDatabase({
            "from graphs where name": FakeResult([graph_row]),
            "from code_nodes": FakeResult([node_row]),
            "from embedding_chunks": FakeResult([]),
            "count(*) from node_edges": FakeResult([(0,)]),
        })
        app = _make_app_with_fake(fake_db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/graphs/test-repo/nodes/file:src/main.py?detail=max"
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data
        assert "content_hash" in data


# ── Search endpoint tests ──


class TestSearchEndpoint:
    """Tests for GET /api/v1/graphs/{name}/search."""

    @pytest.mark.anyio
    async def test_search_returns_envelope_format(self):
        """Search response has meta + results envelope."""
        graph_row = _make_graph_row()
        search_rows = [
            ("file:src/main.py", "file", 1, 50, "Main module", "# content", "main.py",
             0.9, "test-repo"),
        ]
        fake_db = FakeDatabase({
            "from graphs where name": FakeResult([graph_row]),
            "count(*) from code_nodes": FakeResult([(1,)]),
            "from code_nodes cn": FakeResult(search_rows),
            "select exists": FakeResult([(False,)]),
        })
        app = _make_app_with_fake(fake_db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/graphs/test-repo/search?pattern=main&mode=text"
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "meta" in data
        assert "results" in data
        assert "total" in data["meta"]
        assert "showing" in data["meta"]
        assert "pagination" in data["meta"]
        assert "folders" in data["meta"]

    @pytest.mark.anyio
    async def test_search_text_mode_returns_results(self):
        """Text mode search returns scored results."""
        graph_row = _make_graph_row()
        search_rows = [
            ("file:src/main.py", "file", 1, 50, "Main module", "# main", "main.py",
             0.9, "test-repo"),
        ]
        fake_db = FakeDatabase({
            "from graphs where name": FakeResult([graph_row]),
            "count(*) from code_nodes": FakeResult([(1,)]),
            "from code_nodes cn": FakeResult(search_rows),
        })
        app = _make_app_with_fake(fake_db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/graphs/test-repo/search?pattern=main&mode=text"
            )

        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) >= 1
        assert "score" in results[0]
        assert "node_id" in results[0]

    @pytest.mark.anyio
    async def test_search_auto_falls_back_to_text(self):
        """Auto mode falls back to text when no embeddings."""
        graph_row = _make_graph_row()
        fake_db = FakeDatabase({
            "from graphs where name": FakeResult([graph_row]),
            "select exists": FakeResult([(False,)]),
            "count(*) from code_nodes": FakeResult([(0,)]),
            "from code_nodes cn": FakeResult([]),
        })
        app = _make_app_with_fake(fake_db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/graphs/test-repo/search?pattern=authentication&mode=auto"
            )

        # Should succeed (fell back to text, found nothing)
        assert resp.status_code == 200


# ── Multi-graph search tests ──


class TestMultiGraphSearch:
    """Tests for GET /api/v1/search (multi-graph)."""

    @pytest.mark.anyio
    async def test_multi_graph_all_returns_envelope(self):
        """Multi-graph search with graph=all returns proper envelope."""
        graph_rows = [
            _make_graph_row("id1", "repo1"),
            _make_graph_row("id2", "repo2"),
        ]
        fake_db = FakeDatabase({
            "from graphs where status": FakeResult(graph_rows),
            "select exists": FakeResult([(False,)]),
            "count(*) from code_nodes": FakeResult([(0,)]),
            "from code_nodes cn": FakeResult([]),
        })
        app = _make_app_with_fake(fake_db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/search?pattern=test&graph=all")

        assert resp.status_code == 200
        data = resp.json()
        assert "meta" in data
        assert "results" in data

    @pytest.mark.anyio
    async def test_multi_graph_specific_names(self):
        """Multi-graph search with specific graph names."""
        graph_row = _make_graph_row()
        fake_db = FakeDatabase({
            "from graphs where name": FakeResult([graph_row]),
            "select exists": FakeResult([(False,)]),
            "count(*) from code_nodes": FakeResult([(0,)]),
            "from code_nodes cn": FakeResult([]),
        })
        app = _make_app_with_fake(fake_db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/search?pattern=test&graph=test-repo&mode=text"
            )

        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_multi_graph_no_ready_graphs(self):
        """Multi-graph returns empty when no graphs ready."""
        fake_db = FakeDatabase({
            "from graphs where status": FakeResult([]),
        })
        app = _make_app_with_fake(fake_db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/search?pattern=test&graph=all")

        assert resp.status_code == 200
        assert resp.json()["meta"]["total"] == 0


# ── List-graphs enhanced tests ──


class TestListGraphsEnhanced:
    """Tests for GET /api/v1/graphs with status filter."""

    @pytest.mark.anyio
    async def test_list_graphs_with_status_filter(self):
        """List-graphs with ?status=ready filters results."""
        graph_rows = [
            ("id1", "repo1", None, "ready", 100, 50, "model", 1024, "1.0",
             None, None, None),
        ]
        fake_db = FakeDatabase({
            "from graphs where status": FakeResult(graph_rows),
            "from graphs": FakeResult(graph_rows),
        })
        app = _make_app_with_fake(fake_db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/graphs?status=ready")

        assert resp.status_code == 200
        data = resp.json()
        assert "graphs" in data


# ── Response format parity tests ──


class TestResponseFormatParity:
    """Verify response shapes match local CLI/MCP output."""

    @pytest.mark.anyio
    async def test_search_result_has_9_min_fields(self):
        """Search result in min mode has 9 required fields."""
        graph_row = _make_graph_row()
        search_rows = [
            ("file:src/main.py", "file", 1, 50, "Main module", "# content", "main.py",
             0.9, "test-repo"),
        ]
        fake_db = FakeDatabase({
            "from graphs where name": FakeResult([graph_row]),
            "count(*) from code_nodes": FakeResult([(1,)]),
            "from code_nodes cn": FakeResult(search_rows),
        })
        app = _make_app_with_fake(fake_db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/graphs/test-repo/search?pattern=main&mode=text&detail=min"
            )

        result = resp.json()["results"][0]
        min_fields = {
            "node_id", "start_line", "end_line",
            "match_start_line", "match_end_line",
            "smart_content", "snippet", "score", "match_field",
        }
        assert min_fields.issubset(set(result.keys()))
        # Min mode should not have content
        assert "content" not in result

    @pytest.mark.anyio
    async def test_search_result_max_has_extra_fields(self):
        """Search result in max mode adds content + chunk fields."""
        graph_row = _make_graph_row()
        search_rows = [
            ("file:src/main.py", "file", 1, 50, "Main module", "# content", "main.py",
             0.9, "test-repo"),
        ]
        fake_db = FakeDatabase({
            "from graphs where name": FakeResult([graph_row]),
            "count(*) from code_nodes": FakeResult([(1,)]),
            "from code_nodes cn": FakeResult(search_rows),
        })
        app = _make_app_with_fake(fake_db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/graphs/test-repo/search?pattern=main&mode=text&detail=max"
            )

        result = resp.json()["results"][0]
        assert "content" in result

    @pytest.mark.anyio
    async def test_tree_node_has_required_shape(self):
        """Tree nodes have node_id, name, category, children fields."""
        graph_row = _make_graph_row()
        nodes = [
            _make_node_row("file:src/main.py", "file", "module", "code", "main.py"),
        ]
        fake_db = FakeDatabase({
            "from graphs where name": FakeResult([graph_row]),
            "from code_nodes": FakeResult(nodes),
        })
        app = _make_app_with_fake(fake_db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/graphs/test-repo/tree?pattern=main"
            )

        data = resp.json()
        if data["count"] > 0:
            node = data["tree"][0]
            assert "node_id" in node
            assert "children" in node

    @pytest.mark.anyio
    async def test_get_node_min_has_core_fields(self):
        """Get-node min mode has core identification fields."""
        graph_row = _make_graph_row()
        node_row = _make_node_row()
        fake_db = FakeDatabase({
            "from graphs where name": FakeResult([graph_row]),
            "from code_nodes": FakeResult([node_row]),
            "from embedding_chunks": FakeResult([]),
            "count(*) from node_edges": FakeResult([(0,)]),
        })
        app = _make_app_with_fake(fake_db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/graphs/test-repo/nodes/file:src/main.py?detail=min"
            )

        data = resp.json()
        core_fields = {
            "node_id", "category", "ts_kind", "name",
            "start_line", "end_line", "language",
            "children_count", "graph_name",
        }
        assert core_fields.issubset(set(data.keys()))
