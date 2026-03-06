"""fs2 tree command implementation.

Displays code structure from the persisted graph as a hierarchical tree.
Supports path/glob filtering and depth limiting.

Per Clean Architecture: CLI handles only arg parsing + presentation.
Business logic (filtering, root bucketing, tree building) is delegated to TreeService.

Per Phase 1 save-to-file: --json flag outputs JSON to stdout, --file writes to file.
"""

import json
import logging
from pathlib import Path
from typing import Annotated, Any, Literal

import typer
from rich.console import Console
from rich.tree import Tree

from fs2.cli.utils import (
    resolve_graph_from_context,
    safe_write_file,
    validate_save_path,
)
from fs2.config.exceptions import MissingConfigurationError
from fs2.core.adapters.exceptions import GraphNotFoundError, GraphStoreError
from fs2.core.models.tree_node import TreeNode
from fs2.core.services.tree_service import TreeService

# Console for Rich tree display - writes to stdout
console = Console()
# Console for error/status messages - writes to stderr to keep stdout clean for piping
stderr_console = Console(stderr=True)
logger = logging.getLogger("fs2.cli.tree")

# Icon mapping per category (Discovery 13) - PRESENTATION CONCERN stays in CLI
CATEGORY_ICONS = {
    "file": "📄",
    "folder": "📁",  # T001: Virtual folder icon for hierarchical navigation
    "type": "📦",
    "callable": "ƒ",
    "section": "📝",
    "block": "🏗️",
    "definition": "🔹",
    "statement": "▸",
    "expression": "●",
    "other": "○",
}


