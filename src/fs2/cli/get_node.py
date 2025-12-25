"""fs2 get-node command implementation.

Retrieves a single CodeNode by ID and outputs as JSON for scripting and tool integration.

Per Clean Architecture: CLI handles only arg parsing + presentation.
Business logic (graph loading, node retrieval) is delegated to GetNodeService.

Per research finding #01: Use raw print() for JSON output, Console(stderr=True) for errors.
This ensures clean stdout for piping to tools like jq - only JSON on stdout, all else to stderr.
"""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from fs2.config.exceptions import MissingConfigurationError
from fs2.config.objects import GraphConfig
from fs2.config.service import FS2ConfigurationService
from fs2.core.adapters.exceptions import GraphNotFoundError, GraphStoreError
from fs2.core.repos import NetworkXGraphStore
from fs2.core.services.get_node_service import GetNodeService

# Console for error/status messages - writes to stderr to keep stdout clean for piping
console = Console(stderr=True)


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
        # Create configuration service and adapters
        config = FS2ConfigurationService()

        # Per Subtask 001: Get graph_file from global option via context
        if ctx.obj and ctx.obj.graph_file:
            # Override GraphConfig in config service
            config.set(GraphConfig(graph_path=ctx.obj.graph_file))

        graph_store = NetworkXGraphStore(config)

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

        # Serialize to JSON
        # Use asdict() for dataclass serialization, default=str for non-JSON types
        json_str = json.dumps(asdict(node), indent=2, default=str)

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
