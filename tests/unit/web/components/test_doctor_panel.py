"""Tests for DoctorPanel component - Service integration tests.

Per Critical Insight #3: Test service integration only - no render tests.
Streamlit components can't be unit tested for rendering.

These tests verify:
- DoctorPanel correctly calls ValidationService
- DoctorPanel correctly handles validation results
- Error handling works as expected
"""

import pytest

from fs2.web.services.validation import ValidationResult
from fs2.web.services.validation_fake import FakeValidationService


# =============================================================================
# DOCTOR PANEL SERVICE INTEGRATION TESTS
# =============================================================================


class TestDoctorPanelServiceIntegration:
    """Tests for DoctorPanel service integration."""

    def test_given_healthy_result_when_get_status_then_returns_healthy(self):
        """
        Purpose: Verifies DoctorPanel correctly reads healthy status.
        Quality Contribution: Foundation for UI display logic.
        """
        from fs2.web.components.doctor_panel import DoctorPanel

        fake_service = FakeValidationService()
        fake_service.set_result(
            ValidationResult(
                status="healthy",
                llm_configured=True,
                llm_provider="azure",
                embedding_configured=True,
                embedding_mode="azure",
            )
        )

        panel = DoctorPanel(validation_service=fake_service)
        status = panel.get_status()

        assert status.status == "healthy"
        assert status.llm_configured is True
        assert status.embedding_configured is True
        assert "validate" in fake_service.call_history

    def test_given_warning_result_when_get_status_then_returns_warning(self):
        """
        Purpose: Verifies DoctorPanel correctly reads warning status.
        """
        from fs2.web.components.doctor_panel import DoctorPanel

        fake_service = FakeValidationService()
        fake_service.set_result(
            ValidationResult(
                status="warning",
                llm_configured=True,
                embedding_configured=False,
                unresolved_placeholders=[
                    {"name": "TEST_KEY", "resolved": False}
                ],
                suggestions=["Set TEST_KEY environment variable"],
            )
        )

        panel = DoctorPanel(validation_service=fake_service)
        status = panel.get_status()

        assert status.status == "warning"
        assert len(status.unresolved_placeholders) == 1
        assert len(status.suggestions) == 1

    def test_given_error_result_when_get_status_then_returns_error(self):
        """
        Purpose: Verifies DoctorPanel correctly reads error status.
        """
        from fs2.web.components.doctor_panel import DoctorPanel

        fake_service = FakeValidationService()
        fake_service.set_result(
            ValidationResult(
                status="error",
                llm_configured=False,
                llm_misconfigured=True,
                llm_issues=["base_url is required"],
                embedding_configured=True,
                issues=["LLM misconfigured: base_url is required"],
            )
        )

        panel = DoctorPanel(validation_service=fake_service)
        status = panel.get_status()

        assert status.status == "error"
        assert len(status.issues) == 1
        assert "base_url" in status.issues[0]


class TestDoctorPanelErrorHandling:
    """Tests for DoctorPanel error handling."""

    def test_given_service_error_when_get_status_then_returns_error_result(self):
        """
        Purpose: Verifies DoctorPanel handles service errors gracefully.
        Quality Contribution: UI doesn't crash on errors.
        """
        from fs2.web.components.doctor_panel import DoctorPanel

        fake_service = FakeValidationService()
        fake_service.simulate_error = RuntimeError("Config file not found")

        panel = DoctorPanel(validation_service=fake_service)
        status = panel.get_status()

        # Should return error result, not raise
        assert status.status == "error"
        assert len(status.issues) >= 1
        assert "error" in status.issues[0].lower() or "Config" in status.issues[0]
