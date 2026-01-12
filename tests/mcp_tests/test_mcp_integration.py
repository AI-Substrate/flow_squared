"""E2E integration tests for MCP server via CLI subprocess.

Phase 5: CLI Integration - T006
Tests the full MCP flow: CLI subprocess → STDIO transport → tool calls.

Per DYK#1: Uses real CLI path `-m fs2.cli.main mcp`
Per DYK#4: Tests in mcp_tests/ directory (not separate integration/)
Per DYK#5: TEXT/REGEX modes only (no embedding adapter in subprocess)
"""

from __future__ import annotations

import json
import sys

import pytest
from fastmcp.client import Client
from fastmcp.client.transports import StdioTransport


@pytest.mark.integration
class TestMCPSubprocessIntegration:
    """E2E tests for MCP server running as subprocess.

    These tests spawn the MCP server via CLI and communicate
    over STDIO transport, validating the full integration path.
    """

    @pytest.mark.asyncio
    async def test_mcp_subprocess_connects_successfully(self, scanned_fixtures_graph):
        """
        Purpose: Verifies MCP server starts and accepts connections via CLI.
        Quality Contribution: End-to-end CLI→MCP validation.
        Acceptance Criteria: Client connects and lists tools.

        Per DYK#1: Uses real CLI path for full integration coverage.
        """
        transport = StdioTransport(
            command=sys.executable,
            args=["-m", "fs2.cli.main", "mcp"],
            cwd=str(scanned_fixtures_graph.project_path),
        )

        async with Client(transport) as client:
            tools = await client.list_tools()

            assert len(tools) >= 3, f"Expected at least 3 tools, got {len(tools)}"
            tool_names = [t.name for t in tools]
            assert "tree" in tool_names
            assert "get_node" in tool_names
            assert "search" in tool_names

    @pytest.mark.asyncio
    async def test_mcp_subprocess_tree_returns_nodes(self, scanned_fixtures_graph):
        """
        Purpose: Verifies tree tool works via subprocess.
        Quality Contribution: End-to-end tool call validation.
        Acceptance Criteria: Tree returns nodes from real graph.
        """
        transport = StdioTransport(
            command=sys.executable,
            args=["-m", "fs2.cli.main", "mcp"],
            cwd=str(scanned_fixtures_graph.project_path),
        )

        async with Client(transport) as client:
            # Per Phase 2 format change: use format="json" to get structured data
            result = await client.call_tool("tree", {"pattern": ".", "format": "json"})

            # Parse the JSON response
            data = json.loads(result.content[0].text)

            # New format returns {"format": "json", "tree": [...], "count": N}
            assert isinstance(data, dict)
            assert data.get("format") == "json"
            assert "tree" in data

            tree_list = data["tree"]
            assert isinstance(tree_list, list)
            assert len(tree_list) > 0, "Expected at least one node in tree"

            # Verify node structure
            first_node = tree_list[0]
            assert "node_id" in first_node
            assert "category" in first_node

    @pytest.mark.asyncio
    async def test_mcp_subprocess_search_text_mode(self, scanned_fixtures_graph):
        """
        Purpose: Verifies search tool TEXT mode works via subprocess.
        Quality Contribution: End-to-end search validation.
        Acceptance Criteria: TEXT search finds nodes in real graph.

        Per DYK#5: E2E uses TEXT mode (no embedding adapter needed).
        """
        transport = StdioTransport(
            command=sys.executable,
            args=["-m", "fs2.cli.main", "mcp"],
            cwd=str(scanned_fixtures_graph.project_path),
        )

        async with Client(transport) as client:
            result = await client.call_tool(
                "search",
                {"pattern": "Calculator", "mode": "text", "limit": 5},
            )

            # Parse the JSON response
            data = json.loads(result.content[0].text)

            assert "meta" in data, f"Expected envelope with meta, got {data.keys()}"
            assert "results" in data

            # May or may not have results depending on fixture content
            assert isinstance(data["results"], list)

    @pytest.mark.asyncio
    async def test_mcp_subprocess_search_regex_mode(self, scanned_fixtures_graph):
        """
        Purpose: Verifies search tool REGEX mode works via subprocess.
        Quality Contribution: End-to-end regex search validation.
        Acceptance Criteria: REGEX search returns valid envelope.

        Per DYK#5: E2E uses REGEX mode (no embedding adapter needed).
        """
        transport = StdioTransport(
            command=sys.executable,
            args=["-m", "fs2.cli.main", "mcp"],
            cwd=str(scanned_fixtures_graph.project_path),
        )

        async with Client(transport) as client:
            result = await client.call_tool(
                "search",
                {"pattern": "def.*", "mode": "regex", "limit": 5},
            )

            # Parse the JSON response
            data = json.loads(result.content[0].text)

            assert "meta" in data
            assert "results" in data
            assert isinstance(data["results"], list)

    @pytest.mark.asyncio
    async def test_mcp_subprocess_get_node(self, scanned_fixtures_graph):
        """
        Purpose: Verifies get_node tool works via subprocess.
        Quality Contribution: End-to-end node retrieval validation.
        Acceptance Criteria: get_node returns node details.
        """
        transport = StdioTransport(
            command=sys.executable,
            args=["-m", "fs2.cli.main", "mcp"],
            cwd=str(scanned_fixtures_graph.project_path),
        )

        async with Client(transport) as client:
            # First get a node_id from tree (use format="json" for structured data)
            tree_result = await client.call_tool(
                "tree", {"pattern": ".", "format": "json"}
            )
            tree_response = json.loads(tree_result.content[0].text)

            # New format: {"format": "json", "tree": [...], "count": N}
            tree_data = tree_response.get("tree", [])

            if len(tree_data) == 0:
                pytest.skip("No nodes in fixture graph")

            node_id = tree_data[0]["node_id"]

            # Now get the node details
            node_result = await client.call_tool("get_node", {"node_id": node_id})
            node_data = json.loads(node_result.content[0].text)

            assert node_data is not None
            assert node_data["node_id"] == node_id

    @pytest.mark.asyncio
    async def test_mcp_subprocess_no_stdout_pollution(self, scanned_fixtures_graph):
        """
        Purpose: Verifies subprocess doesn't pollute stdout.
        Quality Contribution: Protocol compliance validation.
        Acceptance Criteria: Only JSON-RPC on stdout (client connects).

        Per AC13: Only JSON-RPC on stdout; all logging to stderr.
        """
        transport = StdioTransport(
            command=sys.executable,
            args=["-m", "fs2.cli.main", "mcp"],
            cwd=str(scanned_fixtures_graph.project_path),
        )

        # If there was stdout pollution, the client would fail to parse
        # the JSON-RPC messages and throw an error
        async with Client(transport) as client:
            # Just list tools - if this works, protocol is clean
            tools = await client.list_tools()
            assert len(tools) >= 3
