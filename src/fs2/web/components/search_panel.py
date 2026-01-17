"""SearchPanel component - Search controls and result metadata display.

Per DYK Insight #3: Defaults to AUTO mode, catches SearchError for explicit semantic.
Per AC-11: Multiple search modes (text, regex, semantic).
Per AC-21: Search box filters tree to matching nodes.

Example:
    >>> from fs2.web.components.search_panel import SearchPanel
    >>> from fs2.web.services.search_panel_service import SearchPanelService
    >>>
    >>> service = SearchPanelService(graph_store=store)
    >>> panel = SearchPanel(search_service=service)
    >>> result = panel.do_search(pattern="auth")
    >>> node_ids = panel.get_result_node_ids(result)  # Pass to TreeView
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fs2.core.models.search.search_mode import SearchMode
from fs2.core.services.search.exceptions import SearchError

if TYPE_CHECKING:
    from fs2.web.services.search_panel_service import (
        SearchPanelResult,
        SearchPanelService,
    )


@dataclass
class SearchPanelOutput:
    """Result from SearchPanel.do_search() including error handling.

    Attributes:
        results: List of SearchResult items (empty on error).
        total: Total number of matches.
        mode_used: The SearchMode that was used.
        query: The original search pattern.
        error: Error message if search failed, None otherwise.
    """

    results: list
    total: int
    mode_used: SearchMode
    query: str
    error: str | None = None


class SearchPanel:
    """Search controls and result metadata display component.

    Per DYK Insight #3: Defaults to AUTO mode which gracefully falls back.
    Catches SearchError for explicit SEMANTIC mode and shows actionable message.

    Per Discovery 06: Uses session state with fs2_web_ prefix.

    Attributes:
        RESULTS_KEY: Session state key for search results.
        QUERY_KEY: Session state key for current query.
        CLEARED_KEY: Session state key for cleared state.
    """

    RESULTS_KEY = "fs2_web_search_results"
    QUERY_KEY = "fs2_web_search_query"
    CLEARED_KEY = "fs2_web_search_cleared"

    def __init__(self, search_service: "SearchPanelService") -> None:
        """Initialize SearchPanel with dependencies.

        Args:
            search_service: SearchPanelService for executing searches.
        """
        self._search_service = search_service
        self._is_cleared = True  # Initially no search active

    @property
    def is_cleared(self) -> bool:
        """Check if search is in cleared state (no active search)."""
        return self._is_cleared

    def clear_search(self) -> None:
        """Clear search results and reset to default tree view.

        Returns:
            None to signal TreeView should show default roots.
        """
        self._is_cleared = True
        return None

    def do_search(
        self,
        pattern: str,
        mode: SearchMode = SearchMode.AUTO,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchPanelOutput | None:
        """Execute a search and return results.

        Per DYK Insight #3: Defaults to AUTO mode.
        Catches SearchError and returns error in output instead of raising.

        Args:
            pattern: Search pattern (empty returns None).
            mode: Search mode (default: AUTO).
            limit: Maximum results to return.
            offset: Number of results to skip.

        Returns:
            SearchPanelOutput with results or error, None if pattern empty.
        """
        if not pattern or not pattern.strip():
            return None

        self._is_cleared = False  # Search is now active

        try:
            result = self._search_service.search(
                pattern=pattern,
                mode=mode,
                limit=limit,
                offset=offset,
            )
            return SearchPanelOutput(
                results=result.results,
                total=result.total,
                mode_used=result.mode_used,
                query=result.query,
                error=None,
            )
        except SearchError as e:
            return SearchPanelOutput(
                results=[],
                total=0,
                mode_used=mode,
                query=pattern,
                error=str(e),
            )
        except ValueError as e:
            return SearchPanelOutput(
                results=[],
                total=0,
                mode_used=mode,
                query=pattern,
                error=str(e),
            )

    def format_metadata(self, result: SearchPanelOutput) -> str:
        """Format result metadata for display.

        Args:
            result: SearchPanelOutput to format.

        Returns:
            Formatted string with count and mode.
        """
        if result.error:
            return f"Error: {result.error}"

        mode_name = result.mode_used.value if result.mode_used else "unknown"
        return f"{result.total} results found ({mode_name} mode)"

    def get_result_node_ids(self, result: SearchPanelOutput) -> list[str]:
        """Extract node_ids from results for TreeView.

        Args:
            result: SearchPanelOutput with results.

        Returns:
            List of node_id strings.
        """
        if not result or not result.results:
            return []
        return [r.node_id for r in result.results]

    def render(self) -> list[str]:
        """Render the search panel and return result node_ids.

        Returns:
            List of node_ids from search results (for TreeView).
            Empty list signals TreeView to show default roots.
        """
        import streamlit as st

        # Define clear callback - runs BEFORE widget render on next rerun
        def _clear_callback():
            self.clear_search()
            st.session_state[self.QUERY_KEY] = ""
            st.session_state[self.RESULTS_KEY] = None
            st.session_state[self.CLEARED_KEY] = True

        # Check if we need to show cleared state (from callback)
        show_cleared = st.session_state.get(self.CLEARED_KEY, False)
        if show_cleared:
            st.session_state[self.CLEARED_KEY] = False

        # Search input
        col1, col2 = st.columns([3, 1])

        with col1:
            query = st.text_input(
                "Search",
                value="" if show_cleared else st.session_state.get(self.QUERY_KEY, ""),
                key="_fs2_search_query" if not show_cleared else f"_fs2_search_query_{id(self)}",
                placeholder="Enter search pattern...",
            )

        with col2:
            mode_options = ["auto", "text", "regex", "semantic"]
            selected_mode = st.selectbox(
                "Mode",
                options=mode_options,
                key="_fs2_search_mode",
            )

        # Pagination controls
        col3, col4 = st.columns(2)

        with col3:
            limit = st.number_input(
                "Results per page",
                min_value=1,
                max_value=100,
                value=20,
                key="_fs2_search_limit",
            )

        with col4:
            offset = st.number_input(
                "Skip results",
                min_value=0,
                value=0,
                key="_fs2_search_offset",
            )

        # Search and Clear buttons
        col_btn1, col_btn2 = st.columns(2)

        with col_btn1:
            search_clicked = st.button("🔍 Search", key="_fs2_search_button")

        with col_btn2:
            st.button("✖ Clear", key="_fs2_clear_button", on_click=_clear_callback)

        # Execute search on button click OR when query changes (enter key)
        result = None
        previous_query = st.session_state.get(self.QUERY_KEY, "")
        query_changed = query and query != previous_query

        if (search_clicked or query_changed) and query:
            mode = SearchMode(selected_mode)
            result = self.do_search(
                pattern=query,
                mode=mode,
                limit=int(limit),
                offset=int(offset),
            )

            # Store in session state
            st.session_state[self.QUERY_KEY] = query
            st.session_state[self.RESULTS_KEY] = result
        elif not show_cleared:
            # Restore previous results
            result = st.session_state.get(self.RESULTS_KEY)

        # Display metadata
        if result:
            if result.error:
                st.error(result.error)
            else:
                st.info(self.format_metadata(result))

            return self.get_result_node_ids(result)

        return []
