"""fs2 tree command implementation.

Displays code structure from the persisted graph as a hierarchical tree.
Supports path/glob filtering and depth limiting.

Per Clean Architecture: CLI handles only arg parsing + presentation.
Business logic (filtering, root bucketing, tree building) is delegated to TreeService.
"""

import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.tree import Tree

from fs2.config.exceptions import MissingConfigurationError
from fs2.config.service import FS2ConfigurationService
from fs2.core.adapters.exceptions import GraphNotFoundError, GraphStoreError
from fs2.core.models.tree_node import TreeNode
from fs2.core.repos import NetworkXGraphStore
from fs2.core.services.tree_service import TreeService

console = Console()
logger = logging.getLogger("fs2.cli.tree")

# Icon mapping per category (Discovery 13) - PRESENTATION CONCERN stays in CLI
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
        # === Composition Root ===
        config = FS2ConfigurationService()
        graph_store = NetworkXGraphStore(config)

        # Create service with DI
        service = TreeService(config=config, graph_store=graph_store)

        if verbose:
            console.print("[dim]DEBUG: TreeService created[/dim]")

        # === Service Call ===
        try:
            tree_nodes = service.build_tree(pattern=pattern, max_depth=depth)
        except GraphNotFoundError:
            console.print(
                "[red]Error:[/red] No graph found.\n"
                "  Run [bold]fs2 scan[/bold] first to create the graph."
            )
            raise typer.Exit(code=1) from None
        except GraphStoreError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(code=2) from None

        if verbose:
            console.print(
                f"[dim]DEBUG: TreeService returned {len(tree_nodes)} root nodes[/dim]"
            )

        # === Presentation ===
        # Handle empty results
        if not tree_nodes:
            if pattern == ".":
                console.print("Found 0 nodes in 0 files")
            else:
                console.print(f"No nodes match pattern: {pattern}")
            raise typer.Exit(code=0)

        # Display tree using Rich
        _display_tree(tree_nodes, detail, depth, verbose)

    except MissingConfigurationError:
        console.print(
            "[red]Error:[/red] No configuration found.\n"
            "  Run [bold]fs2 init[/bold] first to create .fs2/config.yaml"
        )
        raise typer.Exit(code=1) from None


def _display_tree(
    tree_nodes: list[TreeNode],
    detail: str,
    max_depth: int,
    verbose: bool = False,
) -> None:
    """Display TreeNodes as Rich Tree.

    Groups files by common path prefix into virtual 📁 folders.

    Args:
        tree_nodes: Root TreeNodes from TreeService.build_tree().
        detail: "min" or "max" detail level.
        max_depth: Maximum depth (for hidden children messages).
        verbose: Whether to show debug output.
    """
    # Group by path prefix for virtual folders
    path_groups: dict[str, list[TreeNode]] = {}

    for tree_node in tree_nodes:
        node = tree_node.node
        # Extract path prefix from node_id
        parts = node.node_id.split(":")
        if len(parts) >= 2:
            file_path = parts[1]
            prefix = str(Path(file_path).parent) if "/" in file_path else ""
        else:
            prefix = ""

        if prefix not in path_groups:
            path_groups[prefix] = []
        path_groups[prefix].append(tree_node)

    # Track all displayed nodes for accurate summary
    display_stats = {"total_nodes": 0, "file_count": 0}

    # Create tree
    if len(path_groups) == 1 and "" in path_groups:
        # No grouping needed - single flat list
        main_tree = Tree("[bold]Code Structure[/bold]")
        for tree_node in sorted(tree_nodes, key=lambda tn: tn.node.node_id):
            _add_tree_node_to_rich_tree(
                main_tree, tree_node, detail, max_depth, 1, display_stats
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

            for tree_node in sorted(
                path_groups[prefix], key=lambda tn: tn.node.node_id
            ):
                _add_tree_node_to_rich_tree(
                    folder_branch, tree_node, detail, max_depth, 1, display_stats
                )

    console.print(main_tree)

    # Summary line with accurate counts
    total_nodes = display_stats["total_nodes"]
    file_count = display_stats["file_count"]
    console.print(f"\n✓ Found {total_nodes} nodes in {file_count} files")


def _add_tree_node_to_rich_tree(
    parent_tree: Tree,
    tree_node: TreeNode,
    detail: str,
    max_depth: int,
    current_depth: int,
    stats: dict[str, int] | None = None,
) -> None:
    """Recursively add a TreeNode and its children to the Rich Tree.

    Args:
        parent_tree: Parent Rich Tree node.
        tree_node: TreeNode to add.
        detail: "min" or "max" detail level.
        max_depth: Maximum depth (for hidden children message).
        current_depth: Current depth in tree.
        stats: Optional dict to track {"total_nodes", "file_count"}.
    """
    node = tree_node.node

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

    # Show hidden children indicator if any
    if tree_node.hidden_children_count > 0:
        branch.add(
            f"[dim][{tree_node.hidden_children_count} children hidden by depth limit][/dim]"
        )

    # Add children
    for child_tree_node in tree_node.children:
        _add_tree_node_to_rich_tree(
            branch, child_tree_node, detail, max_depth, current_depth + 1, stats
        )
