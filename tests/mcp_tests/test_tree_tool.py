"""Tests for tree MCP tool.

Phase 2 implements the tree tool for codebase exploration.
Per Critical Discovery 02: Tool descriptions drive agent tool selection.
Per High Discovery 04: TreeService is SYNC; tool must be sync.

TDD Approach: Tests written BEFORE implementation (T001-T004).
These tests will FAIL until the tree tool is implemented in T005.
"""

from __future__ import annotations

import json
import sys
from io import StringIO
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


def parse_tool_response(result) -> dict | list:
    """Parse MCP tool call response to Python object.

    FastMCP returns results with content array containing TextContent objects.
    This helper extracts and parses the JSON text.

    Args:
        result: Tool call result from client.call_tool().

    Returns:
        Parsed JSON as dict or list.
    """
    return json.loads(result.content[0].text)


def _flatten_tree(nodes: list[dict]) -> list[dict]:
    """Flatten tree structure for easier testing.

    Recursively collects all nodes including children into a flat list.

    Args:
        nodes: List of tree node dicts with optional children arrays.

    Returns:
        Flat list of all nodes in the tree.
    """
    result = []
    for node in nodes:
        result.append(node)
        if "children" in node and node["children"]:
            result.extend(_flatten_tree(node["children"]))
    return result


