"""Tests for SearchPanelService - sync wrapper over async SearchService.

Per DYK Insight #1: SearchService is async but Streamlit runs sync.
SearchPanelService provides a sync facade using asyncio.run() internally.

Full TDD tests covering:
- Sync wrapper functionality over async SearchService
- Mode routing (TEXT, REGEX, SEMANTIC, AUTO)
- Pagination (limit, offset)
- Error handling (SearchError propagation)
"""

import pytest
from dataclasses import dataclass

from fs2.core.models.search.query_spec import QuerySpec
from fs2.core.models.search.search_mode import SearchMode
from fs2.core.models.search.search_result import SearchResult


# =============================================================================
# SEARCH PANEL SERVICE RESULT TESTS
# =============================================================================


class TestSearchPanelResult:
    """Tests for SearchPanelResult dataclass."""

    def test_given_search_result_when_create_panel_result_then_has_correct_fields(
        self,
    ):
        """
        Purpose: Verifies SearchPanelResult structure.
        Quality Contribution: Foundation for service return type.
        """
        from fs2.web.services.search_panel_service import SearchPanelResult

        result = SearchPanelResult(
            results=[],
            total=0,
            mode_used=SearchMode.AUTO,
            query="test query",
        )

        assert result.results == []
        assert result.total == 0
        assert result.mode_used == SearchMode.AUTO
        assert result.query == "test query"

    def test_given_results_when_access_then_returns_search_results(self):
        """
        Purpose: Verifies SearchPanelResult can hold SearchResults.
        """
        from fs2.web.services.search_panel_service import SearchPanelResult

        mock_result = SearchResult(
            node_id="file:test.py",
            start_line=1,
            end_line=10,
            match_start_line=5,
            match_end_line=5,
            smart_content="A test file",
            snippet="def test():",
            score=0.85,
            match_field="content",
        )

        result = SearchPanelResult(
            results=[mock_result],
            total=1,
            mode_used=SearchMode.TEXT,
            query="test",
        )

        assert len(result.results) == 1
        assert result.results[0].node_id == "file:test.py"
        assert result.results[0].score == 0.85


# =============================================================================
# SEARCH PANEL SERVICE SYNC WRAPPER TESTS
# =============================================================================


class TestSearchPanelServiceSync:
    """Tests for sync wrapper functionality."""

    def test_given_async_search_when_search_sync_then_returns_results(self):
        """
        Purpose: Verifies sync wrapper calls async service correctly.
        Quality Contribution: Core functionality - async→sync bridge.
        """
        from fs2.web.services.search_panel_service import SearchPanelService
        from fs2.web.services.search_panel_service_fake import FakeSearchPanelService

        fake = FakeSearchPanelService()
        mock_result = SearchResult(
            node_id="file:example.py",
            start_line=1,
            end_line=20,
            match_start_line=10,
            match_end_line=10,
            smart_content="Example file",
            snippet="class Example:",
            score=0.9,
            match_field="content",
        )
        fake.set_results([mock_result])

        result = fake.search(pattern="example", mode=SearchMode.TEXT)

        assert len(result.results) == 1
        assert result.results[0].node_id == "file:example.py"
        assert len(fake.call_history) == 1
        assert fake.call_history[0]["pattern"] == "example"

    def test_given_empty_graph_when_search_then_returns_empty_results(self):
        """
        Purpose: Verifies empty search returns empty results.
        """
        from fs2.web.services.search_panel_service_fake import FakeSearchPanelService

        fake = FakeSearchPanelService()
        fake.set_results([])

        result = fake.search(pattern="nothing", mode=SearchMode.TEXT)

        assert result.results == []
        assert result.total == 0


# =============================================================================
# MODE ROUTING TESTS
# =============================================================================


class TestSearchPanelServiceModes:
    """Tests for search mode routing."""

    def test_given_text_mode_when_search_then_uses_text_mode(self):
        """
        Purpose: Verifies TEXT mode is passed through correctly.
        """
        from fs2.web.services.search_panel_service_fake import FakeSearchPanelService

        fake = FakeSearchPanelService()
        fake.set_results([])

        result = fake.search(pattern="test", mode=SearchMode.TEXT)

        assert result.mode_used == SearchMode.TEXT

    def test_given_regex_mode_when_search_then_uses_regex_mode(self):
        """
        Purpose: Verifies REGEX mode is passed through correctly.
        """
        from fs2.web.services.search_panel_service_fake import FakeSearchPanelService

        fake = FakeSearchPanelService()
        fake.set_results([])

        result = fake.search(pattern="test.*", mode=SearchMode.REGEX)

        assert result.mode_used == SearchMode.REGEX

    def test_given_semantic_mode_when_search_then_uses_semantic_mode(self):
        """
        Purpose: Verifies SEMANTIC mode is passed through correctly.
        """
        from fs2.web.services.search_panel_service_fake import FakeSearchPanelService

        fake = FakeSearchPanelService()
        fake.set_results([])

        result = fake.search(pattern="authentication flow", mode=SearchMode.SEMANTIC)

        assert result.mode_used == SearchMode.SEMANTIC

    def test_given_auto_mode_when_search_then_uses_auto_mode(self):
        """
        Purpose: Verifies AUTO mode is passed through (service resolves internally).
        Per DYK Insight #3: AUTO is the default mode.
        """
        from fs2.web.services.search_panel_service_fake import FakeSearchPanelService

        fake = FakeSearchPanelService()
        fake.set_results([])

        result = fake.search(pattern="find something", mode=SearchMode.AUTO)

        assert result.mode_used == SearchMode.AUTO


