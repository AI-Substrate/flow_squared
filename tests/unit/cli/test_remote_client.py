"""Tests for RemoteClient and MultiRemoteClient.

Phase 5: Remote CLI + MCP Bridge
Tests HTTP client behavior using httpx.MockTransport (fakes over mocks).

Covers:
- URL construction for tree/search/get_node/list_graphs
- Raw dict passthrough (no object reconstruction)
- Error translation to actionable RemoteClientError
- get_node 404 distinction (node-not-found vs graph-not-found)
- Multi-graph search routing
- MultiRemoteClient merge + partial failure
"""

from __future__ import annotations

import httpx
import pytest

from fs2.cli.remote_client import MultiRemoteClient, RemoteClient, RemoteClientError

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_transport(handler):
    """Create httpx.MockTransport from an async handler."""

    async def _handle(request: httpx.Request) -> httpx.Response:
        return handler(request)

    return httpx.MockTransport(_handle)


def _ok_json(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data)


def _client_with_transport(transport: httpx.MockTransport, **kwargs) -> RemoteClient:
    """Create a RemoteClient whose _client() uses the given transport."""
    client = RemoteClient(base_url="http://test-server", **kwargs)
    original_client = client._client

    def _patched_client():
        c = original_client()
        # Replace the transport on the returned AsyncClient
        c._transport = transport
        return c

    client._client = _patched_client
    return client


# ── URL Construction ─────────────────────────────────────────────────────────


class TestRemoteClientURLConstruction:
    """Verify each public method constructs the correct URL path and params."""

    async def test_given_graph_when_tree_then_url_includes_graph_name(self):
        captured: list[httpx.Request] = []

        def handler(req: httpx.Request) -> httpx.Response:
            captured.append(req)
            return _ok_json({"format": "text", "content": "...", "count": 1})

        client = _client_with_transport(_make_transport(handler))
        await client.tree("my-graph", pattern="src/")

        assert len(captured) == 1
        assert captured[0].url.path == "/api/v1/graphs/my-graph/tree"
        assert captured[0].url.params["pattern"] == "src/"

    async def test_given_graph_when_search_single_then_per_graph_url(self):
        captured: list[httpx.Request] = []

        def handler(req: httpx.Request) -> httpx.Response:
            captured.append(req)
            return _ok_json({"meta": {}, "results": []})

        client = _client_with_transport(_make_transport(handler))
        await client.search("auth", graph="my-graph")

        assert captured[0].url.path == "/api/v1/graphs/my-graph/search"

    async def test_given_comma_graphs_when_search_then_multi_graph_endpoint(self):
        captured: list[httpx.Request] = []

        def handler(req: httpx.Request) -> httpx.Response:
            captured.append(req)
            return _ok_json({"meta": {}, "results": []})

        client = _client_with_transport(_make_transport(handler))
        await client.search("auth", graph="work,oss")

        assert captured[0].url.path == "/api/v1/search"
        assert captured[0].url.params["graph"] == "work,oss"

    async def test_given_no_graph_when_search_then_search_all(self):
        captured: list[httpx.Request] = []

        def handler(req: httpx.Request) -> httpx.Response:
            captured.append(req)
            return _ok_json({"meta": {}, "results": []})

        client = _client_with_transport(_make_transport(handler))
        await client.search("auth")

        assert captured[0].url.path == "/api/v1/search"
        assert captured[0].url.params["graph"] == "all"

    async def test_given_graph_when_get_node_then_url_includes_node_id(self):
        captured: list[httpx.Request] = []

        def handler(req: httpx.Request) -> httpx.Response:
            captured.append(req)
            return _ok_json({"node_id": "class:src/foo.py:Foo", "name": "Foo"})

        client = _client_with_transport(_make_transport(handler))
        await client.get_node("my-graph", "class:src/foo.py:Foo")

        assert "/api/v1/graphs/my-graph/nodes/" in captured[0].url.path

    async def test_given_status_when_list_graphs_then_params_include_status(self):
        captured: list[httpx.Request] = []

        def handler(req: httpx.Request) -> httpx.Response:
            captured.append(req)
            return _ok_json({"graphs": [], "count": 0})

        client = _client_with_transport(_make_transport(handler))
        await client.list_graphs(status="ready")

        assert captured[0].url.path == "/api/v1/graphs"
        assert captured[0].url.params["status"] == "ready"


# ── Raw Dict Passthrough ─────────────────────────────────────────────────────


class TestRemoteClientRawDictPassthrough:
    """Verify responses are returned as-is without object reconstruction."""

    async def test_given_server_json_when_tree_then_returns_raw_dict(self):
        payload = {"format": "text", "content": "📦 Root", "count": 5}

        def handler(_req: httpx.Request) -> httpx.Response:
            return _ok_json(payload)

        client = _client_with_transport(_make_transport(handler))
        result = await client.tree("g")

        assert isinstance(result, dict)
        assert result == payload

    async def test_given_server_json_when_search_then_returns_raw_dict(self):
        payload = {"meta": {"total": 1}, "results": [{"node_id": "x", "score": 0.9}]}

        def handler(_req: httpx.Request) -> httpx.Response:
            return _ok_json(payload)

        client = _client_with_transport(_make_transport(handler))
        result = await client.search("pattern", graph="g")

        assert result == payload


# ── Tree Format Param ─────────────────────────────────────────────────────────


