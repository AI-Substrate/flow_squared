"""Tests for ConsoleLogAdapter implementation.

Purpose: Validate ConsoleLogAdapter behavior per Phase 3 tasks.
Quality Contribution: Ensures logging works correctly for development use.

Per Plan AC7: LogAdapter ABC with debug/info/warning/error.
Per Tasks T001-T006: ConsoleLogAdapter implementation tests.
"""

import re
from datetime import datetime

import pytest


class TestConsoleLogAdapterInfo:
    """Tests for ConsoleLogAdapter.info() method (T001-T002)."""

    def test_given_console_log_adapter_when_info_called_then_outputs_to_stdout(
        self, capsys
    ):
        """
        Purpose: Proves ConsoleLogAdapter.info() writes formatted output to stdout
        Quality Contribution: Validates basic logging contract
        Acceptance Criteria:
        - Output contains "INFO"
        - Output contains message text
        - Output written to stdout (not stderr)
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_console import ConsoleLogAdapter

        config = FakeConfigurationService(LogAdapterConfig(min_level="DEBUG"))
        adapter = ConsoleLogAdapter(config)

        # Act
        adapter.info("Test message")

        # Assert
        captured = capsys.readouterr()
        assert "INFO" in captured.out
        assert "Test message" in captured.out
        assert captured.err == ""  # Nothing to stderr

    def test_given_console_log_adapter_when_info_called_with_context_then_context_formatted(
        self, capsys
    ):
        """
        Purpose: Proves structured context is included in output
        Quality Contribution: Enables trace correlation via context
        Acceptance Criteria:
        - Context key=value pairs appear in output
        - Multiple context items are formatted
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_console import ConsoleLogAdapter

        config = FakeConfigurationService(LogAdapterConfig(min_level="DEBUG"))
        adapter = ConsoleLogAdapter(config)

        # Act
        adapter.info("Processing request", trace_id="abc123", user_id=42)

        # Assert
        captured = capsys.readouterr()
        assert "trace_id=abc123" in captured.out
        assert "user_id=42" in captured.out

    def test_given_console_log_adapter_when_info_called_then_output_matches_format(
        self, capsys
    ):
        """
        Purpose: Proves output format matches specification
        Quality Contribution: Consistent log format enables parsing
        Acceptance Criteria:
        - Format: YYYY-MM-DD HH:MM:SS LEVEL: message key=value
        - Timestamp is valid datetime format
        - Level is uppercase
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_console import ConsoleLogAdapter

        config = FakeConfigurationService(LogAdapterConfig(min_level="DEBUG"))
        adapter = ConsoleLogAdapter(config)

        # Act
        adapter.info("Hello world", key="value")

        # Assert
        captured = capsys.readouterr()
        output = captured.out.strip()

        # Pattern: YYYY-MM-DD HH:MM:SS INFO: message key=value
        pattern = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} INFO: Hello world key=value$"
        assert re.match(pattern, output), f"Output did not match format: {output}"

        # Verify timestamp is parseable
        timestamp_str = output[:19]  # YYYY-MM-DD HH:MM:SS
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        assert timestamp is not None


class TestConsoleLogAdapterError:
    """Tests for ConsoleLogAdapter.error() method (T003-T004)."""

    def test_given_console_log_adapter_when_error_called_then_outputs_to_stderr(
        self, capsys
    ):
        """
        Purpose: Proves ERROR level uses stderr for visibility
        Quality Contribution: Error messages stand out in terminal
        Acceptance Criteria:
        - Output contains "ERROR"
        - Output written to stderr (not stdout)
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_console import ConsoleLogAdapter

        config = FakeConfigurationService(LogAdapterConfig(min_level="DEBUG"))
        adapter = ConsoleLogAdapter(config)

        # Act
        adapter.error("Something failed", error_code="E001")

        # Assert
        captured = capsys.readouterr()
        assert "ERROR" in captured.err
        assert "Something failed" in captured.err
        assert "error_code=E001" in captured.err
        assert captured.out == ""  # Nothing to stdout

    def test_given_console_log_adapter_when_error_called_then_output_matches_format(
        self, capsys
    ):
        """
        Purpose: Proves error output format matches specification
        Quality Contribution: Consistent format enables parsing
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_console import ConsoleLogAdapter

        config = FakeConfigurationService(LogAdapterConfig(min_level="DEBUG"))
        adapter = ConsoleLogAdapter(config)

        # Act
        adapter.error("Connection failed", host="api.example.com")

        # Assert
        captured = capsys.readouterr()
        output = captured.err.strip()

        # Pattern: YYYY-MM-DD HH:MM:SS ERROR: message key=value
        pattern = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ERROR: Connection failed host=api\.example\.com$"
        assert re.match(pattern, output), f"Output did not match format: {output}"


class TestConsoleLogAdapterDebugWarning:
    """Tests for ConsoleLogAdapter.debug() and warning() methods (T005-T006)."""

    def test_given_console_log_adapter_when_debug_called_then_outputs_to_stdout(
        self, capsys
    ):
        """
        Purpose: Proves DEBUG level writes to stdout
        Quality Contribution: Debug messages available for troubleshooting
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_console import ConsoleLogAdapter

        config = FakeConfigurationService(LogAdapterConfig(min_level="DEBUG"))
        adapter = ConsoleLogAdapter(config)

        # Act
        adapter.debug("Cache hit", key="user:123")

        # Assert
        captured = capsys.readouterr()
        assert "DEBUG" in captured.out
        assert "Cache hit" in captured.out
        assert "key=user:123" in captured.out
        assert captured.err == ""

    def test_given_console_log_adapter_when_warning_called_then_outputs_to_stdout(
        self, capsys
    ):
        """
        Purpose: Proves WARNING level writes to stdout
        Quality Contribution: Warnings visible without mixing with errors
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_console import ConsoleLogAdapter

        config = FakeConfigurationService(LogAdapterConfig(min_level="DEBUG"))
        adapter = ConsoleLogAdapter(config)

        # Act
        adapter.warning("Retry attempt", attempt=3, max_retries=5)

        # Assert
        captured = capsys.readouterr()
        assert "WARNING" in captured.out
        assert "Retry attempt" in captured.out
        assert "attempt=3" in captured.out
        assert captured.err == ""


class TestConsoleLogAdapterLevelFiltering:
    """Tests for ConsoleLogAdapter level filtering (T011-T012)."""

    def test_given_min_level_info_when_debug_called_then_no_output(self, capsys):
        """
        Purpose: Proves level filtering works - DEBUG filtered when min_level=INFO
        Quality Contribution: Allows log verbosity control
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_console import ConsoleLogAdapter

        config = FakeConfigurationService(LogAdapterConfig(min_level="INFO"))
        adapter = ConsoleLogAdapter(config)

        # Act
        adapter.debug("This should be filtered")

        # Assert
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_given_min_level_error_when_warning_called_then_no_output(self, capsys):
        """
        Purpose: Proves WARNING filtered when min_level=ERROR
        Quality Contribution: Supports production log reduction
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_console import ConsoleLogAdapter

        config = FakeConfigurationService(LogAdapterConfig(min_level="ERROR"))
        adapter = ConsoleLogAdapter(config)

        # Act
        adapter.debug("Filtered")
        adapter.info("Filtered")
        adapter.warning("Filtered")

        # Assert
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_given_min_level_error_when_error_called_then_output(self, capsys):
        """
        Purpose: Proves ERROR not filtered when min_level=ERROR
        Quality Contribution: Validates filtering threshold
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_console import ConsoleLogAdapter

        config = FakeConfigurationService(LogAdapterConfig(min_level="ERROR"))
        adapter = ConsoleLogAdapter(config)

        # Act
        adapter.error("Error message")

        # Assert
        captured = capsys.readouterr()
        assert "ERROR" in captured.err
        assert "Error message" in captured.err


