"""Tests for FakeValidationService - Test double for validation.

Full TDD tests for the FakeValidationService following Phase 1 pattern:
- call_history tracking
- set_result() for configuring returns
- simulate_error for error testing
"""

import pytest

from fs2.web.services.validation import ValidationResult


# =============================================================================
# FAKE SERVICE STRUCTURE TESTS
# =============================================================================


class TestFakeValidationServiceStructure:
    """Tests for FakeValidationService basic structure."""

    def test_given_new_fake_when_created_then_has_empty_call_history(self):
        """
        Purpose: Verifies fake starts with empty call history.
        Quality Contribution: Clean test isolation.
        """
        from fs2.web.services.validation_fake import FakeValidationService

        fake = FakeValidationService()

        assert fake.call_history == []

    def test_given_new_fake_when_created_then_has_default_result(self):
        """
        Purpose: Verifies fake has sensible default result.
        Quality Contribution: Works out of the box.
        """
        from fs2.web.services.validation_fake import FakeValidationService

        fake = FakeValidationService()
        result = fake.validate()

        assert isinstance(result, ValidationResult)
        assert result.status == "healthy"

    def test_given_new_fake_when_created_then_has_no_error(self):
        """
        Purpose: Verifies fake starts without error simulation.
        """
        from fs2.web.services.validation_fake import FakeValidationService

        fake = FakeValidationService()

        assert fake.simulate_error is None


# =============================================================================
# CALL HISTORY TRACKING TESTS
# =============================================================================


class TestFakeValidationServiceCallHistory:
    """Tests for call history tracking."""

    def test_given_validate_called_when_check_history_then_recorded(self):
        """
        Purpose: Verifies validate() call is recorded.
        Quality Contribution: Enables call verification in tests.
        """
        from fs2.web.services.validation_fake import FakeValidationService

        fake = FakeValidationService()
        fake.validate()

        assert fake.call_history == ["validate"]

    def test_given_multiple_calls_when_check_history_then_all_recorded(self):
        """
        Purpose: Verifies multiple calls are recorded in order.
        """
        from fs2.web.services.validation_fake import FakeValidationService

        fake = FakeValidationService()
        fake.validate()
        fake.validate()
        fake.validate()

        assert fake.call_history == ["validate", "validate", "validate"]

    def test_given_clear_called_when_check_history_then_empty(self):
        """
        Purpose: Verifies clear() resets call history.
        Quality Contribution: Enables test isolation.
        """
        from fs2.web.services.validation_fake import FakeValidationService

        fake = FakeValidationService()
        fake.validate()
        fake.validate()

        fake.clear()

        assert fake.call_history == []


# =============================================================================
# SET RESULT TESTS
# =============================================================================


class TestFakeValidationServiceSetResult:
    """Tests for set_result() configuration."""

    def test_given_custom_result_when_validate_then_returns_custom(self):
        """
        Purpose: Verifies set_result() configures return value.
        Quality Contribution: Enables testing different scenarios.
        """
        from fs2.web.services.validation_fake import FakeValidationService

        fake = FakeValidationService()
        custom_result = ValidationResult(
            status="error",
            llm_configured=False,
            llm_misconfigured=True,
            issues=["Test issue"],
        )
        fake.set_result(custom_result)

        result = fake.validate()

        assert result.status == "error"
        assert result.llm_misconfigured is True
        assert result.issues == ["Test issue"]

    def test_given_warning_result_when_validate_then_returns_warning(self):
        """
        Purpose: Verifies warning state can be configured.
        """
        from fs2.web.services.validation_fake import FakeValidationService

        fake = FakeValidationService()
        fake.set_result(
            ValidationResult(
                status="warning",
                llm_configured=True,
                unresolved_placeholders=[
                    {"name": "TEST_KEY", "resolved": False}
                ],
            )
        )

        result = fake.validate()

        assert result.status == "warning"
        assert len(result.unresolved_placeholders) == 1


# =============================================================================
# SIMULATE ERROR TESTS
# =============================================================================


class TestFakeValidationServiceSimulateError:
    """Tests for error simulation."""

    def test_given_simulate_error_set_when_validate_then_raises(self):
        """
        Purpose: Verifies error simulation works.
        Quality Contribution: Enables testing error handling.
        """
        from fs2.web.services.validation_fake import FakeValidationService

        fake = FakeValidationService()
        fake.simulate_error = ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            fake.validate()

    def test_given_simulate_error_set_when_validate_then_records_call(self):
        """
        Purpose: Verifies call is recorded even when error is raised.
        """
        from fs2.web.services.validation_fake import FakeValidationService

        fake = FakeValidationService()
        fake.simulate_error = RuntimeError("Test")

        try:
            fake.validate()
        except RuntimeError:
            pass

        assert "validate" in fake.call_history
