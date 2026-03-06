"""Shared CLI utilities for fs2 commands.

Per Phase 1 save-to-file plan:
- validate_save_path(): Security function to prevent directory traversal
- safe_write_file(): File write helper with cleanup on error and UTF-8 encoding

Per Phase 4 multi-graph plan:
- resolve_graph_from_context(): Resolve graph from CLI context using GraphService

Per Phase 5 remote CLI:
- resolve_remote_client(): Resolve RemoteClient from CLIContext.remote
- resolve_remotes(): Parse comma-separated remote names/URLs into RemoteClient(s)

Per Insight #2: Wrap file writes in try/except, delete partial file on failure.
Per Insight #3: Always use encoding="utf-8" per JSON spec RFC 8259.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

if TYPE_CHECKING:
    from typing import Any

    from fs2.cli.remote_client import MultiRemoteClient, RemoteClient
    from fs2.config.service import ConfigurationService
    from fs2.core.repos.graph_store import GraphStore


def validate_save_path(file: Path, console: Console) -> Path:
    """Validate save path is under current working directory.

    Per Critical Finding 01: CLI must have same path validation as MCP.
    Mirrors logic from fs2.mcp.server._validate_save_path().

    Args:
        file: Path to validate (relative or absolute).
        console: Console for error output (should be stderr=True).

    Returns:
        Absolute path if valid.

    Raises:
        typer.Exit: If path escapes working directory (exit code 1).
    """
    cwd = Path.cwd().resolve()
    target = (cwd / file).resolve()

    # Check if target is under or equal to cwd
    try:
        target.relative_to(cwd)
    except ValueError:
        console.print(
            f"[red]Error:[/red] Path '{file}' escapes working directory. "
            "Only paths under the current directory are allowed."
        )
        raise typer.Exit(code=1) from None

    return target


def safe_write_file(path: Path, content: str, console: Console) -> None:
    """Write content to file with error cleanup and UTF-8 encoding.

    Per Insight #2: If write fails midway, delete partial file.
    Per Insight #3: Use encoding="utf-8" per JSON spec RFC 8259.
    Per AC10: Auto-create parent directories if needed.

    Args:
        path: Absolute path to write to.
        content: Content to write.
        console: Console for error output (should be stderr=True).

    Raises:
        typer.Exit: If write fails (exit code 1).
    """
    try:
        # Auto-create parent directories (AC10)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write with explicit UTF-8 encoding (Insight #3)
        path.write_text(content, encoding="utf-8")

    except OSError as e:
        # Cleanup partial file on error (Insight #2)
        if path.exists():
            with contextlib.suppress(OSError):
                path.unlink()

        console.print(f"[red]Error:[/red] Failed to write file: {e}")
        raise typer.Exit(code=1) from None


def resolve_graph_from_context(
    ctx: typer.Context,
) -> tuple[ConfigurationService, GraphStore]:
    """Resolve graph from CLI context using GraphService.

    Per DYK-01: Uses GraphService for all graph resolution.
    Per DYK-04: Provides actionable error messages.
    Per CF06: Centralized utility for consistent composition roots.

    Resolution order:
    1. --graph-file: Explicit path override (backward compat)
    2. --graph-name: Named graph from other_graphs config
    3. Neither: Default graph from GraphConfig.graph_path

    Args:
        ctx: Typer context with CLIContext as obj.

    Returns:
        Tuple of (ConfigurationService, GraphStore).

    Raises:
        typer.Exit(1): On unknown graph name or missing graph file.
    """
    from fs2.config.objects import GraphConfig
    from fs2.config.service import FS2ConfigurationService
    from fs2.core import dependencies
    from fs2.core.adapters.exceptions import GraphStoreError
    from fs2.core.repos.graph_store_impl import NetworkXGraphStore
    from fs2.core.services.graph_service import (
        GraphFileNotFoundError,
        UnknownGraphError,
    )

    # Create base configuration service
    config = FS2ConfigurationService()
    cli_ctx = ctx.obj

    # Case 1: Explicit graph file path (--graph-file)
    if cli_ctx and cli_ctx.graph_file:
        from pathlib import Path

        from fs2.core.adapters.exceptions import GraphStoreError as GraphStoreErr

        # Override GraphConfig to use explicit path
        config.set(GraphConfig(graph_path=cli_ctx.graph_file))
        store = NetworkXGraphStore(config)

        # Load the graph (GraphService does this for named graphs, so we do it here too)
        graph_path = Path(cli_ctx.graph_file)
        if not graph_path.exists():
            console = Console(stderr=True)
            console.print(
                f"[red]Error:[/red] Graph file not found: {graph_path}\n"
                "  Run [bold]fs2 scan[/bold] to create the graph."
            )
            raise typer.Exit(code=1) from None

        try:
            store.load(graph_path)
        except GraphStoreErr as e:
            # Exit code 2 for graph corruption
            console = Console(stderr=True)
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(code=2) from None

        return config, store

    # Case 2 & 3: Use GraphService for named or default graph
    try:
        # Get or create GraphService (uses global singleton from dependencies)
        dependencies.set_config(config)
        service = dependencies.get_graph_service()

        # Determine graph name
        graph_name = cli_ctx.graph_name if cli_ctx and cli_ctx.graph_name else "default"

        # Get the graph store via service
        store = service.get_graph(graph_name)
        return config, store

    except UnknownGraphError as e:
        # Per DYK-04: Actionable error with available graphs
        console = Console(stderr=True)
        console.print(f"[red]Error:[/red] {e}")
        console.print(
            "\n[dim]Hint: Check your .fs2/config.yaml other_graphs section.[/dim]"
        )
        raise typer.Exit(code=1) from None

    except GraphFileNotFoundError as e:
        # Per DYK-04: Actionable error with fix instructions
        console = Console(stderr=True)
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None

    except GraphStoreError as e:
        # Exit code 2 for graph corruption (file exists but is corrupted)
        console = Console(stderr=True)
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=2) from None


def resolve_remote_client(
    ctx: typer.Context,
) -> RemoteClient | MultiRemoteClient | None:
    """Resolve remote client from CLIContext.remote.

    Per DYK #4: Does NOT modify resolve_graph_from_context().
    CLI commands check this first and branch early.

    Args:
        ctx: Typer context with CLIContext as obj.

    Returns:
        RemoteClient for single remote, MultiRemoteClient for comma-separated,
        or None if not in remote mode.
    """
    cli_ctx = ctx.obj
    if not cli_ctx or not cli_ctx.remote:
        return None

    clients = resolve_remotes(cli_ctx.remote)
    if len(clients) == 1:
        return clients[0]
    from fs2.cli.remote_client import MultiRemoteClient as _MultiRemoteClient

    return _MultiRemoteClient(clients)


def resolve_remotes(remote_str: str) -> list[RemoteClient]:
    """Parse remote string into RemoteClient instances.

    Supports:
    - Named remote: "work" → look up in RemotesConfig
    - Inline URL: "http://localhost:8000" → use directly
    - Comma-separated: "work,oss" → multiple clients

    Args:
        remote_str: Comma-separated remote names or URLs.

    Returns:
        List of RemoteClient instances.

    Raises:
        typer.Exit(1): If named remote not found in config.
    """
    from fs2.cli.remote_client import RemoteClient
    from fs2.config.objects import RemotesConfig
    from fs2.config.service import FS2ConfigurationService

    parts = [p.strip() for p in remote_str.split(",") if p.strip()]
    if not parts:
        console = Console(stderr=True)
        console.print("[red]Error:[/red] --remote value cannot be empty")
        raise typer.Exit(code=1)

    # Load remotes config (may be None if not configured)
    config = FS2ConfigurationService()
    remotes_config = config.get(RemotesConfig)
    servers_by_name: dict[str, Any] = {}
    if remotes_config:
        for server in remotes_config.servers:
            servers_by_name[server.name] = server

    clients: list[RemoteClient] = []
    for part in parts:
        if part.startswith(("http://", "https://")):
            # Inline URL
            clients.append(RemoteClient(base_url=part, name=part))
        elif part in servers_by_name:
            # Named remote from config
            server = servers_by_name[part]
            clients.append(
                RemoteClient(
                    base_url=server.url,
                    api_key=server.api_key,
                    name=server.name,
                )
            )
        else:
            # Unknown name
            console = Console(stderr=True)
            available = list(servers_by_name.keys()) if servers_by_name else []
            if available:
                console.print(
                    f"[red]Error:[/red] Unknown remote '{part}'. "
                    f"Available remotes: {', '.join(sorted(available))}\n"
                    "  Configure remotes in ~/.config/fs2/config.yaml or .fs2/config.yaml"
                )
            else:
                console.print(
                    f"[red]Error:[/red] Unknown remote '{part}'. "
                    "No remotes configured.\n"
                    "  Add remotes to ~/.config/fs2/config.yaml:\n"
                    "    remotes:\n"
                    "      servers:\n"
                    f'        - name: "{part}"\n'
                    f'          url: "https://your-server.example.com"'
                )
            raise typer.Exit(code=1)

    return clients
