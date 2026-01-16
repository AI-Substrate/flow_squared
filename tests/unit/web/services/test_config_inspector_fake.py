"""Tests for FakeConfigInspectorService.

Per Phase 1 Tasks Dossier:
- T007: Tests verify fake tracks calls, supports simulate_error
- Pattern: Follow fs2 fake pattern (call tracking, error simulation)

Testing Approach: Full TDD (RED phase - tests first)
"""

from pathlib import Path

import pytest

# These imports will fail initially (RED phase)
from fs2.web.services.config_inspector_fake import FakeConfigInspectorService
from fs2.web.services.config_inspector import (
    ConfigValue,
    InspectionResult,
    PlaceholderState,
)


class TestCallTracking:
    """Tests for call tracking functionality."""

    def test_tracks_inspect_calls(self) -> None:
        """Verify inspect() calls are tracked.

        Contract: Each inspect() call is recorded in call_history.
        """
        fake = FakeConfigInspectorService()

        fake.inspect()
        fake.inspect()

        assert len(fake.call_history) == 2
        assert fake.call_history[0] == "inspect"
        assert fake.call_history[1] == "inspect"

    def test_call_history_starts_empty(self) -> None:
        """Verify call_history is empty on creation."""
        fake = FakeConfigInspectorService()
        assert fake.call_history == []

    def test_clear_history(self) -> None:
        """Verify call history can be cleared.

        Contract: clear() resets call_history.
        """
        fake = FakeConfigInspectorService()
        fake.inspect()
        assert len(fake.call_history) == 1

        fake.clear()
        assert fake.call_history == []


class TestConfigurableResponses:
    """Tests for configurable response values."""

    def test_returns_default_empty_result(self) -> None:
        """Verify default result has empty attribution."""
        fake = FakeConfigInspectorService()
        result = fake.inspect()

        assert isinstance(result, InspectionResult)
        assert result.attribution == {}
        assert result.raw_config == {}
        assert result.placeholder_states == {}
        assert result.errors == []

    def test_set_result_returned_on_inspect(self) -> None:
        """Verify set_result() configures returned value.

        Contract: Custom result can be injected for testing.
        """
        custom_result = InspectionResult(
            attribution={
                "llm.timeout": ConfigValue(value=30, source="project"),
            },
            raw_config={"llm": {"timeout": 30}},
        )

        fake = FakeConfigInspectorService()
        fake.set_result(custom_result)

        result = fake.inspect()
        assert result.attribution["llm.timeout"].value == 30
        assert result.raw_config == {"llm": {"timeout": 30}}

    def test_multiple_inspect_returns_same_result(self) -> None:
        """Verify configured result is returned consistently."""
        custom_result = InspectionResult(
            attribution={"key": ConfigValue(value="test", source="user")}
        )

        fake = FakeConfigInspectorService()
        fake.set_result(custom_result)

        result1 = fake.inspect()
        result2 = fake.inspect()

        assert result1.attribution["key"].value == result2.attribution["key"].value


class TestErrorSimulation:
    """Tests for error simulation functionality."""

    def test_simulate_error_raises_on_inspect(self) -> None:
        """Verify simulate_error causes inspect() to raise.

        Contract: Simulated errors propagate to callers.
        """
        fake = FakeConfigInspectorService()
        fake.simulate_error = ValueError("Simulated failure")

        with pytest.raises(ValueError, match="Simulated failure"):
            fake.inspect()

    def test_simulate_error_clears_on_none(self) -> None:
        """Verify setting simulate_error=None clears error."""
        fake = FakeConfigInspectorService()
        fake.simulate_error = ValueError("Error")
        fake.simulate_error = None

        # Should not raise
        result = fake.inspect()
        assert isinstance(result, InspectionResult)

    def test_error_simulation_still_tracks_call(self) -> None:
        """Verify calls are tracked even when error is simulated.

        Contract: Call tracking happens before error is raised.
        """
        fake = FakeConfigInspectorService()
        fake.simulate_error = RuntimeError("Test error")

        with pytest.raises(RuntimeError):
            fake.inspect()

        # Call should still be tracked
        assert len(fake.call_history) == 1


class TestUsagePatterns:
    """Tests demonstrating usage patterns for Phase 2+ tests."""

    def test_use_in_service_test(self) -> None:
        """Demonstrate fake usage in service tests.

        Example of how Phase 2+ tests will use this fake.
        """
        # Arrange: Configure fake with expected config
        fake = FakeConfigInspectorService()
        fake.set_result(InspectionResult(
            attribution={
                "llm.provider": ConfigValue(value="azure", source="project"),
                "llm.api_key": ConfigValue(
                    value="${AZURE_KEY}",
                    source="project",
                    is_secret=True,
                ),
            },
            placeholder_states={
                "llm.api_key": PlaceholderState.RESOLVED,
            },
        ))

        # Act: Simulate what a service would do
        result = fake.inspect()

        # Assert: Verify expected behavior
        assert result.attribution["llm.provider"].value == "azure"
        assert result.placeholder_states["llm.api_key"] == PlaceholderState.RESOLVED
