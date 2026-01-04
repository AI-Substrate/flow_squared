"""CLI guard decorator to require fs2 init before running commands.

Provides @require_init decorator that checks for .fs2/config.yaml
before allowing guarded commands to run.
"""

import functools
from collections.abc import Callable
from pathlib import Path

import typer
from rich.console import Console

console = Console()


def require_init[F: Callable](func: F) -> F:
    """Decorator that requires .fs2/config.yaml to exist before running.

    If config doesn't exist:
    - Shows current directory
    - Warns if no .git folder
    - Suggests running fs2 init
    - Exits with code 1

    If config exists:
    - Runs the decorated function normally

    Note: This must be applied BEFORE @app.command() so that --help still works.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        cwd = Path.cwd()
        config_file = cwd / ".fs2" / "config.yaml"

        # Check if config exists
        if not config_file.exists():
            console.print("[bold red]Error:[/bold red] No fs2 configuration found.\n")
            console.print(f"[bold]Current directory:[/bold] {cwd}\n")

            # Check for .git
            git_path = cwd / ".git"
            if not git_path.exists():
                console.print(
                    "[bold red]⚠ WARNING:[/bold red] No .git folder found!\n"
                    "  Are you sure this is a project root?\n"
                )

            console.print(
                "[bold]To initialize fs2:[/bold]\n"
                "  $ fs2 init\n"
                "\n"
                "This will create .fs2/config.yaml with defaults.\n"
            )
            raise typer.Exit(1)

        # Config exists, run the function
        return func(*args, **kwargs)

    return wrapper  # type: ignore
