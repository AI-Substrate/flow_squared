"""SearchService - Orchestration layer for search operations.

Provides unified search interface that routes to appropriate matchers
based on SearchMode. Composes GraphStore, Matchers, and EmbeddingAdapter
via injection.

Per Discovery 02: Compose GraphStore + RegexMatcher via ABC injection.
Per DYK-P2-01: AUTO detection uses regex chars heuristic for REGEX detection.
Per DYK-P3-02: AUTO routes to SEMANTIC by default, TEXT fallback if no embeddings.
"""

import logging
from typing import TYPE_CHECKING, Protocol

from fs2.core.models.search import QuerySpec, SearchMode, SearchResult
from fs2.core.services.search.regex_matcher import RegexMatcher
from fs2.core.services.search.semantic_matcher import SemanticMatcher
from fs2.core.services.search.text_matcher import TextMatcher

if TYPE_CHECKING:
    from fs2.core.adapters.embedding_adapter import EmbeddingAdapter
    from fs2.core.models.code_node import CodeNode

logger = logging.getLogger(__name__)


class GraphStoreProtocol(Protocol):
    """Protocol for GraphStore - minimal interface needed by SearchService."""

    def get_all_nodes(self) -> list["CodeNode"]:
        """Return all nodes from the graph."""
        ...


# Regex metacharacters for auto-detection heuristic
# Per DYK-P2-01: Simple heuristic - if pattern contains these, use REGEX
REGEX_METACHAR_SET = frozenset(r"*?[]^$|+{}()")


