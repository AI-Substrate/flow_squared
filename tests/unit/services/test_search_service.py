"""Tests for SearchService - orchestration layer for search operations.

TDD tests for Phase 2/3: Search Service.

Per tasks.md:
- T011: Auto-detection heuristics tests
- T013: SearchService orchestration tests
- T010: Missing embeddings check with AUTO fallback (Phase 3)

Per Discovery 02: Compose GraphStore + RegexMatcher via ABC injection.
Per DYK-P2-01: AUTO detection uses regex chars heuristic.
Per DYK-P3-01: Tests are async for compatibility with SemanticMatcher.
Per DYK-P3-02: AUTO mode routes to SEMANTIC by default, TEXT fallback if no embeddings.
"""

import pytest

from fs2.core.models.code_node import CodeNode
from fs2.core.models.search import QuerySpec, SearchMode, SearchResult


# ============================================================================
# Test Fixtures
# ============================================================================


def create_node(
    node_id: str,
    content: str | None = None,
    smart_content: str | None = None,
    start_line: int = 1,
    end_line: int = 10,
    embedding: tuple[tuple[float, ...], ...] | None = None,
) -> CodeNode:
    """Create a test CodeNode with minimal required fields."""
    return CodeNode(
        node_id=node_id,
        category=node_id.split(":")[0],
        ts_kind="function_definition",
        name=node_id.split(":")[-1] if ":" in node_id else node_id,
        qualified_name=node_id.split(":")[-1] if ":" in node_id else node_id,
        start_line=start_line,
        end_line=end_line,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=len(content) if content else 0,
        content=content or "",
        content_hash="test_hash",
        signature=None,
        language="python",
        is_named=True,
        field_name=None,
        smart_content=smart_content,
        embedding=embedding,
    )


class FakeGraphStore:
    """Fake GraphStore for testing."""

    def __init__(self, nodes: list[CodeNode]) -> None:
        self._nodes = nodes

    def get_all_nodes(self) -> list[CodeNode]:
        return self._nodes


# ============================================================================
# T011: Auto-Detection Heuristics Tests
# ============================================================================


class TestSearchServiceAutoDetection:
    """Auto-detection heuristics tests (T011).

    Per AC18: AUTO mode routes based on pattern characteristics.
    Per DYK-P3-02: No regex metacharacters → SEMANTIC (with TEXT fallback).
    """

    def test_auto_mode_detects_regex_pattern(self) -> None:
        """Proves AUTO detects regex metacharacters and routes to REGEX mode.

        Purpose: Patterns like `.*`, `[a-z]+` should use regex.
        Quality Contribution: Smart mode selection.
        Acceptance Criteria: Regex metachar triggers REGEX mode.
        """
        from fs2.core.services.search.search_service import SearchService

        graph_store = FakeGraphStore([create_node("test:node")])
        service = SearchService(graph_store=graph_store)

        # Pattern with regex chars
        detected = service._detect_mode("def.*process")

        assert detected == SearchMode.REGEX

    def test_auto_mode_detects_semantic_pattern(self) -> None:
        """Proves AUTO detects plain text and routes to SEMANTIC mode.

        Purpose: Plain words should use semantic search (per DYK-P3-02).
        Quality Contribution: User-friendly default for natural language.
        Acceptance Criteria: Plain text triggers SEMANTIC mode.
        """
        from fs2.core.services.search.search_service import SearchService

        graph_store = FakeGraphStore([create_node("test:node")])
        service = SearchService(graph_store=graph_store)

        # Plain text pattern - per DYK-P3-02, routes to SEMANTIC
        detected = service._detect_mode("authentication")

        assert detected == SearchMode.SEMANTIC

    def test_auto_mode_star_triggers_regex(self) -> None:
        """Proves asterisk in pattern triggers REGEX mode.

        Purpose: * is common regex quantifier.
        Quality Contribution: Regex patterns handled correctly.
        Acceptance Criteria: * triggers REGEX.
        """
        from fs2.core.services.search.search_service import SearchService

        graph_store = FakeGraphStore([])
        service = SearchService(graph_store=graph_store)

        assert service._detect_mode("a*b") == SearchMode.REGEX

    def test_auto_mode_question_mark_triggers_regex(self) -> None:
        """Proves question mark in pattern triggers REGEX mode.

        Purpose: ? is common regex quantifier.
        Quality Contribution: Regex patterns handled correctly.
        Acceptance Criteria: ? triggers REGEX.
        """
        from fs2.core.services.search.search_service import SearchService

        graph_store = FakeGraphStore([])
        service = SearchService(graph_store=graph_store)

        assert service._detect_mode("colou?r") == SearchMode.REGEX

    def test_auto_mode_bracket_triggers_regex(self) -> None:
        """Proves square brackets trigger REGEX mode.

        Purpose: [...] is character class.
        Quality Contribution: Regex patterns handled correctly.
        Acceptance Criteria: [...] triggers REGEX.
        """
        from fs2.core.services.search.search_service import SearchService

        graph_store = FakeGraphStore([])
        service = SearchService(graph_store=graph_store)

        assert service._detect_mode("[a-z]+") == SearchMode.REGEX

    def test_auto_mode_caret_triggers_regex(self) -> None:
        """Proves caret (^) triggers REGEX mode.

        Purpose: ^ is regex anchor.
        Quality Contribution: Anchored patterns handled correctly.
        Acceptance Criteria: ^ triggers REGEX.
        """
        from fs2.core.services.search.search_service import SearchService

        graph_store = FakeGraphStore([])
        service = SearchService(graph_store=graph_store)

        assert service._detect_mode("^start") == SearchMode.REGEX

    def test_auto_mode_dollar_triggers_regex(self) -> None:
        """Proves dollar sign ($) triggers REGEX mode.

        Purpose: $ is regex anchor.
        Quality Contribution: Anchored patterns handled correctly.
        Acceptance Criteria: $ triggers REGEX.
        """
        from fs2.core.services.search.search_service import SearchService

        graph_store = FakeGraphStore([])
        service = SearchService(graph_store=graph_store)

        assert service._detect_mode("end$") == SearchMode.REGEX

    def test_auto_mode_pipe_triggers_regex(self) -> None:
        """Proves pipe (|) triggers REGEX mode.

        Purpose: | is regex alternation.
        Quality Contribution: Alternation patterns handled correctly.
        Acceptance Criteria: | triggers REGEX.
        """
        from fs2.core.services.search.search_service import SearchService

        graph_store = FakeGraphStore([])
        service = SearchService(graph_store=graph_store)

        assert service._detect_mode("foo|bar") == SearchMode.REGEX

    def test_auto_mode_dot_is_semantic(self) -> None:
        """Proves file.py pattern (dot only) uses SEMANTIC mode.

        Purpose: Dot alone is not treated as regex per updated heuristic.
        Quality Contribution: User-friendly defaults for common patterns.
        Acceptance Criteria: file.py uses SEMANTIC (dot not in metachar set).
        """
        from fs2.core.services.search.search_service import SearchService

        graph_store = FakeGraphStore([])
        service = SearchService(graph_store=graph_store)

        # Dot is not in REGEX_METACHAR_SET anymore, so it routes to SEMANTIC
        result = service._detect_mode("file.py")
        assert result == SearchMode.SEMANTIC


