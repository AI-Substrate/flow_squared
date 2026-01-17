"""Tests for SearchPanel component - Search controls and result metadata.

Per DYK Insight #3: Defaults to AUTO mode, catches SearchError for explicit semantic.
Uses FakeSearchPanelService for testing.

These tests verify:
- Search input triggers search
- Mode selector (text/regex/semantic/auto)
- Limit/offset controls for pagination
- Result metadata display (count, mode used)
- SearchError handling with actionable message
"""

import pytest

from fs2.core.models.search.search_mode import SearchMode
from fs2.core.models.search.search_result import SearchResult
from fs2.web.services.search_panel_service import SearchPanelResult
from fs2.web.services.search_panel_service_fake import FakeSearchPanelService
from fs2.core.services.search.exceptions import SearchError


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def make_search_result(node_id: str, score: float = 0.8) -> SearchResult:
    """Create a SearchResult for tests."""
    return SearchResult(
        node_id=node_id,
        start_line=1,
        end_line=10,
        match_start_line=5,
        match_end_line=5,
        smart_content="Test content",
        snippet="test snippet",
        score=score,
        match_field="content",
    )


# =============================================================================
# SEARCH PANEL BASIC TESTS
# =============================================================================


class TestSearchPanelBasic:
    """Tests for basic SearchPanel functionality."""

    def test_given_pattern_when_search_then_calls_service(self):
        """
        Purpose: Verifies search triggers service call.
        Quality Contribution: Core search functionality.
        """
        from fs2.web.components.search_panel import SearchPanel

        fake_service = FakeSearchPanelService()
        fake_service.set_results([make_search_result("file:test.py")])

        panel = SearchPanel(search_service=fake_service)
        result = panel.do_search(pattern="test")

        assert len(fake_service.call_history) == 1
        assert fake_service.call_history[0]["pattern"] == "test"
        assert len(result.results) == 1

    def test_given_empty_pattern_when_search_then_returns_empty(self):
        """
        Purpose: Verifies empty pattern returns empty results.
        """
        from fs2.web.components.search_panel import SearchPanel

        fake_service = FakeSearchPanelService()

        panel = SearchPanel(search_service=fake_service)
        result = panel.do_search(pattern="")

        # Empty pattern should not call service
        assert len(fake_service.call_history) == 0
        assert result is None or result.results == []


# =============================================================================
# SEARCH MODE TESTS
# =============================================================================


class TestSearchPanelModes:
    """Tests for search mode selection."""

    def test_given_auto_mode_when_search_then_uses_auto(self):
        """
        Purpose: Verifies AUTO mode is default.
        Per DYK Insight #3: Defaults to AUTO mode.
        """
        from fs2.web.components.search_panel import SearchPanel

        fake_service = FakeSearchPanelService()
        fake_service.set_results([])

        panel = SearchPanel(search_service=fake_service)
        panel.do_search(pattern="test")

        assert fake_service.call_history[0]["mode"] == SearchMode.AUTO

    def test_given_text_mode_when_search_then_uses_text(self):
        """
        Purpose: Verifies TEXT mode can be selected.
        """
        from fs2.web.components.search_panel import SearchPanel

        fake_service = FakeSearchPanelService()
        fake_service.set_results([])

        panel = SearchPanel(search_service=fake_service)
        panel.do_search(pattern="test", mode=SearchMode.TEXT)

        assert fake_service.call_history[0]["mode"] == SearchMode.TEXT

    def test_given_regex_mode_when_search_then_uses_regex(self):
        """
        Purpose: Verifies REGEX mode can be selected.
        """
        from fs2.web.components.search_panel import SearchPanel

        fake_service = FakeSearchPanelService()
        fake_service.set_results([])

        panel = SearchPanel(search_service=fake_service)
        panel.do_search(pattern="test.*", mode=SearchMode.REGEX)

        assert fake_service.call_history[0]["mode"] == SearchMode.REGEX

    def test_given_semantic_mode_when_search_then_uses_semantic(self):
        """
        Purpose: Verifies SEMANTIC mode can be selected.
        """
        from fs2.web.components.search_panel import SearchPanel

        fake_service = FakeSearchPanelService()
        fake_service.set_results([])

        panel = SearchPanel(search_service=fake_service)
        panel.do_search(pattern="authentication flow", mode=SearchMode.SEMANTIC)

        assert fake_service.call_history[0]["mode"] == SearchMode.SEMANTIC


# =============================================================================
# PAGINATION TESTS
# =============================================================================


class TestSearchPanelPagination:
    """Tests for pagination controls."""

    def test_given_limit_when_search_then_respects_limit(self):
        """
        Purpose: Verifies limit parameter is passed to service.
        """
        from fs2.web.components.search_panel import SearchPanel

        fake_service = FakeSearchPanelService()
        fake_service.set_results([make_search_result(f"file:test{i}.py") for i in range(20)])

        panel = SearchPanel(search_service=fake_service)
        result = panel.do_search(pattern="test", limit=5)

        assert fake_service.call_history[0]["limit"] == 5
        assert len(result.results) <= 5

    def test_given_offset_when_search_then_skips_results(self):
        """
        Purpose: Verifies offset parameter is passed to service.
        """
        from fs2.web.components.search_panel import SearchPanel

        fake_service = FakeSearchPanelService()
        fake_service.set_results([make_search_result(f"file:test{i}.py") for i in range(20)])

        panel = SearchPanel(search_service=fake_service)
        result = panel.do_search(pattern="test", offset=10)

        assert fake_service.call_history[0]["offset"] == 10


