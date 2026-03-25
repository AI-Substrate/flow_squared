"""fs2 setup-mcp command — install fs2 MCP server into agent configs.

Adds the fs2 MCP server entry to the target agent's config file
so it can use fs2's code intelligence tools (tree, search, get_node, etc.)
in every project without per-project configuration.

Idempotent: skips if already configured, updates if command differs.
"""

import json
from pathlib import Path

import typer
from rich.console import Console

console = Console()

# Target configs
COPILOT_CLI_CONFIG = Path.home() / ".copilot" / "mcp-config.json"
CLAUDE_CODE_CONFIG = Path.home() / ".claude.json"

FS2_MCP_KEY = "flowspace"

# Copilot CLI format
COPILOT_CLI_ENTRY = {
    "type": "local",
    "command": "fs2",
    "args": ["mcp"],
    "tools": ["*"],
}

# Claude Code format
CLAUDE_CODE_ENTRY = {
    "type": "stdio",
    "command": "fs2",
    "args": ["mcp"],
    "env": {},
}


def setup_mcp(
    copilot_cli: bool = typer.Option(
        False,
        "--copilot-cli",
        help="Install into GitHub Copilot CLI (~/.copilot/mcp-config.json)",
    ),
    claude_code: bool = typer.Option(
        False,
        "--claude-code",
        help="Install into Claude Code (~/.claude.json)",
    ),
) -> None:
    """Install the fs2 MCP server into an AI coding agent.

    \b
    Usage:
        $ fs2 setup-mcp --copilot-cli
        $ fs2 setup-mcp --claude-code
    """
    if not copilot_cli and not claude_code:
        console.print(
            "[yellow]![/yellow] Specify a target:\n"
            "  [bold]fs2 setup-mcp --copilot-cli[/bold]   GitHub Copilot CLI\n"
            "  [bold]fs2 setup-mcp --claude-code[/bold]   Claude Code"
        )
        raise typer.Exit(code=1)

    if copilot_cli:
        _install_to_config(COPILOT_CLI_CONFIG, COPILOT_CLI_ENTRY, "Copilot CLI")
    if claude_code:
        _install_to_config(CLAUDE_CODE_CONFIG, CLAUDE_CODE_ENTRY, "Claude Code")


def _install_to_config(
    config_path: Path, entry: dict, label: str
) -> None:
    """Install fs2 MCP server into a JSON config file."""
    config: dict = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            console.print(f"[red]✗[/red] Failed to read {config_path}: {e}")
            raise typer.Exit(code=1) from None

    servers = config.get("mcpServers", {})

    if FS2_MCP_KEY in servers:
        existing = servers[FS2_MCP_KEY]
        if (
            existing.get("command") == entry["command"]
            and existing.get("args") == entry["args"]
        ):
            console.print(
                f"[green]✓[/green] fs2 MCP server already configured in {label}"
            )
            return
        console.print(f"[yellow]![/yellow] Updating fs2 MCP server in {label}")

    servers[FS2_MCP_KEY] = entry
    config["mcpServers"] = servers

    config_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        config_path.write_text(
            json.dumps(config, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as e:
        console.print(f"[red]✗[/red] Failed to write {config_path}: {e}")
        raise typer.Exit(code=1) from None

    console.print(
        f"[green]✓[/green] fs2 MCP server added to {label}\n"
        f"  Config: {config_path}\n"
        "  Restart the agent to activate."
    )
