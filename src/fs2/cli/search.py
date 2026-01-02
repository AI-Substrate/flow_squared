"""fs2 search command implementation.

Searches the code graph and outputs results as JSON for scripting and tool integration.

Per Clean Architecture: CLI handles only arg parsing + presentation.
Business logic (graph loading, search execution) is delegated to SearchService.

Per research finding (get_node.py): Use raw print() for JSON output, Console(stderr=True) for errors.
This ensures clean stdout for piping to tools like jq - only JSON on stdout, all else to stderr.

Per Subtask 003: Output envelope with metadata + results; --include/--exclude filters.
"""

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from fs2.cli.utils import safe_write_file, validate_save_path

from fs2.config.exceptions import MissingConfigurationError
from fs2.config.objects import GraphConfig
from fs2.config.service import FS2ConfigurationService
from fs2.core.adapters.exceptions import GraphNotFoundError, GraphStoreError
from fs2.core.models.search import QuerySpec, SearchMode
from fs2.core.models.search.search_result_meta import (
    SearchResultMeta,
    compute_folder_distribution,
)
from fs2.core.repos import NetworkXGraphStore
from fs2.core.services.search import SearchService
from fs2.core.services.search.exceptions import SearchError
from fs2.core.utils import normalize_filter_pattern

# Console for error/status messages - writes to stderr to keep stdout clean for piping
console = Console(stderr=True)

# Mode string to SearchMode enum mapping
MODE_MAP = {
    "auto": SearchMode.AUTO,
    "text": SearchMode.TEXT,
    "regex": SearchMode.REGEX,
    "semantic": SearchMode.SEMANTIC,
}


