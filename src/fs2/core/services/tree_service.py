"""TreeService - Service for tree operations on the code graph.

This service follows the Clean Architecture pattern:
- Receives ConfigurationService (registry) and GraphStore (ABC) via constructor
- Extracts its own config internally via config.require()
- Depends on interfaces, not implementations
- Uses lazy loading for graph access

CRITICAL: This service MUST NOT store copies of graph data.
All access goes through GraphStore ABC. See rules.md R3.5.

Usage:
    ```python
    # In composition root
    config = FS2ConfigurationService()
    graph_store = NetworkXGraphStore(config)

    service = TreeService(config=config, graph_store=graph_store)

    # Build tree with single call - CLI becomes truly "dumb"
    tree_nodes = service.build_tree(pattern="Calculator", max_depth=2)
    for tree_node in tree_nodes:
        render_tree(tree_node)  # CLI handles Rich rendering
    ```
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING

from fs2.config.objects import GraphConfig
from fs2.core.adapters.exceptions import GraphNotFoundError
from fs2.core.models.code_node import CodeNode
from fs2.core.models.tree_node import TreeNode

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService
    from fs2.core.repos.graph_store import GraphStore


class TreeService:
    """Service for tree operations on the code graph.

    Provides a high-level API for building tree structures from the code graph.
    CLI commands use this service instead of directly accessing GraphStore.

    CRITICAL: This service MUST NOT store copies of graph data.
    All access goes through GraphStore ABC. See rules.md R3.5.

    The main entry point is `build_tree()` which:
    1. Filters nodes by pattern
    2. Builds root bucket (removes children when ancestor matched)
    3. Expands children recursively up to max_depth

    Attributes:
        _config: GraphConfig with graph_path
        _graph_store: GraphStore ABC for graph access (NOT a copy)
        _loaded: Flag for lazy loading

    Example:
        ```python
        service = TreeService(config, graph_store)
        trees = service.build_tree(pattern="Calculator", max_depth=2)
        ```
    """

    def __init__(
        self,
        config: ConfigurationService,
        graph_store: GraphStore,
    ) -> None:
        """Initialize with config registry and graph store.

        Args:
            config: ConfigurationService registry (NOT GraphConfig).
                    Service will call config.require(GraphConfig) internally.
            graph_store: GraphStore ABC for graph operations.

        Raises:
            MissingConfigurationError: If GraphConfig not in registry.
        """
        self._config = config.require(GraphConfig)
        self._graph_store = graph_store
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Lazy load graph on first access.

        Raises:
            GraphNotFoundError: If graph file does not exist.
            GraphStoreError: If graph file is corrupted.
        """
        if self._loaded:
            return
        graph_path = Path(self._config.graph_path)
        if not graph_path.exists():
            raise GraphNotFoundError(graph_path)
        self._graph_store.load(graph_path)
        self._loaded = True

    # === PUBLIC API (CLI uses this) ===

    def build_tree(
        self,
        pattern: str = ".",
        max_depth: int = 0,
    ) -> list[TreeNode]:
        """Build complete tree structure for rendering.

        This is the main entry point - CLI calls this single method.
        Orchestrates filtering, root bucketing, and child expansion.

        Args:
            pattern: Filter pattern (exact, glob, or substring).
                    "." means match all nodes.
            max_depth: How deep to expand children (0 = unlimited).

        Returns:
            List of root TreeNodes with children populated.

        Raises:
            GraphNotFoundError: If graph file does not exist.
            GraphStoreError: If graph file is corrupted.
        """
        self._ensure_loaded()

        # Get all nodes
        all_nodes = self._graph_store.get_all_nodes()

        # Handle empty graph
        if not all_nodes:
            return []

        # Apply pattern filtering
        if pattern == ".":
            matched = all_nodes
        else:
            matched = self._filter_nodes(all_nodes, pattern)

        # Handle no matches
        if not matched:
            return []

        # Build root bucket (remove children when ancestor matched)
        roots = self._build_root_bucket(matched)

        # Build tree structure for each root
        return [
            self._build_tree_node(root, max_depth, 0)
            for root in sorted(roots, key=lambda n: n.node_id)
        ]

    # === PRIVATE METHODS (internal orchestration) ===

    def _filter_nodes(self, nodes: list[CodeNode], pattern: str) -> list[CodeNode]:
        """Filter nodes by pattern using unified node_id matching.

        Matching priority:
        1. Exact match on node_id → short-circuit
        2. Glob pattern (contains *?[]) → fnmatch on node_id
        3. Substring match → partial match on node_id

        Args:
            nodes: List of all CodeNodes.
            pattern: Pattern to match against.

        Returns:
            List of matching CodeNodes.
        """
        # 1. Exact match - short-circuit
        exact_matches = [n for n in nodes if n.node_id == pattern]
        if exact_matches:
            return exact_matches

        # 2. Glob pattern detection
        if any(c in pattern for c in "*?[]"):
            return [n for n in nodes if fnmatch.fnmatch(n.node_id, f"*{pattern}*")]

        # 3. Substring match
        return [n for n in nodes if pattern in n.node_id]

    def _build_root_bucket(self, matched_nodes: list[CodeNode]) -> list[CodeNode]:
        """Build root bucket by removing children when ancestor also matched.

        When both a parent and child match the pattern, only keep the parent
        in the root bucket. This enables proper tree rendering from the
        shallowest matched nodes.

        Args:
            matched_nodes: Nodes that matched the pattern.

        Returns:
            List of root nodes (shallowest matches).
        """
        if not matched_nodes:
            return []

        # Build set of matched node_ids for quick lookup
        matched_ids = {n.node_id for n in matched_nodes}

        # Bucket: node_id → CodeNode
        bucket: dict[str, CodeNode] = {}

        for node in matched_nodes:
            # Check if any ancestor is already matched
            has_matched_ancestor = False
            current_id = node.parent_node_id

            while current_id:
                if current_id in matched_ids:
                    has_matched_ancestor = True
                    break
                parent = self._graph_store.get_node(current_id)
                current_id = parent.parent_node_id if parent else None

            if has_matched_ancestor:
                # Skip this node - ancestor is already a root
                continue

            # Remove any descendants from bucket
            descendants_to_remove = []
            for bucket_id in bucket:
                # Check if bucket_id is a descendant of node
                check_id = bucket[bucket_id].parent_node_id
                while check_id:
                    if check_id == node.node_id:
                        descendants_to_remove.append(bucket_id)
                        break
                    parent = self._graph_store.get_node(check_id)
                    check_id = parent.parent_node_id if parent else None

            for desc_id in descendants_to_remove:
                del bucket[desc_id]

            bucket[node.node_id] = node

        return list(bucket.values())

    def _build_tree_node(
        self,
        node: CodeNode,
        max_depth: int,
        current_depth: int,
    ) -> TreeNode:
        """Recursively build TreeNode with children.

        Args:
            node: CodeNode to convert to TreeNode.
            max_depth: Maximum depth (0 = unlimited).
            current_depth: Current depth in tree.

        Returns:
            TreeNode with children populated (recursively).
        """
        # Get children from graph store (needed for both paths)
        children = self._graph_store.get_children(node.node_id)

        # Check depth limit
        if max_depth > 0 and current_depth >= max_depth:
            # At depth limit - return node without children but with hidden count
            return TreeNode(
                node=node,
                children=(),
                hidden_children_count=len(children),
            )

        # Build child TreeNodes recursively
        child_tree_nodes = tuple(
            self._build_tree_node(child, max_depth, current_depth + 1)
            for child in sorted(children, key=lambda n: n.start_line)
        )

        return TreeNode(node=node, children=child_tree_nodes)
