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

FX001-1: Padding between directory regions + minimum node spacing
  to prevent the dot-matrix overlap pattern.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fs2.core.models.code_node import CodeNode

# Fraction of cell dimension reserved as padding between directory regions
_DIR_PADDING_FRAC = 0.03

# Minimum gap between node centers (in canvas units) to prevent overlap
_MIN_NODE_GAP = 18.0


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
    Adds padding between subdivisions so directory regions are visually distinct.
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

    # Padding between directory regions
    pad_x = w * _DIR_PADDING_FRAC
    pad_y = h * _DIR_PADDING_FRAC

    # Determine split direction: horizontal if wider, vertical if taller
    horizontal = w >= h
    n_items = len(items)

    # Total padding consumed between items
    total_gap = (pad_x if horizontal else pad_y) * (n_items - 1) if n_items > 1 else 0.0

    available = (w if horizontal else h) - total_gap
    if available <= 0:
        available = w if horizontal else h
        total_gap = 0.0

    offset = 0.0
    gap = total_gap / max(1, n_items - 1) if n_items > 1 else 0.0

    for _i, (_key, weight, subtree) in enumerate(items):
        fraction = weight / total_weight
        if horizontal:
            item_w = available * fraction
            item_h = h - pad_y * 2
            item_x = x + pad_x + offset
            item_y = y + pad_y
            offset += item_w + gap
        else:
            item_w = w - pad_x * 2
            item_h = available * fraction
            item_x = x + pad_x
            item_y = y + pad_y + offset
            offset += item_h + gap

        if item_w <= 0 or item_h <= 0:
            continue

        if subtree is not None:
            _layout_rect(subtree, item_x, item_y, item_w, item_h, positions)
        else:
            _layout_local_nodes(local_nodes, item_x, item_y, item_w, item_h, positions)


def _layout_local_nodes(
    nodes: list[CodeNode],
    x: float,
    y: float,
    w: float,
    h: float,
    positions: dict[str, NodePosition],
) -> None:
    """Position local nodes within a cell with minimum spacing.

    Uses a grid layout with enforced minimum gap between node centers
    to prevent the dot-matrix overlap pattern (FX001-1).
    """
    if not nodes:
        return

    # Sort by start_line for deterministic ordering
    sorted_nodes = sorted(nodes, key=lambda n: (n.file_path or "", n.start_line or 0))
    n = len(sorted_nodes)

    # Grid dimensions — constrained by minimum spacing
    max_cols_by_space = max(1, int(w / _MIN_NODE_GAP))
    max_rows_by_space = max(1, int(h / _MIN_NODE_GAP))

    cols = max(1, min(math.ceil(math.sqrt(n)), max_cols_by_space))
    rows = max(1, min(math.ceil(n / cols), max_rows_by_space))

    # If grid can't fit all nodes, increase cols
    while cols * rows < n and cols < max_cols_by_space:
        cols += 1
        rows = math.ceil(n / cols)

    cell_w = w / cols
    cell_h = h / rows

    for idx, node in enumerate(sorted_nodes):
        if idx >= cols * rows:
            # Overflow: stack remaining at last cell with offset
            col = (cols - 1)
            row = (rows - 1)
            overflow_idx = idx - (cols * rows) + 1
            nx = x + (col + 0.5) * cell_w + overflow_idx * 2
            ny = y + (row + 0.5) * cell_h + overflow_idx * 2
        else:
            col = idx % cols
            row = idx // cols
            nx = x + (col + 0.5) * cell_w
            ny = y + (row + 0.5) * cell_h

        size = _compute_node_size(node.start_line, node.end_line)
        positions[node.node_id] = NodePosition(
            x=round(nx, 2), y=round(ny, 2), size=round(size, 2)
        )


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
