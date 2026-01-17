"""Explore page - Browse and search code graphs.

This page provides the unified code exploration interface:
- GraphSelector at top for graph selection
- SearchPanel + TreeView in main area
- NodeInspector in sidebar for source code display

Per AC-19: Global graph selector appears on all exploration pages.
Per AC-21: Search box filters tree to matching nodes.
Per AC-22: Click search result expands node in tree and shows children.

Example usage:
    Run `fs2 web` and navigate to "Explore" in the sidebar.
"""

import streamlit as st
from pathlib import Path

from fs2.web.components.health_badge import HealthBadge


def main() -> None:
    """Render the Explore page."""
    st.set_page_config(
        page_title="fs2 Explore",
        page_icon="🔍",
        layout="wide",
    )

    # Sidebar with health badge and node inspector
    with st.sidebar:
        st.title("fs2")
        badge = HealthBadge()
        badge.render()

        st.divider()
        st.write("**Navigation**")
        st.page_link("1_Dashboard.py", label="Dashboard")
        st.page_link("5_Explore.py", label="Explore (current)")

        st.divider()

        # Node Inspector in sidebar
        _render_node_inspector()

    # Main content
    st.title("🔍 Explore")

    # Graph Selector at top
    selected_graph = _render_graph_selector()

    if not selected_graph:
        st.warning("No graphs available. Run `fs2 scan` to create a graph.")
        return

    st.divider()

    # Main area: Search + TreeView
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Search")
        result_node_ids = _render_search_panel(selected_graph)

    with col2:
        st.subheader("Code Structure")
        _render_tree_view(selected_graph, result_node_ids)


def _render_graph_selector() -> str | None:
    """Render the graph selector and return selected graph name.

    Returns:
        Selected graph name or None if no graphs available.
    """
    try:
        from fs2.core.services.graph_service import GraphService
        from fs2.config.service import ConfigurationService
        from fs2.web.components.graph_selector import GraphSelector

        config = ConfigurationService()
        graph_service = GraphService(config)
        selector = GraphSelector(graph_service=graph_service)

        return selector.render()
    except Exception as e:
        st.error(f"Failed to load graphs: {e}")
        return None


def _render_search_panel(selected_graph: str) -> list[str]:
    """Render the search panel and return result node_ids.

    Args:
        selected_graph: Currently selected graph name.

    Returns:
        List of node_ids from search results.
    """
    try:
        from fs2.config.service import ConfigurationService
        from fs2.config.objects import ScanConfig
        from fs2.core.services.graph_service import GraphService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore
        from fs2.web.services.search_panel_service import SearchPanelService
        from fs2.web.components.search_panel import SearchPanel

        # Get graph store for the selected graph
        config = ConfigurationService()
        graph_service = GraphService(config)
        graph_store = graph_service.get_graph(selected_graph)

        # Create search service and panel
        search_service = SearchPanelService(graph_store=graph_store)
        panel = SearchPanel(search_service=search_service)

        return panel.render()
    except Exception as e:
        st.error(f"Search error: {e}")
        return []


def _render_tree_view(selected_graph: str, starter_nodes: list[str]) -> None:
    """Render the tree view.

    Args:
        selected_graph: Currently selected graph name.
        starter_nodes: Optional list of node_ids to show as roots (from search).
    """
    try:
        from fs2.config.service import ConfigurationService
        from fs2.core.services.graph_service import GraphService
        from fs2.web.components.tree_view import TreeView

        # Get graph store for the selected graph
        config = ConfigurationService()
        graph_service = GraphService(config)
        graph_store = graph_service.get_graph(selected_graph)

        # Create tree view with search results as starter nodes
        tree_view = TreeView(
            graph_store=graph_store,
            starter_nodes=starter_nodes if starter_nodes else None,
        )

        tree_view.render()
    except Exception as e:
        st.error(f"Tree view error: {e}")


def _render_node_inspector() -> None:
    """Render the node inspector in sidebar."""
    try:
        from fs2.config.service import ConfigurationService
        from fs2.core.services.graph_service import GraphService
        from fs2.web.components.node_inspector import NodeInspector

        st.subheader("Source Code")

        # Get selected graph from session state
        selected_graph = st.session_state.get("fs2_web_selected_graph")

        if not selected_graph:
            st.info("Select a graph first.")
            return

        # Get graph store
        config = ConfigurationService()
        graph_service = GraphService(config)

        try:
            graph_store = graph_service.get_graph(selected_graph)
        except Exception:
            st.info("Select a valid graph first.")
            return

        # Create and render inspector
        inspector = NodeInspector(graph_store=graph_store)
        inspector.render()
    except Exception as e:
        st.error(f"Inspector error: {e}")


if __name__ == "__main__":
    main()
