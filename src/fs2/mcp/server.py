"""MCP server module for fs2.

Provides the FastMCP server instance for AI agent integration.
All logging is configured to use stderr BEFORE any fs2 imports
to ensure zero stdout pollution (MCP protocol requirement).

Architecture:
- MCPLoggingConfig configures stderr-only logging FIRST
- FastMCP instance created with name "fs2"
- translate_error() converts domain exceptions to agent-friendly responses
- Tools: tree (Phase 2), get_node (Phase 3), search (Phase 4)

Per Critical Discovery 01: STDIO protocol requires stderr-only logging.
Per Critical Discovery 05: Error translation at MCP boundary.
Per Critical Discovery 07: Logging config BEFORE imports.

Usage:
    # CLI entry point
    from fs2.mcp.server import mcp
    mcp.run()

    # Error translation
    from fs2.mcp.server import translate_error
    try:
        ...
    except Exception as e:
        return translate_error(e)

    # Direct tool access (for testing)
    from fs2.mcp.server import tree
    result = tree(pattern="Calculator")
"""

# CRITICAL: Configure logging BEFORE any fs2 imports
# This ensures all loggers created at module level use stderr
from fs2.core.adapters.logging_config import MCPLoggingConfig

MCPLoggingConfig().configure()

# Emit startup log to confirm logging is active (goes to stderr)
import logging

logging.getLogger(__name__).info("MCP logging configured: all output routed to stderr")

# NOW safe to import FastMCP and other fs2 modules
from typing import Any, Literal

logger = logging.getLogger(__name__)

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from fs2.core.adapters.exceptions import (
    GraphNotFoundError,
    GraphStoreError,
)
from fs2.core.models.tree_node import TreeNode
from fs2.core.services.tree_service import TreeService
from fs2.mcp.dependencies import get_config, get_graph_store

# Create FastMCP server instance
# Note: Tools will be added in Phase 2-4
mcp = FastMCP(
    name="fs2",
    instructions=(
        "fs2 (Flowspace2) is a code intelligence tool for exploring and "
        "querying code repositories. Use the available tools to search, "
        "navigate, and understand codebases."
    ),
)


def translate_error(exc: Exception) -> dict[str, Any]:
    """Translate domain exceptions to agent-friendly responses.

    Converts fs2 exceptions into structured dictionaries with:
    - type: Exception class name
    - message: Human-readable description
    - action: Suggested remediation (or None)

    Per Critical Discovery 05: Error translation at MCP boundary.

    Args:
        exc: Any exception from fs2 operations.

    Returns:
        Dict with type, message, and action keys.

    Example:
        >>> translate_error(GraphNotFoundError(Path(".fs2/graph.pickle")))
        {
            'type': 'GraphNotFoundError',
            'message': "Graph not found at .fs2/graph.pickle. Run 'fs2 scan' first.",
            'action': "Run 'fs2 scan' to create the graph."
        }
    """
    # Log original exception for debugging (goes to stderr per MCP config)
    logger.error("MCP error translation: %s", exc, exc_info=True)

    error_type = type(exc).__name__
    message = str(exc)
    action: str | None = None

    # Specific error handling with actionable guidance
    if isinstance(exc, GraphNotFoundError):
        action = "Run 'fs2 scan' to create the graph."

    elif isinstance(exc, GraphStoreError):
        action = "The graph file may be corrupted. Try running 'fs2 scan' to regenerate it."

    elif isinstance(exc, ValueError):
        # Often regex or pattern errors
        if "regex" in message.lower() or "pattern" in message.lower():
            action = "Check the search pattern for valid regex syntax."
        else:
            action = "Verify the input parameters are valid."

    return {
        "type": error_type,
        "message": message,
        "action": action,
    }


# =============================================================================
# Helper Functions
# =============================================================================


