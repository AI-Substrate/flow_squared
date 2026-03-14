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

Per Phase 0 (Subtask 001):
- Accepts global --graph-file option via context for custom output paths
- Accepts --scan-path option to override scan directories
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.logging import RichHandler

from fs2.config.exceptions import MissingConfigurationError
from fs2.config.objects import GraphConfig, ScanConfig
from fs2.config.service import FS2ConfigurationService
from fs2.core.adapters import FileSystemScanner, RichConsoleAdapter, TreeSitterParser
from fs2.core.adapters.console_adapter import ConsoleAdapter
from fs2.core.repos import NetworkXGraphStore
from fs2.core.services import GraphUtilitiesService, ScanPipeline

logger = logging.getLogger("fs2.cli.scan")


def scan(
    ctx: typer.Context,
    scan_path: Annotated[
        list[str] | None,
        typer.Option(
            "--scan-path",
            help="Directory to scan (repeatable, overrides config). Supports relative and absolute paths.",
        ),
    ] = None,
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
    no_embeddings: Annotated[
        bool,
        typer.Option(
            "--no-embeddings",
            help="Skip embedding generation (faster scans)",
        ),
    ] = False,
    no_cross_refs: Annotated[
        bool,
        typer.Option(
            "--no-cross-refs",
            help="Skip cross-file relationship extraction",
        ),
    ] = False,
    cross_refs_instances: Annotated[
        int | None,
        typer.Option(
            "--cross-refs-instances",
            help="Number of parallel Serena instances (default: 20)",
        ),
    ] = None,
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

        # Per Subtask 001: Get graph_file from global option via context
        # Always resolve to a Path - use CLI flag or GraphConfig default
        if ctx.obj and ctx.obj.graph_file:
            graph_path = Path(ctx.obj.graph_file)
            # Create parent directories if they don't exist (per DYK-04)
            graph_path.parent.mkdir(parents=True, exist_ok=True)
            # Override GraphConfig in config service
            config.set(GraphConfig(graph_path=str(graph_path)))
            console.print_info(f"Graph file: {graph_path}")
        else:
            # Use default from GraphConfig
            graph_config = config.get(GraphConfig) or GraphConfig()
            graph_path = Path(graph_config.graph_path)
            graph_path.parent.mkdir(parents=True, exist_ok=True)
            # Ensure GraphConfig is in registry for GraphUtilitiesService
            config.set(graph_config)

        # Per Subtask 001 (ST002): Override scan_paths if --scan-path provided
        # Path validation happens in FileSystemScanner (per DYK-05 Clean Architecture)
        if scan_path:
            # Get existing ScanConfig to preserve other settings
            existing_scan_config = config.get(ScanConfig) or ScanConfig()
            # Override scan_paths with CLI values
            updated_scan_config = ScanConfig(
                scan_paths=scan_path,
                ignore_patterns=existing_scan_config.ignore_patterns,
                max_file_size_kb=existing_scan_config.max_file_size_kb,
                respect_gitignore=existing_scan_config.respect_gitignore,
                follow_symlinks=existing_scan_config.follow_symlinks,
                sample_lines_for_large_files=existing_scan_config.sample_lines_for_large_files,
            )
            config.set(updated_scan_config)
            if len(scan_path) == 1:
                console.print_info(f"Scan path: {scan_path[0]}")
            else:
                console.print_info(f"Scan paths: {', '.join(scan_path)}")

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

        # Create EmbeddingService if configured and not disabled
        embedding_service = None
        embedding_status = "disabled"

        if no_embeddings:
            embedding_status = "skipped (--no-embeddings)"
            console.print_info(f"Embeddings: {embedding_status}")
        else:
            embedding_service, embedding_status = _create_embedding_service(
                config, console
            )
            if embedding_service:
                console.print_success("Embeddings: enabled")
            else:
                console.print_warning(f"Embeddings: {embedding_status}")

        # ===== STAGE 2: FILE DISCOVERY =====
        console.stage_banner("DISCOVERY")

        file_scanner = FileSystemScanner(config)
        ast_parser = TreeSitterParser(config)
        graph_store = NetworkXGraphStore(config)

        # Track which stage banners have been shown during pipeline run
        smart_content_banner_shown = False
        embedding_banner_shown = False

        # Create progress callback for smart content (uses console adapter)
        def smart_content_progress(progress, error_message):
            """Display smart content progress using console adapter."""
            nonlocal smart_content_banner_shown
            if not smart_content_banner_shown:
                console.stage_banner("SMART CONTENT")
                smart_content_banner_shown = True

            if error_message:
                console.print_error(error_message)
            else:
                total = progress.total or 0
                pct = (progress.processed / total * 100.0) if total else 0.0
                console.print_progress(
                    f"Smart content: {progress.processed}/{progress.total} ({pct:.1f}%) processed, "
                    f"{progress.remaining} remaining"
                )

        def embedding_progress(processed, total, skipped):
            """Display embedding progress using console adapter."""
            nonlocal embedding_banner_shown
            if not embedding_banner_shown:
                console.stage_banner("EMBEDDINGS")
                embedding_banner_shown = True

            pct = (processed / total * 100.0) if total else 0.0
            console.print_progress(
                f"Embeddings: {processed}/{total} ({pct:.1f}%) processed, {skipped} skipped"
            )

        def parsing_progress(processed, total):
            """Display parsing progress using console adapter."""
            pct = (processed / total * 100.0) if total else 0.0
            console.print_progress(f"Parsing: {processed}/{total} files ({pct:.1f}%)")

        def parsing_complete(files_scanned, nodes_created, skip_summary):
            """Display parsing summary before next stage starts."""
            console.print_success(f"Scanned {files_scanned} files")
            console.print_success(f"Created {nodes_created} nodes")
            # Always show skip summary (even if zero)
            if skip_summary:
                skip_parts = [
                    f"{count} {ext}"
                    for ext, count in sorted(skip_summary.items(), key=lambda x: -x[1])
                ]
                console.print_info(f"Skipped: {', '.join(skip_parts)}")
            else:
                console.print_info("Skipped: 0")

        # Create pipeline
        pipeline = ScanPipeline(
            config=config,
            file_scanner=file_scanner,
            ast_parser=ast_parser,
            graph_store=graph_store,
            smart_content_service=smart_content_service,
            smart_content_progress_callback=smart_content_progress
            if smart_content_service
            else None,
            embedding_service=embedding_service,
            embedding_progress_callback=embedding_progress
            if embedding_service
            else None,
            parsing_progress_callback=parsing_progress,
            parsing_complete_callback=parsing_complete,
            graph_path=graph_path,  # Per Subtask 001: Custom output path
        )

        # ===== STAGE 3: PARSING =====
        console.stage_banner("PARSING")

        # Run the pipeline (callbacks show progress and banners during execution)
        summary = pipeline.run()

        # ===== STAGE 4: SMART CONTENT (summary after pipeline) =====
        if smart_content_service:
            # Banner already shown by progress callback if any work done
            if not smart_content_banner_shown:
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

        # ===== STAGE 4.5: EMBEDDINGS =====
        if embedding_service:
            # Banner already shown by progress callback if any work done
            if not embedding_banner_shown:
                console.stage_banner("EMBEDDINGS")

            enriched = summary.metrics.get("embedding_enriched", 0)
            preserved = summary.metrics.get("embedding_preserved", 0)
            errors = summary.metrics.get("embedding_errors", 0)

            if enriched > 0:
                console.print_success(f"Enriched: {enriched} nodes")
            if preserved > 0:
                console.print_progress(f"Preserved: {preserved} nodes (unchanged)")
            if errors > 0:
                console.print_error(f"Errors: {errors} nodes")
        elif not no_embeddings:
            console.stage_banner_skipped("EMBEDDINGS")
            console.print_info(embedding_status)

        # ===== STAGE 5: STORAGE =====
        console.stage_banner("STORAGE")
        # Per Subtask 001 (DYK-02): Show actual path, not hardcoded default
        actual_path = graph_path if graph_path else Path(".fs2/graph.pickle")
        console.print_success(f"Graph saved to {actual_path}")

        # ===== SUMMARY =====
        console.print_line()
        skip_summary = summary.metrics.get("parsing_skipped_by_ext", {})
        _display_final_summary(
            console,
            summary,
            smart_content_enabled=smart_content_service is not None,
            embedding_enabled=embedding_service is not None,
            embedding_skipped=no_embeddings,
            skip_summary=skip_summary,
        )

        # ===== GRAPH CONTENTS (Subtask 002) =====
        # Display extension breakdown from persisted graph
        graph_utils = GraphUtilitiesService(config=config, graph_store=graph_store)
        ext_summary = graph_utils.get_extension_summary()
        _display_graph_contents(console, ext_summary)

        # Show completion timestamp (useful for watch mode)
        _display_completion_timestamp(console)

        # Check for total failure
        if summary.files_scanned > 0 and len(summary.errors) >= summary.files_scanned:
            raise typer.Exit(code=2)

    except MissingConfigurationError:
        console.print_error(
            "No configuration found. Run 'fs2 init' first to create .fs2/config.yaml"
        )
        raise typer.Exit(code=1) from None


def _setup_verbose_logging() -> None:
    """Configure logging for verbose mode with Rich output.

    Sets fs2 loggers to DEBUG while suppressing noisy HTTP client logs
    (httpx, httpcore, openai) that dump full request/response details.
    """
    from rich.console import Console

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(message)s",
        handlers=[
            RichHandler(console=Console(), show_path=False, rich_tracebacks=True)
        ],
    )

    # Suppress noisy HTTP client debug logs - only show warnings and above
    for noisy_logger in ("httpx", "httpcore", "openai", "azure"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


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
    console: ConsoleAdapter,
    summary,
    smart_content_enabled: bool,
    embedding_enabled: bool,
    embedding_skipped: bool,
    skip_summary: dict[str, int] | None = None,
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

    # Show skipped files summary
    if skip_summary:
        skipped_line = f"Skipped: {_format_ext_breakdown(skip_summary, limit=10)}"
        lines.append(skipped_line)

    if smart_content_enabled:
        enriched = summary.metrics.get("smart_content_enriched", 0)
        preserved = summary.metrics.get("smart_content_preserved", 0)
        errors = summary.metrics.get("smart_content_errors", 0)
        lines.append(
            f"Smart Content: {enriched} enriched, {preserved} preserved, {errors} errors"
        )

    if embedding_enabled:
        enriched = summary.metrics.get("embedding_enriched", 0)
        preserved = summary.metrics.get("embedding_preserved", 0)
        errors = summary.metrics.get("embedding_errors", 0)
        lines.append(
            f"Embeddings: {enriched} enriched, {preserved} preserved, {errors} errors"
        )
    elif embedding_skipped:
        lines.append("Embeddings: skipped")

    if summary.errors:
        lines.append(f"Errors: {len(summary.errors)}")

    console.panel(
        "\n".join(lines),
        title="Scan Complete",
        success=summary.success,
    )


def _format_ext_breakdown(counts: dict[str, int], limit: int = 5) -> str:
    """Format extension counts as '120 .py, 80 .ts, ...'.

    Args:
        counts: Dict mapping extension to count.
        limit: Maximum extensions to show (default 5).

    Returns:
        Formatted string like "120 .py, 80 .ts, +3 more"
    """
    if not counts:
        return ""
    sorted_counts = sorted(counts.items(), key=lambda x: -x[1])[:limit]
    parts = [f"{count} {ext}" for ext, count in sorted_counts]
    remaining = len(counts) - limit
    if remaining > 0:
        parts.append(f"+{remaining} more")
    return ", ".join(parts)


def _display_graph_contents(
    console: ConsoleAdapter,
    ext_summary,
) -> None:
    """Display second box with graph contents breakdown.

    KISS: Separate box from scan summary. Shows:
    - Files by extension
    - Nodes by extension

    Args:
        console: Console adapter for output.
        ext_summary: ExtensionSummary from GraphUtilitiesService.
    """
    # Build lines
    files_line = f"Files: {ext_summary.total_files}"
    if ext_summary.files_by_ext:
        files_line += f" ({_format_ext_breakdown(ext_summary.files_by_ext)})"

    nodes_line = f"Nodes: {ext_summary.total_nodes}"
    if ext_summary.nodes_by_ext:
        nodes_line += f" ({_format_ext_breakdown(ext_summary.nodes_by_ext)})"

    lines = [files_line, nodes_line]

    # Display panel (no success flag - informational only)
    console.panel(
        "\n".join(lines),
        title="Graph Contents",
        success=True,  # Always blue/neutral for info panel
    )


def _display_completion_timestamp(console: ConsoleAdapter) -> None:
    """Display completion timestamp (useful for watch mode)."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    console.print_success(f"Completed at {timestamp}")


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
        elif llm_config.provider == "openai":
            from fs2.core.adapters.llm_adapter_openai import OpenAIAdapter

            llm_adapter = OpenAIAdapter(config)
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


def _create_embedding_service(config, console: ConsoleAdapter):
    """Create EmbeddingService if embedding config is present."""
    from fs2.config.objects import EmbeddingConfig
    from fs2.core.services.embedding.embedding_service import EmbeddingService

    try:
        embedding_config = config.require(EmbeddingConfig)
    except MissingConfigurationError:
        return None, "not configured (no embedding section in config.yaml)"

    if embedding_config.mode == "azure" and embedding_config.azure is None:
        return None, "not configured (missing embedding.azure settings)"

    try:
        service = EmbeddingService.create(config)
        return service, "enabled"
    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 100:
            error_msg = error_msg[:100] + "..."
        console.print_warning(f"Embeddings setup error: {error_msg}")
        return None, f"error: {type(e).__name__}"
