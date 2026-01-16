"""Dashboard page - Configuration health overview with quick actions.

This is the main landing page for the fs2 web UI, showing:
- Configuration health status (via DoctorPanel)
- Quick action buttons (scan, open config)
- Overview of current state

Per AC-06: Dashboard page provides health overview with quick actions.
"""

import streamlit as st

from fs2.web.components.doctor_panel import DoctorPanel
from fs2.web.components.health_badge import HealthBadge


def main() -> None:
    """Render the Dashboard page."""
    st.set_page_config(
        page_title="fs2 Dashboard",
        page_icon="*",
        layout="wide",
    )

    # Sidebar with health badge
    with st.sidebar:
        st.title("fs2")
        badge = HealthBadge()
        badge.render()

        st.divider()
        st.write("**Navigation**")
        st.write("- Dashboard (current)")
        st.write("- Configuration (coming soon)")
        st.write("- Graph Management (coming soon)")

    # Main content
    st.title("Dashboard")
    st.write("Welcome to fs2 - Flowspace2 configuration management.")

    # Health status panel
    st.header("Configuration Health")
    panel = DoctorPanel()
    panel.render()

    # Quick actions
    st.header("Quick Actions")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Run Scan", use_container_width=True):
            st.info("Run 'fs2 scan' from the command line to index your codebase.")

    with col2:
        if st.button("View Config", use_container_width=True):
            st.info("Configuration editing coming in Phase 3.")

    with col3:
        if st.button("View Docs", use_container_width=True):
            st.info(
                "Visit https://github.com/AI-Substrate/flow_squared for documentation."
            )


if __name__ == "__main__":
    main()