def _tree_node_to_dict(
    tree_node: TreeNode,
    detail: Literal["min", "max"] = "min",
) -> dict[str, Any]:
    """Convert TreeNode to JSON-serializable dict.

    Per T009: Recursive conversion with correct fields per detail level.
    Shares logic with MCP server's _tree_node_to_dict.

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

    # Base fields (always present)
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


def tree(
    ctx: typer.Context,
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
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output JSON instead of Rich tree (for scripting)"),
    ] = False,
    file: Annotated[
        Path | None,
        typer.Option(
            "--file",
            "-f",
            help="Write JSON to file instead of stdout (requires --json, path validated for security).",
        ),
    ] = None,
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
        $ fs2 tree --json             # Output JSON to stdout
        $ fs2 tree --json --file results.json  # Save JSON to file

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
        stderr_console.print("[dim]DEBUG: Verbose mode enabled[/dim]")

    try:
        # === Remote mode branch ===
        from fs2.cli.remote_client import RemoteClientError
        from fs2.cli.utils import resolve_remote_client

        remote_client = resolve_remote_client(ctx)
        if remote_client is not None:
            import asyncio

            try:
                # Get graph name from context (required for remote tree)
                graph_name = ctx.obj.graph_name if ctx.obj and ctx.obj.graph_name else None
                if not graph_name:
                    # If no graph specified, try to list and pick single graph
                    graphs_resp = asyncio.run(remote_client.list_graphs())
                    graphs = graphs_resp.get("graphs", [])
                    if len(graphs) == 1:
                        graph_name = graphs[0]["name"]
                    elif len(graphs) == 0:
                        stderr_console.print("[red]Error:[/red] No graphs available on remote.")
                        raise typer.Exit(code=1)
                    else:
                        names = [g["name"] for g in graphs]
                        stderr_console.print(
                            "[red]Error:[/red] Multiple graphs on remote. "
                            f"Specify one with --graph-name: {', '.join(names)}"
                        )
                        raise typer.Exit(code=1)

                result = asyncio.run(remote_client.tree(graph_name, pattern=pattern, max_depth=depth))

                if json_output or file:
                    # JSON mode: request JSON format from server
                    result = asyncio.run(remote_client.tree(
                        graph_name, pattern=pattern, max_depth=depth, format="json",
                    ))
                    json_str = json.dumps(result, indent=2, default=str)
                    if file:
                        absolute_path = validate_save_path(file, stderr_console)
                        safe_write_file(absolute_path, json_str, stderr_console)
                        stderr_console.print(f"[green]✓[/green] Wrote tree results to {file}")
                    else:
                        print(json_str)
                else:
                    # Text mode: request pre-rendered text from server (DYK-P5-02)
                    result = asyncio.run(remote_client.tree(
                        graph_name, pattern=pattern, max_depth=depth, format="text",
                    ))
                    content = result.get("content", "")
                    if not content:
                        if pattern == ".":
                            console.print("Found 0 nodes in 0 files")
                        else:
                            console.print(f"No nodes match pattern: {pattern}")
                    else:
                        print(content)
                raise typer.Exit(code=0)
            except RemoteClientError as e:
                stderr_console.print(f"[red]Error:[/red] {e}")
                raise typer.Exit(code=1) from None

        # === Local mode (existing) ===
        # Per Phase 4: Use resolve_graph_from_context for multi-graph support
        config, graph_store = resolve_graph_from_context(ctx)

        if verbose:
            graph_info = (
                ctx.obj.graph_name
                if ctx.obj and ctx.obj.graph_name
                else ctx.obj.graph_file
                if ctx.obj and ctx.obj.graph_file
                else "default"
            )
            stderr_console.print(f"[dim]DEBUG: Using graph: {graph_info}[/dim]")

        # Create service with DI
        service = TreeService(config=config, graph_store=graph_store)

        if verbose:
            stderr_console.print("[dim]DEBUG: TreeService created[/dim]")

        # === Service Call ===
        try:
            tree_nodes = service.build_tree(pattern=pattern, max_depth=depth)
        except GraphNotFoundError:
            stderr_console.print(
                "[red]Error:[/red] No graph found.\n"
                "  Run [bold]fs2 scan[/bold] first to create the graph."
            )
            raise typer.Exit(code=1) from None
        except GraphStoreError as e:
            stderr_console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(code=2) from None

        if verbose:
            stderr_console.print(
                f"[dim]DEBUG: TreeService returned {len(tree_nodes)} root nodes[/dim]"
            )

        # === Presentation ===
        # Handle JSON output mode
        if json_output or file:
            # Convert to JSON-serializable format
            detail_literal: Literal["min", "max"] = "max" if detail == "max" else "min"
            tree_dicts = [_tree_node_to_dict(tn, detail_literal) for tn in tree_nodes]
            envelope = {"tree": tree_dicts}
            json_str = json.dumps(envelope, indent=2, default=str)

            # Handle file output vs stdout
            if file:
                # Validate path for security (AC4b)
                absolute_path = validate_save_path(file, stderr_console)
                # Write file with cleanup on error and UTF-8 encoding
                safe_write_file(absolute_path, json_str, stderr_console)
                # Confirmation on stderr (AC2)
                stderr_console.print(f"[green]✓[/green] Wrote tree results to {file}")
            else:
                # Use raw print() for clean stdout
                print(json_str)
            raise typer.Exit(code=0)

        # Handle empty results (Rich output only)
        if not tree_nodes:
            if pattern == ".":
                console.print("Found 0 nodes in 0 files")
            else:
                console.print(f"No nodes match pattern: {pattern}")
            raise typer.Exit(code=0)

        # Display tree using Rich
        _display_tree(tree_nodes, detail, depth, verbose)

    except MissingConfigurationError:
        stderr_console.print(
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

    # Build label - use full node_id for copy-paste workflow (T012/T013)
    icon = CATEGORY_ICONS.get(node.category, "○")

    if detail == "max":
        # Include signature
        sig = f" {node.signature}" if node.signature else ""
        label = f"{icon} {node.node_id} [{node.start_line}-{node.end_line}]{sig}"
    else:
        # Show full node_id for agent copy-paste
        label = f"{icon} {node.node_id} [{node.start_line}-{node.end_line}]"

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
