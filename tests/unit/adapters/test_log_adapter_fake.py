"""Tests for FakeLogAdapter implementation.

Purpose: Validate FakeLogAdapter behavior per Phase 3 tasks.
Quality Contribution: Ensures test double captures messages for assertions.

Per Plan AC7: LogAdapter ABC with debug/info/warning/error.
Per Tasks T007-T008: FakeLogAdapter message capture tests.
"""

import pytest


class TestFakeLogAdapterMessageCapture:
    """Tests for FakeLogAdapter message capture (T007-T008)."""

    def test_given_fake_log_adapter_when_info_called_then_message_captured_as_log_entry(
        self,
    ):
        """
        Purpose: Proves FakeLogAdapter stores messages as LogEntry instances
        Quality Contribution: Enables test assertions on logging behavior
        Acceptance Criteria:
        - Message stored in .messages list
        - LogEntry has correct level, message, context
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_fake import FakeLogAdapter
        from fs2.core.models.log_level import LogLevel

        config = FakeConfigurationService(LogAdapterConfig(min_level="DEBUG"))
        adapter = FakeLogAdapter(config)

        # Act
        adapter.info("Test message", trace_id="123")

        # Assert
        assert len(adapter.messages) == 1
        entry = adapter.messages[0]
        assert entry.level == LogLevel.INFO
        assert entry.message == "Test message"
        assert entry.context["trace_id"] == "123"

    def test_given_fake_log_adapter_when_multiple_calls_then_all_messages_captured(
        self,
    ):
        """
        Purpose: Proves message history is complete
        Quality Contribution: Tests can verify logging sequence
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_fake import FakeLogAdapter
        from fs2.core.models.log_level import LogLevel

        config = FakeConfigurationService(LogAdapterConfig(min_level="DEBUG"))
        adapter = FakeLogAdapter(config)

        # Act
        adapter.debug("First")
        adapter.info("Second")
        adapter.warning("Third")
        adapter.error("Fourth")

        # Assert
        assert len(adapter.messages) == 4
        assert adapter.messages[0].level == LogLevel.DEBUG
        assert adapter.messages[0].message == "First"
        assert adapter.messages[1].level == LogLevel.INFO
        assert adapter.messages[1].message == "Second"
        assert adapter.messages[2].level == LogLevel.WARNING
        assert adapter.messages[2].message == "Third"
        assert adapter.messages[3].level == LogLevel.ERROR
        assert adapter.messages[3].message == "Fourth"

    def test_given_fake_log_adapter_then_messages_property_returns_list(self):
        """
        Purpose: Proves .messages API exists and returns list[LogEntry]
        Quality Contribution: Documents public API
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_fake import FakeLogAdapter
        from fs2.core.models.log_entry import LogEntry

        config = FakeConfigurationService(LogAdapterConfig(min_level="DEBUG"))
        adapter = FakeLogAdapter(config)

        # Assert - empty list initially
        assert adapter.messages == []
        assert isinstance(adapter.messages, list)

        # Act
        adapter.info("Test")

        # Assert - list with LogEntry
        assert len(adapter.messages) == 1
        assert isinstance(adapter.messages[0], LogEntry)

    def test_given_fake_log_adapter_when_context_provided_then_context_captured(self):
        """
        Purpose: Proves context dict is captured from **kwargs
        Quality Contribution: Enables context assertions in tests
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_fake import FakeLogAdapter

        config = FakeConfigurationService(LogAdapterConfig(min_level="DEBUG"))
        adapter = FakeLogAdapter(config)

        # Act
        adapter.error("Failed", error_code="E001", retries=3, endpoint="/api/users")

        # Assert
        entry = adapter.messages[0]
        assert entry.context["error_code"] == "E001"
        assert entry.context["retries"] == 3
        assert entry.context["endpoint"] == "/api/users"