class SearchService:
    """Orchestration layer for search operations.

    Routes to appropriate matcher based on SearchMode:
    - TEXT: Uses TextMatcher (case-insensitive substring)
    - REGEX: Uses RegexMatcher (pattern matching)
    - SEMANTIC: Uses SemanticMatcher (embedding-based similarity)
    - AUTO: Per DYK-P3-02 - REGEX if metacharacters, SEMANTIC otherwise,
            TEXT fallback if no embeddings available

    Per Discovery 02: Compose GraphStore + Matchers.
    Per DYK-P3-02: AUTO mode prefers SEMANTIC, falls back to TEXT.
    Per DYK-P3-05: Warn about partial embedding coverage.

    Example:
        >>> from fs2.core.repos.graph_store_impl import NetworkXGraphStore
        >>> from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter
        >>> graph_store = NetworkXGraphStore(config)
        >>> graph_store.load(Path(".fs2/graph.pickle"))
        >>> adapter = FakeEmbeddingAdapter()
        >>> service = SearchService(graph_store=graph_store, embedding_adapter=adapter)
        >>> results = await service.search(QuerySpec(pattern="auth", mode=SearchMode.AUTO))
    """

    def __init__(
        self,
        graph_store: GraphStoreProtocol,
        embedding_adapter: "EmbeddingAdapter | None" = None,
        timeout: float = 2.0,
    ) -> None:
        """Initialize SearchService with dependencies.

        Per Discovery 02: Receives GraphStore via injection.

        Args:
            graph_store: GraphStore to load nodes from.
            embedding_adapter: Optional adapter for semantic search embeddings.
                If None, SEMANTIC mode will raise an error.
            timeout: Timeout for regex operations (default: 2.0s).
        """
        self._graph_store = graph_store
        self._embedding_adapter = embedding_adapter
        self._regex_matcher = RegexMatcher(timeout=timeout)
        self._text_matcher = TextMatcher(timeout=timeout)
        self._semantic_matcher: SemanticMatcher | None = None

        if embedding_adapter is not None:
            self._semantic_matcher = SemanticMatcher(embedding_adapter=embedding_adapter)

    async def search(self, spec: QuerySpec) -> list[SearchResult]:
        """Search nodes and return scored results.

        Routes to appropriate matcher based on mode:
        - TEXT: Case-insensitive substring search
        - REGEX: Pattern matching with timeout protection
        - SEMANTIC: Embedding-based similarity (requires embedding_adapter)
        - AUTO: Per DYK-P3-02 - REGEX if metacharacters, SEMANTIC otherwise,
                TEXT fallback if no embeddings

        Per DYK-P3-01: Async for compatibility with SemanticMatcher.
        Per DYK-P3-05: Warns about partial embedding coverage.

        Args:
            spec: Query specification with pattern, mode, and limit.

        Returns:
            List of SearchResult sorted by score (descending).
            Limited to spec.limit results.

        Raises:
            SearchError: If mode is SEMANTIC but no embedding adapter configured,
                         or if regex pattern is invalid.
        """
        from fs2.core.services.search.exceptions import SearchError

        # Resolve AUTO mode
        original_mode = spec.mode
        mode = spec.mode
        if mode == SearchMode.AUTO:
            mode = self._detect_mode(spec.pattern)

        # Get all nodes from graph
        nodes = self._graph_store.get_all_nodes()

        if not nodes:
            return []

        # Handle SEMANTIC mode with smart fallback for AUTO
        if mode == SearchMode.SEMANTIC:
            # Check if semantic matcher is available
            if self._semantic_matcher is None:
                if original_mode == SearchMode.AUTO:
                    # Per DYK-P3-02: Graceful fallback to TEXT for AUTO
                    logger.info(
                        "No embedding adapter configured. AUTO mode falling back to TEXT."
                    )
                    mode = SearchMode.TEXT
                else:
                    # Explicit SEMANTIC mode requires adapter
                    raise SearchError(
                        "SEMANTIC search requires an embedding adapter. "
                        "Configure one via SearchService(embedding_adapter=adapter), "
                        "or use TEXT/REGEX mode."
                    )
            else:
                # Check if any nodes have embeddings
                nodes_with_embeddings = [
                    n for n in nodes
                    if n.embedding or n.smart_content_embedding
                ]

                if not nodes_with_embeddings:
                    if original_mode == SearchMode.AUTO:
                        # Per DYK-P3-02: Graceful fallback to TEXT for AUTO
                        logger.info(
                            "No nodes have embeddings. AUTO mode falling back to TEXT. "
                            "Run `fs2 scan --embed` to index nodes."
                        )
                        mode = SearchMode.TEXT
                    else:
                        # Explicit SEMANTIC mode with no embeddings is an error
                        raise SearchError(
                            "No nodes have embeddings. Run `fs2 scan --embed` to index, "
                            "or use TEXT/REGEX mode."
                        )
                else:
                    # Per DYK-P3-05: Warn about partial coverage
                    nodes_without = len(nodes) - len(nodes_with_embeddings)
                    if nodes_without > 0:
                        logger.warning(
                            f"{nodes_without} of {len(nodes)} nodes lack embeddings "
                            "and are excluded from semantic search. "
                            "Run `fs2 scan --embed` to index all nodes."
                        )

        # Match using appropriate matcher
        if mode == SearchMode.TEXT:
            results = await self._text_matcher.match(spec, nodes)
        elif mode == SearchMode.REGEX:
            results = await self._regex_matcher.match(spec, nodes)
        else:  # SEMANTIC
            assert self._semantic_matcher is not None
            results = await self._semantic_matcher.match(spec, nodes)

        # Sort by score (descending)
        results.sort(key=lambda r: r.score, reverse=True)

        # Apply limit
        return results[: spec.limit]

    def _detect_mode(self, pattern: str) -> SearchMode:
        """Detect appropriate mode from pattern characteristics.

        Per DYK-P3-02: AUTO mode routing:
        1. If pattern contains regex metacharacters → REGEX
        2. Otherwise → SEMANTIC (with TEXT fallback if no embeddings)

        Note: The fallback to TEXT is handled in search() based on
        embedding availability.

        Args:
            pattern: Search pattern to analyze.

        Returns:
            SearchMode.REGEX, SearchMode.SEMANTIC, or SearchMode.TEXT.
        """
        # Check if pattern contains any regex metacharacters
        for char in pattern:
            if char in REGEX_METACHAR_SET:
                return SearchMode.REGEX

        # Per DYK-P3-02: Default to SEMANTIC for non-regex patterns
        # TEXT fallback is handled in search() if no embeddings
        return SearchMode.SEMANTIC
