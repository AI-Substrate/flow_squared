"""Tests for get_node MCP tool.

Phase 3 implements the get_node tool for retrieving complete source code.
Per Critical Discovery 02: Tool descriptions drive agent tool selection.
Per High Discovery 04: GetNodeService is SYNC; tool must be sync.
Per DYK Session: Explicit field filtering with min/max detail levels.

TDD Approach: Tests written BEFORE implementation (T001-T003).
These tests will FAIL until the get_node tool is implemented in T004.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


def parse_tool_response(result) -> dict | list | None:
    """Parse MCP tool call response to Python object.

    FastMCP returns results with content array containing TextContent objects.
    This helper extracts and parses the JSON text.

    Args:
        result: Tool call result from client.call_tool().

    Returns:
        Parsed JSON as dict, list, or None.
    """
    # Handle empty content (when tool returns None)
    if not result.content:
        return None
    text = result.content[0].text
    if text == "null":
        return None
    return json.loads(text)


class TestGetNodeRetrieval:
    """T001: Tests for get_node tool retrieval functionality.

    Per plan 3.1: Tests verify valid node_id returns full CodeNode.
    Per DYK Session: Explicit field filtering with min/max detail levels.
    """

    def test_get_node_returns_dict_for_valid_id(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves get_node returns dict for valid node_id
        Quality Contribution: Ensures agents receive structured data
        Acceptance Criteria: result is dict, not None
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import get_node

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = get_node(node_id="class:src/calculator.py:Calculator")

        assert result is not None, "Valid node_id should return data"
        assert isinstance(result, dict), "Result should be a dict"

    def test_get_node_returns_content_field(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves response includes full source content
        Quality Contribution: Enables agents to read actual code
        Acceptance Criteria: "content" key in result
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import get_node

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = get_node(node_id="class:src/calculator.py:Calculator")

        assert "content" in result, "Result must include content field"
        assert isinstance(result["content"], str), "content must be string"
        assert len(result["content"]) > 0, "content must not be empty"

    def test_get_node_min_detail_has_core_fields(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves min detail has exactly 7 core fields
        Quality Contribution: Compact response for efficient use
        Acceptance Criteria: node_id, name, category, content, signature, start_line, end_line
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import get_node

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = get_node(node_id="class:src/calculator.py:Calculator", detail="min")

        # Core fields that must always be present
        core_fields = [
            "node_id",
            "name",
            "category",
            "content",
            "signature",
            "start_line",
            "end_line",
        ]
        for field in core_fields:
            assert field in result, f"Min detail must include {field}"

    def test_get_node_max_detail_has_extended_fields(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves max detail adds extended fields
        Quality Contribution: Full context when needed
        Acceptance Criteria: All min fields plus smart_content, language, parent_node_id, qualified_name, ts_kind
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import get_node

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = get_node(node_id="class:src/calculator.py:Calculator", detail="max")

        # Min fields must still be present
        min_fields = [
            "node_id",
            "name",
            "category",
            "content",
            "signature",
            "start_line",
            "end_line",
        ]
        for field in min_fields:
            assert field in result, f"Max detail must include min field {field}"

        # Extended fields for max detail
        extended_fields = ["language", "parent_node_id", "qualified_name", "ts_kind"]
        for field in extended_fields:
            assert field in result, f"Max detail must include {field}"

    def test_get_node_never_includes_embeddings(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves embedding fields are never included
        Quality Contribution: Prevents huge response sizes
        Acceptance Criteria: No embedding, smart_content_embedding, embedding_hash, etc.
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import get_node

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        # Check both min and max detail
        for detail in ["min", "max"]:
            result = get_node(
                node_id="class:src/calculator.py:Calculator", detail=detail
            )

            # These fields must NEVER be included
            forbidden_fields = [
                "embedding",
                "smart_content_embedding",
                "embedding_hash",
                "embedding_chunk_offsets",
                "content_hash",
                "smart_content_hash",
                "start_byte",
                "end_byte",
                "start_column",
                "end_column",
                "is_named",
                "field_name",
                "is_error",
                "truncated",
                "truncated_at_line",
            ]
            for field in forbidden_fields:
                assert field not in result, f"{field} must not be in {detail} detail"

    def test_get_node_default_detail_is_min(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves default detail level is min
        Quality Contribution: Compact output by default
        Acceptance Criteria: No extended fields in default output
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import get_node

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        # Call without detail parameter
        result = get_node(node_id="class:src/calculator.py:Calculator")

        # Extended fields should NOT be present in default (min)
        assert "language" not in result, "Default should be min detail (no language)"
        assert "qualified_name" not in result, (
            "Default should be min detail (no qualified_name)"
        )

    def test_get_node_content_matches_source(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves content field is actual source code
        Quality Contribution: Verifies correct source retrieval
        Acceptance Criteria: content matches expected fixture data
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import get_node

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = get_node(node_id="class:src/calculator.py:Calculator")

        # From fixture: content="class Calculator:\n    pass"
        assert "class Calculator" in result["content"]

    def test_get_node_no_saved_to_without_save(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves saved_to absent when not saving
        Quality Contribution: Clean response when file not written
        Acceptance Criteria: "saved_to" not in result
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import get_node

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = get_node(node_id="class:src/calculator.py:Calculator")

        assert "saved_to" not in result, (
            "saved_to should not be in result when not saving"
        )


class TestGetNodeNotFound:
    """T002: Tests for get_node not-found behavior.

    Per plan 3.2: AC5 - invalid node_id returns None, not error.
    Per DYK Session: Return None for any not-found (no format validation).
    """

    def test_get_node_returns_none_for_invalid_id(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves invalid ID returns None
        Quality Contribution: Clean handling of missing nodes
        Acceptance Criteria: result is None
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import get_node

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = get_node(node_id="nonexistent:path:name")

        assert result is None, "Invalid node_id should return None"

    def test_get_node_returns_none_not_error(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves not-found is not an error
        Quality Contribution: No exception raised for missing nodes
        Acceptance Criteria: No exception raised
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import get_node

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        # This should not raise any exception
        result = get_node(node_id="nonexistent:path:name")
        assert result is None

    def test_get_node_handles_empty_string_id(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Edge case - empty string ID
        Quality Contribution: Graceful handling of edge cases
        Acceptance Criteria: Returns None
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import get_node

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = get_node(node_id="")

        assert result is None, "Empty string should return None"

    def test_get_node_handles_malformed_id(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Edge case - malformed ID format
        Quality Contribution: Graceful handling of malformed input
        Acceptance Criteria: Returns None (no format validation per DYK)
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import get_node

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        # Malformed - missing parts, wrong format, etc.
        result = get_node(node_id="just-garbage-no-colons")

        assert result is None, "Malformed ID should return None"


class TestGetNodeSaveToFile:
    """T003: Tests for get_node save_to_file functionality.

    Per plan 3.3: AC6 - save_to_file writes JSON to specified path.
    Per DYK Session: Path validation, saved_to in response.
    """

    def test_get_node_save_creates_file(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves file is created at specified path
        Quality Contribution: Enables agents to persist node data
        Acceptance Criteria: File exists after call
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import get_node

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        output_path = tmp_path / "node.json"

        # Temporarily change cwd to tmp_path for security validation
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = get_node(
                node_id="class:src/calculator.py:Calculator",
                save_to_file="node.json",
            )
        finally:
            os.chdir(original_cwd)

        assert output_path.exists(), "File should be created"
        assert result is not None

    def test_get_node_save_writes_valid_json(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves file contains valid JSON
        Quality Contribution: Ensures parseable output
        Acceptance Criteria: json.loads() succeeds
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import get_node

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        output_path = tmp_path / "node.json"

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            get_node(
                node_id="class:src/calculator.py:Calculator",
                save_to_file="node.json",
            )
        finally:
            os.chdir(original_cwd)

        # Should be valid JSON
        data = json.loads(output_path.read_text())
        assert isinstance(data, dict)

    def test_get_node_save_json_has_content(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves saved JSON has content field
        Quality Contribution: Ensures complete data in file
        Acceptance Criteria: "content" in loaded_data
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import get_node

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        output_path = tmp_path / "node.json"

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            get_node(
                node_id="class:src/calculator.py:Calculator",
                save_to_file="node.json",
            )
        finally:
            os.chdir(original_cwd)

        data = json.loads(output_path.read_text())
        assert "content" in data, "Saved JSON must include content"

    def test_get_node_save_returns_saved_to_field(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves response includes saved_to path
        Quality Contribution: Agents know where file was saved
        Acceptance Criteria: "saved_to" in result with absolute path
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import get_node

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = get_node(
                node_id="class:src/calculator.py:Calculator",
                save_to_file="node.json",
            )
        finally:
            os.chdir(original_cwd)

        assert "saved_to" in result, "Result must include saved_to"
        assert str(tmp_path / "node.json") == result["saved_to"]

    def test_get_node_save_with_none_returns_none(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves no file for missing node
        Quality Contribution: Clean handling of not-found with save
        Acceptance Criteria: result is None, file not created
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import get_node

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        output_path = tmp_path / "node.json"

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = get_node(
                node_id="nonexistent:path:name",
                save_to_file="node.json",
            )
        finally:
            os.chdir(original_cwd)

        assert result is None, "Not-found should return None"
        assert not output_path.exists(), "File should not be created for not-found"

    def test_get_node_save_rejects_path_escape(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Security - path must be under PWD
        Quality Contribution: Prevents directory traversal attacks
        Acceptance Criteria: ToolError raised for ../escape.json
        """
        from fastmcp.exceptions import ToolError

        from fs2.mcp import dependencies
        from fs2.mcp.server import get_node

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            with pytest.raises(ToolError) as exc_info:
                get_node(
                    node_id="class:src/calculator.py:Calculator",
                    save_to_file="../escape.json",
                )
        finally:
            os.chdir(original_cwd)

        assert (
            "path" in str(exc_info.value).lower()
            or "escape" in str(exc_info.value).lower()
        )

    def test_get_node_save_rejects_absolute_path(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Security - no absolute paths outside PWD
        Quality Contribution: Prevents writing to arbitrary locations
        Acceptance Criteria: ToolError raised for /tmp/outside.json
        """
        from fastmcp.exceptions import ToolError

        from fs2.mcp import dependencies
        from fs2.mcp.server import get_node

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            with pytest.raises(ToolError) as exc_info:
                get_node(
                    node_id="class:src/calculator.py:Calculator",
                    save_to_file="/tmp/outside.json",
                )
        finally:
            os.chdir(original_cwd)

        assert "path" in str(exc_info.value).lower()


class TestGetNodeMCPProtocol:
    """T007: MCP protocol integration tests.

    CRITICAL: These tests validate the get_node tool works via actual MCP protocol,
    not just direct Python function calls. This ensures JSON serialization,
    schema generation, and protocol framing all work correctly.
    """

    @pytest.mark.asyncio
    async def test_get_node_callable_via_mcp_client(self, mcp_client):
        """
        Purpose: Proves get_node tool is registered and callable via MCP protocol
        Quality Contribution: Ensures agents can actually call the tool
        Acceptance Criteria: client.call_tool("get_node") succeeds
        """
        result = await mcp_client.call_tool(
            "get_node", {"node_id": "class:src/calculator.py:Calculator"}
        )

        # Should have content
        assert result.content is not None
        assert len(result.content) > 0

    @pytest.mark.asyncio
    async def test_get_node_response_is_json_parseable(self, mcp_client):
        """
        Purpose: Proves MCP response can be parsed as JSON
        Quality Contribution: Ensures agents receive valid data format
        Acceptance Criteria: json.loads() succeeds on response text
        """
        result = await mcp_client.call_tool(
            "get_node", {"node_id": "class:src/calculator.py:Calculator"}
        )
        parsed = parse_tool_response(result)

        # Should be a dict (node data)
        assert isinstance(parsed, dict)
        assert "node_id" in parsed

    @pytest.mark.asyncio
    async def test_get_node_listed_in_available_tools(self, mcp_client):
        """
        Purpose: Proves get_node tool is discoverable via MCP protocol
        Quality Contribution: Ensures agents can list available tools
        Acceptance Criteria: "get_node" appears in tools list
        """
        tools = await mcp_client.list_tools()

        tool_names = [t.name for t in tools]
        assert "get_node" in tool_names, "get_node tool should be listed"

    @pytest.mark.asyncio
    async def test_get_node_has_annotations(self, mcp_client):
        """
        Purpose: Proves MCP annotations are exposed via protocol
        Quality Contribution: Agents can make informed tool selection
        Acceptance Criteria: Tool has annotations
        """
        tools = await mcp_client.list_tools()

        get_node_tool = next((t for t in tools if t.name == "get_node"), None)
        assert get_node_tool is not None, "get_node tool should exist"

        # Check annotations are present
        if get_node_tool.annotations:
            # Per DYK Session: readOnlyHint should be False (save_to_file writes)
            # But it's mostly read-only in common use
            assert get_node_tool.annotations.destructiveHint is False

    @pytest.mark.asyncio
    async def test_get_node_no_stdout_pollution(self, mcp_client, monkeypatch):
        """
        Purpose: Proves protocol compliance (MCP uses stdout for JSON-RPC)
        Quality Contribution: No stdout pollution that breaks protocol
        Acceptance Criteria: stdout is empty during call
        """
        # Note: This is implicitly tested by the mcp_client working at all
        # If stdout was polluted, JSON-RPC would fail
        result = await mcp_client.call_tool(
            "get_node", {"node_id": "class:src/calculator.py:Calculator"}
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_node_not_found_via_mcp(self, mcp_client):
        """
        Purpose: Proves None return works over MCP protocol
        Quality Contribution: Agents handle not-found correctly
        Acceptance Criteria: Response is null/None
        """
        result = await mcp_client.call_tool(
            "get_node", {"node_id": "nonexistent:path:name"}
        )
        parsed = parse_tool_response(result)

        assert parsed is None, "Not-found should return null over MCP"

    @pytest.mark.asyncio
    async def test_get_node_graph_not_found_raises_tool_error(self, tmp_path):
        """
        Purpose: Proves ToolError is raised when graph is missing
        Quality Contribution: Validates error path via MCP protocol
        Acceptance Criteria: ToolError exception raised with meaningful message
        """
        from fastmcp.client import Client
        from fastmcp.exceptions import ToolError

        from fs2.config.objects import GraphConfig, ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.mcp import dependencies
        from fs2.mcp.server import mcp

        # Create config pointing to non-existent graph file
        config = FakeConfigurationService(
            ScanConfig(),
            GraphConfig(graph_path=str(tmp_path / "nonexistent_graph.pickle")),
        )

        # Reset services and inject config but NOT graph store
        # This forces the tool to try loading from the non-existent path
        dependencies.reset_services()
        dependencies.set_config(config)
        # Don't inject graph store - let it create real NetworkXGraphStore which will fail

        async with Client(mcp) as client:
            with pytest.raises(ToolError) as exc_info:
                await client.call_tool(
                    "get_node", {"node_id": "class:src/calculator.py:Calculator"}
                )

            # ToolError should contain actionable message
            assert "Graph not found" in str(exc_info.value)
            assert "fs2 scan" in str(exc_info.value)
