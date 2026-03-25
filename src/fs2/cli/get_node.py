"""fs2 get-node command implementation.

Retrieves a single CodeNode by ID and outputs as JSON for scripting and tool integration.

Per Clean Architecture: CLI handles only arg parsing + presentation.
Business logic (graph loading, node retrieval) is delegated to GetNodeService.

Per research finding #01: Use raw print() for JSON output, Console(stderr=True) for errors.
This ensures clean stdout for piping to tools like jq - only JSON on stdout, all else to stderr.

Per DYK-P3-03: Uses explicit field selection to prevent embedding leakage.
"""

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from fs2.cli.utils import resolve_graph_from_context
from fs2.config.exceptions import MissingConfigurationError
from fs2.core.adapters.exceptions import GraphNotFoundError, GraphStoreError
from fs2.core.models.code_node import CodeNode
from fs2.core.services.get_node_service import GetNodeService

# Console for error/status messages - writes to stderr to keep stdout clean for piping
console = Console(stderr=True)


def _code_node_to_cli_dict(
    node: CodeNode,
    graph_store: Any = None,
) -> dict[str, Any]:
    """Convert CodeNode to JSON-serializable dict with explicit field selection.

    Matches MCP _code_node_to_dict pattern. NEVER includes embedding vectors
    or internal hash fields. Always outputs max detail for CLI (users expect
    all available metadata).

    Args:
        node: CodeNode from GetNodeService.get_node().
        graph_store: Optional GraphStore for relationship edge queries.

    Returns:
        Dict suitable for JSON serialization.
    """
    result: dict[str, Any] = {
        "node_id": node.node_id,
        "name": node.name,
        "category": node.category,
        "content": node.content,
        "signature": node.signature,
        "start_line": node.start_line,
        "end_line": node.end_line,
        "smart_content": node.smart_content,
        "leading_context": node.leading_context,
        "language": node.language,
        "parent_node_id": node.parent_node_id,
        "qualified_name": node.qualified_name,
        "ts_kind": node.ts_kind,
    }

    # Cross-file relationships (omit when empty)
    if graph_store is not None:
        incoming = graph_store.get_edges(
            node.node_id, direction="incoming", edge_type="references"
        )
        outgoing = graph_store.get_edges(
            node.node_id, direction="outgoing", edge_type="references"
        )
        rels: dict[str, list[str]] = {}
        if incoming:
            rels["referenced_by"] = [nid for nid, _ in incoming]
        if outgoing:
            rels["references"] = [nid for nid, _ in outgoing]
        if rels:
            result["relationships"] = rels

    return result


def get_node(
    ctx: typer.Context,
    node_id: Annotated[
        str,
        typer.Argument(
            help="The node_id to retrieve (e.g., 'file:src/main.py', 'callable:src/main.py:main')"
        ),
    ],
    file: Annotated[
        Path | None,
        typer.Option("--file", "-f", help="Write JSON to file instead of stdout"),
    ] = None,
) -> None:
    """Retrieve a single code node by ID and output as JSON.

    Outputs the complete CodeNode data as JSON, suitable for piping to jq
    or other JSON-processing tools.

    \\b
    Examples:
        $ fs2 get-node "file:src/main.py"                  # Output to stdout
        $ fs2 get-node "callable:src/main.py:main" | jq    # Pipe to jq
        $ fs2 get-node "file:src/main.py" --file out.json  # Write to file

    \\b
    Exit codes:
        0 - Success
        1 - User error (missing graph, missing config, node not found)
        2 - System error (corrupted graph)
    """
    try:
        # === Composition Root ===
        # Per Phase 4: Use resolve_graph_from_context for multi-graph support
        config, graph_store = resolve_graph_from_context(ctx)

        # Create service with DI
        service = GetNodeService(config=config, graph_store=graph_store)

        # === Service Call ===
        # Service handles graph loading (lazy) and node retrieval
        try:
            node = service.get_node(node_id)
        except GraphNotFoundError:
            # Graph file doesn't exist - exit 1 (user error)
            console.print(
                "[red]Error:[/red] No graph found.\n"
                "  Run [bold]fs2 scan[/bold] first to create the graph."
            )
            raise typer.Exit(code=1) from None
        except GraphStoreError as e:
            # Exit 2 for corruption (file exists but bad)
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(code=2) from None

        # === Presentation ===
        if node is None:
            # Node not found - exit 1 (user error)
            console.print(f"[red]Error:[/red] Node not found: {node_id}")
            raise typer.Exit(code=1)

        # Serialize to JSON with explicit field selection (DYK-P3-03: no embedding leak)
        node_dict = _code_node_to_cli_dict(node, graph_store=graph_store)
        json_str = json.dumps(node_dict, indent=2, default=str)

        # Output to file or stdout
        if file:
            file.write_text(json_str)
            console.print(f"[green]✓[/green] Wrote {node_id} to {file}")
        else:
            # Use raw print() for clean stdout (per research finding #01)
            print(json_str)

    except MissingConfigurationError:
        # Missing config - exit 1 (user error)
        console.print(
            "[red]Error:[/red] No configuration found.\n"
            "  Run [bold]fs2 init[/bold] first to create .fs2/config.yaml"
        )
        raise typer.Exit(code=1) from None