# ============================================================================
# T013: SearchService Orchestration Tests
# ============================================================================


class TestSearchServiceOrchestration:
    """SearchService orchestration tests (T013).

    Per Discovery 02: Compose GraphStore + Matchers via ABC injection.
    """

    @pytest.mark.asyncio
    async def test_search_routes_to_text_matcher(self) -> None:
        """Proves TEXT mode uses TextMatcher.

        Purpose: Mode routing works correctly.
        Quality Contribution: Correct matcher selection.
        Acceptance Criteria: TEXT mode uses case-insensitive search.
        """
        from fs2.core.services.search.search_service import SearchService

        graph_store = FakeGraphStore([
            create_node("callable:test.py:AuthService"),
        ])
        service = SearchService(graph_store=graph_store)

        results = await service.search(
            QuerySpec(pattern="authservice", mode=SearchMode.TEXT)
        )

        # Case-insensitive - should match
        assert len(results) == 1
        assert results[0].node_id == "callable:test.py:AuthService"

    @pytest.mark.asyncio
    async def test_search_routes_to_regex_matcher(self) -> None:
        """Proves REGEX mode uses RegexMatcher.

        Purpose: Mode routing works correctly.
        Quality Contribution: Correct matcher selection.
        Acceptance Criteria: REGEX mode uses pattern matching.
        """
        from fs2.core.services.search.search_service import SearchService

        graph_store = FakeGraphStore([
            create_node("callable:test.py:process_data"),
            create_node("callable:test.py:validate_data"),
        ])
        service = SearchService(graph_store=graph_store)

        results = await service.search(
            QuerySpec(pattern=".*_data", mode=SearchMode.REGEX)
        )

        # Regex match
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_respects_limit(self) -> None:
        """Proves search respects limit parameter.

        Purpose: Limit enforcement.
        Quality Contribution: Performance and UX control.
        Acceptance Criteria: Returns at most `limit` results.
        """
        from fs2.core.services.search.search_service import SearchService

        graph_store = FakeGraphStore([
            create_node("callable:test.py:func1"),
            create_node("callable:test.py:func2"),
            create_node("callable:test.py:func3"),
            create_node("callable:test.py:func4"),
            create_node("callable:test.py:func5"),
        ])
        service = SearchService(graph_store=graph_store)

        results = await service.search(
            QuerySpec(pattern="func", mode=SearchMode.TEXT, limit=2)
        )

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_sorts_by_score_descending(self) -> None:
        """Proves results are sorted by score (highest first).

        Purpose: Best matches appear first.
        Quality Contribution: Useful result ordering.
        Acceptance Criteria: Results sorted by score descending.
        """
        from fs2.core.services.search.search_service import SearchService

        graph_store = FakeGraphStore([
            # This one has pattern only in content (score 0.5)
            create_node(
                "callable:test.py:process",
                content="uses AuthService internally",
            ),
            # This one has pattern in node_id (score 0.8)
            create_node("callable:test.py:AuthService"),
        ])
        service = SearchService(graph_store=graph_store)

        results = await service.search(
            QuerySpec(pattern="AuthService", mode=SearchMode.TEXT)
        )

        assert len(results) == 2
        # Higher score should come first
        assert results[0].score >= results[1].score
        assert results[0].node_id == "callable:test.py:AuthService"

    @pytest.mark.asyncio
    async def test_search_auto_mode_routes_to_regex_for_pattern(self) -> None:
        """Proves AUTO mode detects regex pattern and routes correctly.

        Purpose: End-to-end AUTO mode validation for regex.
        Quality Contribution: Smart mode selection works.
        Acceptance Criteria: AUTO detects regex pattern and matches.
        """
        from fs2.core.services.search.search_service import SearchService

        graph_store = FakeGraphStore([
            create_node("callable:test.py:process_data"),
        ])
        service = SearchService(graph_store=graph_store)

        # Regex pattern with AUTO mode - should route to REGEX
        results = await service.search(
            QuerySpec(pattern="process.*data", mode=SearchMode.AUTO)
        )

        # Should detect REGEX and match
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_auto_mode_falls_back_to_text_without_embeddings(self) -> None:
        """Proves AUTO mode falls back to TEXT when no embeddings available.

        Purpose: Per DYK-P3-02 - AUTO uses TEXT if no embeddings.
        Quality Contribution: Graceful degradation.
        Acceptance Criteria: Plain text with AUTO and no embeddings uses TEXT.
        """
        from fs2.core.services.search.search_service import SearchService

        # Nodes WITHOUT embeddings
        graph_store = FakeGraphStore([
            create_node("callable:test.py:AuthService"),
        ])
        # No embedding_adapter provided
        service = SearchService(graph_store=graph_store)

        # Plain text with AUTO mode - should fall back to TEXT
        results = await service.search(
            QuerySpec(pattern="authservice", mode=SearchMode.AUTO)
        )

        # Should fall back to TEXT and match (case-insensitive)
        assert len(results) == 1
        assert results[0].node_id == "callable:test.py:AuthService"

    @pytest.mark.asyncio
    async def test_search_empty_nodes_returns_empty(self) -> None:
        """Proves searching empty graph returns empty list.

        Purpose: Edge case handling.
        Quality Contribution: Graceful empty state handling.
        Acceptance Criteria: Empty graph returns empty results.
        """
        from fs2.core.services.search.search_service import SearchService

        graph_store = FakeGraphStore([])
        service = SearchService(graph_store=graph_store)

        results = await service.search(
            QuerySpec(pattern="anything", mode=SearchMode.TEXT)
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_search_no_matches_returns_empty(self) -> None:
        """Proves non-matching pattern returns empty list.

        Purpose: No-match case handling.
        Quality Contribution: Clean no-match response.
        Acceptance Criteria: Non-matching pattern returns [].
        """
        from fs2.core.services.search.search_service import SearchService

        graph_store = FakeGraphStore([
            create_node("callable:test.py:func"),
        ])
        service = SearchService(graph_store=graph_store)

        results = await service.search(
            QuerySpec(pattern="xyz_nonexistent", mode=SearchMode.TEXT)
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_search_semantic_mode_without_adapter_raises_error(self) -> None:
        """Proves explicit SEMANTIC mode without adapter raises SearchError.

        Purpose: Clear error for missing adapter.
        Quality Contribution: Actionable error message.
        Acceptance Criteria: SearchError with helpful message.
        """
        from fs2.core.services.search.search_service import SearchService
        from fs2.core.services.search.exceptions import SearchError

        graph_store = FakeGraphStore([create_node("test:node")])
        service = SearchService(graph_store=graph_store)  # No embedding_adapter

        with pytest.raises(SearchError) as exc_info:
            await service.search(
                QuerySpec(pattern="concept", mode=SearchMode.SEMANTIC)
            )

        assert "SEMANTIC" in str(exc_info.value)
        assert "embedding adapter" in str(exc_info.value).lower()


# ============================================================================
# T010: Missing Embeddings and AUTO Fallback Tests
# ============================================================================


class TestSearchServiceSemanticFallback:
    """AUTO mode fallback tests (T010).

    Per DYK-P3-02: AUTO falls back to TEXT if no embeddings available.
    Per DYK-P3-05: Warn about partial embedding coverage.
    """

    @pytest.mark.asyncio
    async def test_auto_mode_uses_semantic_with_embeddings(self) -> None:
        """Proves AUTO mode uses SEMANTIC when embeddings are available.

        Purpose: Per DYK-P3-02 - SEMANTIC is preferred.
        Quality Contribution: Semantic search for natural language.
        Acceptance Criteria: AUTO routes to SEMANTIC with embeddings.
        """
        from fs2.core.services.search.search_service import SearchService
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        # Node WITH embedding
        graph_store = FakeGraphStore([
            create_node(
                "callable:test.py:AuthService",
                embedding=((1.0, 0.0, 0.0, 0.0),),
            ),
        ])

        # Set up adapter to return matching embedding
        adapter = FakeEmbeddingAdapter()
        adapter.set_response([1.0, 0.0, 0.0, 0.0])

        service = SearchService(graph_store=graph_store, embedding_adapter=adapter)

        # Plain text with AUTO mode and embeddings - should use SEMANTIC
        results = await service.search(
            QuerySpec(pattern="authentication", mode=SearchMode.AUTO)
        )

        # Should find match via semantic search
        assert len(results) == 1
        assert results[0].node_id == "callable:test.py:AuthService"
        # match_field should be from semantic search
        assert results[0].match_field in ["embedding", "smart_content_embedding"]

    @pytest.mark.asyncio
    async def test_auto_mode_falls_back_to_text_no_embeddings_in_nodes(self) -> None:
        """Proves AUTO falls back to TEXT when nodes lack embeddings.

        Purpose: Per DYK-P3-02 - graceful fallback.
        Quality Contribution: Works even without embeddings.
        Acceptance Criteria: AUTO uses TEXT when nodes have no embeddings.
        """
        from fs2.core.services.search.search_service import SearchService
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        # Nodes WITHOUT embeddings
        graph_store = FakeGraphStore([
            create_node("callable:test.py:AuthService"),
        ])

        adapter = FakeEmbeddingAdapter()
        service = SearchService(graph_store=graph_store, embedding_adapter=adapter)

        # Plain text with AUTO - should fall back to TEXT
        results = await service.search(
            QuerySpec(pattern="authservice", mode=SearchMode.AUTO)
        )

        # Should fall back to TEXT and match (case-insensitive)
        assert len(results) == 1
        # match_field should be from text/regex search
        assert results[0].match_field in ["node_id", "content", "smart_content"]

    @pytest.mark.asyncio
    async def test_explicit_semantic_with_no_embeddings_raises_error(self) -> None:
        """Proves explicit SEMANTIC raises error when no embeddings exist.

        Purpose: Clear error for missing embeddings.
        Quality Contribution: Actionable error message.
        Acceptance Criteria: SearchError with scan instructions.
        """
        from fs2.core.services.search.search_service import SearchService
        from fs2.core.services.search.exceptions import SearchError
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        # Nodes WITHOUT embeddings
        graph_store = FakeGraphStore([
            create_node("callable:test.py:func"),
        ])

        adapter = FakeEmbeddingAdapter()
        service = SearchService(graph_store=graph_store, embedding_adapter=adapter)

        with pytest.raises(SearchError) as exc_info:
            await service.search(
                QuerySpec(pattern="concept", mode=SearchMode.SEMANTIC)
            )

        assert "embeddings" in str(exc_info.value).lower()
        assert "scan" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_semantic_search_with_adapter(self) -> None:
        """Proves SEMANTIC mode works with proper setup.

        Purpose: Full semantic search flow.
        Quality Contribution: End-to-end semantic validation.
        Acceptance Criteria: SEMANTIC mode finds similar nodes.
        """
        from fs2.core.services.search.search_service import SearchService
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        # Create embedding that will match
        query_embedding = [1.0, 0.0, 0.0, 0.0]

        # Node with similar embedding
        graph_store = FakeGraphStore([
            create_node(
                "callable:test.py:AuthService",
                embedding=((0.95, 0.1, 0.0, 0.0),),
            ),
        ])

        adapter = FakeEmbeddingAdapter()
        adapter.set_response(query_embedding)

        service = SearchService(graph_store=graph_store, embedding_adapter=adapter)

        results = await service.search(
            QuerySpec(pattern="find auth", mode=SearchMode.SEMANTIC)
        )

        assert len(results) == 1
        assert results[0].node_id == "callable:test.py:AuthService"
        assert results[0].score > 0.9
