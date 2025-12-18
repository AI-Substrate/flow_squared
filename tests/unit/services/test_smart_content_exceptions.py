"""Tests for smart content service-layer exceptions.

T011: SmartContentError hierarchy tests.
Purpose: Lock the exception inheritance contract for later phases.
"""

import pytest


@pytest.mark.unit
class TestSmartContentExceptions:
    """T011: Tests for smart content exception hierarchy."""

    def test_given_exceptions_when_importing_then_have_expected_inheritance(self):
        """
        Purpose: Proves service-layer exceptions share a common base type.
        Quality Contribution: Enables consistent error handling in later phases.
        Acceptance Criteria: TemplateError and SmartContentProcessingError subclass SmartContentError.

        Task: T011
        """
        from fs2.core.services.smart_content.exceptions import (
            SmartContentError,
            SmartContentProcessingError,
            TemplateError,
        )

        assert issubclass(TemplateError, SmartContentError)
        assert issubclass(SmartContentProcessingError, SmartContentError)