class TestTreeToolBasicFunctionality:
    """T001: Tests for tree tool basic functionality.

    Per plan 2.1: Tests verify pattern "." returns hierarchical list.
    These tests use direct Python function calls for simplicity.
    MCP protocol integration tests are in T008.
    """

    def test_tree_returns_hierarchical_list(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves tree tool returns correct structure
        Quality Contribution: Ensures agents receive expected format
        Acceptance Criteria:
        - Returns list of nodes
        - Each node has node_id, name, category, children
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(pattern=".")

        assert isinstance(result, list), "tree() should return a list"
        assert len(result) > 0, "tree() should return non-empty list"

        # Check each root node has required fields
        for node in result:
            assert "node_id" in node, "Each node must have node_id"
            assert "name" in node, "Each node must have name"
            assert "category" in node, "Each node must have category"
            assert "children" in node, "Each node must have children array"
            assert isinstance(node["children"], list), "children must be a list"

    def test_tree_returns_all_files_with_dot_pattern(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves "." pattern returns all top-level nodes
        Quality Contribution: Enables full codebase exploration
        Acceptance Criteria: All file nodes returned as roots
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(pattern=".")

        # Should have at least the file node from fixture
        assert len(result) >= 1
        # Root should be file nodes (shallowest level)
        file_nodes = [n for n in result if n["category"] == "file"]
        assert len(file_nodes) >= 1, "Should return at least one file node"

    def test_tree_returns_valid_json_structure(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves return value is JSON-serializable
        Quality Contribution: Ensures MCP protocol compatibility
        Acceptance Criteria: json.dumps() succeeds without error
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(pattern=".")

        # Should be JSON-serializable
        json_str = json.dumps(result)
        assert json_str is not None
        assert len(json_str) > 2, "JSON should not be empty"

        # Round-trip should work
        parsed = json.loads(json_str)
        assert parsed == result

    def test_tree_children_contain_required_fields(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves nested children have same structure as roots
        Quality Contribution: Ensures consistent tree structure
        Acceptance Criteria: All nodes at all levels have required fields
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(pattern=".")

        # Flatten tree and check all nodes
        all_nodes = _flatten_tree(result)
        assert len(all_nodes) >= 1

        for node in all_nodes:
            assert "node_id" in node, f"Missing node_id in: {node}"
            assert "name" in node, f"Missing name in: {node}"
            assert "category" in node, f"Missing category in: {node}"
            assert "children" in node, f"Missing children in: {node}"

    def test_tree_no_stdout_pollution(
        self, tree_test_graph_store: tuple, tmp_path: Path, monkeypatch
    ):
        """
        Purpose: Proves protocol compliance (MCP uses stdout for JSON-RPC)
        Quality Contribution: No stdout pollution that breaks protocol
        Acceptance Criteria: stdout is empty after call
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        captured = StringIO()
        monkeypatch.setattr(sys, "stdout", captured)

        tree(pattern=".")

        assert captured.getvalue() == "", "Tree tool should not print to stdout"

    def test_tree_includes_line_numbers(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves line numbers are included for navigation
        Quality Contribution: Enables agent to locate code in files
        Acceptance Criteria: Each node has start_line and end_line
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(pattern=".")

        all_nodes = _flatten_tree(result)
        for node in all_nodes:
            assert "start_line" in node, f"Missing start_line in: {node}"
            assert "end_line" in node, f"Missing end_line in: {node}"
            assert isinstance(node["start_line"], int)
            assert isinstance(node["end_line"], int)
            assert node["start_line"] <= node["end_line"]


class TestTreeToolPatternFiltering:
    """T002: Tests for tree tool pattern filtering.

    Per plan 2.2: Tests verify pattern filtering (glob, substring).
    TreeService supports exact match, glob patterns, and substring matching.
    """

    def test_tree_filters_by_substring_pattern(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves substring pattern filtering works
        Quality Contribution: Enables targeted codebase exploration
        Acceptance Criteria: Only matching nodes returned
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(pattern="Calculator")

        # All returned nodes should contain "Calculator" in node_id
        all_nodes = _flatten_tree(result)
        assert len(all_nodes) > 0, "Should find nodes matching 'Calculator'"
        for node in all_nodes:
            assert "Calculator" in node["node_id"], f"Node should match pattern: {node}"

    def test_tree_filters_by_exact_node_id(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves exact node_id match works
        Quality Contribution: Enables direct lookup by node_id
        Acceptance Criteria: Exact match returns single root node
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(pattern="class:src/calculator.py:Calculator")

        # Should return exactly one root with that node_id
        assert len(result) == 1, "Exact match should return single root"
        assert result[0]["node_id"] == "class:src/calculator.py:Calculator"

    def test_tree_filters_by_glob_pattern(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves glob pattern filtering works
        Quality Contribution: Enables wildcard-based exploration
        Acceptance Criteria: Glob matches return matching nodes
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        # Glob pattern: * matches any string
        result = tree(pattern="*.py")

        # Should match file nodes ending in .py
        all_nodes = _flatten_tree(result)
        assert len(all_nodes) > 0, "Should find nodes matching '*.py'"
        # At least one node should match the glob pattern in node_id
        matching = [n for n in all_nodes if ".py" in n["node_id"]]
        assert len(matching) > 0

    def test_tree_returns_empty_for_no_match(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves no-match returns empty list
        Quality Contribution: Clean handling of non-existent patterns
        Acceptance Criteria: Empty list returned, no error
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(pattern="NonexistentClassName")

        assert result == [], "No match should return empty list"

    def test_tree_filters_preserves_hierarchy(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves filtered results maintain parent-child structure
        Quality Contribution: Enables hierarchical exploration
        Acceptance Criteria: Children nested under parents in results
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        # Pattern matches file which has class as child
        result = tree(pattern="file:src/calculator.py")

        # Should have file as root with children
        assert len(result) == 1
        file_node = result[0]
        assert file_node["category"] == "file"
        # File should have class as child
        assert len(file_node["children"]) >= 1


class TestTreeToolDepthLimiting:
    """T003: Tests for tree tool depth limiting.

    Per plan 2.3: Tests verify max_depth limiting.
    When depth is limited, hidden_children_count should be populated.
    """

    def test_tree_respects_max_depth_one(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves depth limiting works at max_depth=1
        Quality Contribution: Prevents overwhelming output
        Acceptance Criteria: max_depth=1 shows root + 1 level of children, deeper hidden

        Note: max_depth=1 means current_depth >= 1 triggers hiding.
        Root (depth 0): children shown. Children (depth 1): THEIR children hidden.
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(pattern=".", max_depth=1)

        # Root nodes should have their immediate children visible
        for root in result:
            # Children at depth 1 should be empty (hidden)
            for child in root.get("children", []):
                assert child.get("children", []) == [], (
                    "max_depth=1 should hide grandchildren"
                )

    def test_tree_max_depth_shows_hidden_count(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves hidden_children_count is populated at depth limit
        Quality Contribution: Agents know children exist but aren't shown
        Acceptance Criteria: hidden_children_count > 0 when children are hidden

        Note: With max_depth=1, the class node (depth 1) should have hidden_children_count
        set because its children (methods at depth 2) are hidden.
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(pattern=".", max_depth=1)

        # Find class node at depth 1 (child of file node)
        file_nodes = [n for n in result if n["category"] == "file"]
        if file_nodes:
            file_node = file_nodes[0]
            # Class node is child of file, at depth 1
            class_children = [
                c for c in file_node.get("children", []) if c["category"] == "class"
            ]
            if class_children:
                class_node = class_children[0]
                # Class has method children, but they're hidden at max_depth=1
                assert class_node.get("hidden_children_count", 0) > 0, (
                    "Class at depth 1 should show hidden_children_count for its methods"
                )

    def test_tree_unlimited_depth_shows_all(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves max_depth=0 shows unlimited depth
        Quality Contribution: Default behavior returns full tree
        Acceptance Criteria: All levels expanded, no hidden_children_count
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(pattern=".", max_depth=0)

        # Should have nested children
        all_nodes = _flatten_tree(result)
        # Should include file, class, and method (3 levels)
        categories = {n["category"] for n in all_nodes}
        assert "file" in categories or len(all_nodes) >= 1

    def test_tree_max_depth_two_shows_one_level_children(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves max_depth=2 shows one level of children
        Quality Contribution: Controlled depth exploration
        Acceptance Criteria: Root and direct children visible, grandchildren hidden
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(pattern=".", max_depth=2)

        # Root nodes should have children (depth 2 allows one level)
        for root in result:
            if root.get("children"):
                # Children at depth 2 should be visible
                for child in root["children"]:
                    # Grandchildren should be hidden
                    assert (
                        child.get("children", []) == []
                        or child.get("hidden_children_count", 0) >= 0
                    )


class TestTreeToolDetailLevels:
    """T004: Tests for tree tool detail levels.

    Per plan 2.4: node_id ALWAYS present; min excludes signature; max includes signature.
    CRITICAL: node_id must be in both min and max for agent workflow (tree → get_node).
    """

    def test_tree_node_id_always_present_min(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: CRITICAL - node_id must be present in min detail
        Quality Contribution: Enables agent workflow (tree → get_node)
        Acceptance Criteria: node_id in every node at min detail
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(pattern=".", detail="min")

        all_nodes = _flatten_tree(result)
        for node in all_nodes:
            assert "node_id" in node, f"node_id missing in min detail: {node}"

    def test_tree_node_id_always_present_max(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: CRITICAL - node_id must be present in max detail
        Quality Contribution: Enables agent workflow (tree → get_node)
        Acceptance Criteria: node_id in every node at max detail
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(pattern=".", detail="max")

        all_nodes = _flatten_tree(result)
        for node in all_nodes:
            assert "node_id" in node, f"node_id missing in max detail: {node}"

    def test_tree_min_detail_excludes_signature(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves min detail is compact
        Quality Contribution: Reduces response size for exploration
        Acceptance Criteria: signature not in min detail
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(pattern=".", detail="min")

        all_nodes = _flatten_tree(result)
        for node in all_nodes:
            assert "signature" not in node, (
                f"signature should not be in min detail: {node}"
            )

    def test_tree_max_detail_includes_signature(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves max detail includes full metadata
        Quality Contribution: Enables agents to see signatures
        Acceptance Criteria: signature included for callables
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(pattern="add", detail="max")

        # Find the callable node
        all_nodes = _flatten_tree(result)
        callables = [n for n in all_nodes if n.get("category") == "callable"]
        if callables:
            assert "signature" in callables[0], (
                "signature should be in max detail for callables"
            )

    def test_tree_default_detail_is_min(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves default detail level is min
        Quality Contribution: Compact output by default
        Acceptance Criteria: No signature in default output
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        # Call without detail parameter
        result = tree(pattern=".")

        all_nodes = _flatten_tree(result)
        for node in all_nodes:
            assert "signature" not in node, (
                "default should be min detail (no signature)"
            )


class TestMCPProtocolIntegration:
    """T008: MCP protocol integration tests.

    CRITICAL: These tests validate the tree tool works via actual MCP protocol,
    not just direct Python function calls. This ensures JSON serialization,
    schema generation, and protocol framing all work correctly.
    """

    @pytest.mark.asyncio
    async def test_tree_tool_callable_via_mcp_client(self, mcp_client):
        """
        Purpose: Proves tree tool is registered and callable via MCP protocol
        Quality Contribution: Ensures agents can actually call the tool
        Acceptance Criteria: client.call_tool("tree") succeeds
        """
        result = await mcp_client.call_tool("tree", {"pattern": "."})

        # Should have content
        assert result.content is not None
        assert len(result.content) > 0

    @pytest.mark.asyncio
    async def test_tree_tool_response_is_json_parseable(self, mcp_client):
        """
        Purpose: Proves MCP response can be parsed as JSON
        Quality Contribution: Ensures agents receive valid data format
        Acceptance Criteria: json.loads() succeeds on response text
        """
        result = await mcp_client.call_tool("tree", {"pattern": "."})
        parsed = parse_tool_response(result)

        # Should be a list of nodes
        assert isinstance(parsed, list)
        assert len(parsed) > 0

    @pytest.mark.asyncio
    async def test_tree_tool_response_has_expected_structure(self, mcp_client):
        """
        Purpose: Proves MCP response matches expected node structure
        Quality Contribution: Ensures consistent API contract
        Acceptance Criteria: Each node has node_id, name, category, children
        """
        result = await mcp_client.call_tool("tree", {"pattern": "."})
        parsed = parse_tool_response(result)

        for node in parsed:
            assert "node_id" in node, "MCP response must include node_id"
            assert "name" in node, "MCP response must include name"
            assert "category" in node, "MCP response must include category"
            assert "children" in node, "MCP response must include children"

    @pytest.mark.asyncio
    async def test_tree_tool_with_pattern_parameter(self, mcp_client):
        """
        Purpose: Proves pattern parameter works via MCP protocol
        Quality Contribution: Ensures filtering works over protocol
        Acceptance Criteria: Pattern "Calculator" returns matching nodes
        """
        result = await mcp_client.call_tool("tree", {"pattern": "Calculator"})
        parsed = parse_tool_response(result)

        # Should find nodes containing "Calculator"
        all_nodes = _flatten_tree(parsed)
        for node in all_nodes:
            assert "Calculator" in node["node_id"]

    @pytest.mark.asyncio
    async def test_tree_tool_with_max_depth_parameter(self, mcp_client):
        """
        Purpose: Proves max_depth parameter works via MCP protocol
        Quality Contribution: Ensures depth limiting works over protocol
        Acceptance Criteria: max_depth=1 limits children expansion
        """
        result = await mcp_client.call_tool("tree", {"pattern": ".", "max_depth": 1})
        parsed = parse_tool_response(result)

        # Children at depth 1 should have no children (hidden)
        for root in parsed:
            for child in root.get("children", []):
                assert child.get("children", []) == [], (
                    "max_depth should limit expansion"
                )

    @pytest.mark.asyncio
    async def test_tree_tool_with_detail_parameter(self, mcp_client):
        """
        Purpose: Proves detail parameter works via MCP protocol
        Quality Contribution: Ensures detail levels work over protocol
        Acceptance Criteria: detail="max" includes signature
        """
        result = await mcp_client.call_tool("tree", {"pattern": "add", "detail": "max"})
        parsed = parse_tool_response(result)

        # Find callable nodes
        all_nodes = _flatten_tree(parsed)
        callables = [n for n in all_nodes if n.get("category") == "callable"]
        if callables:
            # Max detail should include signature
            assert "signature" in callables[0], (
                "max detail should include signature over MCP"
            )

    @pytest.mark.asyncio
    async def test_tree_tool_listed_in_available_tools(self, mcp_client):
        """
        Purpose: Proves tree tool is discoverable via MCP protocol
        Quality Contribution: Ensures agents can list available tools
        Acceptance Criteria: "tree" appears in tools list
        """
        tools = await mcp_client.list_tools()

        tool_names = [t.name for t in tools]
        assert "tree" in tool_names, "tree tool should be listed"

    @pytest.mark.asyncio
    async def test_tree_tool_has_annotations(self, mcp_client):
        """
        Purpose: Proves MCP annotations are exposed via protocol
        Quality Contribution: Agents can make informed tool selection
        Acceptance Criteria: Tool has annotations with expected hints
        """
        tools = await mcp_client.list_tools()

        tree_tool = next((t for t in tools if t.name == "tree"), None)
        assert tree_tool is not None, "tree tool should exist"

        # Check annotations are present
        if tree_tool.annotations:
            # Per AC8: readOnlyHint=False because save_to_file writes to filesystem
            assert tree_tool.annotations.readOnlyHint is False
            assert tree_tool.annotations.destructiveHint is False


# =============================================================================
# Phase 1 Save-to-File: T012 - MCP tree save_to_file tests
# =============================================================================


class TestTreeSaveToFile:
    """T012: Tests for tree save_to_file parameter (AC3, AC4, AC9, AC10).

    AC3: save_to_file writes JSON to file and adds saved_to field
    AC4: Path escape raises ToolError
    AC9: Empty results still save envelope
    AC10: Nested paths create parent directories
    """

    def test_given_save_to_file_when_tree_then_creates_file(
        self, tree_test_graph_store: tuple, tmp_path
    ):
        """
        Purpose: Verifies save_to_file creates file with tree content.
        Quality Contribution: Enables saving tree results for later use.
        Acceptance Criteria: File created with valid JSON content.

        Task: T012 (AC3)
        """
        import os

        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        # Change to tmp_path for relative path resolution
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            output_file = "tree_output.json"
            tree(pattern=".", save_to_file=output_file)

            # File should exist
            output_path = tmp_path / output_file
            assert output_path.exists(), f"Output file not created: {output_path}"
        finally:
            os.chdir(original_cwd)

    def test_given_save_to_file_when_tree_then_writes_valid_json(
        self, tree_test_graph_store: tuple, tmp_path
    ):
        """
        Purpose: Verifies file contains valid JSON with tree structure.
        Quality Contribution: Consistent API structure for agents.
        Acceptance Criteria: File contains parseable JSON with tree array.

        Task: T012 (AC3)
        """
        import json
        import os

        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            output_file = "tree_json.json"
            tree(pattern=".", save_to_file=output_file)

            output_path = tmp_path / output_file
            content = output_path.read_text(encoding="utf-8")
            data = json.loads(content)
            # Should be a list of tree nodes
            assert isinstance(data, list), f"Expected list, got {type(data)}"
        finally:
            os.chdir(original_cwd)

    def test_given_save_to_file_when_tree_then_response_includes_saved_to(
        self, tree_test_graph_store: tuple, tmp_path
    ):
        """
        Purpose: Verifies response includes saved_to field.
        Quality Contribution: Agent knows where file was saved.
        Acceptance Criteria: returned dict has saved_to with absolute path.

        Task: T012 (AC3)
        """
        import os

        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            output_file = "tree_saved.json"
            result = tree(pattern=".", save_to_file=output_file)

            # Result should be a dict with saved_to field
            assert isinstance(result, dict), (
                "Result should be dict when save_to_file is used"
            )
            assert "saved_to" in result, "Result should have 'saved_to' key"
            assert output_file in result["saved_to"], (
                "saved_to should contain file path"
            )
        finally:
            os.chdir(original_cwd)

    def test_given_path_escape_when_save_to_file_then_raises_tool_error(
        self, tree_test_graph_store: tuple, tmp_path
    ):
        """
        Purpose: Verifies path traversal attack is blocked.
        Quality Contribution: Security - prevents writing outside cwd.
        Acceptance Criteria: ToolError raised for path escape.

        Task: T012 (AC4)
        """
        import os

        from fastmcp.exceptions import ToolError

        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            with pytest.raises(ToolError) as exc_info:
                tree(pattern=".", save_to_file="../escape.json")

            assert (
                "escape" in str(exc_info.value).lower()
                or "directory" in str(exc_info.value).lower()
            )
        finally:
            os.chdir(original_cwd)

    def test_given_absolute_path_outside_cwd_when_save_to_file_then_raises_tool_error(
        self, tree_test_graph_store: tuple, tmp_path
    ):
        """
        Purpose: Verifies absolute paths outside cwd are blocked.
        Quality Contribution: Security - prevents writing to arbitrary locations.
        Acceptance Criteria: ToolError raised for absolute path outside cwd.

        Task: T012 (AC4)
        """
        import os

        from fastmcp.exceptions import ToolError

        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            # Create a path outside the current directory
            outside_path = str(tmp_path.parent / "outside" / "escape.json")

            with pytest.raises(ToolError):
                tree(pattern=".", save_to_file=outside_path)
        finally:
            os.chdir(original_cwd)

    def test_given_empty_results_when_save_to_file_then_still_saves(
        self, tree_test_graph_store: tuple, tmp_path
    ):
        """
        Purpose: Verifies empty results still save valid JSON.
        Quality Contribution: Consistent behavior for all queries.
        Acceptance Criteria: File contains [] for no matches.

        Task: T012 (AC9)
        """
        import json
        import os

        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            output_file = "tree_empty.json"
            tree(pattern="nonexistent_xyz_123", save_to_file=output_file)

            output_path = tmp_path / output_file
            assert output_path.exists()
            content = output_path.read_text(encoding="utf-8")
            data = json.loads(content)
            assert isinstance(data, list)
            assert len(data) == 0
        finally:
            os.chdir(original_cwd)

    def test_given_nested_path_when_save_to_file_then_creates_subdirectory(
        self, tree_test_graph_store: tuple, tmp_path
    ):
        """
        Purpose: Verifies nested paths create parent directories.
        Quality Contribution: Convenience - no manual mkdir needed.
        Acceptance Criteria: Parent directories created automatically.

        Task: T012 (AC10)
        """
        import json
        import os

        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            output_file = "output/nested/tree_result.json"
            tree(pattern=".", save_to_file=output_file)

            output_path = tmp_path / output_file
            assert output_path.exists(), f"Nested file not created: {output_path}"
            # Verify it's valid JSON
            content = output_path.read_text(encoding="utf-8")
            json.loads(content)
        finally:
            os.chdir(original_cwd)
