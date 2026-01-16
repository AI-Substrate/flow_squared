"""HealthBadge component - Compact health status indicator.

Displays a colored badge in the sidebar showing configuration health:
- Green: All checks passed (healthy)
- Yellow: Warnings exist (warning)
- Red: Errors found (error)

Per AC-06: Health badge in sidebar shows green/yellow/red state.
"""

from typing import Protocol

from fs2.web.services.validation import ValidationResult, ValidationService


class ValidationServiceProtocol(Protocol):
    """Protocol for validation service (allows fake injection)."""

    def validate(self) -> ValidationResult: ...


class HealthBadge:
    """Compact health status badge for sidebar.

    Composes with ValidationService to display color-coded health.

    Usage:
        ```python
        import streamlit as st
        from fs2.web.components.health_badge import HealthBadge

        badge = HealthBadge()
        color = badge.get_color()

        # Use in sidebar
        with st.sidebar:
            badge.render()
        ```
    """

    def __init__(
        self,
        validation_service: ValidationServiceProtocol | None = None,
    ) -> None:
        """Initialize with optional validation service.

        Args:
            validation_service: Validation service (default: creates new one)
        """
        self._validation_service = validation_service or ValidationService()

    def get_color(self) -> str:
        """Get badge color based on health status.

        Returns:
            Color string: "green", "yellow", or "red"
        """
        try:
            result = self._validation_service.validate()

            if result.status == "healthy":
                return "green"
            elif result.status == "warning":
                return "yellow"
            else:
                return "red"
        except Exception:
            return "red"  # Error state

    def render(self) -> None:
        """Render the badge using Streamlit.

        Note: This method uses Streamlit and should only be called
        in a Streamlit context. Unit tests should use get_color() instead.
        """
        import streamlit as st

        color = self.get_color()

        # Color mapping for display
        color_map = {
            "green": ("success", "Healthy"),
            "yellow": ("warning", "Warning"),
            "red": ("error", "Error"),
        }

        status_type, label = color_map.get(color, ("error", "Unknown"))

        # Display colored badge
        if status_type == "success":
            st.sidebar.success(f"Config: {label}")
        elif status_type == "warning":
            st.sidebar.warning(f"Config: {label}")
        else:
            st.sidebar.error(f"Config: {label}")
