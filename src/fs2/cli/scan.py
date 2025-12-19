"""fs2 scan command implementation.

Orchestrates the ScanPipeline to scan a codebase and build the code graph.
Displays progress feedback and summary output using Rich.

Per Phase 6 (Scan Pipeline Integration):
- Supports --no-smart-content flag to skip AI enrichment
- Shows smart content statistics in summary (enriched, preserved, errors)
- Shows clear stage banners with Rich formatting
"""

import logging
import sys
from typing import Annotated

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.rule import Rule

from fs2.config.exceptions import MissingConfigurationError
from fs2.config.service import FS2ConfigurationService
from fs2.core.adapters import FileSystemScanner, TreeSitterParser
from fs2.core.repos import NetworkXGraphStore
from fs2.core.services import ScanPipeline

console = Console()
logger = logging.getLogger("fs2.cli.scan")


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
    no_smart_content: Annotated[
        bool,
        typer.Option(
            "--no-smart-content",
            help="Skip AI-powered smart content generation (faster scans)",
        ),
    ] = False,
) -> None:
    """Scan the codebase and build the code graph.

    Walks configured directories, parses source files with tree-sitter,
    and stores the resulting code structure in a graph.

    When LLM is configured, also generates AI-powered smart content
    (summaries) for each code node. Use --no-smart-content to skip.
    """
    # Configure logging for verbose mode
    if verbose:
        _setup_verbose_logging()

    try:
        # ===== STAGE 1: CONFIGURATION =====
        console.print()
        console.print(Rule("[bold cyan]CONFIGURATION[/bold cyan]", style="cyan"))

        config = FS2ConfigurationService()
        console.print("  [green]✓[/green] Loaded .fs2/config.yaml")

        # Create SmartContentService if LLM is configured and not disabled
        smart_content_service = None
        smart_content_status = "disabled"

        if no_smart_content:
            smart_content_status = "skipped (--no-smart-content)"
            console.print(f"  [dim]Smart content: {smart_content_status}[/dim]")
        else:
            smart_content_service, smart_content_status = _create_smart_content_service(
                config
            )
            if smart_content_service:
                console.print("  [green]✓[/green] Smart content: [green]enabled[/green]")
            else:
                console.print(f"  [yellow]![/yellow] Smart content: [dim]{smart_content_status}[/dim]")

        # ===== STAGE 2: FILE DISCOVERY =====
        console.print()
        console.print(Rule("[bold cyan]DISCOVERY[/bold cyan]", style="cyan"))

        file_scanner = FileSystemScanner(config)
        ast_parser = TreeSitterParser(config)
        graph_store = NetworkXGraphStore(config)

        # Create pipeline
        pipeline = ScanPipeline(
            config=config,
            file_scanner=file_scanner,
            ast_parser=ast_parser,
            graph_store=graph_store,
            smart_content_service=smart_content_service,
        )

        # ===== STAGE 3: PARSING =====
        console.print()
        console.print(Rule("[bold cyan]PARSING[/bold cyan]", style="cyan"))

        # Run the pipeline
        summary = pipeline.run()

        console.print(f"  [green]✓[/green] Scanned {summary.files_scanned} files")
        console.print(f"  [green]✓[/green] Created {summary.nodes_created} nodes")

        # ===== STAGE 4: SMART CONTENT =====
        if smart_content_service:
            console.print()
            console.print(Rule("[bold cyan]SMART CONTENT[/bold cyan]", style="cyan"))

            enriched = summary.metrics.get("smart_content_enriched", 0)
            preserved = summary.metrics.get("smart_content_preserved", 0)
            errors = summary.metrics.get("smart_content_errors", 0)

            if enriched > 0:
                console.print(f"  [green]✓[/green] Enriched: [green]{enriched}[/green] nodes")
            if preserved > 0:
                console.print(f"  [blue]↻[/blue] Preserved: [blue]{preserved}[/blue] nodes (unchanged)")
            if errors > 0:
                console.print(f"  [yellow]![/yellow] Errors: [yellow]{errors}[/yellow] nodes")
        elif not no_smart_content:
            console.print()
            console.print(Rule("[dim]SMART CONTENT (skipped)[/dim]", style="dim"))
            console.print(f"  [dim]{smart_content_status}[/dim]")

        # ===== STAGE 5: STORAGE =====
        console.print()
        console.print(Rule("[bold cyan]STORAGE[/bold cyan]", style="cyan"))
        console.print("  [green]✓[/green] Graph saved to .fs2/graph.pickle")

        # ===== SUMMARY =====
        console.print()
        _display_final_summary(summary, smart_content_service is not None)

        # Check for total failure
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


