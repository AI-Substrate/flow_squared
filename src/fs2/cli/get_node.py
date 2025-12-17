"""fs2 get-node command implementation.

Retrieves a single CodeNode by ID and outputs as JSON for scripting and tool integration.

Per research finding #01: Use raw print() for JSON output.
Errors go through Rich Console for formatting (matching tree.py pattern).
This ensures clean stdout for piping to tools like jq on successful retrieval.
"""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from fs2.config.exceptions import MissingConfigurationError
from fs2.config.objects import TreeConfig
from fs2.config.service import FS2ConfigurationService
from fs2.core.adapters.exceptions import GraphStoreError
from fs2.core.repos import NetworkXGraphStore
from fs2.core.repos.graph_store import GraphStore

# Console for error messages (matches tree.py pattern)
console = Console()


def get_node(
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
        # Load configuration (T011)
        config = FS2ConfigurationService()
        tree_config = config.require(TreeConfig)

        # Get graph path
        graph_path = Path(tree_config.graph_path)

        # Check if graph exists (T011 - exit 1 for missing)
        if not graph_path.exists():
            console.print(
                "[red]Error:[/red] No graph found.\n"
                "  Run [bold]fs2 scan[/bold] first to create the graph."
            )
            raise typer.Exit(code=1)

        # Create graph store and load (T012)
        graph_store: GraphStore = NetworkXGraphStore(config)

        try:
            graph_store.load(graph_path)
        except GraphStoreError as e:
            # Exit 2 for corruption (file exists but bad) - T015
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(code=2) from None

        # Get node by ID (T012)
        node = graph_store.get_node(node_id)

        if node is None:
            # Node not found - exit 1 (user error) - T012
            console.print(f"[red]Error:[/red] Node not found: {node_id}")
            raise typer.Exit(code=1)

        # Serialize to JSON (T013)
        # Use asdict() for dataclass serialization, default=str for non-JSON types
        json_str = json.dumps(asdict(node), indent=2, default=str)

        # Output to file or stdout (T013, T014)
        if file:
            file.write_text(json_str)
            console.print(f"[green]✓[/green] Wrote {node_id} to {file}")
        else:
            # Use raw print() for clean stdout (per research finding #01)
            print(json_str)

    except MissingConfigurationError:
        # Missing config - exit 1 (user error) - T015
        console.print(
            "[red]Error:[/red] No configuration found.\n"
            "  Run [bold]fs2 init[/bold] first to create .fs2/config.yaml"
        )
        raise typer.Exit(code=1) from None
