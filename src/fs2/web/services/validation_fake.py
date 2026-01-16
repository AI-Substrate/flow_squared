"""FakeValidationService - Test double for validation service.

Per Phase 1 pattern:
- call_history: List of method calls for assertions
- set_result(): Configure what validate() returns
- simulate_error: Set to Exception to make validate() raise

Usage for component tests:
    ```python
    fake = FakeValidationService()
    fake.set_result(ValidationResult(
        status="warning",
        unresolved_placeholders=[{"name": "TEST_KEY", "resolved": False}],
    ))

    # Use in component tests
    panel = DoctorPanel(validation_service=fake)
    panel.render()

    # Assert validate was called
    assert "validate" in fake.call_history
    ```
"""

from fs2.web.services.validation import ValidationResult


class FakeValidationService:
    """Test double for ValidationService.

    Provides:
    - call_history: List of method calls for assertions
    - set_result(): Configure what validate() returns
    - simulate_error: Set to Exception to make validate() raise

    Does NOT require actual config files - returns configurable results.
    """

    def __init__(self) -> None:
        """Initialize with default healthy result."""
        self._call_history: list[str] = []
        self._result: ValidationResult = ValidationResult(
            status="healthy",
            llm_configured=True,
            embedding_configured=True,
        )
        self.simulate_error: Exception | None = None

    @property
    def call_history(self) -> list[str]:
        """Get list of method calls made.

        Returns:
            List of method names called (e.g., ["validate", "validate"]).
        """
        return self._call_history

    def clear(self) -> None:
        """Clear call history.

        Useful for test isolation between assertions.
        """
        self._call_history.clear()

    def set_result(self, result: ValidationResult) -> None:
        """Configure the result returned by validate().

        Args:
            result: ValidationResult to return on validate() calls.
        """
        self._result = result

    def validate(self) -> ValidationResult:
        """Fake validate that returns configured result.

        Records call in history, then returns configured result
        or raises if simulate_error is set.

        Returns:
            Configured ValidationResult (default: healthy).

        Raises:
            Exception: If simulate_error is set to an exception.
        """
        self._call_history.append("validate")

        if self.simulate_error is not None:
            raise self.simulate_error

        return self._result
