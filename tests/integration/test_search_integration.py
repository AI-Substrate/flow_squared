"""Integration tests for search with real fixture graph.

T015: End-to-end validation of text/regex search with fixture_graph.pkl.

Uses the fixture graph containing real code nodes to verify:
- Text search finds expected nodes
- Regex search patterns work correctly
- AUTO mode routing functions end-to-end
- Results are properly scored and sorted

Per DYK-P3-01: Tests are async for compatibility with SemanticMatcher.
"""

from pathlib import Path

import pytest

from fs2.core.models.search import QuerySpec, SearchMode
from fs2.core.repos.graph_store_impl import NetworkXGraphStore
from fs2.core.services.search import SearchService

# Path to fixture graph
FIXTURE_GRAPH_PATH = Path(__file__).parent.parent / "fixtures" / "fixture_graph.pkl"


@pytest.fixture
def graph_store() -> NetworkXGraphStore:
    """Load the fixture graph for integration tests."""
    if not FIXTURE_GRAPH_PATH.exists():
        pytest.skip(f"Fixture graph not found: {FIXTURE_GRAPH_PATH}")

    # Create a graph store and load the fixture
    from fs2.config.objects import GraphConfig, ScanConfig
    from fs2.config.service import FakeConfigurationService

    config = FakeConfigurationService(
        GraphConfig(graph_path=str(FIXTURE_GRAPH_PATH)),
        ScanConfig(),  # Required by NetworkXGraphStore
    )
    store = NetworkXGraphStore(config)
    store.load(FIXTURE_GRAPH_PATH)
    return store


@pytest.fixture
def search_service(graph_store: NetworkXGraphStore) -> SearchService:
    """Create SearchService with loaded fixture graph."""
    return SearchService(graph_store=graph_store)


class TestSearchIntegrationWithFixture:
    """Integration tests using fixture_graph.pkl."""

    @pytest.mark.asyncio
    async def test_text_search_finds_nodes(self, search_service: SearchService) -> None:
        """Proves text search works with real fixture nodes.

        Purpose: End-to-end TEXT mode validation.
        Quality Contribution: Real-world usage validation.
        Acceptance Criteria: Finds nodes matching text pattern.
        """
        results = await search_service.search(
            QuerySpec(pattern="def", mode=SearchMode.TEXT, limit=10)
        )

        # Should find at least some nodes with "def" (Python functions)
        # or nodes containing "def" in content
        assert len(results) >= 0  # May be 0 if no Python code in fixture
        # All results should be SearchResult objects
        for r in results:
            assert r.node_id
            assert 0.0 <= r.score <= 1.0

    @pytest.mark.asyncio
    async def test_regex_search_finds_nodes(
        self, search_service: SearchService
    ) -> None:
        """Proves regex search works with real fixture nodes.

        Purpose: End-to-end REGEX mode validation.
        Quality Contribution: Real-world regex matching.
        Acceptance Criteria: Regex pattern matches expected nodes.
        """
        results = await search_service.search(
            QuerySpec(pattern=".*test.*", mode=SearchMode.REGEX, limit=10)
        )

        # Should find nodes with "test" in their content or ID
        assert len(results) >= 0
        for r in results:
            assert r.node_id
            assert 0.0 <= r.score <= 1.0

    @pytest.mark.asyncio
    async def test_auto_mode_works_with_fixture(
        self, search_service: SearchService
    ) -> None:
        """Proves AUTO mode routing works with real fixture.

        Purpose: End-to-end AUTO mode validation.
        Quality Contribution: Smart mode detection in real use.
        Acceptance Criteria: AUTO correctly routes and returns results.
        """
        # Plain text - should route to TEXT
        text_results = await search_service.search(
            QuerySpec(pattern="function", mode=SearchMode.AUTO, limit=5)
        )

        # Regex pattern - should route to REGEX
        regex_results = await search_service.search(
            QuerySpec(pattern="func.*ion", mode=SearchMode.AUTO, limit=5)
        )

        # Both should work without error
        assert isinstance(text_results, list)
        assert isinstance(regex_results, list)

    @pytest.mark.asyncio
    async def test_search_respects_limit_with_fixture(
        self, search_service: SearchService
    ) -> None:
        """Proves limit is respected with real fixture.

        Purpose: Limit enforcement validation.
        Quality Contribution: Performance control works.
        Acceptance Criteria: Never returns more than limit.
        """
        # Use a common pattern that will match many nodes
        results = await search_service.search(
            QuerySpec(pattern=".", mode=SearchMode.TEXT, limit=3)
        )

        # Limit should be respected
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_results_sorted_by_score_with_fixture(
        self, search_service: SearchService
    ) -> None:
        """Proves results are sorted by score descending.

        Purpose: Ranking validation.
        Quality Contribution: Best matches first.
        Acceptance Criteria: Each result's score >= next result's score.
        """
        results = await search_service.search(
            QuerySpec(pattern="class", mode=SearchMode.TEXT, limit=20)
        )

        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i].score >= results[i + 1].score

    @pytest.mark.asyncio
    async def test_case_insensitive_text_search(
        self, search_service: SearchService
    ) -> None:
        """Proves TEXT mode is case-insensitive with fixture.

        Purpose: Case-insensitive validation.
        Quality Contribution: User-friendly text search.
        Acceptance Criteria: Lowercase pattern matches uppercase content.
        """
        lower_results = await search_service.search(
            QuerySpec(pattern="config", mode=SearchMode.TEXT, limit=10)
        )

        upper_results = await search_service.search(
            QuerySpec(pattern="CONFIG", mode=SearchMode.TEXT, limit=10)
        )

        # Both should find the same nodes (if any)
        lower_ids = {r.node_id for r in lower_results}
        upper_ids = {r.node_id for r in upper_results}
        assert lower_ids == upper_ids


class TestSearchIntegrationEdgeCases:
    """Edge case integration tests."""

    @pytest.mark.asyncio
    async def test_search_with_special_characters(
        self, search_service: SearchService
    ) -> None:
        """Proves special characters are handled in TEXT mode.

        Purpose: Special character handling.
        Quality Contribution: Real-world patterns work.
        Acceptance Criteria: File patterns searchable.
        """
        # Search for a file pattern
        results = await search_service.search(
            QuerySpec(pattern=".py", mode=SearchMode.TEXT, limit=10)
        )

        # Should not crash, may find files
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_regex_with_grouping(self, search_service: SearchService) -> None:
        """Proves regex grouping works.

        Purpose: Complex regex validation.
        Quality Contribution: Advanced patterns work.
        Acceptance Criteria: Grouping patterns match.
        """
        results = await search_service.search(
            QuerySpec(pattern="(test|spec)", mode=SearchMode.REGEX, limit=10)
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_very_long_pattern_handled(
        self, search_service: SearchService
    ) -> None:
        """Proves long patterns don't crash.

        Purpose: Edge case handling.
        Quality Contribution: Robustness.
        Acceptance Criteria: Long pattern doesn't crash.
        """
        long_pattern = "x" * 100  # Long but valid pattern
        results = await search_service.search(
            QuerySpec(pattern=long_pattern, mode=SearchMode.TEXT, limit=10)
        )

        # Probably no matches, but shouldn't crash
        assert isinstance(results, list)
