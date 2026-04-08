"""fs2 report command implementation.

Generates self-contained HTML reports from the code graph.
First report type: codebase-graph — interactive visualization
of all nodes and cross-file reference edges.

Uses ConsoleAdapter ABC for all console output (no direct Rich usage).
Delegates business logic to ReportService (per Clean Architecture).
"""

import webbrowser
from pathlib import Path

import typer
from rich.console import Console

from fs2.cli.utils import (
    resolve_graph_from_context,
    safe_write_file,
    validate_save_path,
)
from fs2.core.adapters.console_adapter_rich import RichConsoleAdapter

report_app = typer.Typer(
    name="report",
    help="Generate reports from the code graph",
    no_args_is_help=True,
)


@report_app.command(name="codebase-graph")
def codebase_graph(
    ctx: typer.Context,
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output HTML file path (default: .fs2/reports/codebase-graph.html)",
    ),
    open_browser: bool = typer.Option(
        False,
        "--open",
        help="Open report in default browser after generation",
    ),
    no_smart_content: bool = typer.Option(
        False,
        "--no-smart-content",
        help="Exclude AI summaries from report (smaller file)",
    ),
    exclude: list[str] = typer.Option(  # noqa: B008
        [],
        "--exclude",
        help="Glob patterns to exclude nodes by node_id (e.g. 'test_*', '*.test.*'). Repeatable.",
    ),
    include: list[str] = typer.Option(  # noqa: B008
        [],
        "--include",
        help="Glob patterns to include — only matching nodes kept. Repeatable.",
    ),
) -> None:
    """Generate an interactive codebase graph report.

    Produces a self-contained HTML file with all nodes and cross-file
    reference edges from the code graph. The report works offline —
    no server or CDN needed.
    """
    console = RichConsoleAdapter()
    stderr_console = Console(stderr=True)

    try:
        # Composition root: resolve graph from CLI context
        config, graph_store = resolve_graph_from_context(ctx)

        console.stage_banner("REPORT: CODEBASE GRAPH")

        # Determine output path (reuse CLI path-safety helpers)
        if output:
            output_path = validate_save_path(Path(output), stderr_console)
        else:
            # Try to get configured output_dir
            try:
                from fs2.config.objects import ReportsConfig

                reports_config = config.require(ReportsConfig)
                output_dir = Path(reports_config.output_dir)
            except Exception:
                output_dir = Path(".fs2/reports")
            output_path = validate_save_path(
                output_dir / "codebase-graph.html",
                stderr_console,
            )

        console.print_info(
            f"Graph: {graph_store.get_metadata().get('node_count', '?')} nodes"
        )

        # Determine graph_path for metadata
        cli_context = ctx.obj
        graph_path = None
        if cli_context and cli_context.graph_file:
            graph_path = Path(cli_context.graph_file)

        # Generate report
        from fs2.core.services.report_service import ReportService

        service = ReportService(config=config, graph_store=graph_store)
        console.print_progress("Generating report...")

        include_smart = not no_smart_content
        result = service.generate_codebase_graph(
            include_smart_content=include_smart,
            graph_path=graph_path,
            exclude_patterns=exclude or None,
            include_patterns=include or None,
        )

        # Write output (reuse CLI safe-write helper for cleanup on failure)
        safe_write_file(output_path, result.html, stderr_console)

        # Summary
        meta = result.metadata
        file_size_kb = len(result.html) / 1024
        console.print_success(
            f"Report saved to {output_path} "
            f"({file_size_kb:.0f} KB, "
            f"{meta.get('node_count', 0)} nodes, "
            f"{meta.get('reference_edge_count', 0)} references)"
        )

        # Open in browser (DYK-02: graceful fallback)
        if open_browser:
            try:
                webbrowser.open(output_path.as_uri())
                console.print_info("Opened in browser")
            except (webbrowser.Error, OSError):
                console.print_info(
                    f"Could not open browser. Open manually: {output_path}"
                )

    except typer.Exit:
        raise
    except Exception as e:
        stderr_console.print(f"[red]Error generating report:[/red] {e}")
        raise typer.Exit(code=2) from None
