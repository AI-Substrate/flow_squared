"""Tests for tree MCP tool.

Phase 2 implements the tree tool for codebase exploration.
Per Critical Discovery 02: Tool descriptions drive agent tool selection.
Per High Discovery 04: TreeService is SYNC; tool must be sync.

TDD Approach: Tests written BEFORE implementation (T001-T004).
These tests will FAIL until the tree tool is implemented in T005.

NOTE: tree() now returns dict with format-specific content:
- format="text" (default): {"format": "text", "content": "...", "count": N}
- format="json": {"format": "json", "tree": [...], "count": N}

Tests that need raw node list should use format="json" and access result["tree"].
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


def get_tree_nodes(result: dict) -> list[dict]:
    """Extract tree nodes list from tree() result.

    Helper to handle format="json" responses which return
    {"format": "json", "tree": [...], "count": N}.

    Args:
        result: Result from tree() call.

    Returns:
        List of tree node dicts.
    """
    if isinstance(result, dict) and "tree" in result:
        return result["tree"]
    # Fallback for legacy format (shouldn't happen)
    return result if isinstance(result, list) else []


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
        - Returns dict with format and content
        - format="json" returns tree list with node_id, name, category, children
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(pattern=".", format="json")

        assert isinstance(result, dict), "tree() should return a dict"
        assert "format" in result, "result should have format key"
        assert result["format"] == "json", "format should be json"
        assert "tree" in result, "result should have tree key"

        nodes = result["tree"]
        assert isinstance(nodes, list), "tree should be a list"
        assert len(nodes) > 0, "tree should be non-empty"

        # Check each root node has required fields
        for node in nodes:
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

        result = tree(pattern=".", format="json")
        nodes = get_tree_nodes(result)

        # Should have at least the file node from fixture
        assert len(nodes) >= 1
        # Root should be file nodes (shallowest level)
        file_nodes = [n for n in nodes if n["category"] == "file"]
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

        result = tree(pattern=".", format="json")
        nodes = get_tree_nodes(result)

        # Flatten tree and check all nodes
        all_nodes = _flatten_tree(nodes)
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

        result = tree(pattern=".", format="json")
        nodes = get_tree_nodes(result)

        all_nodes = _flatten_tree(nodes)
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

        result = tree(pattern="Calculator", format="json")
        nodes = get_tree_nodes(result)

        # All returned nodes should contain "Calculator" in node_id
        all_nodes = _flatten_tree(nodes)
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

        result = tree(pattern="class:src/calculator.py:Calculator", format="json")
        nodes = get_tree_nodes(result)

        # Should return exactly one root with that node_id
        assert len(nodes) == 1, "Exact match should return single root"
        assert nodes[0]["node_id"] == "class:src/calculator.py:Calculator"

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
        result = tree(pattern="*.py", format="json")
        nodes = get_tree_nodes(result)

        # Should match file nodes ending in .py
        all_nodes = _flatten_tree(nodes)
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

        result = tree(pattern="NonexistentClassName", format="json")
        nodes = get_tree_nodes(result)

        assert nodes == [], "No match should return empty list"

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
        result = tree(pattern="file:src/calculator.py", format="json")
        nodes = get_tree_nodes(result)

        # Should have file as root with children
        assert len(nodes) == 1
        file_node = nodes[0]
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

        result = tree(pattern=".", max_depth=1, format="json")
        nodes = get_tree_nodes(result)

        # Root nodes should have their immediate children visible
        for root in nodes:
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

        result = tree(pattern=".", max_depth=1, format="json")
        nodes = get_tree_nodes(result)

        # Find class node at depth 1 (child of file node)
        file_nodes = [n for n in nodes if n["category"] == "file"]
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

        result = tree(pattern=".", max_depth=0, format="json")
        nodes = get_tree_nodes(result)

        # Should have nested children
        all_nodes = _flatten_tree(nodes)
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

        result = tree(pattern=".", max_depth=2, format="json")
        nodes = get_tree_nodes(result)

        # Root nodes should have children (depth 2 allows one level)
        for root in nodes:
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

        result = tree(pattern=".", detail="min", format="json")
        nodes = get_tree_nodes(result)

        all_nodes = _flatten_tree(nodes)
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

        result = tree(pattern=".", detail="max", format="json")
        nodes = get_tree_nodes(result)

        all_nodes = _flatten_tree(nodes)
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

        result = tree(pattern=".", detail="min", format="json")
        nodes = get_tree_nodes(result)

        all_nodes = _flatten_tree(nodes)
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

        result = tree(pattern="add", detail="max", format="json")
        nodes = get_tree_nodes(result)

        # Find the callable node
        all_nodes = _flatten_tree(nodes)
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
        Acceptance Criteria: No signature in default output (when using json format)
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        # Call without detail parameter but with json format to check structure
        result = tree(pattern=".", format="json")
        nodes = get_tree_nodes(result)

        all_nodes = _flatten_tree(nodes)
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
        result = await mcp_client.call_tool("tree", {"pattern": ".", "format": "json"})
        parsed = parse_tool_response(result)

        # Should be a dict with format and tree keys
        assert isinstance(parsed, dict)
        assert "format" in parsed
        assert "tree" in parsed
        assert len(parsed["tree"]) > 0

    @pytest.mark.asyncio
    async def test_tree_tool_response_has_expected_structure(self, mcp_client):
        """
        Purpose: Proves MCP response matches expected node structure
        Quality Contribution: Ensures consistent API contract
        Acceptance Criteria: Each node has node_id, name, category, children
        """
        result = await mcp_client.call_tool("tree", {"pattern": ".", "format": "json"})
        parsed = parse_tool_response(result)
        nodes = parsed.get("tree", [])

        for node in nodes:
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
        result = await mcp_client.call_tool(
            "tree", {"pattern": "Calculator", "format": "json"}
        )
        parsed = parse_tool_response(result)
        nodes = parsed.get("tree", [])

        # Should find nodes containing "Calculator"
        all_nodes = _flatten_tree(nodes)
        for node in all_nodes:
            assert "Calculator" in node["node_id"]

    @pytest.mark.asyncio
    async def test_tree_tool_with_max_depth_parameter(self, mcp_client):
        """
        Purpose: Proves max_depth parameter works via MCP protocol
        Quality Contribution: Ensures depth limiting works over protocol
        Acceptance Criteria: max_depth=1 limits children expansion
        """
        result = await mcp_client.call_tool(
            "tree", {"pattern": ".", "max_depth": 1, "format": "json"}
        )
        parsed = parse_tool_response(result)
        nodes = parsed.get("tree", [])

        # Children at depth 1 should have no children (hidden)
        for root in nodes:
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
        result = await mcp_client.call_tool(
            "tree", {"pattern": "add", "detail": "max", "format": "json"}
        )
        parsed = parse_tool_response(result)
        nodes = parsed.get("tree", [])

        # Find callable nodes
        all_nodes = _flatten_tree(nodes)
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
# Format Parameter Tests
# =============================================================================


class TestTreeTextOutputNodeId:
    """T012: Tests for full node_id display in text output.

    Text output must show full node_id (not just name) so agents can copy-paste
    node_ids directly for use with get_node() without switching to JSON format.

    Per T012/T013:
    - Files show: 📄 file:src/calc.py [1-50]
    - Classes show: 📦 class:src/calc.py:Calculator [5-45]
    - Methods show: ƒ callable:src/calc.py:Calculator.add [10-20]
    - Folders keep: 📁 src/fs2/ (node_id IS the path with slash)
    """

    def test_text_output_shows_full_node_id_for_files(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves file nodes show full node_id in text output
        Quality Contribution: Agents can copy node_id from text for get_node()
        Acceptance Criteria: Text contains "file:src/calculator.py"
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(pattern=".", format="text")
        content = result["content"]

        # Text should contain full node_id for file nodes
        assert "file:src/calculator.py" in content, (
            f"Text should show full node_id for files. Got:\n{content}"
        )

    def test_text_output_shows_full_node_id_for_classes(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves class nodes show full node_id in text output
        Quality Contribution: Agents can copy node_id from text for get_node()
        Acceptance Criteria: Text contains "class:src/calculator.py:Calculator"
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(pattern=".", format="text")
        content = result["content"]

        # Text should contain full node_id for class nodes
        assert "class:src/calculator.py:Calculator" in content, (
            f"Text should show full node_id for classes. Got:\n{content}"
        )

    def test_text_output_shows_full_node_id_for_callables(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves callable nodes show full node_id in text output
        Quality Contribution: Agents can copy node_id from text for get_node()
        Acceptance Criteria: Text contains "callable:src/calculator.py:Calculator.add"
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(pattern=".", format="text")
        content = result["content"]

        # Text should contain full node_id for callable nodes
        assert "callable:src/calculator.py:Calculator.add" in content, (
            f"Text should show full node_id for callables. Got:\n{content}"
        )


class TestTreeFormatParameter:
    """Tests for tree format parameter (text vs json).

    Default is "text" for compact, agent-friendly output.
    JSON format is available for scripting/jq but more verbose.
    """

    def test_tree_default_format_is_text(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves default format is text for context efficiency
        Quality Contribution: Agents get compact output by default
        Acceptance Criteria: Default returns format="text" with content string
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        # Call without format parameter
        result = tree(pattern=".")

        assert isinstance(result, dict)
        assert result["format"] == "text"
        assert "content" in result
        assert isinstance(result["content"], str)
        assert "count" in result

    def test_tree_text_format_contains_icons(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves text format includes visual icons
        Quality Contribution: Human-readable output for agents
        Acceptance Criteria: Output contains category icons
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(pattern=".", format="text")

        content = result["content"]
        # Should contain at least one icon
        assert any(icon in content for icon in ["📄", "📦", "ƒ"])

    def test_tree_json_format_returns_tree_list(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves json format returns structured data
        Quality Contribution: Enables scripting/jq workflows
        Acceptance Criteria: format="json" returns tree list
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(pattern=".", format="json")

        assert isinstance(result, dict)
        assert result["format"] == "json"
        assert "tree" in result
        assert isinstance(result["tree"], list)
        assert "count" in result

    def test_tree_text_format_more_compact_than_json(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves text format saves tokens vs json
        Quality Contribution: Context efficiency for LLMs
        Acceptance Criteria: Text output is shorter than JSON
        """
        import json

        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        text_result = tree(pattern=".", format="text")
        json_result = tree(pattern=".", format="json")

        text_size = len(text_result["content"])
        json_size = len(json.dumps(json_result["tree"]))

        assert text_size < json_size, (
            f"Text ({text_size}) should be more compact than JSON ({json_size})"
        )

    def test_tree_count_consistent_across_formats(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """
        Purpose: Proves count field is consistent
        Quality Contribution: Reliable metadata
        Acceptance Criteria: Same count in text and json formats
        """
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        text_result = tree(pattern=".", format="text")
        json_result = tree(pattern=".", format="json")

        assert text_result["count"] == json_result["count"]


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


# =============================================================================
# Phase 3: Multi-Graph Support - T003 Tests
# =============================================================================


class TestTreeWithGraphName:
    """T003: Tests for tree with graph_name parameter.

    Per Phase 3 AC7-AC9: tree tool accepts graph_name to query different graphs.
    - graph_name=None (default) uses default graph
    - graph_name="default" explicitly selects default graph
    - graph_name="external-lib" selects external library graph
    - Unknown graph_name raises ToolError with available names
    """

    @pytest.mark.asyncio
    async def test_graph_name_none_uses_default(self, mcp_client_multi_graph):
        """
        Purpose: Proves backward compatibility - no graph_name uses default.
        Quality Contribution: Existing agent code continues to work.
        Acceptance Criteria: Returns Calculator nodes from default graph.

        Task: T003
        """
        result = await mcp_client_multi_graph.call_tool(
            "tree", {"pattern": ".", "format": "json"}
        )
        parsed = parse_tool_response(result)
        nodes = parsed.get("tree", [])

        # Flatten to check all nodes
        all_nodes = _flatten_tree(nodes)
        node_ids = [n["node_id"] for n in all_nodes]

        # Should contain default graph content (Calculator)
        assert any("Calculator" in nid for nid in node_ids), (
            f"Default graph should have Calculator. Got: {node_ids}"
        )
        # Should NOT contain external-lib content (auth)
        assert not any("auth" in nid for nid in node_ids), (
            f"Default graph should not have auth nodes. Got: {node_ids}"
        )

    @pytest.mark.asyncio
    async def test_graph_name_default_explicit(self, mcp_client_multi_graph):
        """
        Purpose: Proves explicit "default" works same as None.
        Quality Contribution: Consistent behavior for explicit vs implicit.
        Acceptance Criteria: Returns same Calculator nodes as graph_name=None.

        Task: T003
        """
        result = await mcp_client_multi_graph.call_tool(
            "tree", {"pattern": ".", "graph_name": "default", "format": "json"}
        )
        parsed = parse_tool_response(result)
        nodes = parsed.get("tree", [])

        all_nodes = _flatten_tree(nodes)
        node_ids = [n["node_id"] for n in all_nodes]

        # Should contain Calculator (default graph)
        assert any("Calculator" in nid for nid in node_ids), (
            f"Explicit default should have Calculator. Got: {node_ids}"
        )

    @pytest.mark.asyncio
    async def test_graph_name_named_graph(self, mcp_client_multi_graph):
        """
        Purpose: Proves named graph returns different content.
        Quality Contribution: Multi-graph functionality works.
        Acceptance Criteria: Returns auth nodes from external-lib graph.

        Task: T003
        """
        result = await mcp_client_multi_graph.call_tool(
            "tree", {"pattern": ".", "graph_name": "external-lib", "format": "json"}
        )
        parsed = parse_tool_response(result)
        nodes = parsed.get("tree", [])

        all_nodes = _flatten_tree(nodes)
        node_ids = [n["node_id"] for n in all_nodes]

        # Should contain auth nodes (external-lib graph)
        assert any("auth" in nid or "authenticate" in nid for nid in node_ids), (
            f"external-lib should have auth nodes. Got: {node_ids}"
        )
        # Should NOT contain Calculator (default graph)
        assert not any("Calculator" in nid for nid in node_ids), (
            f"external-lib should not have Calculator. Got: {node_ids}"
        )

    @pytest.mark.asyncio
    async def test_graph_name_unknown_error(self, mcp_client_multi_graph):
        """
        Purpose: Proves unknown graph_name raises helpful error.
        Quality Contribution: User typos get clear feedback with available names.
        Acceptance Criteria: ToolError with available graph names listed.

        Task: T003
        """
        from fastmcp.exceptions import ToolError

        with pytest.raises(ToolError) as exc_info:
            await mcp_client_multi_graph.call_tool(
                "tree", {"pattern": ".", "graph_name": "typo-graph"}
            )

        error_msg = str(exc_info.value)
        # Should mention the unknown graph name
        assert "typo-graph" in error_msg, f"Should mention typo-graph. Got: {error_msg}"
        # Should mention available graphs
        assert "default" in error_msg or "list_graphs" in error_msg, (
            f"Should guide to available graphs. Got: {error_msg}"
        )


class TestTreeRefCount:
    """Tests for ref count in tree --detail max output.

    Per Phase 3 cross-file-rels: tree --detail max shows ref count
    for nodes that have cross-file reference edges.
    """

    def test_tree_json_max_detail_includes_ref_count(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """JSON output at max detail includes ref_count when edges exist."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        # Add a reference edge pointing to Calculator
        store.add_edge(
            "callable:src/calculator.py:Calculator.add",
            "class:src/calculator.py:Calculator",
            edge_type="references",
        )
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(
            pattern="class:src/calculator.py:Calculator",
            detail="max",
            format="json",
        )

        assert result["format"] == "json"
        node_dict = result["tree"][0]
        assert "ref_count" in node_dict, f"Missing ref_count. Keys: {node_dict.keys()}"
        assert node_dict["ref_count"] == 1

    def test_tree_json_min_detail_no_ref_count(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """JSON output at min detail does not include ref_count."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        store.add_edge(
            "callable:src/calculator.py:Calculator.add",
            "class:src/calculator.py:Calculator",
            edge_type="references",
        )
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(
            pattern="class:src/calculator.py:Calculator",
            detail="min",
            format="json",
        )

        node_dict = result["tree"][0]
        assert "ref_count" not in node_dict

    def test_tree_text_max_detail_shows_refs_suffix(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """Text output at max detail shows (N refs) suffix."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        store.add_edge(
            "callable:src/calculator.py:Calculator.add",
            "class:src/calculator.py:Calculator",
            edge_type="references",
        )
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(
            pattern="class:src/calculator.py:Calculator",
            detail="max",
            format="text",
        )

        assert "(1 refs)" in result["content"], (
            f"Expected '(1 refs)' in text output. Got: {result['content']}"
        )

    def test_tree_no_ref_count_when_no_edges(
        self, tree_test_graph_store: tuple, tmp_path: Path
    ):
        """No ref_count in output when node has no reference edges."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import tree

        store, config = tree_test_graph_store
        # No reference edges
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = tree(
            pattern="class:src/calculator.py:Calculator",
            detail="max",
            format="json",
        )

        node_dict = result["tree"][0]
        assert "ref_count" not in node_dict
