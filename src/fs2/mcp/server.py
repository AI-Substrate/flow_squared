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
from fs2.core.models.code_node import CodeNode
from fs2.core.models.tree_node import TreeNode
from fs2.core.services.get_node_service import GetNodeService
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


# =============================================================================
# MCP Tools (Phase 3: get_node)
# =============================================================================


def _code_node_to_dict(
    node: CodeNode,
    detail: Literal["min", "max"] = "min",
) -> dict[str, Any]:
    """Convert CodeNode to JSON-serializable dict with explicit field selection.

    Per DYK Session: Explicit field filtering to prevent embedding leakage.
    NEVER include embedding vectors or internal hash fields.

    Fields in min detail (7 core fields):
    - node_id, name, category, content, signature, start_line, end_line

    Fields in max detail (adds 5 more):
    - smart_content, language, parent_node_id, qualified_name, ts_kind

    NEVER included (embedding data and internal metadata):
    - embedding, smart_content_embedding, embedding_hash, embedding_chunk_offsets
    - content_hash, smart_content_hash
    - start_byte, end_byte, start_column, end_column
    - is_named, field_name, is_error, truncated, truncated_at_line, content_type

    Args:
        node: CodeNode from GetNodeService.get_node().
        detail: "min" for compact output, "max" for full metadata.

    Returns:
        Dict suitable for JSON serialization.
    """
    # Core fields (always present)
    result: dict[str, Any] = {
        "node_id": node.node_id,
        "name": node.name,
        "category": node.category,
        "content": node.content,
        "signature": node.signature,
        "start_line": node.start_line,
        "end_line": node.end_line,
    }

    # Extended fields (max detail only)
    if detail == "max":
        result["smart_content"] = node.smart_content
        result["language"] = node.language
        result["parent_node_id"] = node.parent_node_id
        result["qualified_name"] = node.qualified_name
        result["ts_kind"] = node.ts_kind

    return result


def _validate_save_path(save_to_file: str) -> str:
    """Validate save_to_file path is under current working directory.

    Per DYK Session: Security constraint - path must be at or under PWD.
    Prevents directory traversal attacks.

    Args:
        save_to_file: Relative or absolute path to validate.

    Returns:
        Absolute path string if valid.

    Raises:
        ToolError: If path escapes PWD or is absolute outside PWD.
    """
    from pathlib import Path

    cwd = Path.cwd().resolve()
    target = (cwd / save_to_file).resolve()

    # Check if target is under or equal to cwd
    try:
        target.relative_to(cwd)
    except ValueError:
        raise ToolError(
            f"Path '{save_to_file}' escapes working directory. "
            "Only paths under the current directory are allowed."
        ) from None

    return str(target)


def get_node(
    node_id: str,
    save_to_file: str | None = None,
    detail: Literal["min", "max"] = "min",
) -> dict[str, Any] | None:
    """Retrieve complete code node by ID.

    Returns full source content and metadata for a specific code element.
    Use after tree() or search() to get the complete source code for a node.

    Args:
        node_id: Unique identifier from tree() or search() results.
            Format: 'category:path:name' (e.g., 'class:src/calc.py:Calculator')
        save_to_file: Optional file path to save node as JSON.
            Path must be under current working directory.
        detail: Output verbosity level.
            - "min" = 7 core fields (default)
            - "max" = adds smart_content, language, parent_node_id, etc.

    Returns:
        CodeNode dict if found, None if node_id doesn't exist.
        When save_to_file is used, includes 'saved_to' field with absolute path.

    Raises:
        ToolError: If graph not found or path escapes working directory.
    """
    try:
        config = get_config()
        store = get_graph_store()
        service = GetNodeService(config=config, graph_store=store)
        code_node = service.get_node(node_id)

        # Return None for not-found (per AC5 - not an error)
        if code_node is None:
            return None

        # Convert to dict with explicit field selection
        result = _code_node_to_dict(code_node, detail)

        # Handle save_to_file if specified
        if save_to_file is not None:
            import json

            # Validate path security
            absolute_path = _validate_save_path(save_to_file)

            # Write JSON to file
            with open(absolute_path, "w") as f:
                json.dump(result, f, indent=2)

            # Add saved_to field per DYK Session decision
            result["saved_to"] = absolute_path

        return result

    except GraphNotFoundError:
        raise ToolError("Graph not found. Run 'fs2 scan' to create the graph.") from None
    except GraphStoreError as e:
        raise ToolError(f"Graph error: {e}. The graph file may be corrupted.") from None
    except ToolError:
        # Re-raise ToolErrors (from path validation) as-is
        raise
    except Exception as e:
        logger.exception("Unexpected error in get_node tool")
        raise ToolError(f"Unexpected error: {e}") from None


# Register get_node function as MCP tool with annotations (per T006)
# Per DYK Session: readOnlyHint=False because save_to_file writes to filesystem
_get_node_tool = mcp.tool(
    annotations={
        "title": "Get Code Node",
        "readOnlyHint": False,  # Can write files via save_to_file
        "destructiveHint": False,  # Doesn't destroy existing data
        "idempotentHint": True,  # Same inputs return same outputs
        "openWorldHint": False,  # No external network/API calls
    }
)(get_node)
