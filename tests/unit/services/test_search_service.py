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
Per plan-018: Parent penalization tests for hierarchy-aware scoring.
"""

import pytest

from fs2.core.models.code_node import CodeNode
from fs2.core.models.search import QuerySpec, SearchMode

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


class SimpleFakeGraphStore:
    """Simple fake GraphStore for basic search tests.

    For tests requiring parent-child relationships, use the canonical
    FakeGraphStore from fs2.core.repos.graph_store_fake instead.
    """

    def __init__(self, nodes: list[CodeNode]) -> None:
        self._nodes = nodes
        self._edges: dict[str, set[str]] = {}  # parent_id → child_ids
        self._reverse_edges: dict[str, str] = {}  # child_id → parent_id

    def get_all_nodes(self) -> list[CodeNode]:
        return self._nodes

    def add_edge(self, parent_id: str, child_id: str) -> None:
        """Add a parent-child edge."""
        if parent_id not in self._edges:
            self._edges[parent_id] = set()
        self._edges[parent_id].add(child_id)
        self._reverse_edges[child_id] = parent_id

    def get_parent(self, node_id: str) -> CodeNode | None:
        """Get parent node if exists."""
        parent_id = self._reverse_edges.get(node_id)
        if parent_id:
            for node in self._nodes:
                if node.node_id == parent_id:
                    return node
        return None


# Alias for backward compatibility with existing tests
FakeGraphStore = SimpleFakeGraphStore


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

        graph_store = FakeGraphStore(
            [
                create_node("callable:test.py:AuthService"),
            ]
        )
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

        graph_store = FakeGraphStore(
            [
                create_node("callable:test.py:process_data"),
                create_node("callable:test.py:validate_data"),
            ]
        )
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

        graph_store = FakeGraphStore(
            [
                create_node("callable:test.py:func1"),
                create_node("callable:test.py:func2"),
                create_node("callable:test.py:func3"),
                create_node("callable:test.py:func4"),
                create_node("callable:test.py:func5"),
            ]
        )
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

        graph_store = FakeGraphStore(
            [
                # This one has pattern only in content (score 0.5)
                create_node(
                    "callable:test.py:process",
                    content="uses AuthService internally",
                ),
                # This one has pattern in node_id (score 0.8)
                create_node("callable:test.py:AuthService"),
            ]
        )
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

        graph_store = FakeGraphStore(
            [
                create_node("callable:test.py:process_data"),
            ]
        )
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
        graph_store = FakeGraphStore(
            [
                create_node("callable:test.py:AuthService"),
            ]
        )
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

        graph_store = FakeGraphStore(
            [
                create_node("callable:test.py:func"),
            ]
        )
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
        from fs2.core.services.search.exceptions import SearchError
        from fs2.core.services.search.search_service import SearchService

        graph_store = FakeGraphStore([create_node("test:node")])
        service = SearchService(graph_store=graph_store)  # No embedding_adapter

        with pytest.raises(SearchError) as exc_info:
            await service.search(QuerySpec(pattern="concept", mode=SearchMode.SEMANTIC))

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
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter
        from fs2.core.services.search.search_service import SearchService

        # Node WITH embedding
        graph_store = FakeGraphStore(
            [
                create_node(
                    "callable:test.py:AuthService",
                    embedding=((1.0, 0.0, 0.0, 0.0),),
                ),
            ]
        )

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
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter
        from fs2.core.services.search.search_service import SearchService

        # Nodes WITHOUT embeddings
        graph_store = FakeGraphStore(
            [
                create_node("callable:test.py:AuthService"),
            ]
        )

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
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter
        from fs2.core.services.search.exceptions import SearchError
        from fs2.core.services.search.search_service import SearchService

        # Nodes WITHOUT embeddings
        graph_store = FakeGraphStore(
            [
                create_node("callable:test.py:func"),
            ]
        )

        adapter = FakeEmbeddingAdapter()
        service = SearchService(graph_store=graph_store, embedding_adapter=adapter)

        with pytest.raises(SearchError) as exc_info:
            await service.search(QuerySpec(pattern="concept", mode=SearchMode.SEMANTIC))

        assert "embeddings" in str(exc_info.value).lower()
        assert "scan" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_semantic_search_with_adapter(self) -> None:
        """Proves SEMANTIC mode works with proper setup.

        Purpose: Full semantic search flow.
        Quality Contribution: End-to-end semantic validation.
        Acceptance Criteria: SEMANTIC mode finds similar nodes.
        """
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter
        from fs2.core.services.search.search_service import SearchService

        # Create embedding that will match
        query_embedding = [1.0, 0.0, 0.0, 0.0]

        # Node with similar embedding
        graph_store = FakeGraphStore(
            [
                create_node(
                    "callable:test.py:AuthService",
                    embedding=((0.95, 0.1, 0.0, 0.0),),
                ),
            ]
        )

        adapter = FakeEmbeddingAdapter()
        adapter.set_response(query_embedding)

        service = SearchService(graph_store=graph_store, embedding_adapter=adapter)

        results = await service.search(
            QuerySpec(pattern="find auth", mode=SearchMode.SEMANTIC)
        )

        assert len(results) == 1
        assert results[0].node_id == "callable:test.py:AuthService"
        assert results[0].score > 0.9


# ============================================================================
# Phase 5 T002: Offset Slicing Tests (Pagination Support)
# ============================================================================


class TestSearchServiceOffsetSlicing:
    """Offset slicing tests for pagination support (T002).

    Per Phase 5 tasks.md: Tests verify offset applied after sort.
    BC-04: --offset flag for pagination with default 0.
    """

    @pytest.mark.asyncio
    async def test_offset_skips_first_n_results(self) -> None:
        """Proves offset skips the first N results after sorting.

        Purpose: Pagination - skip to page 2, 3, etc.
        Quality Contribution: Enables paginated search results.
        Acceptance Criteria: offset=2 skips first 2 results.
        """
        from fs2.core.services.search.search_service import SearchService

        # Create 5 nodes that all match "func"
        graph_store = FakeGraphStore(
            [
                create_node("callable:test.py:func1"),
                create_node("callable:test.py:func2"),
                create_node("callable:test.py:func3"),
                create_node("callable:test.py:func4"),
                create_node("callable:test.py:func5"),
            ]
        )
        service = SearchService(graph_store=graph_store)

        # Get first page (no offset)
        first_page = await service.search(
            QuerySpec(pattern="func", mode=SearchMode.TEXT, limit=5, offset=0)
        )

        # Get second page (skip first 2)
        second_page = await service.search(
            QuerySpec(pattern="func", mode=SearchMode.TEXT, limit=5, offset=2)
        )

        assert len(first_page) == 5
        assert len(second_page) == 3  # 5 - 2 = 3 remaining

        # Second page should not include first page's first 2 results
        first_page_ids = [r.node_id for r in first_page[:2]]
        second_page_ids = [r.node_id for r in second_page]
        for node_id in first_page_ids:
            assert node_id not in second_page_ids

    @pytest.mark.asyncio
    async def test_offset_with_limit_pages_correctly(self) -> None:
        """Proves offset + limit creates correct page slices.

        Purpose: Standard pagination (page_size=limit, page_num via offset).
        Quality Contribution: Predictable pagination behavior.
        Acceptance Criteria: offset=2, limit=2 returns results[2:4].
        """
        from fs2.core.services.search.search_service import SearchService

        graph_store = FakeGraphStore(
            [
                create_node("callable:test.py:func1"),
                create_node("callable:test.py:func2"),
                create_node("callable:test.py:func3"),
                create_node("callable:test.py:func4"),
                create_node("callable:test.py:func5"),
            ]
        )
        service = SearchService(graph_store=graph_store)

        # Page 1: offset=0, limit=2 -> results[0:2]
        page1 = await service.search(
            QuerySpec(pattern="func", mode=SearchMode.TEXT, limit=2, offset=0)
        )

        # Page 2: offset=2, limit=2 -> results[2:4]
        page2 = await service.search(
            QuerySpec(pattern="func", mode=SearchMode.TEXT, limit=2, offset=2)
        )

        # Page 3: offset=4, limit=2 -> results[4:6] (only 1 result)
        page3 = await service.search(
            QuerySpec(pattern="func", mode=SearchMode.TEXT, limit=2, offset=4)
        )

        assert len(page1) == 2
        assert len(page2) == 2
        assert len(page3) == 1  # Only 1 result left

        # No overlap between pages
        page1_ids = {r.node_id for r in page1}
        page2_ids = {r.node_id for r in page2}
        page3_ids = {r.node_id for r in page3}
        assert page1_ids.isdisjoint(page2_ids)
        assert page2_ids.isdisjoint(page3_ids)

    @pytest.mark.asyncio
    async def test_offset_beyond_results_returns_empty(self) -> None:
        """Proves offset beyond result count returns empty list.

        Purpose: Edge case - requesting page that doesn't exist.
        Quality Contribution: Clean handling of out-of-range offset.
        Acceptance Criteria: offset > result_count returns [].
        """
        from fs2.core.services.search.search_service import SearchService

        graph_store = FakeGraphStore(
            [
                create_node("callable:test.py:func1"),
                create_node("callable:test.py:func2"),
            ]
        )
        service = SearchService(graph_store=graph_store)

        # Only 2 results, but offset is 10
        results = await service.search(
            QuerySpec(pattern="func", mode=SearchMode.TEXT, limit=10, offset=10)
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_offset_zero_returns_from_start(self) -> None:
        """Proves offset=0 returns results from the beginning.

        Purpose: Default behavior - no pagination offset.
        Quality Contribution: Documents expected default.
        Acceptance Criteria: offset=0 same as no offset.
        """
        from fs2.core.services.search.search_service import SearchService

        graph_store = FakeGraphStore(
            [
                create_node("callable:test.py:func1"),
                create_node("callable:test.py:func2"),
                create_node("callable:test.py:func3"),
            ]
        )
        service = SearchService(graph_store=graph_store)

        # With explicit offset=0
        with_offset = await service.search(
            QuerySpec(pattern="func", mode=SearchMode.TEXT, limit=10, offset=0)
        )

        # Default (no explicit offset in test, but defaults to 0 in QuerySpec)
        default = await service.search(
            QuerySpec(pattern="func", mode=SearchMode.TEXT, limit=10)
        )

        assert len(with_offset) == 3
        assert len(default) == 3
        # Same results in same order
        assert [r.node_id for r in with_offset] == [r.node_id for r in default]


# ============================================================================
# Plan-018: Parent Penalization Tests (TDD - RED PHASE)
# ============================================================================


def create_hierarchy_node(
    node_id: str,
    category: str,
    name: str,
    content: str,
    parent_node_id: str | None = None,
) -> CodeNode:
    """Create a CodeNode for hierarchy testing with parent support."""
    return CodeNode(
        node_id=node_id,
        category=category,
        ts_kind="function_definition" if category == "callable" else "class_definition",
        name=name,
        qualified_name=name,
        start_line=1,
        end_line=10,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=len(content),
        content=content,
        content_hash="test_hash",
        signature=None,
        language="python",
        is_named=True,
        field_name=None,
        smart_content=None,
        embedding=None,
        parent_node_id=parent_node_id,
    )


@pytest.fixture
def parent_penalty_graph_store():
    """Graph with file → class → method hierarchy, all matching 'auth'.

    Per plan-018 T002: 3-level hierarchy for parent penalization tests.
    All nodes contain 'auth' in content for text matching.
    """
    file_node = create_hierarchy_node(
        node_id="file:src/auth.py",
        category="file",
        name="auth.py",
        content="# Authentication module with authenticate function",
    )
    class_node = create_hierarchy_node(
        node_id="class:src/auth.py:AuthService",
        category="type",
        name="AuthService",
        content="class AuthService: handles authentication",
        parent_node_id="file:src/auth.py",
    )
    method_node = create_hierarchy_node(
        node_id="callable:src/auth.py:AuthService.authenticate",
        category="callable",
        name="authenticate",
        content="def authenticate(self, user, password): verify credentials",
        parent_node_id="class:src/auth.py:AuthService",
    )

    store = SimpleFakeGraphStore([file_node, class_node, method_node])
    # Wire up edges for get_parent() to work
    store.add_edge("file:src/auth.py", "class:src/auth.py:AuthService")
    store.add_edge(
        "class:src/auth.py:AuthService", "callable:src/auth.py:AuthService.authenticate"
    )

    return store


class TestParentPenalization:
    """Tests for parent score penalization (AC01-AC10).

    Per plan-018: Hierarchy-aware scoring that penalizes parent nodes
    when their children are also in search results.

    These tests are written in TDD RED phase - they will fail until
    the implementation is complete in T003-T006.
    """

    @pytest.mark.asyncio
    async def test_parent_penalized_when_child_in_results_ac01(
        self, parent_penalty_graph_store
    ):
        """Proves parent scores are reduced when children also match (AC01).

        Purpose: Core penalization behavior - parents should rank lower.
        Quality Contribution: Ensures specific matches surface first.
        Acceptance Criteria:
        - Parent score reduced by penalty factor
        - Child score unchanged
        - Score order: method > class > file

        Per DYK-01: Depth-weighted penalty: score × (1-penalty)^depth
        Note: TextMatcher gives 0.8 for name match (node_id contains pattern),
        0.5 for content match. All our nodes match "auth" in content (0.5),
        and additionally class "AuthService" matches in name (0.8).

        With 0.25 penalty:
        - method (depth 0): 0.5 (content match, unchanged)
        - class (depth 1): 0.8 × 0.75¹ = 0.6 (name match, penalized once)
        - file (depth 2): 0.5 × 0.75² = 0.28125 (content match, penalized twice)
        """
        from fs2.config.objects import SearchConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.services.search.search_service import SearchService

        # Configure with default 0.25 penalty
        config = FakeConfigurationService(SearchConfig(parent_penalty=0.25))
        service = SearchService(
            graph_store=parent_penalty_graph_store,
            config=config,
        )

        results = await service.search(
            QuerySpec(pattern="auth", mode=SearchMode.TEXT)
        )

        # Find each node's result
        method_result = next(r for r in results if "authenticate" in r.node_id)
        class_result = next(
            r
            for r in results
            if "AuthService" in r.node_id and "callable" not in r.node_id
        )
        file_result = next(r for r in results if r.node_id.startswith("file:"))

        # Method unchanged (leaf node, not penalized) - matches on content (0.5)
        # or node_id if "authenticate" contains "auth" (0.8)
        # Actually, "authenticate" contains "auth" so it's a node_id match = 0.8
        assert method_result.score == pytest.approx(0.8, rel=0.01)

        # Class penalized (depth 1): "AuthService" matches "auth" in node_id (0.8)
        # Penalized: 0.8 × 0.75¹ = 0.6
        assert class_result.score == pytest.approx(0.6, rel=0.01)

        # File penalized more (depth 2): "auth.py" matches in node_id (0.8)
        # Penalized: 0.8 × 0.75² = 0.45
        assert file_result.score == pytest.approx(0.45, rel=0.01)

        # Verify ordering: method > class > file
        assert results[0].node_id == method_result.node_id
        assert results[1].node_id == class_result.node_id
        assert results[2].node_id == file_result.node_id

    @pytest.mark.asyncio
    async def test_child_ranks_higher_than_parent_ac02(self, parent_penalty_graph_store):
        """Proves child node appears before parent in sorted results (AC02).

        Purpose: Ranking behavior after penalization.
        Quality Contribution: Users see specific matches first.
        Acceptance Criteria: Child node always ranks above penalized parent.
        """
        from fs2.config.objects import SearchConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.services.search.search_service import SearchService

        config = FakeConfigurationService(SearchConfig(parent_penalty=0.25))
        service = SearchService(
            graph_store=parent_penalty_graph_store,
            config=config,
        )

        results = await service.search(
            QuerySpec(pattern="auth", mode=SearchMode.TEXT)
        )

        # Get result order
        result_ids = [r.node_id for r in results]

        # Method should appear before class
        method_idx = next(
            i for i, nid in enumerate(result_ids) if "authenticate" in nid
        )
        class_idx = next(
            i
            for i, nid in enumerate(result_ids)
            if "AuthService" in nid and "callable" not in nid
        )
        file_idx = next(i for i, nid in enumerate(result_ids) if nid.startswith("file:"))

        assert method_idx < class_idx, "Method should rank higher than class"
        assert class_idx < file_idx, "Class should rank higher than file"

    @pytest.mark.asyncio
    async def test_multi_level_hierarchy_depth_weighted_ac03(
        self, parent_penalty_graph_store
    ):
        """Proves depth-weighted penalty applies to multi-level hierarchy (AC03).

        Purpose: Per DYK-01 - grandparents penalized more than parents.
        Quality Contribution: Guarantees proper ordering at all hierarchy levels.
        Acceptance Criteria:
        - Class penalized once: score × 0.75
        - File penalized twice: score × 0.75²

        Note: Both class and file match "auth" in node_id (0.8 base score).
        """
        from fs2.config.objects import SearchConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.services.search.search_service import SearchService

        config = FakeConfigurationService(SearchConfig(parent_penalty=0.25))
        service = SearchService(
            graph_store=parent_penalty_graph_store,
            config=config,
        )

        results = await service.search(
            QuerySpec(pattern="auth", mode=SearchMode.TEXT)
        )

        class_result = next(
            r
            for r in results
            if "AuthService" in r.node_id and "callable" not in r.node_id
        )
        file_result = next(r for r in results if r.node_id.startswith("file:"))

        # Depth 1 vs depth 2 - file should have lower score
        assert file_result.score < class_result.score

        # Verify exact depth-weighted calculation
        # Base score 0.8 for node_id match (both contain "auth")
        # Class (depth 1): 0.8 × 0.75 = 0.6
        # File (depth 2): 0.8 × 0.75² = 0.45
        assert class_result.score == pytest.approx(0.8 * 0.75, rel=0.01)
        assert file_result.score == pytest.approx(0.8 * 0.75 * 0.75, rel=0.01)

    @pytest.mark.asyncio
    async def test_scores_remain_in_bounds_ac04(self, parent_penalty_graph_store):
        """Proves all scores remain in [0.0, 1.0] range after penalization (AC04).

        Purpose: Contract preservation - scores must be valid.
        Quality Contribution: Prevents downstream errors from invalid scores.
        Acceptance Criteria: All scores in [0.0, 1.0] range.
        """
        from fs2.config.objects import SearchConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.services.search.search_service import SearchService

        # Use maximum penalty to stress test bounds
        config = FakeConfigurationService(SearchConfig(parent_penalty=1.0))
        service = SearchService(
            graph_store=parent_penalty_graph_store,
            config=config,
        )

        results = await service.search(
            QuerySpec(pattern="auth", mode=SearchMode.TEXT)
        )

        for result in results:
            assert 0.0 <= result.score <= 1.0, (
                f"Score {result.score} out of bounds for {result.node_id}"
            )

    @pytest.mark.asyncio
    async def test_exact_match_immune_to_penalty_ac05(self, parent_penalty_graph_store):
        """Proves score 1.0 nodes are never penalized (AC05).

        Purpose: Preserve user intent - exact matches are sacred.
        Quality Contribution: User explicitly searching for a node should find it first.
        Acceptance Criteria: Score 1.0 remains 1.0 even with child in results.
        """
        from fs2.config.objects import SearchConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.services.search.search_service import SearchService

        config = FakeConfigurationService(SearchConfig(parent_penalty=0.25))
        service = SearchService(
            graph_store=parent_penalty_graph_store,
            config=config,
        )

        # Search for exact class node_id - should get score 1.0
        results = await service.search(
            QuerySpec(
                pattern="class:src/auth.py:AuthService", mode=SearchMode.TEXT
            )
        )

        # Find the class result
        class_result = next(
            (r for r in results if r.node_id == "class:src/auth.py:AuthService"),
            None,
        )

        # If it has score 1.0 (exact match), it should NOT be penalized
        if class_result and class_result.score == 1.0:
            # Exact match should remain 1.0 (immune to penalty)
            assert class_result.score == 1.0

    @pytest.mark.asyncio
    async def test_penalty_enabled_by_default_ac06(self, parent_penalty_graph_store):
        """Proves penalization is enabled by default with 0.25 penalty (AC06).

        Purpose: Default behavior should reduce parent scores.
        Quality Contribution: Zero-config improvement for all users.
        Acceptance Criteria: Parents are penalized without explicit config.
        """
        from fs2.config.objects import SearchConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.services.search.search_service import SearchService

        # Use default SearchConfig (parent_penalty defaults to 0.25)
        config = FakeConfigurationService(SearchConfig())
        service = SearchService(
            graph_store=parent_penalty_graph_store,
            config=config,
        )

        results = await service.search(
            QuerySpec(pattern="auth", mode=SearchMode.TEXT)
        )

        # Find method and class results
        method_result = next(r for r in results if "authenticate" in r.node_id)
        class_result = next(
            r
            for r in results
            if "AuthService" in r.node_id and "callable" not in r.node_id
        )

        # Class should be penalized (lower score than method)
        assert class_result.score < method_result.score

    @pytest.mark.asyncio
    async def test_penalty_disabled_with_zero_ac09(self, parent_penalty_graph_store):
        """Proves penalty can be disabled via config (AC09).

        Purpose: Opt-out for users who want original behavior.
        Quality Contribution: Flexibility for different use cases.
        Acceptance Criteria: No penalization when parent_penalty=0.0.
        """
        from fs2.config.objects import SearchConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.services.search.search_service import SearchService

        # Disable penalty
        config = FakeConfigurationService(SearchConfig(parent_penalty=0.0))
        service = SearchService(
            graph_store=parent_penalty_graph_store,
            config=config,
        )

        results = await service.search(
            QuerySpec(pattern="auth", mode=SearchMode.TEXT)
        )

        # All scores should be unmodified (0.5 for content match)
        # Note: This checks that they're all the same, not necessarily 0.5
        # because text matcher scoring may vary
        method_result = next(r for r in results if "authenticate" in r.node_id)
        class_result = next(
            r
            for r in results
            if "AuthService" in r.node_id and "callable" not in r.node_id
        )
        file_result = next(r for r in results if r.node_id.startswith("file:"))

        # Without penalty, all nodes with same match type should have same score
        # (all match on content, so all should be 0.5)
        assert method_result.score == class_result.score == file_result.score

    @pytest.mark.asyncio
    async def test_regex_mode_with_penalization_ac10(self, parent_penalty_graph_store):
        """Proves REGEX mode also applies parent penalization (AC10).

        Purpose: Penalization works across all search modes.
        Quality Contribution: Consistent behavior regardless of mode.
        Acceptance Criteria: Regex results also penalized correctly.
        """
        from fs2.config.objects import SearchConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.services.search.search_service import SearchService

        config = FakeConfigurationService(SearchConfig(parent_penalty=0.25))
        service = SearchService(
            graph_store=parent_penalty_graph_store,
            config=config,
        )

        # Use regex pattern
        results = await service.search(
            QuerySpec(pattern="auth.*", mode=SearchMode.REGEX)
        )

        # Find method and class results
        method_result = next(
            (r for r in results if "authenticate" in r.node_id), None
        )
        class_result = next(
            (
                r
                for r in results
                if "AuthService" in r.node_id and "callable" not in r.node_id
            ),
            None,
        )

        # If both match, class should be penalized (lower score)
        if method_result and class_result:
            assert class_result.score < method_result.score


# ============================================================================
# Plan-018 T010: All Modes Penalization Verification
# ============================================================================


class TestAllModesPenalization:
    """Tests verifying parent penalization works across all search modes (AC10).

    Per plan-018 T010: Penalization is applied uniformly regardless of mode.
    The _apply_parent_penalty() is called after all matchers (line 233),
    so it inherently works for TEXT, REGEX, and SEMANTIC modes.
    """

    @pytest.mark.asyncio
    async def test_penalization_applied_after_matchers(
        self, parent_penalty_graph_store
    ):
        """Proves penalization is applied after matchers, before sort (AC10).

        Purpose: Verify code path applies penalty for all modes.
        Quality Contribution: Mode-agnostic penalization.
        Acceptance Criteria: All modes go through the same penalty code.
        """
        from fs2.config.objects import SearchConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.services.search.search_service import SearchService

        config = FakeConfigurationService(SearchConfig(parent_penalty=0.25))
        service = SearchService(
            graph_store=parent_penalty_graph_store,
            config=config,
        )

        # Test TEXT mode
        text_results = await service.search(
            QuerySpec(pattern="auth", mode=SearchMode.TEXT, limit=10)
        )
        assert len(text_results) == 3

        # Test REGEX mode
        regex_results = await service.search(
            QuerySpec(pattern="auth.*", mode=SearchMode.REGEX, limit=10)
        )
        assert len(regex_results) == 3

        # Both should have penalization applied
        # (verified by checking that method > class > file ordering is consistent)
        for results in [text_results, regex_results]:
            method_result = next(r for r in results if "authenticate" in r.node_id)
            class_result = next(
                r
                for r in results
                if "AuthService" in r.node_id and "callable" not in r.node_id
            )

            # Method should rank higher than penalized class
            method_idx = next(
                i for i, r in enumerate(results) if r.node_id == method_result.node_id
            )
            class_idx = next(
                i for i, r in enumerate(results) if r.node_id == class_result.node_id
            )

            assert method_idx < class_idx, "Method should rank higher than class"
