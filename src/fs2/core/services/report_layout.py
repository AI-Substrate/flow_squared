"""Treemap layout algorithm for codebase graph reports.

Computes 2D positions for code nodes using a squarified treemap layout.
Nodes are grouped by directory hierarchy (from file_path), NOT by
parent_node_id (which represents AST containment).

Architecture:
    ReportService → compute_treemap(nodes) → {node_id: NodePosition}
    Pure function — no dependencies, no side effects, deterministic.

DYK-06: Two-level hierarchy:
  1. Directory tree from file_path (spatial grouping)
  2. Within each file, nodes positioned by start_line order
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fs2.core.models.code_node import CodeNode


@dataclass(frozen=True)
class NodePosition:
    """Position and size of a node in the treemap layout."""

    x: float
    y: float
    size: float


def _compute_node_size(start_line: int | None, end_line: int | None) -> float:
    """Compute node display size from line count.

    Formula from Workshop 001:
        max(4, min(14, 3 + log2(lines + 1) * 1.5))
    """
    if start_line is None or end_line is None:
        return 4.0
    lines = max(1, end_line - start_line + 1)
    return max(4.0, min(14.0, 3.0 + math.log2(lines + 1) * 1.5))


def build_directory_tree(
    nodes: list[CodeNode],
) -> dict:
    """Build a nested directory tree grouping nodes by file_path.

    Shared logic used by both report_layout (treemap) and potentially
    tree_service (folder hierarchy). Extracted per FT-004 review finding.

    Args:
        nodes: CodeNodes to group by directory.

    Returns:
        Nested dict: {"__nodes__": [nodes_here], "subdir_name": {...}, ...}
        Each level has "__nodes__" for items at that level and
        string keys for child directories.
    """
    root: dict = {"__nodes__": []}
    for node in nodes:
        fp = node.file_path or ""
        parts = fp.split("/") if fp else []
        current = root
        if len(parts) > 1:
            for folder in parts[:-1]:
                if folder not in current:
                    current[folder] = {"__nodes__": []}
                current = current[folder]
        current["__nodes__"].append(node)
    return root


def _count_nodes(tree: dict) -> int:
    """Count total nodes in a directory tree (recursive)."""
    count = len(tree["__nodes__"])
    for key, subtree in sorted(tree.items()):
        if key == "__nodes__":
            continue
        count += _count_nodes(subtree)
    return count


def _layout_rect(
    tree: dict,
    x: float,
    y: float,
    w: float,
    h: float,
    positions: dict[str, NodePosition],
) -> None:
    """Recursively lay out a directory tree into a rectangle.

    Uses a simplified squarified treemap: subdivide the rectangle
    proportionally among subdirectories and local nodes.
    """
    if w <= 0 or h <= 0:
        return

    # Collect items to lay out: (key, weight) pairs
    items: list[tuple[str, int, dict | None]] = []

    # Local nodes as a group
    local_nodes = tree["__nodes__"]
    if local_nodes:
        items.append(("__local__", len(local_nodes), None))

    # Subdirectories
    for key in sorted(tree.keys()):
        if key == "__nodes__":
            continue
        subtree = tree[key]
        count = _count_nodes(subtree)
        if count > 0:
            items.append((key, count, subtree))

    if not items:
        return

    total_weight = sum(weight for _, weight, _ in items)
    if total_weight == 0:
        return

    # Determine split direction: horizontal if wider, vertical if taller
    horizontal = w >= h
    offset = 0.0

    for _key, weight, subtree in items:
        fraction = weight / total_weight
        if horizontal:
            item_w = w * fraction
            item_h = h
            item_x = x + offset
            item_y = y
            offset += item_w
        else:
            item_w = w
            item_h = h * fraction
            item_x = x
            item_y = y + offset
            offset += item_h

        if subtree is not None:
            # Recurse into subdirectory
            _layout_rect(subtree, item_x, item_y, item_w, item_h, positions)
        else:
            # Lay out local nodes within this cell
            _layout_local_nodes(local_nodes, item_x, item_y, item_w, item_h, positions)


def _layout_local_nodes(
    nodes: list[CodeNode],
    x: float,
    y: float,
    w: float,
    h: float,
    positions: dict[str, NodePosition],
) -> None:
    """Position local nodes within a cell using a grid layout."""
    if not nodes:
        return

    # Sort by start_line for deterministic ordering
    sorted_nodes = sorted(nodes, key=lambda n: (n.file_path or "", n.start_line or 0))
    n = len(sorted_nodes)

    # Grid dimensions
    cols = max(1, math.ceil(math.sqrt(n)))
    rows = max(1, math.ceil(n / cols))

    cell_w = w / cols
    cell_h = h / rows

    for idx, node in enumerate(sorted_nodes):
        col = idx % cols
        row = idx // cols
        # Center of the grid cell
        nx = x + (col + 0.5) * cell_w
        ny = y + (row + 0.5) * cell_h
        size = _compute_node_size(node.start_line, node.end_line)
        positions[node.node_id] = NodePosition(x=round(nx, 2), y=round(ny, 2), size=round(size, 2))


def compute_treemap(
    nodes: list[CodeNode],
    canvas_size: float = 1000.0,
) -> dict[str, NodePosition]:
    """Compute treemap positions for all nodes.

    Groups nodes by directory hierarchy (from file_path),
    then positions them using a squarified treemap layout.

    Args:
        nodes: List of CodeNodes to position.
        canvas_size: Size of the square canvas (default 1000).

    Returns:
        Dict mapping node_id to NodePosition(x, y, size).
    """
    if not nodes:
        return {}

    tree = build_directory_tree(nodes)
    positions: dict[str, NodePosition] = {}
    _layout_rect(tree, 0, 0, canvas_size, canvas_size, positions)
    return positions
