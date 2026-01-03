"""fs2 init command implementation.

Creates both local .fs2/config.yaml and global ~/.config/fs2/ configuration
in a single command. Shows current directory, warns if no .git folder,
and creates .gitignore to protect secrets.
"""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from fs2.config.paths import get_user_config_dir

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

# .gitignore for .fs2 directory - ignores everything except config.yaml
FS2_GITIGNORE = """\
# Ignore everything in .fs2/ except config.yaml
*
!.gitignore
!config.yaml
"""


def init(
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing local config"),
    ] = False,
) -> None:
    """Initialize fs2 configuration for this project.

    Creates both local (.fs2/) and global (~/.config/fs2/) configuration.
    Global config is created only if it doesn't exist.

    \b
    Example:
        $ fs2 init
        Current directory: /path/to/project
        ✓ Created local config at .fs2/config.yaml
        ✓ Created global config at ~/.config/fs2/
    """
    cwd = Path.cwd()
    local_config_dir = cwd / ".fs2"
    local_config_file = local_config_dir / "config.yaml"
    local_gitignore = local_config_dir / ".gitignore"

    global_config_dir = get_user_config_dir()
    global_config_file = global_config_dir / "config.yaml"

    # Show current directory
    console.print(f"[bold]Current directory:[/bold] {cwd}")
    console.print()

    # Check for .git (file or directory - supports worktrees)
    git_path = cwd / ".git"
    if not git_path.exists():
        console.print(
            "[bold red]⚠ WARNING:[/bold red] No .git folder found!\n"
            "  Are you sure this is a project root?\n"
        )

    # Track what we did
    actions = []

    # === Handle global config ===
    if global_config_file.exists():
        actions.append(f"Skipped global config (already exists at {global_config_dir})")
    else:
        # Create global config directory and file
        global_config_dir.mkdir(parents=True, exist_ok=True)
        global_config_file.write_text(DEFAULT_CONFIG)
        actions.append(f"Created global config at {global_config_dir}")

    # === Handle local config ===
    if local_config_file.exists() and not force:
        console.print(
            "[yellow]⚠[/yellow] Local config already exists at .fs2/config.yaml\n"
            "  Use [bold]--force[/bold] to overwrite."
        )
        # Still report global action
        for action in actions:
            if "global" in action.lower():
                console.print(f"[dim]{action}[/dim]")
        return

    # Create local config directory if needed
    local_config_dir.mkdir(exist_ok=True)

    # Write local config
    local_config_file.write_text(DEFAULT_CONFIG)
    actions.append("Created local config at .fs2/config.yaml")

    # Create .gitignore in .fs2/
    local_gitignore.write_text(FS2_GITIGNORE)
    actions.append("Created .fs2/.gitignore")

    # Report all actions
    console.print("[bold]Actions:[/bold]")
    for action in actions:
        if action.startswith("Skipped"):
            console.print(f"  [dim]• {action}[/dim]")
        else:
            console.print(f"  [green]✓[/green] {action}")

    console.print()
    console.print(
        "  Edit .fs2/config.yaml to customize scan settings.\n"
        "  Then run [bold]fs2 scan[/bold] to scan your codebase."
    )
