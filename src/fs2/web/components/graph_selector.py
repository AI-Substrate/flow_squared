"""GraphSelector component - Global graph selection for web UI.

Per AC-19: Global graph selector appears on all exploration pages.
Per AC-20: Graph selection persists across page navigation.
Per DYK Insight #2: Uses GraphInfo.available to gray out missing graphs.

Example:
    >>> from fs2.web.components.graph_selector import GraphSelector
    >>> from fs2.core.services.graph_service import GraphService
    >>>
    >>> service = GraphService(config)
    >>> selector = GraphSelector(graph_service=service)
    >>>
    >>> # In Streamlit
    >>> selected = selector.render()  # Renders dropdown, returns selected name
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fs2.core.services.graph_service import GraphInfo

if TYPE_CHECKING:
    from fs2.core.services.graph_service import GraphService


class GraphSelector:
    """Graph selection dropdown component.

    Per Discovery 07: Graph selection must persist across page navigation.
    Uses session state with st.rerun() on selection change.

    Per DYK Insight #2: Uses GraphInfo.available to determine if graph
    can be selected. Unavailable graphs are grayed out with "(unavailable)"
    suffix.

    Attributes:
        SESSION_STATE_KEY: Session state key for persisting selection.
    """

    SESSION_STATE_KEY = "fs2_web_selected_graph"

    def __init__(self, graph_service: "GraphService") -> None:
        """Initialize GraphSelector with dependencies.

        Args:
            graph_service: GraphService for listing available graphs.
        """
        self._graph_service = graph_service

    def get_options(self) -> list[GraphInfo]:
        """Get all available graph options.

        Returns:
            List of GraphInfo for all graphs (including unavailable ones).
        """
        return self._graph_service.list_graphs()

    def get_available_options(self) -> list[GraphInfo]:
        """Get only available graph options.

        Returns:
            List of GraphInfo for available graphs only.
        """
        return [g for g in self.get_options() if g.available]

    @staticmethod
    def format_label(graph: GraphInfo) -> str:
        """Format graph info for display in dropdown.

        Per DYK Insight #2: Unavailable graphs have "(unavailable)" suffix.

        Args:
            graph: GraphInfo to format.

        Returns:
            Display label for the graph.
        """
        if not graph.available:
            return f"{graph.name} (unavailable)"
        return graph.name

    def get_selected(
        self, session_state: dict[str, Any] | None = None
    ) -> str | None:
        """Get currently selected graph name.

        Per AC-20: Selection persists across page navigation.

        Args:
            session_state: Session state dict (for testing). If None, uses
                Streamlit's session_state in production.

        Returns:
            Selected graph name, or first available if none selected,
            or None if no graphs available.
        """
        # Get options to find default
        options = self.get_options()
        available = [g for g in options if g.available]

        if not options:
            return None

        # Check session state for existing selection
        if session_state is not None:
            selected = session_state.get(self.SESSION_STATE_KEY)
        else:
            # In production, use Streamlit's session_state
            import streamlit as st

            selected = st.session_state.get(self.SESSION_STATE_KEY)

        # Validate selection is still available
        if selected:
            matching = [g for g in options if g.name == selected and g.available]
            if matching:
                return selected
            # Selected graph is now unavailable, fall back

        # Default to "default" if available, otherwise first available
        default_graph = next((g for g in available if g.name == "default"), None)
        if default_graph:
            return "default"

        if available:
            return available[0].name

        return None

    def render(self) -> str | None:
        """Render the graph selector dropdown.

        Per AC-19: Appears on all exploration pages.
        Per Discovery 07: Triggers st.rerun() on selection change.

        Returns:
            Selected graph name, or None if no graphs available.
        """
        import streamlit as st

        options = self.get_options()
        if not options:
            st.warning("No graphs available. Run `fs2 scan` to create a graph.")
            return None

        # Build options with labels
        labels = [self.format_label(g) for g in options]
        names = [g.name for g in options]
        disabled = [not g.available for g in options]

        # Get current selection
        current = self.get_selected()
        current_index = 0
        if current and current in names:
            current_index = names.index(current)

        # Render selectbox
        selected_label = st.selectbox(
            "Select Graph",
            options=labels,
            index=current_index,
            key="_fs2_graph_selector",
        )

        if selected_label:
            # Extract name from label (remove "(unavailable)" suffix if present)
            selected_name = selected_label.replace(" (unavailable)", "")

            # Update session state if changed
            if st.session_state.get(self.SESSION_STATE_KEY) != selected_name:
                st.session_state[self.SESSION_STATE_KEY] = selected_name
                st.rerun()

            return selected_name

        return None
