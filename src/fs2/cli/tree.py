"""fs2 tree command implementation.

Displays code structure from the persisted graph as a hierarchical tree.
Supports path/glob filtering and depth limiting.
"""

import fnmatch
import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.tree import Tree

from fs2.config.exceptions import MissingConfigurationError
from fs2.config.objects import TreeConfig
from fs2.config.service import FS2ConfigurationService
from fs2.core.adapters.exceptions import GraphStoreError
from fs2.core.models.code_node import CodeNode
from fs2.core.repos import NetworkXGraphStore
from fs2.core.repos.graph_store import GraphStore

console = Console()
logger = logging.getLogger("fs2.cli.tree")

# Icon mapping per category (Discovery 13)
CATEGORY_ICONS = {
    "file": "📄",
    "type": "📦",
    "callable": "ƒ",
    "section": "📝",
    "block": "🏗️",
    "definition": "🔹",
    "statement": "▸",
    "expression": "●",
    "other": "○",
}


def tree(
    pattern: Annotated[
        str,
        typer.Argument(
            help="Pattern to filter nodes (path, name, glob, or node_id)",
        ),
    ] = ".",
    detail: Annotated[
        str,
        typer.Option("--detail", help="Detail level: min or max"),
    ] = "min",
    depth: Annotated[
        int,
        typer.Option("--depth", "-d", help="Maximum tree depth (0 = unlimited)"),
    ] = 0,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable debug logging"),
    ] = False,
) -> None:
    """Display code structure as a hierarchical tree.

    Loads the scanned graph and displays code elements in a tree structure.
    Supports filtering by path, name, glob pattern, or exact node_id.

    \\b
    Examples:
        $ fs2 tree                    # Show all files
        $ fs2 tree src/core           # Filter by path
        $ fs2 tree Calculator         # Filter by name
        $ fs2 tree "*.py"             # Glob pattern
        $ fs2 tree --depth 2          # Limit depth
        $ fs2 tree --detail max       # Show node IDs

    \\b
    Exit codes:
        0 - Success
        1 - User error (missing graph, missing config)
        2 - System error (corrupted graph)
    """
    # Configure verbose logging if requested
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        console.print("[dim]DEBUG: Verbose mode enabled[/dim]")

    try:
        # Load configuration
        config = FS2ConfigurationService()
        tree_config = config.require(TreeConfig)

        # Get graph path
        graph_path = Path(tree_config.graph_path)

        # Check if graph exists (Insight #5: exit 1 for missing)
        if not graph_path.exists():
            console.print(
                "[red]Error:[/red] No graph found.\n"
                "  Run [bold]fs2 scan[/bold] first to create the graph."
            )
            raise typer.Exit(code=1)

        if verbose:
            console.print(f"[dim]DEBUG: Loading graph from {graph_path}[/dim]")

        # Create graph store and load
        graph_store: GraphStore = NetworkXGraphStore(config)

        try:
            graph_store.load(graph_path)
        except GraphStoreError as e:
            # Insight #5: exit 2 for corruption (file exists but bad)
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(code=2) from None

        # Get all nodes
        all_nodes = graph_store.get_all_nodes()

        # Handle empty graph
        if not all_nodes:
            console.print("Found 0 nodes in 0 files")
            raise typer.Exit(code=0)

        # Apply pattern filtering
        if pattern == ".":
            matched_nodes = all_nodes
            if verbose:
                console.print(
                    f"[dim]DEBUG: No pattern filter, using all {len(all_nodes)} nodes[/dim]"
                )
        else:
            matched_nodes = _filter_nodes(all_nodes, pattern)
            if verbose:
                console.print(
                    f"[dim]DEBUG: Pattern '{pattern}' matched {len(matched_nodes)} nodes[/dim]"
                )

        # Handle no matches
        if not matched_nodes:
            console.print(f"No nodes match pattern: {pattern}")
            raise typer.Exit(code=0)

        # Build root bucket (remove children when ancestor matched)
        root_nodes = _build_root_bucket(matched_nodes, graph_store)
        if verbose:
            console.print(
                f"[dim]DEBUG: Root bucket has {len(root_nodes)} root nodes[/dim]"
            )

        # Build and display tree
        _display_tree(root_nodes, graph_store, detail, depth, verbose)

    except MissingConfigurationError:
        console.print(
            "[red]Error:[/red] No configuration found.\n"
            "  Run [bold]fs2 init[/bold] first to create .fs2/config.yaml"
        )
        raise typer.Exit(code=1) from None


