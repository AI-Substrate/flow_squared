"""Tests for HealthBadge component - Service integration tests.

Per Critical Insight #3: Test data flow only - no render tests.
"""

import pytest

from fs2.web.services.validation import ValidationResult
from fs2.web.services.validation_fake import FakeValidationService


# =============================================================================
# HEALTH BADGE SERVICE INTEGRATION TESTS
# =============================================================================


class TestHealthBadgeServiceIntegration:
    """Tests for HealthBadge service integration."""

    def test_given_healthy_status_when_get_color_then_returns_green(self):
        """
        Purpose: Verifies HealthBadge returns green for healthy.
        Quality Contribution: Correct sidebar indicator color.
        """
        from fs2.web.components.health_badge import HealthBadge

        fake_service = FakeValidationService()
        fake_service.set_result(
            ValidationResult(
                status="healthy",
                llm_configured=True,
                embedding_configured=True,
            )
        )

        badge = HealthBadge(validation_service=fake_service)
        color = badge.get_color()

        assert color == "green"
        assert "validate" in fake_service.call_history

    def test_given_warning_status_when_get_color_then_returns_yellow(self):
        """
        Purpose: Verifies HealthBadge returns yellow for warning.
        """
        from fs2.web.components.health_badge import HealthBadge

        fake_service = FakeValidationService()
        fake_service.set_result(
            ValidationResult(
                status="warning",
                llm_configured=True,
                embedding_configured=False,
            )
        )

        badge = HealthBadge(validation_service=fake_service)
        color = badge.get_color()

        assert color == "yellow"

    def test_given_error_status_when_get_color_then_returns_red(self):
        """
        Purpose: Verifies HealthBadge returns red for error.
        """
        from fs2.web.components.health_badge import HealthBadge

        fake_service = FakeValidationService()
        fake_service.set_result(
            ValidationResult(
                status="error",
                llm_misconfigured=True,
                issues=["LLM misconfigured"],
            )
        )

        badge = HealthBadge(validation_service=fake_service)
        color = badge.get_color()

        assert color == "red"