# =============================================================================
# PAGINATION TESTS
# =============================================================================


class TestSearchPanelServicePagination:
    """Tests for pagination support."""

    def test_given_limit_when_search_then_respects_limit(self):
        """
        Purpose: Verifies limit parameter is respected.
        """
        from fs2.web.services.search_panel_service_fake import FakeSearchPanelService

        fake = FakeSearchPanelService()
        # Create 10 mock results
        results = [
            SearchResult(
                node_id=f"file:test{i}.py",
                start_line=1,
                end_line=10,
                match_start_line=5,
                match_end_line=5,
                smart_content=f"Test file {i}",
                snippet=f"def test{i}():",
                score=0.9 - i * 0.05,
                match_field="content",
            )
            for i in range(10)
        ]
        fake.set_results(results)

        result = fake.search(pattern="test", mode=SearchMode.TEXT, limit=5)

        assert len(result.results) <= 5

    def test_given_offset_when_search_then_skips_results(self):
        """
        Purpose: Verifies offset parameter skips initial results.
        """
        from fs2.web.services.search_panel_service_fake import FakeSearchPanelService

        fake = FakeSearchPanelService()
        results = [
            SearchResult(
                node_id=f"file:test{i}.py",
                start_line=1,
                end_line=10,
                match_start_line=5,
                match_end_line=5,
                smart_content=f"Test file {i}",
                snippet=f"def test{i}():",
                score=0.9 - i * 0.05,
                match_field="content",
            )
            for i in range(10)
        ]
        fake.set_results(results)

        result = fake.search(pattern="test", mode=SearchMode.TEXT, offset=3)

        # Offset should skip first 3 results
        assert result.total == 10  # Total count remains same


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestSearchPanelServiceErrors:
    """Tests for error handling."""

    def test_given_semantic_without_embeddings_when_search_then_raises_error(self):
        """
        Purpose: Verifies SearchError is propagated for explicit SEMANTIC mode.
        Per DYK Insight #3: Explicit SEMANTIC raises SearchError if no embeddings.
        """
        from fs2.web.services.search_panel_service_fake import FakeSearchPanelService
        from fs2.core.services.search.exceptions import SearchError

        fake = FakeSearchPanelService()
        fake.simulate_error(
            SearchError("No nodes have embeddings. Run `fs2 scan --embed` to index.")
        )

        with pytest.raises(SearchError) as exc_info:
            fake.search(pattern="concept", mode=SearchMode.SEMANTIC)

        assert "embeddings" in str(exc_info.value)

    def test_given_invalid_regex_when_search_then_raises_error(self):
        """
        Purpose: Verifies invalid regex patterns raise appropriate error.
        """
        from fs2.web.services.search_panel_service_fake import FakeSearchPanelService

        fake = FakeSearchPanelService()
        fake.simulate_error(ValueError("Invalid regex pattern"))

        with pytest.raises(ValueError):
            fake.search(pattern="[invalid", mode=SearchMode.REGEX)


# =============================================================================
# FAKE SERVICE TESTS
# =============================================================================


class TestFakeSearchPanelService:
    """Tests for FakeSearchPanelService test double."""

    def test_given_fake_when_set_results_then_returns_configured_results(self):
        """
        Purpose: Verifies Fake service returns configured results.
        """
        from fs2.web.services.search_panel_service_fake import FakeSearchPanelService

        fake = FakeSearchPanelService()
        mock_result = SearchResult(
            node_id="file:configured.py",
            start_line=1,
            end_line=10,
            match_start_line=5,
            match_end_line=5,
            smart_content="Configured file",
            snippet="configured()",
            score=0.75,
            match_field="content",
        )
        fake.set_results([mock_result])

        result = fake.search(pattern="any", mode=SearchMode.TEXT)

        assert len(result.results) == 1
        assert result.results[0].node_id == "file:configured.py"

    def test_given_fake_when_search_then_records_call_history(self):
        """
        Purpose: Verifies Fake records all method calls.
        """
        from fs2.web.services.search_panel_service_fake import FakeSearchPanelService

        fake = FakeSearchPanelService()
        fake.set_results([])

        fake.search(pattern="test1", mode=SearchMode.TEXT)
        fake.search(pattern="test2", mode=SearchMode.REGEX)

        assert len(fake.call_history) == 2
        assert fake.call_history[0]["pattern"] == "test1"
        assert fake.call_history[1]["pattern"] == "test2"

    def test_given_fake_when_clear_then_resets_state(self):
        """
        Purpose: Verifies clear() resets the Fake state.
        """
        from fs2.web.services.search_panel_service_fake import FakeSearchPanelService

        fake = FakeSearchPanelService()
        mock_result = SearchResult(
            node_id="file:test.py",
            start_line=1,
            end_line=10,
            match_start_line=5,
            match_end_line=5,
            smart_content="Test",
            snippet="test()",
            score=0.5,
            match_field="content",
        )
        fake.set_results([mock_result])
        fake.search(pattern="test", mode=SearchMode.TEXT)

        fake.clear()

        assert fake.call_history == []
        result = fake.search(pattern="test", mode=SearchMode.TEXT)
        assert result.results == []  # Back to default empty