def _display_final_summary(summary, smart_content_enabled: bool) -> None:
    """Display final summary panel."""
    if summary.success:
        status = "[green]SUCCESS[/green]"
    elif summary.errors:
        status = "[yellow]COMPLETED WITH ERRORS[/yellow]"
    else:
        status = "[red]FAILED[/red]"

    lines = [
        f"Status: {status}",
        f"Files: {summary.files_scanned}",
        f"Nodes: {summary.nodes_created}",
    ]

    if smart_content_enabled:
        enriched = summary.metrics.get("smart_content_enriched", 0)
        preserved = summary.metrics.get("smart_content_preserved", 0)
        errors = summary.metrics.get("smart_content_errors", 0)
        lines.append(f"Smart Content: {enriched} enriched, {preserved} preserved, {errors} errors")

    if summary.errors:
        lines.append(f"Errors: {len(summary.errors)}")

    console.print(Panel(
        "\n".join(lines),
        title="[bold]Scan Complete[/bold]",
        border_style="green" if summary.success else "yellow",
    ))


def _create_smart_content_service(config):
    """Create SmartContentService if LLM is configured.

    Returns:
        Tuple of (service, status_string).
        service is None if not configured.
        status_string describes what happened.
    """
    from fs2.config.objects import LLMConfig, SmartContentConfig

    # Check if LLM is configured
    try:
        llm_config = config.require(LLMConfig)
    except MissingConfigurationError:
        return None, "not configured (no llm section in config.yaml)"

    # Check if SmartContentConfig exists
    try:
        config.require(SmartContentConfig)
    except MissingConfigurationError:
        return None, "not configured (no smart_content section in config.yaml)"

    # Check if provider is set
    if not llm_config.provider:
        return None, "not configured (no provider set)"

    # Try to create the service
    try:
        from fs2.core.adapters.llm_adapter_azure import AzureOpenAIAdapter
        from fs2.core.adapters.token_counter_adapter_tiktoken import (
            TiktokenTokenCounterAdapter,
        )
        from fs2.core.services.llm_service import LLMService
        from fs2.core.services.smart_content.smart_content_service import (
            SmartContentService,
        )
        from fs2.core.services.smart_content.template_service import TemplateService

        # Create adapter based on provider
        if llm_config.provider == "azure":
            llm_adapter = AzureOpenAIAdapter(config)
        elif llm_config.provider == "fake":
            from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
            llm_adapter = FakeLLMAdapter()
        else:
            return None, f"unsupported provider: {llm_config.provider}"

        llm_service = LLMService(config, llm_adapter)
        template_service = TemplateService(config)
        token_counter = TiktokenTokenCounterAdapter(config)

        service = SmartContentService(
            config=config,
            llm_service=llm_service,
            template_service=template_service,
            token_counter=token_counter,
        )

        return service, "enabled"

    except Exception as e:
        # Show the actual error - no silent failures!
        error_msg = str(e)
        if len(error_msg) > 100:
            error_msg = error_msg[:100] + "..."
        console.print(f"  [yellow]Warning:[/yellow] {error_msg}")
        return None, f"error: {type(e).__name__}"