def search(
    ctx: typer.Context,
    pattern: Annotated[
        str,
        typer.Argument(
            help="Search pattern (text, regex, or semantic query)"
        ),
    ],
    mode: Annotated[
        str,
        typer.Option(
            "--mode", "-m",
            help="Search mode: auto, text, regex, semantic (default: auto)",
        ),
    ] = "auto",
    limit: Annotated[
        int,
        typer.Option(
            "--limit", "-l",
            help="Maximum number of results (default: 20)",
        ),
    ] = 20,
    offset: Annotated[
        int,
        typer.Option(
            "--offset", "-o",
            help="Skip first N results for pagination (default: 0)",
        ),
    ] = 0,
    detail: Annotated[
        str,
        typer.Option(
            "--detail", "-d",
            help="Detail level: min (9 fields) or max (13 fields) (default: min)",
        ),
    ] = "min",
    include: Annotated[
        list[str] | None,
        typer.Option(
            "--include",
            help="Filter by pattern (glob like *.py or regex). Repeatable for OR logic.",
        ),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option(
            "--exclude",
            help="Exclude by pattern (glob like *.py or regex). Repeatable for OR logic.",
        ),
    ] = None,
    file: Annotated[
        Path | None,
        typer.Option(
            "--file", "-f",
            help="Write JSON to file instead of stdout (path validated for security).",
        ),
    ] = None,
) -> None:
    """Search the code graph and output results as JSON envelope.

    Searches the indexed code graph using text, regex, or semantic matching.
    Results are output as a JSON envelope with metadata for scripting.

    \\b
    Examples:
        $ fs2 search "authentication"              # Auto-detect mode
        $ fs2 search "def.*test" --mode regex      # Regex search
        $ fs2 search "config" --limit 10           # Limit results
        $ fs2 search "auth" --offset 10            # Pagination (page 2)
        $ fs2 search "error" --detail max          # Include full content
        $ fs2 search "auth" | jq '.results[]'      # Pipe to jq
        $ fs2 search "auth" --include "src/"       # Filter to src/ folder
        $ fs2 search "auth" --exclude "test"       # Exclude tests
        $ fs2 search "auth" --include "src/" --include "lib/"  # OR logic
        $ fs2 search "auth" --file results.json  # Save to file

    \\b
    Exit codes:
        0 - Success (even if no results)
        1 - User error (missing graph, missing config, invalid pattern)
        2 - System error (corrupted graph)
    """
    # Validate mode
    mode_lower = mode.lower()
    if mode_lower not in MODE_MAP:
        console.print(
            f"[red]Error:[/red] Invalid mode '{mode}'. "
            f"Valid modes: auto, text, regex, semantic"
        )
        raise typer.Exit(code=1)

    # Validate detail
    detail_lower = detail.lower()
    if detail_lower not in ("min", "max"):
        console.print(
            f"[red]Error:[/red] Invalid detail level '{detail}'. "
            f"Valid levels: min, max"
        )
        raise typer.Exit(code=1)

    # Validate limit
    if limit < 1:
        console.print(
            f"[red]Error:[/red] Limit must be >= 1, got {limit}"
        )
        raise typer.Exit(code=1)

    # Validate offset
    if offset < 0:
        console.print(
            f"[red]Error:[/red] Offset must be >= 0, got {offset}"
        )
        raise typer.Exit(code=1)

    # Convert glob patterns to regex, then to tuples for QuerySpec
    # normalize_filter_pattern() auto-detects globs like *.py and .cs
    try:
        include_patterns = (
            tuple(normalize_filter_pattern(p) for p in include) if include else None
        )
        exclude_patterns = (
            tuple(normalize_filter_pattern(p) for p in exclude) if exclude else None
        )
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None

    try:
        # === Composition Root ===
        config = FS2ConfigurationService()

        # Get graph_file from global option via context
        if ctx.obj and ctx.obj.graph_file:
            config.set(GraphConfig(graph_path=ctx.obj.graph_file))

        graph_config = config.require(GraphConfig)
        graph_store = NetworkXGraphStore(config)

        # === Load Graph (lazy loading) ===
        from pathlib import Path
        graph_path = Path(graph_config.graph_path)
        if not graph_path.exists():
            raise GraphNotFoundError(graph_path)
        graph_store.load(graph_path)

        # Try to create embedding adapter if configured (for semantic search)
        from fs2.core.adapters.embedding_adapter import (
            create_embedding_adapter_from_config,
        )

        embedding_adapter = create_embedding_adapter_from_config(config)

        # Create SearchService with dependency injection
        service = SearchService(
            graph_store=graph_store,
            embedding_adapter=embedding_adapter,
        )

        # Build QuerySpec - get all filtered results (no pagination yet)
        # Per fix 2025-12-26: Filters applied in service layer before pagination
        # We need total count for envelope, so fetch all filtered first, then paginate
        search_mode = MODE_MAP[mode_lower]
        spec = QuerySpec(
            pattern=pattern,
            mode=search_mode,
            limit=10000,  # High limit to get all filtered results
            offset=0,
            include=include_patterns,
            exclude=exclude_patterns,
        )

        # === Service Call ===
        try:
            # SearchService.search is async, so we need asyncio.run()
            # Returns all filtered results (up to high limit)
            results = asyncio.run(service.search(spec))
        except GraphNotFoundError:
            console.print(
                "[red]Error:[/red] No graph found.\n"
                "  Run [bold]fs2 scan[/bold] first to create the graph."
            )
            raise typer.Exit(code=1) from None
        except GraphStoreError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(code=2) from None
        except SearchError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(code=1) from None
        except ValueError as e:
            # Handle invalid regex from QuerySpec validation
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(code=1) from None

        # Track filtered count (filters already applied by service)
        filtered_count = len(results) if (include_patterns or exclude_patterns) else None

        # Apply pagination locally (service returned all filtered results)
        total_after_filter = len(results)
        paginated_results = results[offset : offset + limit]

        # === Build metadata envelope ===
        # Compute folder distribution from filtered (but not paginated) results
        node_ids = [r.node_id for r in results]
        folders = compute_folder_distribution(node_ids)

        # Build showing info
        showing_from = offset
        showing_to = offset + len(paginated_results)
        showing_count = len(paginated_results)

        # Create metadata (convert tuples to lists for JSON output)
        meta = SearchResultMeta(
            total=total_after_filter,
            showing={"from": showing_from, "to": showing_to, "count": showing_count},
            pagination={"limit": limit, "offset": offset},
            folders=folders,
            include=list(include_patterns) if include_patterns else None,
            exclude=list(exclude_patterns) if exclude_patterns else None,
            filtered=filtered_count,
        )

        # === Presentation ===
        # Convert results to dicts with appropriate detail level
        result_dicts = [r.to_dict(detail=detail_lower) for r in paginated_results]

        # Build envelope: { "meta": {...}, "results": [...] }
        envelope = {
            "meta": meta.to_dict(),
            "results": result_dicts,
        }

        # Output as JSON
        json_str = json.dumps(envelope, indent=2, default=str)

        # Handle file output vs stdout
        if file:
            # Validate path for security (AC4b)
            absolute_path = validate_save_path(file, console)
            # Write file with cleanup on error and UTF-8 encoding
            safe_write_file(absolute_path, json_str, console)
            # Confirmation on stderr (AC2)
            console.print(f"[green]✓[/green] Wrote search results to {file}")
        else:
            # Use raw print() for clean stdout
            print(json_str)

    except MissingConfigurationError:
        console.print(
            "[red]Error:[/red] No configuration found.\n"
            "  Run [bold]fs2 init[/bold] first to create .fs2/config.yaml"
        )
        raise typer.Exit(code=1) from None