class TestFakeLogAdapterLevelFiltering:
    """Tests for FakeLogAdapter level filtering (T011-T012)."""

    def test_given_min_level_info_when_debug_called_then_message_not_captured(self):
        """
        Purpose: Proves level filtering works - DEBUG filtered when min_level=INFO
        Quality Contribution: Allows log verbosity control
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_fake import FakeLogAdapter

        config = FakeConfigurationService(LogAdapterConfig(min_level="INFO"))
        adapter = FakeLogAdapter(config)

        # Act
        adapter.debug("This should be filtered")
        adapter.info("This should be captured")

        # Assert
        assert len(adapter.messages) == 1
        assert adapter.messages[0].message == "This should be captured"

    def test_given_min_level_debug_when_debug_called_then_message_captured(self):
        """
        Purpose: Proves DEBUG not filtered when min_level=DEBUG
        Quality Contribution: Validates filtering threshold
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_fake import FakeLogAdapter

        config = FakeConfigurationService(LogAdapterConfig(min_level="DEBUG"))
        adapter = FakeLogAdapter(config)

        # Act
        adapter.debug("Debug message")

        # Assert
        assert len(adapter.messages) == 1
        assert adapter.messages[0].message == "Debug message"

    def test_given_min_level_error_when_warning_called_then_message_not_captured(self):
        """
        Purpose: Proves WARNING filtered when min_level=ERROR
        Quality Contribution: Supports production log reduction
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_fake import FakeLogAdapter

        config = FakeConfigurationService(LogAdapterConfig(min_level="ERROR"))
        adapter = FakeLogAdapter(config)

        # Act
        adapter.debug("Filtered")
        adapter.info("Filtered")
        adapter.warning("Filtered")
        adapter.error("Captured")

        # Assert
        assert len(adapter.messages) == 1
        assert adapter.messages[0].message == "Captured"


class TestFakeLogAdapterConfigInjection:
    """Tests for ConfigurationService injection pattern (T013-T014)."""

    def test_given_fake_log_adapter_then_receives_configuration_service(self):
        """
        Purpose: Proves no concept leakage - receives registry not config
        Quality Contribution: Enforces architectural pattern from footnote [^10]
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_fake import FakeLogAdapter

        config = FakeConfigurationService(LogAdapterConfig(min_level="DEBUG"))

        # Act - Adapter receives ConfigurationService, not LogAdapterConfig
        adapter = FakeLogAdapter(config)

        # Assert - Adapter works (config was retrieved internally)
        assert adapter is not None
        assert adapter.messages == []

    def test_given_fake_log_adapter_without_config_then_raises_missing_config_error(
        self,
    ):
        """
        Purpose: Proves adapter requires LogAdapterConfig to be registered
        Quality Contribution: Clear error when config not provided
        """
        # Arrange
        from fs2.config.exceptions import MissingConfigurationError
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_fake import FakeLogAdapter

        config = FakeConfigurationService()  # No LogAdapterConfig registered

        # Act & Assert
        with pytest.raises(MissingConfigurationError) as exc_info:
            FakeLogAdapter(config)

        assert "LogAdapterConfig" in str(exc_info.value)


class TestFakeLogAdapterABCInheritance:
    """Tests for ABC inheritance validation (T015-T016)."""

    def test_given_fake_log_adapter_then_inherits_from_log_adapter(self):
        """
        Purpose: Proves FakeLogAdapter properly inherits from LogAdapter ABC
        Quality Contribution: Ensures polymorphism works
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter import LogAdapter
        from fs2.core.adapters.log_adapter_fake import FakeLogAdapter

        config = FakeConfigurationService(LogAdapterConfig(min_level="DEBUG"))

        # Act
        adapter = FakeLogAdapter(config)

        # Assert
        assert isinstance(adapter, LogAdapter)

    def test_given_fake_log_adapter_then_has_all_required_methods(self):
        """
        Purpose: Proves all ABC methods are implemented
        Quality Contribution: Contract enforcement
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_fake import FakeLogAdapter

        config = FakeConfigurationService(LogAdapterConfig(min_level="DEBUG"))
        adapter = FakeLogAdapter(config)

        # Assert - all methods exist and are callable
        assert callable(adapter.debug)
        assert callable(adapter.info)
        assert callable(adapter.warning)
        assert callable(adapter.error)
