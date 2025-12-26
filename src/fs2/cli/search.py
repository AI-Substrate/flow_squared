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
import re
from typing import Annotated

import typer
from rich.console import Console

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
            help="Keep only results matching pattern (text/regex). Repeatable for OR logic.",
        ),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option(
            "--exclude",
            help="Remove results matching pattern (text/regex). Repeatable for OR logic.",
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

    # Validate include/exclude patterns (compile to check regex validity)
    include_patterns = include or []
    exclude_patterns = exclude or []

    for p in include_patterns:
        try:
            re.compile(p)
        except re.error as e:
            console.print(
                f"[red]Error:[/red] Invalid regex in --include '{p}': {e}"
            )
            raise typer.Exit(code=1) from None

    for p in exclude_patterns:
        try:
            re.compile(p)
        except re.error as e:
            console.print(
                f"[red]Error:[/red] Invalid regex in --exclude '{p}': {e}"
            )
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
        embedding_adapter = _create_embedding_adapter(config)

        # Create SearchService with dependency injection
        service = SearchService(
            graph_store=graph_store,
            embedding_adapter=embedding_adapter,
        )

        # Build QuerySpec
        search_mode = MODE_MAP[mode_lower]
        spec = QuerySpec(
            pattern=pattern,
            mode=search_mode,
            limit=limit,
            offset=offset,
        )

        # === Service Call ===
        try:
            # SearchService.search is async, so we need asyncio.run()
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

        # === Apply filters ===
        # Apply include filter (keep only matching - OR logic across patterns)
        if include_patterns:
            results = [
                r for r in results
                if any(re.search(p, r.node_id) for p in include_patterns)
            ]

        # Apply exclude filter (remove matching - OR logic across patterns)
        if exclude_patterns:
            results = [
                r for r in results
                if not any(re.search(p, r.node_id) for p in exclude_patterns)
            ]

        # Track filtered count
        filtered_count = len(results) if (include_patterns or exclude_patterns) else None

        # Apply pagination AFTER filtering
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

        # Create metadata
        meta = SearchResultMeta(
            total=total_after_filter,
            showing={"from": showing_from, "to": showing_to, "count": showing_count},
            pagination={"limit": limit, "offset": offset},
            folders=folders,
            include=include_patterns if include_patterns else None,
            exclude=exclude_patterns if exclude_patterns else None,
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

        # Output as JSON using raw print() for clean stdout
        json_str = json.dumps(envelope, indent=2, default=str)
        print(json_str)

    except MissingConfigurationError:
        console.print(
            "[red]Error:[/red] No configuration found.\n"
            "  Run [bold]fs2 init[/bold] first to create .fs2/config.yaml"
        )
        raise typer.Exit(code=1) from None


def _create_embedding_adapter(config):
    """Create embedding adapter if configured, None otherwise.

    Returns None silently if embeddings not configured - AUTO mode
    will fall back to TEXT search gracefully.
    """
    from fs2.config.objects import EmbeddingConfig

    try:
        embedding_config = config.require(EmbeddingConfig)
    except MissingConfigurationError:
        return None

    # Create adapter based on mode
    if embedding_config.mode == "azure":
        if embedding_config.azure is None:
            return None
        from fs2.core.adapters.embedding_adapter_azure import AzureEmbeddingAdapter
        return AzureEmbeddingAdapter(config)
    elif embedding_config.mode == "fake":
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter
        return FakeEmbeddingAdapter(dimensions=embedding_config.dimensions)
    else:
        return None