class TestConsoleLogAdapterConfigInjection:
    """Tests for ConfigurationService injection pattern (T013-T014)."""

    def test_given_console_log_adapter_then_receives_configuration_service(self):
        """
        Purpose: Proves no concept leakage - receives registry not config
        Quality Contribution: Enforces architectural pattern from footnote [^10]
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_console import ConsoleLogAdapter

        config = FakeConfigurationService(LogAdapterConfig(min_level="DEBUG"))

        # Act - Adapter receives ConfigurationService, not LogAdapterConfig
        adapter = ConsoleLogAdapter(config)

        # Assert - Adapter works (config was retrieved internally)
        assert adapter is not None
        # The fact that it doesn't crash proves it called config.require() internally

    def test_given_console_log_adapter_without_config_then_raises_missing_config_error(
        self,
    ):
        """
        Purpose: Proves adapter requires LogAdapterConfig to be registered
        Quality Contribution: Clear error when config not provided
        """
        # Arrange
        from fs2.config.exceptions import MissingConfigurationError
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_console import ConsoleLogAdapter

        config = FakeConfigurationService()  # No LogAdapterConfig registered

        # Act & Assert
        with pytest.raises(MissingConfigurationError) as exc_info:
            ConsoleLogAdapter(config)

        assert "LogAdapterConfig" in str(exc_info.value)


class TestConsoleLogAdapterABCInheritance:
    """Tests for ABC inheritance validation (T015-T016)."""

    def test_given_console_log_adapter_then_inherits_from_log_adapter(self):
        """
        Purpose: Proves ConsoleLogAdapter properly inherits from LogAdapter ABC
        Quality Contribution: Ensures polymorphism works
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter import LogAdapter
        from fs2.core.adapters.log_adapter_console import ConsoleLogAdapter

        config = FakeConfigurationService(LogAdapterConfig(min_level="DEBUG"))

        # Act
        adapter = ConsoleLogAdapter(config)

        # Assert
        assert isinstance(adapter, LogAdapter)

    def test_given_console_log_adapter_then_has_all_required_methods(self):
        """
        Purpose: Proves all ABC methods are implemented
        Quality Contribution: Contract enforcement
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_console import ConsoleLogAdapter

        config = FakeConfigurationService(LogAdapterConfig(min_level="DEBUG"))
        adapter = ConsoleLogAdapter(config)

        # Assert - all methods exist and are callable
        assert callable(adapter.debug)
        assert callable(adapter.info)
        assert callable(adapter.warning)
        assert callable(adapter.error)
