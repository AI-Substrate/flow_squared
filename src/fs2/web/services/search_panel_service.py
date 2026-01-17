"""SearchPanelService - Sync wrapper over async SearchService.

Per DYK Insight #1: SearchService is async (async def search()), but Streamlit
runs in a synchronous context. This service provides a sync facade using
asyncio.run() internally to bridge the gap.

Per Phase 3 Tasks T016/T017: This follows the established Phase 1/2 pattern
where web services are composition wrappers over core services.

Example:
    >>> from fs2.web.services.search_panel_service import SearchPanelService
    >>> service = SearchPanelService(graph_store=store, embedding_adapter=adapter)
    >>> result = service.search(pattern="auth", mode=SearchMode.AUTO)
    >>> print(f"Found {result.total} results")
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fs2.core.models.search.query_spec import QuerySpec
from fs2.core.models.search.search_mode import SearchMode
from fs2.core.models.search.search_result import SearchResult
from fs2.core.services.search.search_service import SearchService

if TYPE_CHECKING:
    from fs2.core.adapters.embedding_adapter import EmbeddingAdapter
    from fs2.core.repos.graph_store import GraphStore
    from fs2.config.service import ConfigurationService


@dataclass(frozen=True)
class SearchPanelResult:
    """Result from SearchPanelService.search().

    Per DYK Insight #1: Provides structured result for UI components.

    Attributes:
        results: List of SearchResult items.
        total: Total number of matches (before pagination).
        mode_used: The SearchMode that was actually used (may differ from AUTO).
        query: The original search query pattern.
    """

    results: list[SearchResult]
    total: int
    mode_used: SearchMode
    query: str


class SearchPanelService:
    """Synchronous facade over async SearchService for Streamlit.

    Per DYK Insight #1: Streamlit's execution model is sync (each user interaction
    triggers a top-to-bottom script rerun). SearchService is async. This service
    bridges the gap using asyncio.run() internally.

    Per Phase 1/2 pattern: Web services are composition wrappers that:
    - Receive core services/repositories via constructor injection
    - Provide sync API for Streamlit components
    - Never cache state (stateless per Streamlit rerun)

    Example:
        >>> from fs2.core.repos.graph_store_impl import NetworkXGraphStore
        >>> from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter
        >>> from fs2.config.service import FakeConfigurationService
        >>> from fs2.config.objects import ScanConfig
        >>>
        >>> config = FakeConfigurationService(ScanConfig())
        >>> store = NetworkXGraphStore(config)
        >>> store.load(Path(".fs2/graph.pickle"))
        >>>
        >>> service = SearchPanelService(graph_store=store)
        >>> result = service.search(pattern="auth", mode=SearchMode.AUTO)
        >>> for r in result.results:
        ...     print(f"{r.node_id}: {r.score:.2f}")
    """

    def __init__(
        self,
        graph_store: "GraphStore",
        embedding_adapter: "EmbeddingAdapter | None" = None,
        config: "ConfigurationService | None" = None,
        timeout: float = 2.0,
    ) -> None:
        """Initialize SearchPanelService with dependencies.

        Args:
            graph_store: GraphStore containing the code graph to search.
            embedding_adapter: Optional adapter for semantic search.
                If None, SEMANTIC mode will raise SearchError.
            config: ConfigurationService for search config (parent_penalty, etc).
            timeout: Timeout for regex operations (default: 2.0s).
        """
        self._search_service = SearchService(
            graph_store=graph_store,
            embedding_adapter=embedding_adapter,
            config=config,
            timeout=timeout,
        )

    def search(
        self,
        pattern: str,
        mode: SearchMode = SearchMode.AUTO,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchPanelResult:
        """Search for nodes matching the pattern.

        Per DYK Insight #1: Wraps async SearchService.search() with asyncio.run().
        Per DYK Insight #3: Defaults to AUTO mode which gracefully falls back.

        Args:
            pattern: Search pattern (cannot be empty).
            mode: Search mode (default: AUTO per DYK Insight #3).
            limit: Maximum results to return (default: 20).
            offset: Number of results to skip for pagination.

        Returns:
            SearchPanelResult with matching nodes, total count, and mode used.

        Raises:
            SearchError: If explicit SEMANTIC mode but no embeddings available.
            ValueError: If pattern is empty or invalid regex.
        """
        spec = QuerySpec(
            pattern=pattern,
            mode=mode,
            limit=limit,
            offset=offset,
        )

        # Per DYK Insight #1: Bridge async→sync using asyncio.run()
        results = asyncio.run(self._search_service.search(spec))

        return SearchPanelResult(
            results=results,
            total=len(results),  # Note: This is post-pagination count
            mode_used=mode,
            query=pattern,
        )
