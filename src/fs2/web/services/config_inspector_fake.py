"""FakeConfigInspectorService - Test double for config inspection.

Per Phase 1 Foundation:
- T008: Implement with call_history and simulate_error
- Pattern: Follow fs2 fake pattern

Usage for Phase 2+ tests:
    ```python
    fake = FakeConfigInspectorService()
    fake.set_result(InspectionResult(
        attribution={"llm.timeout": ConfigValue(value=30, source="project")}
    ))

    # Use in service tests
    service = ConfigEditorService(inspector=fake)
    service.load_config()

    # Assert inspect was called
    assert fake.call_history == ["inspect"]
    ```
"""

from fs2.web.services.config_inspector import InspectionResult


class FakeConfigInspectorService:
    """Test double for ConfigInspectorService.

    Provides:
    - call_history: List of method calls for assertions
    - set_result(): Configure what inspect() returns
    - simulate_error: Set to Exception to make inspect() raise

    Does NOT require actual config files - returns configurable results.
    """

    def __init__(self) -> None:
        """Initialize with empty state."""
        self._call_history: list[str] = []
        self._result: InspectionResult = InspectionResult()
        self.simulate_error: Exception | None = None

    @property
    def call_history(self) -> list[str]:
        """Get list of method calls made.

        Returns:
            List of method names called (e.g., ["inspect", "inspect"]).
        """
        return self._call_history

    def clear(self) -> None:
        """Clear call history.

        Useful for test isolation between assertions.
        """
        self._call_history.clear()

    def set_result(self, result: InspectionResult) -> None:
        """Configure the result returned by inspect().

        Args:
            result: InspectionResult to return on inspect() calls.
        """
        self._result = result

    def inspect(self) -> InspectionResult:
        """Fake inspect that returns configured result.

        Records call in history, then returns configured result
        or raises if simulate_error is set.

        Returns:
            Configured InspectionResult (default: empty result).

        Raises:
            Exception: If simulate_error is set to an exception.
        """
        self._call_history.append("inspect")

        if self.simulate_error is not None:
            raise self.simulate_error

        return self._result
