"""SearchService - Orchestration layer for search operations.

Provides unified search interface that routes to appropriate matchers
based on SearchMode. Composes GraphStore, Matchers, and EmbeddingAdapter
via injection.

Per Discovery 02: Compose GraphStore + RegexMatcher via ABC injection.
Per DYK-P2-01: AUTO detection uses regex chars heuristic for REGEX detection.
Per DYK-P3-02: AUTO routes to SEMANTIC by default, TEXT fallback if no embeddings.
Per fix 2025-12-26: include/exclude filters applied BEFORE sorting and pagination.
Per plan-018: Parent penalization reduces parent scores when children also match.
"""

import dataclasses
import logging
import re
from typing import TYPE_CHECKING, Protocol

from fs2.core.models.search import QuerySpec, SearchMode, SearchResult
from fs2.core.services.search.regex_matcher import RegexMatcher
from fs2.core.services.search.semantic_matcher import SemanticMatcher
from fs2.core.services.search.text_matcher import TextMatcher

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.embedding_adapter import EmbeddingAdapter
    from fs2.core.models.code_node import CodeNode

logger = logging.getLogger(__name__)


class GraphStoreProtocol(Protocol):
    """Protocol for GraphStore - minimal interface needed by SearchService.

    Per plan-018: Extended with get_parent() for hierarchy-aware scoring.
    """

    def get_all_nodes(self) -> list["CodeNode"]:
        """Return all nodes from the graph."""
        ...

    def get_parent(self, node_id: str) -> "CodeNode | None":
        """Get parent node by child node_id.

        Per plan-018: Required for parent penalization to walk hierarchy.

        Args:
            node_id: Child node's identifier.

        Returns:
            Parent CodeNode if exists, None if node has no parent.
        """
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
    Per plan-018: Parent penalization reduces parent scores when children match.

    Example:
        >>> from fs2.core.repos.graph_store_impl import NetworkXGraphStore
        >>> from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter
        >>> from fs2.config.service import FakeConfigurationService
        >>> from fs2.config.objects import SearchConfig
        >>> graph_store = NetworkXGraphStore(config)
        >>> graph_store.load(Path(".fs2/graph.pickle"))
        >>> adapter = FakeEmbeddingAdapter()
        >>> config = FakeConfigurationService(SearchConfig())
        >>> service = SearchService(graph_store=graph_store, embedding_adapter=adapter, config=config)
        >>> results = await service.search(QuerySpec(pattern="auth", mode=SearchMode.AUTO))
    """

    def __init__(
        self,
        graph_store: GraphStoreProtocol,
        embedding_adapter: "EmbeddingAdapter | None" = None,
        timeout: float = 2.0,
        config: "ConfigurationService | None" = None,
    ) -> None:
        """Initialize SearchService with dependencies.

        Per Discovery 02: Receives GraphStore via injection.
        Per plan-018/DYK-02: Receives ConfigurationService for parent_penalty.

        Args:
            graph_store: GraphStore to load nodes from.
            embedding_adapter: Optional adapter for semantic search embeddings.
                If None, SEMANTIC mode will raise an error.
            timeout: Timeout for regex operations (default: 2.0s).
            config: ConfigurationService for accessing SearchConfig.
                If None, uses default parent_penalty of 0.25.
        """
        self._graph_store = graph_store
        self._embedding_adapter = embedding_adapter
        self._config = config
        self._regex_matcher = RegexMatcher(timeout=timeout)
        self._text_matcher = TextMatcher(timeout=timeout)
        self._semantic_matcher: SemanticMatcher | None = None

        if embedding_adapter is not None:
            self._semantic_matcher = SemanticMatcher(
                embedding_adapter=embedding_adapter
            )

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
                    n for n in nodes if n.embedding or n.smart_content_embedding
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
                    # Per DYK-P3-05: Warn about partial coverage (only if >50% missing)
                    nodes_without = len(nodes) - len(nodes_with_embeddings)
                    missing_ratio = nodes_without / len(nodes) if len(nodes) > 0 else 0
                    if missing_ratio > 0.5:
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

        # Apply include filter (keep only matching - OR logic across patterns)
        # Per fix 2025-12-26: Filters applied BEFORE sorting and pagination
        if spec.include:
            results = [
                r for r in results if any(re.search(p, r.node_id) for p in spec.include)
            ]

        # Apply exclude filter (remove matching - OR logic across patterns)
        if spec.exclude:
            results = [
                r
                for r in results
                if not any(re.search(p, r.node_id) for p in spec.exclude)
            ]

        # Apply parent penalization (per plan-018)
        # Per PL-11: Penalization happens AFTER matchers, BEFORE sort
        results = self._apply_parent_penalty(results)

        # Sort by score (descending)
        results.sort(key=lambda r: r.score, reverse=True)

        # Apply offset and limit (pagination)
        return results[spec.offset : spec.offset + spec.limit]

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

    def _get_parent_penalty(self) -> float:
        """Get parent penalty factor from config.

        Returns:
            Penalty factor (0.0-1.0). Defaults to 0.25 if no config provided.
        """
        if self._config is None:
            return 0.25  # Default per AC06

        from fs2.config.objects import SearchConfig

        search_config = self._config.get(SearchConfig)
        if search_config is None:
            return 0.25  # Default per AC06
        return search_config.parent_penalty

    def _find_ancestors_in_results(
        self,
        node_id: str,
        result_ids: set[str],
    ) -> dict[str, int]:
        """Walk UP parent chain via GraphStore edges.

        Per plan-018/PL-04: Use graph-based parent traversal.
        Per DYK-04: Include visited set for cycle protection.

        Args:
            node_id: Starting node to walk up from.
            result_ids: Set of node_ids that are in the result set.

        Returns:
            Dict mapping ancestor node_id to depth (1 = parent, 2 = grandparent).
            Only includes ancestors that are also in the result set.
        """
        ancestors: dict[str, int] = {}
        visited: set[str] = set()  # Per DYK-04: Cycle protection
        depth = 0

        current_id = node_id
        while current_id and current_id not in visited:
            visited.add(current_id)
            parent = self._graph_store.get_parent(current_id)
            if parent is None:
                break

            depth += 1
            if parent.node_id in result_ids:
                ancestors[parent.node_id] = depth

            current_id = parent.node_id

        return ancestors

    def _apply_parent_penalty(
        self,
        results: list[SearchResult],
    ) -> list[SearchResult]:
        """Apply depth-weighted penalty to parent nodes when children also match.

        Per plan-018: Reduces parent scores to surface specific child matches first.
        Per DYK-01: Depth-weighted formula: score × (1 - penalty)^depth
        Per AC05: Score 1.0 (exact match) is immune to penalty.
        Per Finding 06: Uses dataclasses.replace() for frozen SearchResult.

        Args:
            results: List of SearchResult from matchers.

        Returns:
            List of SearchResult with parent scores reduced.
        """
        penalty = self._get_parent_penalty()

        # Early exit if penalty is 0 (disabled per AC09)
        if penalty == 0.0:
            return results

        # Build set of result node_ids for O(1) lookup
        result_ids = {r.node_id for r in results}

        # Find all nodes that are ancestors of other results, with their max depth
        # A node can be ancestor of multiple children - use max depth for penalty
        parents_to_penalize: dict[str, int] = {}  # node_id → max depth
        for result in results:
            ancestors = self._find_ancestors_in_results(result.node_id, result_ids)
            for ancestor_id, depth in ancestors.items():
                if ancestor_id not in parents_to_penalize:
                    parents_to_penalize[ancestor_id] = depth
                else:
                    # Use max depth if ancestor appears at multiple levels
                    parents_to_penalize[ancestor_id] = max(
                        parents_to_penalize[ancestor_id], depth
                    )

        # Apply penalty (skip exact matches per AC05)
        penalized: list[SearchResult] = []
        for result in results:
            if result.node_id in parents_to_penalize and result.score < 1.0:
                depth = parents_to_penalize[result.node_id]
                # Per DYK-01: Depth-weighted penalty
                retention = (1.0 - penalty) ** depth
                new_score = max(
                    0.0, min(1.0, result.score * retention)
                )  # Clamp per AC04
                result = dataclasses.replace(result, score=new_score)
            penalized.append(result)

        return penalized
