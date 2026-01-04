"""Main CLI entry point for fs2.

Provides the Typer app instance with registered commands.
Commands:
- scan: Scan codebase and build code graph
- init: Initialize .fs2/config.yaml with defaults
- tree: Display code structure as hierarchical tree
- get-node: Retrieve a single node by ID as JSON
- install: Install fs2 permanently via uv tool
- upgrade: Upgrade fs2 (alias for install)

Global Options:
- --graph-file: Override graph file path (applies to all graph commands)
- --version: Show version and exit
"""

from dataclasses import dataclass
from typing import Annotated

import typer

from fs2.cli.doctor import doctor_app
from fs2.cli.get_node import get_node
from fs2.cli.guard import require_init
from fs2.cli.init import init
from fs2.cli.install import get_version_string, install, upgrade
from fs2.cli.mcp import mcp
from fs2.cli.scan import scan
from fs2.cli.search import search
from fs2.cli.tree import tree


@dataclass
class CLIContext:
    """Context object for passing global options to subcommands."""

    graph_file: str | None = None


def _version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        print(get_version_string())  # noqa: T201
        raise typer.Exit()


app = typer.Typer(
    name="fs2",
    help="Flowspace2 - Code intelligence for your codebase",
    no_args_is_help=True,
)


@app.callback()
def main(
    ctx: typer.Context,
    graph_file: Annotated[
        str | None,
        typer.Option(
            "--graph-file",
            help="Graph file path (overrides config). Default: .fs2/graph.pickle",
        ),
    ] = None,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-V",
            help="Show version and exit",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """Flowspace2 - Code intelligence for your codebase."""
    ctx.obj = CLIContext(graph_file=graph_file)


# Register commands
# Commands that require init (guarded)
app.command(name="scan")(require_init(scan))
app.command(name="tree")(require_init(tree))
app.command(name="get-node")(require_init(get_node))
app.command(name="search")(require_init(search))
app.command(name="mcp")(require_init(mcp))

# Commands that always work (not guarded)
app.command(name="init")(init)
app.add_typer(doctor_app, name="doctor")  # Command group with subcommands
app.command(name="install")(install)
app.command(name="upgrade")(upgrade)


if __name__ == "__main__":
    app()
