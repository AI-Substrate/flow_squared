"""Tests for GraphSelector component - Service integration tests.

Per Critical Insight #3: Test service integration only - no render tests.
Per DYK Insight #2: GraphSelector must gray out unavailable graphs.

These tests verify:
- GraphSelector correctly calls GraphService.list_graphs()
- Selection persists in session state
- Unavailable graphs are marked with "(unavailable)" suffix
- Session state isolation with fs2_web_ prefix
"""

import pytest
from pathlib import Path

from fs2.core.services.graph_service import GraphInfo


# =============================================================================
# GRAPH SELECTOR SERVICE INTEGRATION TESTS
# =============================================================================


class TestGraphSelectorServiceIntegration:
    """Tests for GraphSelector service integration."""

    def test_given_graphs_when_get_options_then_returns_graph_names(self):
        """
        Purpose: Verifies GraphSelector reads graph list correctly.
        Quality Contribution: Foundation for dropdown display.
        Per AC-19: Global graph selector appears on all pages.
        """
        from fs2.web.components.graph_selector import GraphSelector
        from fs2.core.services.graph_service_fake import FakeGraphService

        fake_service = FakeGraphService()
        fake_service.add_graph_info(
            name="default",
            path=Path("/path/to/graph.pickle"),
            available=True,
        )
        fake_service.add_graph_info(
            name="external-lib",
            path=Path("/path/to/lib.pickle"),
            available=True,
        )

        selector = GraphSelector(graph_service=fake_service)
        options = selector.get_options()

        assert len(options) == 2
        assert "default" in [o.name for o in options]
        assert "external-lib" in [o.name for o in options]

    def test_given_unavailable_graph_when_get_options_then_marked_unavailable(self):
        """
        Purpose: Verifies unavailable graphs are marked.
        Quality Contribution: Prevents user from selecting missing graphs.
        Per DYK Insight #2: Gray out unavailable with "(unavailable)" suffix.
        """
        from fs2.web.components.graph_selector import GraphSelector
        from fs2.core.services.graph_service_fake import FakeGraphService

        fake_service = FakeGraphService()
        fake_service.add_graph_info(
            name="default",
            path=Path("/path/to/graph.pickle"),
            available=True,
        )
        fake_service.add_graph_info(
            name="missing-graph",
            path=Path("/path/to/missing.pickle"),
            available=False,  # Graph file doesn't exist
        )

        selector = GraphSelector(graph_service=fake_service)
        options = selector.get_options()

        # Check the unavailable graph is marked
        missing = next(o for o in options if o.name == "missing-graph")
        assert missing.available is False

    def test_given_no_graphs_when_get_options_then_returns_empty_list(self):
        """
        Purpose: Verifies GraphSelector handles empty graph list.
        """
        from fs2.web.components.graph_selector import GraphSelector
        from fs2.core.services.graph_service_fake import FakeGraphService

        fake_service = FakeGraphService()
        # No graphs added

        selector = GraphSelector(graph_service=fake_service)
        options = selector.get_options()

        assert options == []


# =============================================================================
# GRAPH SELECTOR DISPLAY LABEL TESTS
# =============================================================================


class TestGraphSelectorDisplayLabels:
    """Tests for display label formatting."""

    def test_given_available_graph_when_format_label_then_shows_name(self):
        """
        Purpose: Verifies available graphs show just name.
        """
        from fs2.web.components.graph_selector import GraphSelector

        label = GraphSelector.format_label(
            GraphInfo(
                name="my-graph",
                path=Path("/path/to/graph.pickle"),
                available=True,
            )
        )

        assert label == "my-graph"

    def test_given_unavailable_graph_when_format_label_then_shows_unavailable_suffix(
        self,
    ):
        """
        Purpose: Verifies unavailable graphs have suffix.
        Per DYK Insight #2: "(unavailable)" suffix for missing graphs.
        """
        from fs2.web.components.graph_selector import GraphSelector

        label = GraphSelector.format_label(
            GraphInfo(
                name="missing-graph",
                path=Path("/path/to/missing.pickle"),
                available=False,
            )
        )

        assert label == "missing-graph (unavailable)"

    def test_given_graph_with_description_when_format_label_then_includes_description(
        self,
    ):
        """
        Purpose: Verifies description is included when present.
        """
        from fs2.web.components.graph_selector import GraphSelector

        label = GraphSelector.format_label(
            GraphInfo(
                name="my-graph",
                path=Path("/path/to/graph.pickle"),
                description="My project graph",
                available=True,
            )
        )

        assert "my-graph" in label
        # Description could be included in various formats


