"""fs2 Hub - Streamlit Web UI.

Per Phase 1 Foundation:
- T013: Basic app with sidebar navigation and page placeholders
- Critical Discovery 06: Session isolation (stateless service pattern)

Launch with: fs2 web

The app follows Streamlit's multi-page pattern where each page
is a separate module that re-runs on every interaction.

Per Critical Insight #2: Services are stateless - always load fresh.
This means every interaction loads configuration from disk, ensuring
the UI always shows current state.
"""

import streamlit as st

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
        st.markdown("---")

        # Navigation menu (placeholder for future pages)
        page = st.radio(
            "Navigation",
            options=[
                "Dashboard",
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
    elif page == "Configuration":
        _render_configuration()
    elif page == "Graph Browser":
        _render_graph_browser()
    elif page == "Doctor":
        _render_doctor()


def _render_dashboard() -> None:
    """Render the dashboard page (placeholder).

    Future: Show quick stats, recent scans, health status.
    """
    st.info(
        "**Dashboard** - Coming in Phase 2\n\n"
        "This page will show:\n"
        "- Quick stats about your codebase\n"
        "- Recent scan activity\n"
        "- Health status indicators"
    )


def _render_configuration() -> None:
    """Render the configuration page (placeholder).

    Future: Show and edit config with source attribution.
    """
    st.info(
        "**Configuration** - Coming in Phase 2\n\n"
        "This page will show:\n"
        "- Current config values with source attribution\n"
        "- Placeholder resolution status\n"
        "- Edit functionality (Phase 3)"
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


def _render_doctor() -> None:
    """Render the doctor diagnostics page (placeholder).

    Future: Run health checks, show issues.
    """
    st.info(
        "**Doctor** - Coming in Phase 6\n\n"
        "This page will show:\n"
        "- Configuration health checks\n"
        "- Graph health status\n"
        "- Issue resolution guidance"
    )


if __name__ == "__main__":
    main()
