"""Main CLI entry point for fs2.

Provides the Typer app instance with registered commands.
Commands:
- scan: Scan codebase and build code graph
- init: Initialize .fs2/config.yaml with defaults
- tree: Display code structure as hierarchical tree
"""

import typer

from fs2.cli.init import init
from fs2.cli.scan import scan
from fs2.cli.tree import tree

app = typer.Typer(
    name="fs2",
    help="Flowspace2 - Code intelligence for your codebase",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Flowspace2 - Code intelligence for your codebase."""
    pass


# Register commands
app.command(name="scan")(scan)
app.command(name="init")(init)
app.command(name="tree")(tree)
