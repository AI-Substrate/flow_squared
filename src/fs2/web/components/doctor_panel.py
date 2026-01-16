"""DoctorPanel component - Configuration health status display.

Displays configuration health status with:
- Overall status (healthy/warning/error)
- LLM and embedding provider status
- Unresolved placeholders
- Actionable fix suggestions

Per AC-06: Doctor panel shows current health status with actionable fix suggestions.
"""

from typing import Protocol

from fs2.web.services.validation import ValidationResult, ValidationService


class ValidationServiceProtocol(Protocol):
    """Protocol for validation service (allows fake injection)."""

    def validate(self) -> ValidationResult: ...


class DoctorPanel:
    """Configuration health status panel component.

    Composes with ValidationService to display health status.
    Handles errors gracefully for robust UI.

    Usage:
        ```python
        import streamlit as st
        from fs2.web.components.doctor_panel import DoctorPanel

        panel = DoctorPanel()
        status = panel.get_status()

        if status.status == "healthy":
            st.success("All checks passed!")
        elif status.status == "warning":
            for s in status.suggestions:
                st.warning(s)
        else:
            for issue in status.issues:
                st.error(issue)
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

    def get_status(self) -> ValidationResult:
        """Get current configuration health status.

        Calls validation service and returns result.
        Handles errors gracefully - returns error result instead of raising.

        Returns:
            ValidationResult with status, issues, suggestions, etc.
        """
        try:
            return self._validation_service.validate()
        except Exception as e:
            # Return error result instead of crashing UI
            return ValidationResult(
                status="error",
                issues=[f"Validation error: {e}"],
            )

    def render(self) -> None:
        """Render the panel using Streamlit.

        Note: This method uses Streamlit and should only be called
        in a Streamlit context. Unit tests should use get_status() instead.
        """
        import streamlit as st

        status = self.get_status()

        # Status header
        if status.status == "healthy":
            st.success("All checks passed")
        elif status.status == "warning":
            st.warning(f"{len(status.suggestions)} items need attention")
        else:
            st.error(f"{len(status.issues)} issues found")

        # Provider status
        col1, col2 = st.columns(2)
        with col1:
            if status.llm_configured:
                st.write(f"**LLM Provider**: {status.llm_provider} (configured)")
            elif status.llm_misconfigured:
                st.write("**LLM Provider**: Misconfigured")
            else:
                st.write("**LLM Provider**: Not configured")

        with col2:
            if status.embedding_configured:
                st.write(f"**Embedding**: {status.embedding_mode} (configured)")
            elif status.embedding_misconfigured:
                st.write("**Embedding**: Misconfigured")
            else:
                st.write("**Embedding**: Not configured")

        # Issues
        if status.issues:
            st.subheader("Issues")
            for issue in status.issues:
                st.error(issue)

        # Suggestions
        if status.suggestions:
            st.subheader("Suggestions")
            for suggestion in status.suggestions:
                st.info(suggestion)

        # Unresolved placeholders
        if status.unresolved_placeholders:
            st.subheader("Unresolved Placeholders")
            for p in status.unresolved_placeholders:
                st.warning(f"${{{p['name']}}} is not set")
