"""fs2 scan command implementation.

Orchestrates the ScanPipeline to scan a codebase and build the code graph.
Displays progress feedback and summary output using ConsoleAdapter.

Per Phase 6 (Scan Pipeline Integration):
- Supports --no-smart-content flag to skip AI enrichment
- Shows smart content statistics in summary (enriched, preserved, errors)
- Shows clear stage banners with Rich formatting

Per Clean Architecture:
- Uses ConsoleAdapter ABC for all console output (no direct Rich usage)
- CLI layer creates RichConsoleAdapter and passes to helpers
"""

import logging
import sys
from typing import Annotated

import typer
from rich.logging import RichHandler

from fs2.config.exceptions import MissingConfigurationError
from fs2.config.service import FS2ConfigurationService
from fs2.core.adapters import FileSystemScanner, RichConsoleAdapter, TreeSitterParser
from fs2.core.adapters.console_adapter import ConsoleAdapter
from fs2.core.repos import NetworkXGraphStore
from fs2.core.services import ScanPipeline

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
    # Create console adapter (injectable for testing)
    console: ConsoleAdapter = RichConsoleAdapter()

    # Configure logging for verbose mode
    if verbose:
        _setup_verbose_logging()

    try:
        # ===== STAGE 1: CONFIGURATION =====
        console.stage_banner("CONFIGURATION")

        config = FS2ConfigurationService()
        console.print_success("Loaded .fs2/config.yaml")

        # Create SmartContentService if LLM is configured and not disabled
        smart_content_service = None
        smart_content_status = "disabled"

        if no_smart_content:
            smart_content_status = "skipped (--no-smart-content)"
            console.print_info(f"Smart content: {smart_content_status}")
        else:
            smart_content_service, smart_content_status = _create_smart_content_service(
                config, console
            )
            if smart_content_service:
                console.print_success("Smart content: enabled")
            else:
                console.print_warning(f"Smart content: {smart_content_status}")

        # ===== STAGE 2: FILE DISCOVERY =====
        console.stage_banner("DISCOVERY")

        file_scanner = FileSystemScanner(config)
        ast_parser = TreeSitterParser(config)
        graph_store = NetworkXGraphStore(config)

        # Create progress callback for smart content (uses console adapter)
        def smart_content_progress(progress, error_message):
            """Display smart content progress using console adapter."""
            if error_message:
                console.print_error(error_message)
            else:
                console.print_progress(
                    f"Progress: {progress.processed}/{progress.total} processed, "
                    f"{progress.remaining} remaining"
                )

        # Create pipeline
        pipeline = ScanPipeline(
            config=config,
            file_scanner=file_scanner,
            ast_parser=ast_parser,
            graph_store=graph_store,
            smart_content_service=smart_content_service,
            smart_content_progress_callback=smart_content_progress if smart_content_service else None,
        )

        # ===== STAGE 3: PARSING =====
        console.stage_banner("PARSING")

        # Run the pipeline
        summary = pipeline.run()

        console.print_success(f"Scanned {summary.files_scanned} files")
        console.print_success(f"Created {summary.nodes_created} nodes")

        # ===== STAGE 4: SMART CONTENT =====
        if smart_content_service:
            console.stage_banner("SMART CONTENT")

            enriched = summary.metrics.get("smart_content_enriched", 0)
            preserved = summary.metrics.get("smart_content_preserved", 0)
            errors = summary.metrics.get("smart_content_errors", 0)

            if enriched > 0:
                console.print_success(f"Enriched: {enriched} nodes")
            if preserved > 0:
                console.print_progress(f"Preserved: {preserved} nodes (unchanged)")
            if errors > 0:
                console.print_error(f"Errors: {errors} nodes")
        elif not no_smart_content:
            console.stage_banner_skipped("SMART CONTENT")
            console.print_info(smart_content_status)

        # ===== STAGE 5: STORAGE =====
        console.stage_banner("STORAGE")
        console.print_success("Graph saved to .fs2/graph.pickle")

        # ===== SUMMARY =====
        console.print_line()
        _display_final_summary(console, summary, smart_content_service is not None)

        # Check for total failure
        if summary.files_scanned > 0 and len(summary.errors) >= summary.files_scanned:
            raise typer.Exit(code=2)

    except MissingConfigurationError:
        console.print_error(
            "No configuration found. Run 'fs2 init' first to create .fs2/config.yaml"
        )
        raise typer.Exit(code=1) from None


def _setup_verbose_logging() -> None:
    """Configure logging for verbose mode with Rich output."""
    from rich.console import Console

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(message)s",
        handlers=[
            RichHandler(console=Console(), show_path=False, rich_tracebacks=True)
        ],
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


def _display_final_summary(
    console: ConsoleAdapter, summary, smart_content_enabled: bool
) -> None:
    """Display final summary panel."""
    if summary.success:
        status = "SUCCESS"
    elif summary.errors:
        status = "COMPLETED WITH ERRORS"
    else:
        status = "FAILED"

    lines = [
        f"Status: {status}",
        f"Files: {summary.files_scanned}",
        f"Nodes: {summary.nodes_created}",
    ]

    if smart_content_enabled:
        enriched = summary.metrics.get("smart_content_enriched", 0)
        preserved = summary.metrics.get("smart_content_preserved", 0)
        errors = summary.metrics.get("smart_content_errors", 0)
        lines.append(
            f"Smart Content: {enriched} enriched, {preserved} preserved, {errors} errors"
        )

    if summary.errors:
        lines.append(f"Errors: {len(summary.errors)}")

    console.panel(
        "\n".join(lines),
        title="Scan Complete",
        success=summary.success,
    )


def _create_smart_content_service(config, console: ConsoleAdapter):
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
        console.print_warning(f"Smart content setup error: {error_msg}")
        return None, f"error: {type(e).__name__}"
