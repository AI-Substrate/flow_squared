"""fs2 init command implementation.

Creates the .fs2/config.yaml file with sensible defaults.
"""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

console = Console()

DEFAULT_CONFIG = """\
# fs2 configuration file
# See docs/how/scanning.md for all options

scan:
  # Directories to scan (relative to project root)
  scan_paths:
    - "."

  # Respect .gitignore patterns
  respect_gitignore: true

  # Maximum file size to parse (in KB)
  max_file_size_kb: 500

  # Follow symbolic links
  follow_symlinks: false
"""


def init(
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing config"),
    ] = False,
) -> None:
    """Initialize fs2 configuration for this project.

    Creates a .fs2/config.yaml file with sensible defaults.
    Run this before using `fs2 scan`.

    \b
    Example:
        $ fs2 init
        ✓ Created .fs2/config.yaml with defaults
    """
    config_dir = Path(".fs2")
    config_file = config_dir / "config.yaml"

    # Check if config already exists
    if config_file.exists() and not force:
        console.print(
            "[yellow]⚠[/yellow] Config already exists at .fs2/config.yaml\n"
            "  Use [bold]--force[/bold] to overwrite."
        )
        return

    # Create config directory if needed
    config_dir.mkdir(exist_ok=True)

    # Write default config
    config_file.write_text(DEFAULT_CONFIG)

    console.print(
        "[green]✓[/green] Created .fs2/config.yaml with defaults\n"
        "  Edit this file to customize scan settings.\n"
        "  Then run [bold]fs2 scan[/bold] to scan your codebase."
    )
