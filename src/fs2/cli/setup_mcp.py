"""fs2 setup-mcp command — install fs2 MCP server into Claude config.

Adds the fs2 MCP server entry to ~/.claude.json so Claude Code
can use fs2's code intelligence tools (tree, search, get_node, etc.)
in every project without per-project configuration.

Idempotent: skips if already configured, updates if command differs.
"""

import json
import shutil
from pathlib import Path

import typer
from rich.console import Console

console = Console()

# Central Claude config file
CLAUDE_CONFIG = Path.home() / ".claude.json"

# MCP server entry for fs2
FS2_MCP_KEY = "flowspace"
FS2_MCP_ENTRY = {
    "type": "stdio",
    "command": "fs2",
    "args": ["mcp"],
    "env": {},
}


def _find_fs2_command() -> str:
    """Find the fs2 executable path, falling back to 'fs2'."""
    path = shutil.which("fs2")
    return path if path else "fs2"


def setup_mcp() -> None:
    """Install the fs2 MCP server into Claude Code configuration.

    Adds fs2 as an MCP server in ~/.claude.json so Claude Code
    can use fs2's code intelligence tools in every session.

    \b
    Usage:
        $ fs2 setup-mcp
        > fs2 MCP server added to ~/.claude.json
          Restart Claude Code to activate.

    \b
    Already configured:
        $ fs2 setup-mcp
        > fs2 MCP server already configured in ~/.claude.json
    """
    if not CLAUDE_CONFIG.exists():
        console.print(
            "[red]✗[/red] ~/.claude.json not found.\n"
            "  Is Claude Code installed? Run [bold]claude[/bold] first."
        )
        raise typer.Exit(code=1)

    try:
        config = json.loads(CLAUDE_CONFIG.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        console.print(f"[red]✗[/red] Failed to read ~/.claude.json: {e}")
        raise typer.Exit(code=1) from None

    servers = config.get("mcpServers", {})

    # Check if already configured
    if FS2_MCP_KEY in servers:
        existing = servers[FS2_MCP_KEY]
        if (
            existing.get("command") == FS2_MCP_ENTRY["command"]
            and existing.get("args") == FS2_MCP_ENTRY["args"]
        ):
            console.print(
                f"[green]✓[/green] fs2 MCP server already configured in {CLAUDE_CONFIG}"
            )
            return

        # Update existing entry
        console.print(
            f"[yellow]![/yellow] Updating fs2 MCP server config in {CLAUDE_CONFIG}"
        )
        servers[FS2_MCP_KEY] = FS2_MCP_ENTRY
    else:
        # Add new entry
        servers[FS2_MCP_KEY] = FS2_MCP_ENTRY

    config["mcpServers"] = servers

    try:
        CLAUDE_CONFIG.write_text(
            json.dumps(config, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as e:
        console.print(f"[red]✗[/red] Failed to write ~/.claude.json: {e}")
        raise typer.Exit(code=1) from None

    console.print(
        f"[green]✓[/green] fs2 MCP server added to {CLAUDE_CONFIG}\n"
        "  Restart Claude Code to activate."
    )
