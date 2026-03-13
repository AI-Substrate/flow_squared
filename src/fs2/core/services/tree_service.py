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
from typing import TYPE_CHECKING, Literal

from fs2.config.objects import GraphConfig
from fs2.core.adapters.exceptions import GraphNotFoundError
from fs2.core.models.code_node import CodeNode
from fs2.core.models.tree_node import TreeNode
from fs2.core.utils.hash import compute_content_hash

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService
    from fs2.core.repos.graph_store import GraphStore


def _create_folder_node(folder_path: str) -> CodeNode:
    """Create a synthetic folder CodeNode.

    Per DD1, DD5: Folders use category="folder", start_line=0, end_line=0,
    and node_id is the path with trailing slash.

    Args:
        folder_path: Folder path (with or without trailing slash).

    Returns:
        Synthetic CodeNode for the folder.
    """
    # Ensure trailing slash for consistency
    path = folder_path if folder_path.endswith("/") else folder_path + "/"
    # Extract folder name from path
    name = (
        path.rstrip("/").split("/")[-1] if "/" in path.rstrip("/") else path.rstrip("/")
    )

    return CodeNode(
        node_id=path,
        category="folder",
        ts_kind="folder",
        name=name,
        qualified_name=name,
        start_line=0,
        end_line=0,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=0,
        content="",
        content_hash=compute_content_hash(""),
        signature=None,
        language="",
        is_named=True,
        field_name=None,
    )


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

        Per Phase 3 Multi-Graph: If the store already has nodes (e.g., loaded
        by GraphService), skip loading. This prevents overwriting external
        graphs with the default config.graph_path.

        Raises:
            GraphNotFoundError: If graph file does not exist.
            GraphStoreError: If graph file is corrupted.
        """
        if self._loaded:
            return
        # Per Phase 3: Skip loading if store already has content (e.g., from GraphService)
        if len(self._graph_store.get_all_nodes()) > 0:
            self._loaded = True
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

        When pattern="." and max_depth > 0, computes virtual folder hierarchy
        for progressive disclosure (see _compute_folder_hierarchy).

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

        # Per Phase 2: For "." pattern with depth limit, compute folder hierarchy
        # This enables progressive disclosure: depth=1 shows folders, depth=2 shows contents
        if pattern == "." and max_depth > 0:
            return self._compute_folder_hierarchy(matched, max_depth)

        # Build root bucket (remove children when ancestor matched)
        roots = self._build_root_bucket(matched)

        # Build tree structure for each root
        return [
            self._build_tree_node(root, max_depth, 0)
            for root in sorted(roots, key=lambda n: n.node_id)
        ]

    # === PRIVATE METHODS (internal orchestration) ===

    @staticmethod
    def _detect_input_mode(
        pattern: str,
    ) -> Literal["folder", "node_id", "pattern"]:
        """Detect input mode from pattern syntax.

        Per T003: Detection order is CRITICAL - check `:` before `/`.
        This ensures `file:src/main.py` is detected as node_id, not folder.

        Detection logic:
        1. Contains `:` → node_id (e.g., "file:src/main.py", "type:...:Calculator")
        2. Contains `/` → folder (e.g., "src/", "src/fs2/")
        3. Otherwise → pattern (e.g., "Calculator", "*.py", ".")

        Args:
            pattern: User input pattern string.

        Returns:
            "node_id" | "folder" | "pattern"
        """
        # 1. Check for colon FIRST (node_id mode)
        if ":" in pattern:
            return "node_id"

        # 2. Check for slash (folder mode)
        if "/" in pattern:
            return "folder"

        # 3. Default to pattern mode
        return "pattern"

    @staticmethod
    def _extract_file_path(node_id: str) -> str:
        """Extract file path from node_id.

        Node ID format: {category}:{file_path} or {category}:{file_path}:{qualified_name}
        Examples:
        - "file:src/main.py" → "src/main.py"
        - "type:src/calc.py:Calculator" → "src/calc.py"
        - "callable:src/calc.py:Calculator.add" → "src/calc.py"

        Args:
            node_id: Full node ID string.

        Returns:
            File path portion of the node ID.
        """
        parts = node_id.split(":")
        if len(parts) >= 2:
            # For file nodes: file:path → path
            # For other nodes: category:path:name → path
            return parts[1]
        return ""

    def _filter_nodes(self, nodes: list[CodeNode], pattern: str) -> list[CodeNode]:
        """Filter nodes by pattern using mode-aware matching.

        Per T007: Uses _detect_input_mode() to determine matching strategy:
        - node_id mode: exact match on node_id
        - folder mode: filter files by path prefix
        - pattern mode: existing matching priority (exact → glob → substring)

        Args:
            nodes: List of all CodeNodes.
            pattern: Pattern to match against.

        Returns:
            List of matching CodeNodes.
        """
        mode = self._detect_input_mode(pattern)

        # Handle folder mode: filter files by path prefix
        if mode == "folder":
            # Normalize folder pattern (ensure trailing slash for exact prefix matching)
            folder_prefix = pattern if pattern.endswith("/") else pattern + "/"
            # Match files whose path starts with the folder prefix
            # Extract file_path from node_id format: {category}:{file_path} or {category}:{file_path}:{name}
            return [
                n
                for n in nodes
                if self._extract_file_path(n.node_id).startswith(folder_prefix)
            ]

        # Handle node_id mode: exact match
        if mode == "node_id":
            return [n for n in nodes if n.node_id == pattern]

        # Handle pattern mode: existing matching priority
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

    def _get_containment_children(self, node: CodeNode) -> list[CodeNode]:
        """Get children filtered to same-file containment edges only.

        Cross-file reference edges are excluded to prevent foreign nodes
        from appearing in the tree hierarchy.

        Args:
            node: Parent CodeNode.

        Returns:
            List of child CodeNodes from the same file.
        """
        children = self._graph_store.get_children(node.node_id)
        parent_file = node.file_path
        return [c for c in children if c.file_path == parent_file]

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
        # Get children from graph store, filtered to same-file only
        children = self._get_containment_children(node)

        # Check depth limit (max_depth=1 means root only, max_depth=2 means root+children)
        if max_depth > 0 and current_depth + 1 >= max_depth:
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

    def _compute_folder_hierarchy(
        self,
        file_nodes: list[CodeNode],
        max_depth: int,
    ) -> list[TreeNode]:
        """Compute virtual folder hierarchy from file nodes.

        Per Phase 2: Creates synthetic folder nodes to enable progressive disclosure.
        At depth=1, only top-level folders are shown. At depth=2, folders + immediate
        contents are shown, etc.

        Per DD1: Folders use synthetic CodeNode with category="folder".
        Per DD4: Folders appear first, then files (both sorted alphabetically).
        Per DD5: Folder node_id uses path with trailing slash (e.g., "src/fs2/").

        Args:
            file_nodes: List of file CodeNodes to compute folders from.
            max_depth: Maximum depth to expand (1 = top-level only).

        Returns:
            List of TreeNodes representing the folder hierarchy.
        """
        if not file_nodes:
            return []

        # Build a nested dict structure: path -> {files: [], folders: {}}
        # This represents the folder hierarchy
        root: dict = {"files": [], "folders": {}}

        for node in file_nodes:
            # Extract file path from node_id (e.g., "file:src/main.py" -> "src/main.py")
            file_path = self._extract_file_path(node.node_id)
            if not file_path:
                # Root-level file without path prefix
                root["files"].append(node)
                continue

            # Split path into components
            parts = file_path.split("/")
            if len(parts) == 1:
                # Root-level file (no folder)
                root["files"].append(node)
            else:
                # Navigate/create folder structure
                current = root
                for folder in parts[:-1]:  # All but the filename
                    if folder not in current["folders"]:
                        current["folders"][folder] = {"files": [], "folders": {}}
                    current = current["folders"][folder]
                # Add file to its parent folder
                current["files"].append(node)

        # Convert to TreeNodes with depth limiting
        return self._build_folder_tree_nodes(root, max_depth, 0, "")

    def _build_folder_tree_nodes(
        self,
        folder_dict: dict,
        max_depth: int,
        current_depth: int,
        path_prefix: str,
    ) -> list[TreeNode]:
        """Recursively build TreeNodes from folder dict structure.

        Per DD4: Sorts folders first, then files (both alphabetically).

        Args:
            folder_dict: Dict with "files" and "folders" keys.
            max_depth: Maximum depth to expand.
            current_depth: Current depth in hierarchy.
            path_prefix: Path prefix for constructing folder node_ids.

        Returns:
            List of TreeNodes for the current level.
        """
        result: list[TreeNode] = []

        # Process folders first (DD4: folders before files)
        for folder_name in sorted(folder_dict["folders"].keys()):
            folder_contents = folder_dict["folders"][folder_name]
            folder_path = f"{path_prefix}{folder_name}/"

            # Count total items in this folder (recursive)
            total_items = self._count_folder_items(folder_contents)

            # Create synthetic folder node
            folder_node = _create_folder_node(folder_path)

            # Check depth limit
            if current_depth + 1 >= max_depth:
                # At depth limit - folder with hidden children count
                result.append(
                    TreeNode(
                        node=folder_node,
                        children=(),
                        hidden_children_count=total_items,
                    )
                )
            else:
                # Expand children
                children = self._build_folder_tree_nodes(
                    folder_contents,
                    max_depth,
                    current_depth + 1,
                    folder_path,
                )
                # Count any items that would be hidden at deeper levels
                immediate_items = len(folder_contents["files"]) + len(
                    folder_contents["folders"]
                )
                hidden_count = (
                    total_items - immediate_items
                    if current_depth + 2 >= max_depth
                    else 0
                )
                result.append(
                    TreeNode(
                        node=folder_node,
                        children=tuple(children),
                        hidden_children_count=hidden_count,
                    )
                )

        # Process files second (DD4: files after folders)
        for file_node in sorted(folder_dict["files"], key=lambda n: n.name or ""):
            # Check depth limit for files
            if current_depth + 1 >= max_depth:
                # At depth limit - files without their symbol children
                children_count = len(self._get_containment_children(file_node))
                result.append(
                    TreeNode(
                        node=file_node,
                        children=(),
                        hidden_children_count=children_count,
                    )
                )
            else:
                # Expand file's symbol children
                result.append(
                    self._build_tree_node(file_node, max_depth, current_depth + 1)
                )

        return result

    def _count_folder_items(self, folder_dict: dict) -> int:
        """Count total files recursively in a folder.

        Per spec: Folder counts show files only (e.g., `📁 src/ (89 files)`).

        Args:
            folder_dict: Dict with "files" and "folders" keys.

        Returns:
            Total count of all nested files (not including subfolders themselves).
        """
        count = len(folder_dict["files"])
        for subfolder in folder_dict["folders"].values():
            count += self._count_folder_items(subfolder)
        return count
