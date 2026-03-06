"""fs2 list-remotes command implementation.

Lists all configured remote servers from user and project config.
Config-only — no HTTP calls. For checking connectivity, use `fs2 list-graphs --remote`.
"""

import json
import logging
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

logger = logging.getLogger("fs2.cli.list_remotes")

console = Console()
stderr_console = Console(stderr=True)


def list_remotes(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output JSON instead of table"),
    ] = False,
) -> None:
    """List all configured remote fs2 servers.

    Shows named remotes from ~/.config/fs2/config.yaml and .fs2/config.yaml.
    Does NOT contact remotes — use `fs2 list-graphs --remote` to verify connectivity.

    \\b
    Examples:
        $ fs2 list-remotes              # Show table
        $ fs2 list-remotes --json       # Output JSON

    \\b
    Exit codes:
        0 - Success
        1 - Configuration error
    """
    from fs2.config.objects import RemotesConfig
    from fs2.config.service import FS2ConfigurationService

    try:
        config = FS2ConfigurationService()
        remotes_config = config.get(RemotesConfig)
    except Exception:
        remotes_config = None

    servers = remotes_config.servers if remotes_config else []

    if json_output:
        output = {
            "remotes": [
                {
                    "name": s.name,
                    "url": s.url,
                    "has_api_key": s.api_key is not None,
                    "description": s.description,
                }
                for s in servers
            ],
            "count": len(servers),
        }
        print(json.dumps(output, indent=2))
        raise typer.Exit(code=0)

    if not servers:
        console.print("No remotes configured.")
        console.print(
            "\n[dim]Add remotes to ~/.config/fs2/config.yaml:[/dim]\n"
            "  remotes:\n"
            "    servers:\n"
            '      - name: "work"\n'
            '        url: "https://fs2.your-company.com"\n'
            '        description: "Team server"'
        )
        raise typer.Exit(code=0)

    table = Table(title="Configured Remotes")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("URL")
    table.add_column("Auth", justify="center")
    table.add_column("Description")

    for s in servers:
        auth = "[green]✓[/green]" if s.api_key else "[dim]—[/dim]"
        table.add_row(s.name, s.url, auth, s.description or "")

    console.print(table)
    console.print(f"\nTotal: {len(servers)} remote(s)")
    console.print("[dim]Tip: Use --remote <name> with any command to query a remote.[/dim]")