class TestRemoteClientTreeFormat:
    """Verify format parameter is forwarded correctly."""

    async def test_given_format_text_when_tree_then_query_param_set(self):
        captured: list[httpx.Request] = []

        def handler(req: httpx.Request) -> httpx.Response:
            captured.append(req)
            return _ok_json({"format": "text", "content": "...", "count": 0})

        client = _client_with_transport(_make_transport(handler))
        await client.tree("g", format="text")

        assert captured[0].url.params["format"] == "text"

    async def test_given_format_json_when_tree_then_query_param_set(self):
        captured: list[httpx.Request] = []

        def handler(req: httpx.Request) -> httpx.Response:
            captured.append(req)
            return _ok_json({"format": "json", "tree": [], "count": 0})

        client = _client_with_transport(_make_transport(handler))
        await client.tree("g", format="json")

        assert captured[0].url.params["format"] == "json"


# ── Error Handling ────────────────────────────────────────────────────────────


class TestRemoteClientErrorHandling:
    """Verify HTTP errors are translated to actionable RemoteClientError."""

    async def test_given_connect_error_when_request_then_actionable_error(self):
        async def _raise_connect(_req: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        client = _client_with_transport(httpx.MockTransport(_raise_connect), name="work")

        with pytest.raises(RemoteClientError, match="unreachable"):
            await client.tree("g")

    async def test_given_404_when_request_then_actionable_not_found(self):
        def handler(_req: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"detail": "Graph 'x' not found"})

        client = _client_with_transport(_make_transport(handler), name="work")

        with pytest.raises(RemoteClientError, match="Not found"):
            await client.tree("x")

    async def test_given_401_when_request_then_actionable_auth_error(self):
        def handler(_req: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"detail": "Invalid token"})

        client = _client_with_transport(_make_transport(handler), name="work")

        with pytest.raises(RemoteClientError, match="Authentication failed"):
            await client.tree("g")

    async def test_given_timeout_when_request_then_actionable_timeout(self):
        async def _raise_timeout(_req: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out")

        client = _client_with_transport(
            httpx.MockTransport(_raise_timeout), name="slow-server"
        )

        with pytest.raises(RemoteClientError, match="timed out"):
            await client.search("q")

    async def test_given_error_then_remote_name_and_url_on_exception(self):
        def handler(_req: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={})

        client = _client_with_transport(_make_transport(handler), name="work")

        with pytest.raises(RemoteClientError) as exc_info:
            await client.tree("g")

        assert exc_info.value.remote_name == "work"
        assert exc_info.value.url == "http://test-server"


# ── get_node 404 Distinction ─────────────────────────────────────────────────


class TestGetNodeNotFoundDistinction:
    """Verify get_node distinguishes node-not-found from graph-not-found."""

    async def test_given_node_not_found_when_get_node_then_returns_none(self):
        def handler(_req: httpx.Request) -> httpx.Response:
            return httpx.Response(
                404, json={"detail": "Node 'class:a.py:X' not found in graph 'g'"}
            )

        client = _client_with_transport(_make_transport(handler))
        result = await client.get_node("g", "class:a.py:X")

        assert result is None

    async def test_given_graph_not_found_when_get_node_then_raises(self):
        def handler(_req: httpx.Request) -> httpx.Response:
            return httpx.Response(
                404, json={"detail": "Graph 'unknown' not found"}
            )

        client = _client_with_transport(_make_transport(handler))

        with pytest.raises(RemoteClientError, match="Not found"):
            await client.get_node("unknown", "class:a.py:X")


# ── MultiRemoteClient ────────────────────────────────────────────────────────


class TestMultiRemoteClientSearch:
    """Verify MultiRemoteClient merges results from multiple remotes."""

    async def test_given_two_remotes_when_search_then_merged_sorted_by_score(self):
        def handler_a(_req: httpx.Request) -> httpx.Response:
            return _ok_json({
                "meta": {"total": 1},
                "results": [{"node_id": "a", "score": 0.5}],
            })

        def handler_b(_req: httpx.Request) -> httpx.Response:
            return _ok_json({
                "meta": {"total": 1},
                "results": [{"node_id": "b", "score": 0.9}],
            })

        client_a = _client_with_transport(_make_transport(handler_a), name="alpha")
        client_b = _client_with_transport(_make_transport(handler_b), name="beta")
        multi = MultiRemoteClient([client_a, client_b])

        result = await multi.search("auth")

        assert result["results"][0]["node_id"] == "b"  # higher score first
        assert result["results"][1]["node_id"] == "a"
        assert result["meta"]["total"] == 2
        assert set(result["meta"]["remotes"]) == {"alpha", "beta"}

    async def test_given_two_remotes_when_search_then_results_tagged_with_remote(self):
        def handler(_req: httpx.Request) -> httpx.Response:
            return _ok_json({
                "meta": {"total": 1},
                "results": [{"node_id": "x", "score": 0.7}],
            })

        client_a = _client_with_transport(_make_transport(handler), name="r1")
        client_b = _client_with_transport(_make_transport(handler), name="r2")
        multi = MultiRemoteClient([client_a, client_b])

        result = await multi.search("q")

        remote_tags = {r["_remote"] for r in result["results"]}
        assert remote_tags == {"r1", "r2"}


class TestMultiRemoteClientPartialFailure:
    """Verify partial failure returns results with warning (not abort)."""

    async def test_given_one_fails_when_search_then_other_results_returned(self, capsys):
        def handler_ok(_req: httpx.Request) -> httpx.Response:
            return _ok_json({
                "meta": {"total": 1},
                "results": [{"node_id": "ok-node", "score": 0.8}],
            })

        async def handler_fail(_req: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        client_ok = _client_with_transport(_make_transport(handler_ok), name="good")
        client_fail = _client_with_transport(
            httpx.MockTransport(handler_fail), name="bad"
        )
        multi = MultiRemoteClient([client_ok, client_fail])

        result = await multi.search("q")

        assert len(result["results"]) == 1
        assert result["results"][0]["node_id"] == "ok-node"

        captured = capsys.readouterr()
        assert "bad" in captured.err
        assert "failed" in captured.err.lower() or "Warning" in captured.err