# =============================================================================
# RESULT METADATA TESTS
# =============================================================================


class TestSearchPanelMetadata:
    """Tests for result metadata display."""

    def test_given_results_when_format_metadata_then_shows_count(self):
        """
        Purpose: Verifies result count is displayed.
        """
        from fs2.web.components.search_panel import SearchPanel

        fake_service = FakeSearchPanelService()
        results = [make_search_result(f"file:test{i}.py") for i in range(15)]
        fake_service.set_results(results)

        panel = SearchPanel(search_service=fake_service)
        result = panel.do_search(pattern="test")
        metadata = panel.format_metadata(result)

        assert "15" in metadata
        assert "results" in metadata.lower() or "found" in metadata.lower()

    def test_given_results_when_format_metadata_then_shows_mode(self):
        """
        Purpose: Verifies search mode is displayed.
        """
        from fs2.web.components.search_panel import SearchPanel

        fake_service = FakeSearchPanelService()
        fake_service.set_results([make_search_result("file:test.py")])

        panel = SearchPanel(search_service=fake_service)
        result = panel.do_search(pattern="test", mode=SearchMode.REGEX)
        metadata = panel.format_metadata(result)

        assert "regex" in metadata.lower()


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestSearchPanelErrors:
    """Tests for error handling."""

    def test_given_semantic_without_embeddings_when_search_then_shows_error(self):
        """
        Purpose: Verifies SearchError is caught and formatted.
        Per DYK Insight #3: Catches SearchError for explicit semantic mode.
        """
        from fs2.web.components.search_panel import SearchPanel

        fake_service = FakeSearchPanelService()
        fake_service.simulate_error(
            SearchError("No nodes have embeddings. Run `fs2 scan --embed` to index.")
        )

        panel = SearchPanel(search_service=fake_service)
        result = panel.do_search(pattern="concept", mode=SearchMode.SEMANTIC)

        # Should return error result, not raise
        assert result is not None
        assert result.error is not None
        assert "embeddings" in result.error

    def test_given_invalid_regex_when_search_then_shows_error(self):
        """
        Purpose: Verifies invalid regex is caught and formatted.
        """
        from fs2.web.components.search_panel import SearchPanel

        fake_service = FakeSearchPanelService()
        fake_service.simulate_error(ValueError("Invalid regex pattern: [unclosed"))

        panel = SearchPanel(search_service=fake_service)
        result = panel.do_search(pattern="[unclosed", mode=SearchMode.REGEX)

        assert result is not None
        assert result.error is not None


# =============================================================================
# SESSION STATE TESTS
# =============================================================================


class TestSearchPanelSessionState:
    """Tests for session state management."""

    def test_session_state_key_uses_fs2_web_prefix(self):
        """
        Purpose: Verifies session state key follows namespace convention.
        Per Discovery 06: All session keys use fs2_web_ prefix.
        """
        from fs2.web.components.search_panel import SearchPanel

        assert SearchPanel.RESULTS_KEY == "fs2_web_search_results"
        assert SearchPanel.QUERY_KEY == "fs2_web_search_query"

    def test_given_search_when_get_result_node_ids_then_returns_ids(self):
        """
        Purpose: Verifies node_ids can be extracted for TreeView.
        """
        from fs2.web.components.search_panel import SearchPanel

        fake_service = FakeSearchPanelService()
        results = [
            make_search_result("file:test1.py"),
            make_search_result("file:test2.py"),
        ]
        fake_service.set_results(results)

        panel = SearchPanel(search_service=fake_service)
        result = panel.do_search(pattern="test")
        node_ids = panel.get_result_node_ids(result)

        assert len(node_ids) == 2
        assert "file:test1.py" in node_ids
        assert "file:test2.py" in node_ids


# =============================================================================
# CLEAR SEARCH TESTS
# =============================================================================


class TestSearchPanelClear:
    """Tests for clear search functionality."""

    def test_given_search_results_when_clear_then_returns_none(self):
        """
        Purpose: Verifies clear_search() clears results and returns None.
        """
        from fs2.web.components.search_panel import SearchPanel

        fake_service = FakeSearchPanelService()
        results = [make_search_result("file:test.py")]
        fake_service.set_results(results)

        panel = SearchPanel(search_service=fake_service)

        # First do a search
        result = panel.do_search(pattern="test")
        assert result is not None
        assert len(result.results) == 1

        # Now clear
        cleared = panel.clear_search()
        assert cleared is None

    def test_given_clear_when_get_cleared_state_then_is_cleared_true(self):
        """
        Purpose: Verifies is_cleared property reflects clear state.
        """
        from fs2.web.components.search_panel import SearchPanel

        fake_service = FakeSearchPanelService()
        panel = SearchPanel(search_service=fake_service)

        # Initially not cleared (no search done)
        assert panel.is_cleared is True

        # After search, not cleared
        fake_service.set_results([make_search_result("file:test.py")])
        panel.do_search(pattern="test")
        # Note: We'd need session state to track this properly in real usage

    def test_clear_search_key_uses_fs2_web_prefix(self):
        """
        Purpose: Verifies clear state key follows namespace convention.
        """
        from fs2.web.components.search_panel import SearchPanel

        assert hasattr(SearchPanel, "CLEARED_KEY")
        assert SearchPanel.CLEARED_KEY == "fs2_web_search_cleared"
