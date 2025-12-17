"""fs2 scan command implementation.

Orchestrates the ScanPipeline to scan a codebase and build the code graph.
Displays progress feedback and summary output.
"""

import logging
import sys
from typing import Annotated

import typer
from rich.console import Console
from rich.logging import RichHandler

from fs2.config.exceptions import MissingConfigurationError
from fs2.config.service import FS2ConfigurationService
from fs2.core.adapters import FileSystemScanner, TreeSitterParser
from fs2.core.repos import NetworkXGraphStore
from fs2.core.services import ScanPipeline

console = Console()
logger = logging.getLogger("fs2.cli.scan")

# Progress threshold (files) - show spinner for large scans
PROGRESS_THRESHOLD = 50


def scan(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show detailed per-file output"),
    ] = False,
    no_progress: Annotated[
        bool,
        typer.Option("--no-progress", help="Disable progress spinner"),
    ] = False,
    progress: Annotated[
        bool,
        typer.Option("--progress", help="Force progress spinner even in non-TTY"),
    ] = False,
) -> None:
    """Scan the codebase and build the code graph.

    Walks configured directories, parses source files with tree-sitter,
    and stores the resulting code structure in a graph.

    \b
    Example:
        $ fs2 scan
        ✓ Scanned 50 files, created 200 nodes
          Graph saved to .fs2/graph.pickle

    \b
    Verbose mode:
        $ fs2 scan --verbose
        Discovering files...
        Parsing src/main.py...
        Parsing src/utils.py...
        ✓ Scanned 2 files, created 10 nodes
    """
    # Configure logging for verbose mode
    if verbose:
        _setup_verbose_logging()

    # Determine if progress should be shown (for future progress bar)
    show_progress = _should_show_progress(no_progress, progress)  # noqa: F841

    try:
        # Load configuration
        config = FS2ConfigurationService()

        # Create adapters
        file_scanner = FileSystemScanner(config)
        ast_parser = TreeSitterParser(config)
        graph_store = NetworkXGraphStore(config)

        # Create and run pipeline
        pipeline = ScanPipeline(
            config=config,
            file_scanner=file_scanner,
            ast_parser=ast_parser,
            graph_store=graph_store,
        )

        # Show discovery phase if verbose
        if verbose:
            console.print("Discovering files...")

        summary = pipeline.run()

        # Display output
        _display_summary(summary, verbose=verbose)

        # Check for total failure (all files errored)
        if summary.files_scanned > 0 and len(summary.errors) >= summary.files_scanned:
            raise typer.Exit(code=2)

    except MissingConfigurationError:
        console.print(
            "[red]Error:[/red] No configuration found.\n"
            "  Run [bold]fs2 init[/bold] first to create .fs2/config.yaml"
        )
        raise typer.Exit(code=1) from None


def _setup_verbose_logging() -> None:
    """Configure logging for verbose mode with Rich output."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_path=False, rich_tracebacks=True)],
    )


def _should_show_progress(no_progress: bool, force_progress: bool) -> bool:
    """Determine if progress spinner should be shown.

    Priority: CLI args > env vars > TTY detection
    """
    import os

    # CLI flags take highest priority
    if no_progress:
        return False
    if force_progress:
        return True

    # Check env var
    env_no_progress = os.environ.get("FS2_SCAN__NO_PROGRESS", "").lower()
    if env_no_progress in ("true", "1", "yes"):
        return False

    # Default to TTY detection
    return sys.stdout.isatty()


def _display_summary(summary, verbose: bool = False) -> None:
    """Display scan summary to user.

    Args:
        summary: ScanSummary from pipeline run.
        verbose: Whether to show detailed output.
    """
    # Determine success indicator
    if summary.success:
        indicator = "[green]✓[/green]"
    elif summary.errors:
        indicator = "[yellow]⚠[/yellow]"
    else:
        indicator = "[red]✗[/red]"

    # Main summary line
    file_word = "file" if summary.files_scanned == 1 else "files"
    node_word = "node" if summary.nodes_created == 1 else "nodes"

    if summary.errors:
        error_count = len(summary.errors)
        error_word = "error" if error_count == 1 else "errors"
        console.print(
            f"{indicator} Scanned {summary.files_scanned} {file_word}, "
            f"created {summary.nodes_created} {node_word} "
            f"({error_count} {error_word})"
        )
        # Show error details in verbose mode
        if verbose:
            for error in summary.errors:
                console.print(f"  [dim]- {error}[/dim]")
    else:
        console.print(
            f"{indicator} Scanned {summary.files_scanned} {file_word}, "
            f"created {summary.nodes_created} {node_word}"
        )

    # Graph location
    console.print("  Graph saved to .fs2/graph.pickle")
