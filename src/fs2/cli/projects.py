"""fs2 project management CLI commands.

Commands:
- discover-projects: Detect language projects and show indexer status
- add-project: Add discovered projects to .fs2/config.yaml

Per Phase 3 dossier: no require_init guard (setup commands).
Follows list_graphs.py pattern (Rich table, JSON output, stderr errors).
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from fs2.core.services.project_discovery import (
    INDEXER_BINARIES,
    INDEXER_INSTALL,
    DiscoveredProject,
    detect_project_roots,
)

logger = logging.getLogger("fs2.cli.projects")

console = Console()
stderr_console = Console(stderr=True)

# Cache discovery results for add-project to reference by number
_last_discovered: list[DiscoveredProject] = []


def _check_indexer(language: str) -> tuple[str, str]:
    """Check if the SCIP indexer for a language is installed.

    Returns:
        (status_icon, install_hint) tuple.
    """
    binary = INDEXER_BINARIES.get(language)
    if binary is None:
        return "⚠️", "no SCIP indexer available"
    if shutil.which(binary) is not None:
        return "✅", ""
    install_cmd = INDEXER_INSTALL.get(language, f"install {binary}")
    return "❌", install_cmd


def _relative_path(project_path: str, base: Path) -> str:
    """Make project path relative to base, or return as-is."""
    try:
        return str(Path(project_path).relative_to(base))
    except ValueError:
        return project_path


def discover_projects(
    ctx: typer.Context,
    scan_path: Annotated[
        str | None,
        typer.Option(
            "--scan-path",
            help="Directory to scan (default: current directory)",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output JSON instead of table"),
    ] = False,
) -> None:
    """Discover language projects in the current directory.

    Walks the directory tree looking for project marker files
    (pyproject.toml, tsconfig.json, go.mod, .csproj, etc.)
    and shows indexer availability status.

    \\b
    Examples:
        $ fs2 discover-projects
        $ fs2 discover-projects --json
        $ fs2 discover-projects --scan-path /path/to/repo
    """
    global _last_discovered  # noqa: PLW0603

    root = Path(scan_path).resolve() if scan_path else Path.cwd().resolve()

    if not root.is_dir():
        stderr_console.print(f"[red]Not a directory: {root}[/red]")
        raise typer.Exit(code=1)

    projects = detect_project_roots(str(root))
    _last_discovered = projects

    if json_output:
        items = []
        for i, p in enumerate(projects, 1):
            status, hint = _check_indexer(p.language)
            binary = INDEXER_BINARIES.get(p.language, "")
            items.append({
                "number": i,
                "type": p.language,
                "path": _relative_path(p.path, root),
                "marker_file": p.marker_file,
                "indexer": binary,
                "indexer_installed": status == "✅",
                "install_hint": hint,
            })
        output = {"projects": items, "count": len(items)}
        print(json.dumps(output, indent=2))  # noqa: T201
        raise typer.Exit(code=0)

    if not projects:
        console.print("[yellow]No language projects detected.[/yellow]")
        console.print("Looking for: pyproject.toml, tsconfig.json, go.mod, .csproj, Gemfile, etc.")
        raise typer.Exit(code=0)

    table = Table(title="Discovered Projects")
    table.add_column("#", style="cyan", justify="right", no_wrap=True)
    table.add_column("Type", style="bold")
    table.add_column("Path", overflow="fold")
    table.add_column("Marker", style="dim")
    table.add_column("Indexer", justify="center")

    missing_indexers: list[tuple[str, str]] = []

    for i, p in enumerate(projects, 1):
        status, hint = _check_indexer(p.language)
        rel_path = _relative_path(p.path, root)
        if rel_path == str(root):
            rel_path = "."
        table.add_row(str(i), p.language, rel_path, p.marker_file, status)
        if hint:
            missing_indexers.append((p.language, hint))

    console.print(table)
    console.print(f"\nTotal: {len(projects)} project(s)")

    if missing_indexers:
        console.print("\n[yellow]Missing indexers:[/yellow]")
        seen = set()
        for lang, hint in missing_indexers:
            if lang not in seen:
                seen.add(lang)
                console.print(f"  {lang}: [dim]{hint}[/dim]")

    console.print(
        "\n[dim]Add projects to config:[/dim] "
        "[bold]fs2 add-project 1 2 3[/bold] [dim]or[/dim] [bold]fs2 add-project --all[/bold]"
    )


def add_project(
    ctx: typer.Context,
    numbers: Annotated[
        list[int] | None,
        typer.Argument(
            help="Project numbers from discover-projects output",
        ),
    ] = None,
    all_projects: Annotated[
        bool,
        typer.Option("--all", help="Add all discovered projects"),
    ] = False,
    scan_path: Annotated[
        str | None,
        typer.Option(
            "--scan-path",
            help="Directory to scan (default: current directory)",
        ),
    ] = None,
) -> None:
    """Add discovered projects to .fs2/config.yaml.

    Run `fs2 discover-projects` first to see available projects,
    then use project numbers to add specific ones.

    Uses comment-preserving YAML writes (ruamel.yaml).

    \\b
    Examples:
        $ fs2 add-project 1 2 3
        $ fs2 add-project --all
    """
    global _last_discovered  # noqa: PLW0603

    root = Path(scan_path).resolve() if scan_path else Path.cwd().resolve()

    # Re-discover if no cached results
    if not _last_discovered:
        _last_discovered = detect_project_roots(str(root))

    projects = _last_discovered

    if not projects:
        stderr_console.print("[yellow]No projects discovered. Run fs2 discover-projects first.[/yellow]")
        raise typer.Exit(code=1)

    # Determine which projects to add
    if all_projects:
        selected = projects
    elif numbers:
        selected = []
        for n in numbers:
            if n < 1 or n > len(projects):
                stderr_console.print(f"[red]Invalid project number: {n} (valid: 1-{len(projects)})[/red]")
                raise typer.Exit(code=1)
            selected.append(projects[n - 1])
    else:
        stderr_console.print("[red]Specify project numbers or --all[/red]")
        stderr_console.print("Run [bold]fs2 discover-projects[/bold] to see available projects.")
        raise typer.Exit(code=1)

    # Build entries
    config_path = root / ".fs2" / "config.yaml"

    from ruamel.yaml import YAML

    yaml = YAML()
    yaml.preserve_quotes = True  # type: ignore[assignment]

    if config_path.exists():
        with open(config_path) as f:
            data = yaml.load(f)
        if not isinstance(data, dict):
            data = {}
    else:
        data = {}

    # Ensure projects.entries exists
    if "projects" not in data:
        data["projects"] = {}
    if "entries" not in data["projects"] or data["projects"]["entries"] is None:
        data["projects"]["entries"] = []

    existing_entries = data["projects"]["entries"]

    # Build set of already-configured (type, path) pairs for idempotency
    existing_keys: set[tuple[str, str]] = set()
    for entry in existing_entries:
        if isinstance(entry, dict):
            existing_keys.add((entry.get("type", ""), entry.get("path", "")))

    added = 0
    skipped = 0
    for p in selected:
        rel_path = _relative_path(p.path, root)
        if rel_path == str(root):
            rel_path = "."
        key = (p.language, rel_path)
        if key in existing_keys:
            console.print(f"  [dim]Skipped (already in config):[/dim] {p.language} @ {rel_path}")
            skipped += 1
            continue

        entry = {"type": p.language, "path": rel_path}
        if p.marker_file not in _default_marker_for(p.language):
            entry["project_file"] = p.marker_file
        existing_entries.append(entry)
        existing_keys.add(key)
        console.print(f"  [green]Added:[/green] {p.language} @ {rel_path}")
        added += 1

    if added > 0:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            yaml.dump(data, f)
        console.print(f"\n[green]Wrote {added} project(s) to {config_path}[/green]")
    else:
        console.print(f"\n[dim]No new projects to add ({skipped} already in config)[/dim]")


def _default_marker_for(language: str) -> set[str]:
    """Return the primary/default marker files for a language."""
    from fs2.core.services.project_discovery import PROJECT_MARKERS

    markers = PROJECT_MARKERS.get(language, [])
    return {m for m in markers if "*" not in m}
