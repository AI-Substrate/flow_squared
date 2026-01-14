"""fs2 list-graphs command implementation.

Lists all available graphs with their name, path, availability status, and description.
Provides CLI parity with the MCP list_graphs() tool.

Per Subtask 001: Add list-graphs CLI command for graph discovery.
Per Critical Insight #2: Wrap get_graph_service() in try/except for config errors.
Per Critical Insight #3: JSON output must match MCP list_graphs() structure exactly.
Per Critical Insight #5: Table shows 4 columns; source_url available via --json.
"""

import dataclasses
import json
import logging
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from fs2.config.exceptions import MissingConfigurationError

logger = logging.getLogger("fs2.cli.list_graphs")

# Console for Rich table output - writes to stdout
console = Console()
# Console for error/status messages - writes to stderr to keep stdout clean for piping
stderr_console = Console(stderr=True)


def list_graphs(
    ctx: typer.Context,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output JSON instead of table (for scripting)"),
    ] = False,
) -> None:
    """List all available graphs with metadata.

    Shows the default local project graph and any configured external graphs.
    Use this command to discover available graphs before querying with --graph-name.

    \\b
    Examples:
        $ fs2 list-graphs                # Show table with name, status, path, description
        $ fs2 list-graphs --json         # Output JSON matching MCP list_graphs() format

    \\b
    Exit codes:
        0 - Success
        1 - Configuration error (no config found)
    """
    try:
        # Per Critical Insight #2: Wrap get_graph_service() in try/except
        # for both MissingConfigurationError AND FileNotFoundError
        from fs2.core.dependencies import get_graph_service

        try:
            service = get_graph_service()
            graph_infos = service.list_graphs()
        except (MissingConfigurationError, FileNotFoundError):
            stderr_console.print("[red]No fs2 configuration found.[/red]")
            stderr_console.print("Run [bold]fs2 init[/bold] to initialize.")
            raise typer.Exit(code=1)

        # Per Critical Insight #3: JSON output must match MCP list_graphs() exactly
        if json_output:
            # Use dataclasses.asdict() pattern matching MCP server
            docs_list = []
            for info in graph_infos:
                info_dict = dataclasses.asdict(info)
                # Convert Path to string for JSON serialization
                info_dict["path"] = str(info_dict["path"])
                docs_list.append(info_dict)

            output = {
                "docs": docs_list,
                "count": len(docs_list),
            }
            # Use raw print() for clean stdout
            print(json.dumps(output, indent=2))  # noqa: T201
            raise typer.Exit(code=0)

        # Per Critical Insight #5: Table shows 4 columns (Name, Status, Path, Description)
        # source_url available via --json for complete data
        table = Table(title="Available Graphs")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center")
        table.add_column("Path", style="dim", overflow="fold")
        table.add_column("Description")

        for info in graph_infos:
            status = "[green]✓[/green]" if info.available else "[red]✗[/red]"
            description = info.description or ""
            table.add_row(info.name, status, str(info.path), description)

        console.print(table)
        console.print(f"\nTotal: {len(graph_infos)} graph(s)")

    except MissingConfigurationError:
        stderr_console.print("[red]No fs2 configuration found.[/red]")
        stderr_console.print("Run [bold]fs2 init[/bold] to initialize.")
        raise typer.Exit(code=1)
