"""Main CLI entry point for fs2.

Provides the Typer app instance with registered commands.
Commands:
- scan: Scan codebase and build code graph
- init: Initialize .fs2/config.yaml with defaults
- tree: Display code structure as hierarchical tree
- get-node: Retrieve a single node by ID as JSON

Global Options:
- --graph-file: Override graph file path (applies to all graph commands)
"""

from dataclasses import dataclass
from typing import Annotated

import typer

from fs2.cli.get_node import get_node
from fs2.cli.init import init
from fs2.cli.mcp import mcp
from fs2.cli.scan import scan
from fs2.cli.search import search
from fs2.cli.tree import tree


@dataclass
class CLIContext:
    """Context object for passing global options to subcommands."""

    graph_file: str | None = None


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
) -> None:
    """Flowspace2 - Code intelligence for your codebase."""
    ctx.obj = CLIContext(graph_file=graph_file)


# Register commands
app.command(name="scan")(scan)
app.command(name="init")(init)
app.command(name="tree")(tree)
app.command(name="get-node")(get_node)
app.command(name="search")(search)
app.command(name="mcp")(mcp)


if __name__ == "__main__":
    app()