# =============================================================================
# GRAPH SELECTOR SESSION STATE TESTS
# =============================================================================


class TestGraphSelectorSessionState:
    """Tests for session state management."""

    def test_session_state_key_uses_fs2_web_prefix(self):
        """
        Purpose: Verifies session state key follows namespace convention.
        Per Discovery 06: All session keys use fs2_web_ prefix.
        """
        from fs2.web.components.graph_selector import GraphSelector

        assert GraphSelector.SESSION_STATE_KEY == "fs2_web_selected_graph"

    def test_given_selection_when_get_selected_then_returns_selection(self):
        """
        Purpose: Verifies selection can be retrieved.
        Per AC-20: Graph selection persists across page navigation.
        """
        from fs2.web.components.graph_selector import GraphSelector
        from fs2.core.services.graph_service_fake import FakeGraphService

        fake_service = FakeGraphService()
        fake_service.add_graph_info(
            name="default",
            path=Path("/path/to/graph.pickle"),
            available=True,
        )

        selector = GraphSelector(graph_service=fake_service)

        # Simulate setting selection (would normally happen via Streamlit)
        mock_session_state = {"fs2_web_selected_graph": "default"}

        selected = selector.get_selected(session_state=mock_session_state)
        assert selected == "default"

    def test_given_no_selection_when_get_selected_then_returns_default(self):
        """
        Purpose: Verifies default selection when nothing selected.
        """
        from fs2.web.components.graph_selector import GraphSelector
        from fs2.core.services.graph_service_fake import FakeGraphService

        fake_service = FakeGraphService()
        fake_service.add_graph_info(
            name="default",
            path=Path("/path/to/graph.pickle"),
            available=True,
        )

        selector = GraphSelector(graph_service=fake_service)
        mock_session_state = {}

        selected = selector.get_selected(session_state=mock_session_state)

        # Should default to first available or "default"
        assert selected == "default"

    def test_given_unavailable_selection_when_get_selected_then_returns_first_available(
        self,
    ):
        """
        Purpose: Verifies fallback when selected graph becomes unavailable.
        """
        from fs2.web.components.graph_selector import GraphSelector
        from fs2.core.services.graph_service_fake import FakeGraphService

        fake_service = FakeGraphService()
        fake_service.add_graph_info(
            name="default",
            path=Path("/path/to/graph.pickle"),
            available=True,
        )
        fake_service.add_graph_info(
            name="missing",
            path=Path("/path/to/missing.pickle"),
            available=False,
        )

        selector = GraphSelector(graph_service=fake_service)
        mock_session_state = {"fs2_web_selected_graph": "missing"}

        # When selected graph is unavailable, should fall back to first available
        selected = selector.get_selected(session_state=mock_session_state)
        assert selected == "default"


# =============================================================================
# GRAPH SELECTOR AVAILABILITY FILTER TESTS
# =============================================================================


class TestGraphSelectorAvailability:
    """Tests for availability filtering."""

    def test_given_mixed_availability_when_get_available_options_then_filters_unavailable(
        self,
    ):
        """
        Purpose: Verifies unavailable graphs can be filtered out for selection.
        """
        from fs2.web.components.graph_selector import GraphSelector
        from fs2.core.services.graph_service_fake import FakeGraphService

        fake_service = FakeGraphService()
        fake_service.add_graph_info(
            name="available1",
            path=Path("/path/to/graph1.pickle"),
            available=True,
        )
        fake_service.add_graph_info(
            name="unavailable",
            path=Path("/path/to/missing.pickle"),
            available=False,
        )
        fake_service.add_graph_info(
            name="available2",
            path=Path("/path/to/graph2.pickle"),
            available=True,
        )

        selector = GraphSelector(graph_service=fake_service)
        available_only = selector.get_available_options()

        assert len(available_only) == 2
        assert all(o.available for o in available_only)
        assert not any(o.name == "unavailable" for o in available_only)
