"""fs2 Hub - Streamlit Web UI.

Per Phase 1 Foundation:
- T013: Basic app with sidebar navigation and page placeholders
- Critical Discovery 06: Session isolation (stateless service pattern)

Per Phase 2 Diagnostics Integration:
- Dashboard shows health status via DoctorPanel
- Sidebar shows HealthBadge with color-coded status

Launch with: fs2 web

The app follows Streamlit's multi-page pattern where each page
is a separate module that re-runs on every interaction.

Per Critical Insight #2: Services are stateless - always load fresh.
This means every interaction loads configuration from disk, ensuring
the UI always shows current state.
"""

import streamlit as st

from fs2.web.components.doctor_panel import DoctorPanel
from fs2.web.components.health_badge import HealthBadge

# Page configuration must be first Streamlit call
st.set_page_config(
    page_title="fs2 Hub",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    """Main entry point for fs2 Hub."""
    # Sidebar navigation
    with st.sidebar:
        st.title("🔍 fs2 Hub")

        # Health badge (Phase 2)
        badge = HealthBadge()
        badge.render()

        st.markdown("---")

        # Navigation menu
        page = st.radio(
            "Navigation",
            options=[
                "Dashboard",
                "Explore",
                "Configuration",
                "Graph Browser",
                "Doctor",
            ],
            label_visibility="collapsed",
        )

        st.markdown("---")
        st.caption("fs2 - Code Intelligence")

    # Main content area
    st.title(f"📄 {page}")

    if page == "Dashboard":
        _render_dashboard()
    elif page == "Explore":
        _render_explore()
    elif page == "Configuration":
        _render_configuration()
    elif page == "Graph Browser":
        _render_graph_browser()
    elif page == "Doctor":
        _render_doctor()


def _render_dashboard() -> None:
    """Render the dashboard page with health status.

    Per Phase 2: Shows configuration health via DoctorPanel.
    """
    st.write("Welcome to fs2 Hub - your code intelligence dashboard.")

    # Configuration health panel (Phase 2)
    st.subheader("Configuration Health")
    panel = DoctorPanel()
    panel.render()

    # Quick actions
    st.subheader("Quick Actions")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Run Scan", use_container_width=True):
            st.info("Run `fs2 scan` from the command line to index your codebase.")

    with col2:
        if st.button("View Config", use_container_width=True):
            st.info("Configuration editing coming in Phase 3.")

    with col3:
        if st.button("View Docs", use_container_width=True):
            st.info(
                "Visit https://github.com/AI-Substrate/flow_squared for documentation."
            )


def _render_configuration() -> None:
    """Render the configuration page (placeholder).

    Future: Show and edit config with source attribution.
    """
    st.info(
        "**Configuration** - Coming in Phase 3\n\n"
        "This page will show:\n"
        "- Current config values with source attribution\n"
        "- Placeholder resolution status\n"
        "- Edit functionality"
    )

    # Demo: Show config inspection result structure
    with st.expander("Preview: Configuration Structure"):
        st.code(
            """
# Example of how config will be displayed:
llm:
  provider: azure       # Source: project (.fs2/config.yaml)
  api_key: ${API_KEY}   # ✅ Resolved from .env
  timeout: 30           # Source: default
""",
            language="yaml",
        )


def _render_graph_browser() -> None:
    """Render the graph browser page (placeholder).

    Future: Browse code structure, search nodes.
    """
    st.info(
        "**Graph Browser** - Coming in Phase 5\n\n"
        "This page will show:\n"
        "- Code structure tree\n"
        "- Node search and filtering\n"
        "- Node details viewer"
    )


def _render_explore() -> None:
    """Render the Explore page with graph browser and search.

    Per Phase 3: Browse and search code graphs.
    Per AC-19: Global graph selector appears on all exploration pages.
    Per AC-21: Search box filters tree to matching nodes.
    Per AC-22: Click search result expands node in tree.
    """
    st.write("Browse and search your code graphs.")

    try:
        from fs2.core.services.graph_service import GraphService
        from fs2.config.service import FS2ConfigurationService
        from fs2.web.components.graph_selector import GraphSelector
        from fs2.web.components.tree_view import TreeView
        from fs2.web.components.search_panel import SearchPanel
        from fs2.web.components.node_inspector import NodeInspector
        from fs2.web.services.search_panel_service import SearchPanelService

        config = FS2ConfigurationService()
        graph_service = GraphService(config)

        # Graph Selector at top
        selector = GraphSelector(graph_service=graph_service)
        selected_graph = selector.render()

        if not selected_graph:
            st.warning("No graphs available. Run `fs2 scan` to create a graph.")
            return

        st.divider()

        # Get the selected graph store
        graph_store = graph_service.get_graph(selected_graph)

        # Main area: Search + TreeView side by side
        col1, col2 = st.columns([1, 2])

        with col1:
            st.subheader("🔍 Search")
            search_service = SearchPanelService(graph_store=graph_store)
            search_panel = SearchPanel(search_service=search_service)
            result_node_ids = search_panel.render()

        with col2:
            st.subheader("📂 Code Structure")
            tree_view = TreeView(
                graph_store=graph_store,
                starter_nodes=result_node_ids if result_node_ids else None,
            )
            tree_view.render()

        # Node Inspector below (or could be in sidebar)
        st.divider()
        st.subheader("📄 Source Code")
        inspector = NodeInspector(graph_store=graph_store)
        inspector.render()

    except Exception as e:
        st.error(f"Failed to load Explore page: {e}")
        st.info(
            "Make sure you have scanned a codebase with `fs2 scan`.\n\n"
            "Error details: " + str(e)
        )


def _render_doctor() -> None:
    """Render the doctor diagnostics page.

    Shows detailed health checks (basic version from Dashboard DoctorPanel).
    """
    st.write("Detailed configuration diagnostics.")

    # Reuse DoctorPanel for now - can be expanded in future phases
    panel = DoctorPanel()
    panel.render()

    st.info(
        "**Tip**: Run `fs2 doctor` from the command line for CLI-based diagnostics."
    )


if __name__ == "__main__":
    main()