def _filter_nodes(nodes: list[CodeNode], pattern: str) -> list[CodeNode]:
    """Filter nodes by pattern using unified node_id matching.

    Matching priority (Insight #2):
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


def _build_root_bucket(
    matched_nodes: list[CodeNode], store: GraphStore
) -> list[CodeNode]:
    """Build root bucket by removing children when ancestor also matched.

    When both a parent and child match the pattern, only keep the parent
    in the root bucket. This enables proper tree rendering from the
    shallowest matched nodes.

    Args:
        matched_nodes: Nodes that matched the pattern.
        store: GraphStore for hierarchy queries.

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
            parent = store.get_node(current_id)
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
                parent = store.get_node(check_id)
                check_id = parent.parent_node_id if parent else None

        for desc_id in descendants_to_remove:
            del bucket[desc_id]

        bucket[node.node_id] = node

    return list(bucket.values())


def _display_tree(
    root_nodes: list[CodeNode],
    store: GraphStore,
    detail: str,
    max_depth: int,
    verbose: bool = False,
) -> None:
    """Display nodes as Rich Tree.

    Groups files by common path prefix into virtual 📁 folders.

    Args:
        root_nodes: Root nodes to display.
        store: GraphStore for children queries.
        detail: "min" or "max" detail level.
        max_depth: Maximum depth (0 = unlimited).
        verbose: Whether to show debug output.
    """
    # Group by path prefix for virtual folders
    path_groups: dict[str, list[CodeNode]] = {}

    for node in root_nodes:
        # Extract path prefix from node_id
        parts = node.node_id.split(":")
        if len(parts) >= 2:
            file_path = parts[1]
            prefix = str(Path(file_path).parent) if "/" in file_path else ""
        else:
            prefix = ""

        if prefix not in path_groups:
            path_groups[prefix] = []
        path_groups[prefix].append(node)

    # Track all displayed nodes for accurate summary
    display_stats = {"total_nodes": 0, "file_count": 0}

    # Create tree
    if len(path_groups) == 1 and "" in path_groups:
        # No grouping needed - single flat list
        main_tree = Tree("[bold]Code Structure[/bold]")
        for node in sorted(root_nodes, key=lambda n: n.node_id):
            _add_node_to_tree(
                main_tree, node, store, detail, max_depth, 1, display_stats
            )
    else:
        # Group by path prefix
        main_tree = Tree("[bold]Code Structure[/bold]")
        for prefix in sorted(path_groups.keys()):
            if prefix:
                folder_label = f"📁 {prefix}/"
                folder_branch = main_tree.add(folder_label)
            else:
                folder_branch = main_tree

            for node in sorted(path_groups[prefix], key=lambda n: n.node_id):
                _add_node_to_tree(
                    folder_branch, node, store, detail, max_depth, 1, display_stats
                )

    console.print(main_tree)

    # Summary line with accurate counts
    total_nodes = display_stats["total_nodes"]
    file_count = display_stats["file_count"]
    console.print(f"\n✓ Found {total_nodes} nodes in {file_count} files")


def _add_node_to_tree(
    parent_tree: Tree,
    node: CodeNode,
    store: GraphStore,
    detail: str,
    max_depth: int,
    current_depth: int,
    stats: dict[str, int] | None = None,
) -> None:
    """Recursively add a node and its children to the tree.

    Args:
        parent_tree: Parent Rich Tree node.
        node: CodeNode to add.
        store: GraphStore for children queries.
        detail: "min" or "max" detail level.
        max_depth: Maximum depth (0 = unlimited).
        current_depth: Current depth in tree.
        stats: Optional dict to track {"total_nodes", "file_count"}.
    """
    # Track stats for summary
    if stats is not None:
        stats["total_nodes"] += 1
        if node.category == "file":
            stats["file_count"] += 1

    # Build label
    icon = CATEGORY_ICONS.get(node.category, "○")
    name = node.name or node.qualified_name

    if detail == "max":
        # Include node_id and signature
        sig = f" {node.signature}" if node.signature else ""
        label = f"{icon} {name} [{node.start_line}-{node.end_line}]{sig}"
        label += f"\n    [dim]{node.node_id}[/dim]"
    else:
        # Minimal: icon, name, line range
        label = f"{icon} {name} [{node.start_line}-{node.end_line}]"

    branch = parent_tree.add(label)

    # Check depth limit
    if max_depth > 0 and current_depth >= max_depth:
        children = store.get_children(node.node_id)
        if children:
            branch.add(f"[dim][{len(children)} children hidden by depth limit][/dim]")
        return

    # Add children
    children = store.get_children(node.node_id)
    for child in sorted(children, key=lambda n: n.start_line):
        _add_node_to_tree(
            branch, child, store, detail, max_depth, current_depth + 1, stats
        )
