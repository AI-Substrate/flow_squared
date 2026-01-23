"""Symbol resolver utilities for line-to-symbol mapping.

Per Phase 8 Tasks:
- T015: Implement find_node_at_line() utility function

Per DYK-2: O(n) scan for MVP; defer index optimization if profiling shows bottleneck.

This module provides utilities for resolving LSP line locations to symbol-level
CodeNode instances, enabling method-to-method edge construction.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fs2.core.models.code_node import CodeNode


def find_node_at_line(
    nodes: list["CodeNode"],
    line: int,
    file_path: str | None = None,
) -> "CodeNode | None":
    """Find the innermost CodeNode containing the given line.

    This enables symbol-level resolution from LSP locations. When LSP reports
    a definition at line N, this function finds whether that line is inside
    a method, class, or file, returning the most specific (innermost) match.

    Algorithm (O(n) scan, per DYK-2):
    1. Filter nodes by file_path if provided
    2. Find all nodes that contain the line (start_line <= line <= end_line)
    3. Return the innermost one (smallest line range = most specific)

    Args:
        nodes: List of CodeNode instances to search.
        line: 1-indexed line number to find.
        file_path: Optional file path filter. If provided, only nodes from
                   this file are considered.

    Returns:
        The innermost CodeNode containing the line, or None if no match.

    Example:
        >>> # Given: file (1-100), class (10-50), method (20-30)
        >>> # Line 25 is in all three, but method is innermost
        >>> result = find_node_at_line(nodes, 25)
        >>> result.category
        'method'

    Performance:
        O(n) where n = len(nodes). For MVP this is acceptable.
        If profiling shows bottleneck, optimize with line-indexed data structure.
    """
    if not nodes:
        return None

    # Filter by file path if provided
    if file_path is not None:
        # Extract file path from node_id or use file_path attribute
        nodes = [n for n in nodes if _node_matches_file(n, file_path)]

    # Find all nodes containing the line
    containing_nodes: list[CodeNode] = []
    for node in nodes:
        if _node_contains_line(node, line):
            containing_nodes.append(node)

    if not containing_nodes:
        return None

    # Return innermost (smallest line range)
    return min(containing_nodes, key=_node_line_span)


def _node_contains_line(node: "CodeNode", line: int) -> bool:
    """Check if node's line range contains the given line.

    Args:
        node: CodeNode to check.
        line: Line number to find.

    Returns:
        True if start_line <= line <= end_line.
    """
    return node.start_line <= line <= node.end_line


def _node_line_span(node: "CodeNode") -> int:
    """Get the line span (size) of a node.

    Args:
        node: CodeNode to measure.

    Returns:
        Number of lines the node spans (end_line - start_line + 1).
    """
    return node.end_line - node.start_line + 1


def _node_matches_file(node: "CodeNode", file_path: str) -> bool:
    """Check if node belongs to the given file.

    Args:
        node: CodeNode to check.
        file_path: File path to match.

    Returns:
        True if node is from this file.
    """
    # Extract file path from node_id (format: "category:path:name" or "file:path")
    node_id = node.node_id
    if ":" in node_id:
        parts = node_id.split(":", 2)
        if len(parts) >= 2:
            node_file = parts[1]
            return node_file == file_path
    return False