def _tree_node_to_dict(
    tree_node: TreeNode,
    detail: Literal["min", "max"] = "min",
) -> dict[str, Any]:
    """Convert TreeNode to JSON-serializable dict.

    Per T005a: Recursive conversion with correct fields per detail level.

    Fields always included:
    - node_id, name, category, start_line, end_line, children

    Fields included when > 0:
    - hidden_children_count

    Fields included only in max detail:
    - signature, smart_content

    Args:
        tree_node: TreeNode from TreeService.build_tree().
        detail: "min" for compact output, "max" for full metadata.

    Returns:
        Dict suitable for JSON serialization.
    """
    node = tree_node.node

    # Base fields (always present - CRITICAL: node_id always included for agent workflow)
    result: dict[str, Any] = {
        "node_id": node.node_id,
        "name": node.name,
        "category": node.category,
        "start_line": node.start_line,
        "end_line": node.end_line,
        "children": [_tree_node_to_dict(child, detail) for child in tree_node.children],
    }

    # Add hidden_children_count only when > 0
    if tree_node.hidden_children_count > 0:
        result["hidden_children_count"] = tree_node.hidden_children_count

    # Max detail includes additional fields
    if detail == "max":
        if node.signature:
            result["signature"] = node.signature
        if node.smart_content:
            result["smart_content"] = node.smart_content

    return result


# =============================================================================
# MCP Tools (Phase 2: tree)
# =============================================================================


def tree(
    pattern: str = ".",
    max_depth: int = 0,
    detail: Literal["min", "max"] = "min",
) -> list[dict[str, Any]]:
    """Explore codebase structure as a hierarchical tree.

    WHEN TO USE: Start here to understand what exists in a codebase.
    Returns files, classes, and functions with their containment relationships.

    PREREQUISITES: Requires 'fs2 scan' to have been run first.
    If you get a "Graph not found" error, the codebase hasn't been indexed.

    WORKFLOW:
    1. Use tree(pattern=".") to see all top-level files
    2. Use tree(pattern="ClassName") to find specific classes/functions
    3. Use returned node_id values with get_node() for detailed source code

    Parameters:
        pattern: Filter pattern for matching code elements.
            - "." returns all nodes (default)
            - "ClassName" finds nodes containing that substring
            - "file:path/to/file.py" matches exact node_id
            - "*.py" or "Calculator*" for glob patterns
        max_depth: How many levels deep to expand.
            - 0 = unlimited depth (full tree)
            - 1 = root nodes only
            - 2 = roots + one level of children
        detail: Output verbosity level.
            - "min" = node_id, name, category, lines, children (default)
            - "max" = adds signature, smart_content for detailed inspection

    Returns:
        List of tree nodes in hierarchical structure. Each node contains:
        - node_id: Unique identifier (use with get_node() for full source)
        - name: Display name (e.g., "Calculator", "add")
        - category: "file" | "class" | "callable" | etc.
        - start_line, end_line: Line range in source file
        - children: Nested list of child nodes
        - hidden_children_count: (when max_depth limits) count of hidden children

    Example:
        >>> tree(pattern="Calculator")
        [{"node_id": "class:src/calc.py:Calculator",
          "name": "Calculator",
          "category": "class",
          "start_line": 5,
          "end_line": 45,
          "children": [
            {"node_id": "callable:src/calc.py:Calculator.add", ...}
          ]}]
    """
    try:
        config = get_config()
        store = get_graph_store()
        service = TreeService(config=config, graph_store=store)
        tree_nodes = service.build_tree(pattern=pattern, max_depth=max_depth)
        return [_tree_node_to_dict(tn, detail) for tn in tree_nodes]
    except GraphNotFoundError:
        raise ToolError("Graph not found. Run 'fs2 scan' to create the graph.") from None
    except GraphStoreError as e:
        raise ToolError(f"Graph error: {e}. The graph file may be corrupted.") from None
    except Exception as e:
        logger.exception("Unexpected error in tree tool")
        raise ToolError(f"Unexpected error: {e}") from None


# Register tree function as MCP tool with annotations (per T007)
# Per Critical Discovery 02: Tool descriptions drive agent tool selection
# Per plan 2.7: Annotations indicate tool behavior to clients
_tree_tool = mcp.tool(
    annotations={
        "title": "Explore Code Tree",
        "readOnlyHint": True,  # Tool only reads data, doesn't modify
        "destructiveHint": False,  # No destructive side effects
        "idempotentHint": True,  # Same inputs always return same outputs
        "openWorldHint": False,  # No external network/API calls
    }
)(tree)
