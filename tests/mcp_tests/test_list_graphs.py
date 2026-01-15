"""Tests for list_graphs MCP tool.

Per Phase 3 T002: Tests for the new list_graphs MCP tool that returns
information about available graphs including availability status.

Testing via MCP protocol validates JSON serialization, schema generation,
and protocol framing - not just Python function behavior.
"""

from __future__ import annotations

import json

import pytest


class TestListGraphs:
    """Tests for list_graphs MCP tool."""

    @pytest.mark.asyncio
    async def test_list_graphs_returns_default_and_configured(
        self, mcp_client_multi_graph
    ):
        """list_graphs returns both default and configured graphs.

        Per Phase 3 AC6: list_graphs() shows all available graphs.
        """
        result = await mcp_client_multi_graph.call_tool("list_graphs", {})
        data = json.loads(result.content[0].text)

        # Should have docs list and count
        assert "docs" in data
        assert "count" in data
        assert data["count"] == 2

        # Should include both default and external-lib
        names = [doc["name"] for doc in data["docs"]]
        assert "default" in names
        assert "external-lib" in names

    @pytest.mark.asyncio
    async def test_list_graphs_includes_availability_status(
        self, mcp_client_multi_graph
    ):
        """list_graphs includes availability status for each graph.

        Per Critical Finding 08: GraphInfo includes available field.
        """
        result = await mcp_client_multi_graph.call_tool("list_graphs", {})
        data = json.loads(result.content[0].text)

        # All graphs should have available field
        for doc in data["docs"]:
            assert "available" in doc
            assert isinstance(doc["available"], bool)

    @pytest.mark.asyncio
    async def test_list_graphs_includes_description(self, mcp_client_multi_graph):
        """list_graphs includes description when provided.

        Per Phase 3 AC6: GraphInfo contains description.
        """
        result = await mcp_client_multi_graph.call_tool("list_graphs", {})
        data = json.loads(result.content[0].text)

        # Find external-lib which has description in fixture
        external = next((d for d in data["docs"] if d["name"] == "external-lib"), None)
        assert external is not None
        assert external["description"] == "External library"

    @pytest.mark.asyncio
    async def test_list_graphs_includes_source_url(self, mcp_client_multi_graph):
        """list_graphs includes source_url when provided.

        Per Phase 3 AC6: GraphInfo contains source_url.
        """
        result = await mcp_client_multi_graph.call_tool("list_graphs", {})
        data = json.loads(result.content[0].text)

        # Find external-lib which has source_url in fixture
        external = next((d for d in data["docs"] if d["name"] == "external-lib"), None)
        assert external is not None
        assert external["source_url"] == "https://github.com/example/lib"

    @pytest.mark.asyncio
    async def test_list_graphs_includes_path(self, mcp_client_multi_graph):
        """list_graphs includes resolved path for each graph.

        Per Phase 3 AC6: GraphInfo contains resolved path.
        """
        result = await mcp_client_multi_graph.call_tool("list_graphs", {})
        data = json.loads(result.content[0].text)

        # All graphs should have path field
        for doc in data["docs"]:
            assert "path" in doc
            assert isinstance(doc["path"], str)
            assert len(doc["path"]) > 0

    @pytest.mark.asyncio
    async def test_list_graphs_count_matches_docs_length(self, mcp_client_multi_graph):
        """list_graphs count field matches docs array length.

        Per Phase 3 T002 validation: count field is accurate.
        """
        result = await mcp_client_multi_graph.call_tool("list_graphs", {})
        data = json.loads(result.content[0].text)

        assert data["count"] == len(data["docs"])
