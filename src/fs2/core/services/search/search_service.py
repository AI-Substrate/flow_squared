"""SearchService - Orchestration layer for search operations.

Provides unified search interface that routes to appropriate matchers
based on SearchMode. Composes GraphStore and Matchers via ABC injection.

Per Discovery 02: Compose GraphStore + RegexMatcher via ABC injection.
Per DYK-P2-01: AUTO detection uses regex chars heuristic (temporary).
"""

from typing import TYPE_CHECKING, Protocol

from fs2.core.models.search import QuerySpec, SearchMode, SearchResult
from fs2.core.services.search.regex_matcher import RegexMatcher
from fs2.core.services.search.text_matcher import TextMatcher

if TYPE_CHECKING:
    from fs2.core.models.code_node import CodeNode


class GraphStoreProtocol(Protocol):
    """Protocol for GraphStore - minimal interface needed by SearchService."""

    def get_all_nodes(self) -> list["CodeNode"]:
        """Return all nodes from the graph."""
        ...


# Regex metacharacters for auto-detection heuristic
# Per DYK-P2-01: Simple heuristic - if pattern contains these, use REGEX
REGEX_METACHAR_SET = frozenset(r"*?[]^$|+{}()\.")


class SearchService:
    """Orchestration layer for search operations.

    Routes to appropriate matcher based on SearchMode:
    - TEXT: Uses TextMatcher (case-insensitive substring)
    - REGEX: Uses RegexMatcher (pattern matching)
    - AUTO: Detects mode based on pattern characteristics
    - SEMANTIC: Not implemented in Phase 2 (raises NotImplementedError)

    Per Discovery 02: Compose GraphStore + Matchers.
    Per DYK-P2-01: AUTO detection heuristic is temporary.

    Example:
        >>> from fs2.core.repos.graph_store_impl import NetworkXGraphStore
        >>> graph_store = NetworkXGraphStore(config)
        >>> graph_store.load(Path(".fs2/graph.pickle"))
        >>> service = SearchService(graph_store=graph_store)
        >>> results = service.search(QuerySpec(pattern="auth", mode=SearchMode.AUTO))
    """

    def __init__(
        self,
        graph_store: GraphStoreProtocol,
        timeout: float = 2.0,
    ) -> None:
        """Initialize SearchService with dependencies.

        Per Discovery 02: Receives GraphStore via injection.

        Args:
            graph_store: GraphStore to load nodes from.
            timeout: Timeout for regex operations (default: 2.0s).
        """
        self._graph_store = graph_store
        self._regex_matcher = RegexMatcher(timeout=timeout)
        self._text_matcher = TextMatcher(timeout=timeout)

    def search(self, spec: QuerySpec) -> list[SearchResult]:
        """Search nodes and return scored results.

        Routes to appropriate matcher based on mode:
        - TEXT: Case-insensitive substring search
        - REGEX: Pattern matching with timeout protection
        - AUTO: Detects mode from pattern characteristics
        - SEMANTIC: Not implemented (Phase 3)

        Args:
            spec: Query specification with pattern, mode, and limit.

        Returns:
            List of SearchResult sorted by score (descending).
            Limited to spec.limit results.

        Raises:
            NotImplementedError: If mode is SEMANTIC.
            SearchError: If regex pattern is invalid.
        """
        # Resolve AUTO mode
        mode = spec.mode
        if mode == SearchMode.AUTO:
            mode = self._detect_mode(spec.pattern)

        # Route to appropriate matcher
        if mode == SearchMode.SEMANTIC:
            raise NotImplementedError(
                "SEMANTIC search is not implemented in Phase 2. "
                "Use TEXT or REGEX mode, or wait for Phase 3."
            )

        # Get all nodes from graph
        nodes = self._graph_store.get_all_nodes()

        if not nodes:
            return []

        # Match using appropriate matcher
        if mode == SearchMode.TEXT:
            results = self._text_matcher.match(spec, nodes)
        else:  # REGEX
            results = self._regex_matcher.match(spec, nodes)

        # Sort by score (descending)
        results.sort(key=lambda r: r.score, reverse=True)

        # Apply limit
        return results[: spec.limit]

    def _detect_mode(self, pattern: str) -> SearchMode:
        """Detect appropriate mode from pattern characteristics.

        Per DYK-P2-01: Simple heuristic for Phase 2.
        If pattern contains regex metacharacters, use REGEX.
        Otherwise, use TEXT (case-insensitive substring).

        Note: This heuristic is temporary. Phase 3+ may add:
        - SEMANTIC detection for natural language queries
        - Better regex vs. text discrimination

        Args:
            pattern: Search pattern to analyze.

        Returns:
            SearchMode.REGEX or SearchMode.TEXT.
        """
        # Check if pattern contains any regex metacharacters
        for char in pattern:
            if char in REGEX_METACHAR_SET:
                return SearchMode.REGEX

        return SearchMode.TEXT
