"""Tests for domain models (frozen dataclasses).

Tests verify:
- LogLevel IntEnum ordering and values
- LogEntry immutability and fields
- ProcessResult success/error states

Per Finding 06: Frozen dataclasses for domain models
Per AC5: @dataclass(frozen=True), zero imports from services/adapters/repos
"""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from enum import IntEnum

import pytest


@pytest.mark.unit
class TestLogLevel:
    """Tests for LogLevel IntEnum."""

    def test_given_log_level_enum_then_is_int_enum(self):
        """
        Purpose: Proves LogLevel is an IntEnum for ordering support
        Quality Contribution: Enables Phase 3 level filtering with comparisons
        """
        from fs2.core.models.log_level import LogLevel

        assert issubclass(LogLevel, IntEnum)

    def test_given_log_level_enum_then_has_debug_info_warning_error(self):
        """
        Purpose: Proves LogLevel has all required levels
        Quality Contribution: Documents complete level set
        """
        from fs2.core.models.log_level import LogLevel

        assert hasattr(LogLevel, "DEBUG")
        assert hasattr(LogLevel, "INFO")
        assert hasattr(LogLevel, "WARNING")
        assert hasattr(LogLevel, "ERROR")

    def test_given_log_levels_then_debug_less_than_info(self):
        """
        Purpose: Proves DEBUG is less severe than INFO
        Quality Contribution: Enables correct filtering
        """
        from fs2.core.models.log_level import LogLevel

        assert LogLevel.DEBUG < LogLevel.INFO

    def test_given_log_levels_then_info_less_than_warning(self):
        """
        Purpose: Proves INFO is less severe than WARNING
        Quality Contribution: Enables correct filtering
        """
        from fs2.core.models.log_level import LogLevel

        assert LogLevel.INFO < LogLevel.WARNING

    def test_given_log_levels_then_warning_less_than_error(self):
        """
        Purpose: Proves WARNING is less severe than ERROR
        Quality Contribution: Enables correct filtering
        """
        from fs2.core.models.log_level import LogLevel

        assert LogLevel.WARNING < LogLevel.ERROR

    def test_given_log_level_then_ordering_is_complete(self):
        """
        Purpose: Proves complete ordering: DEBUG < INFO < WARNING < ERROR
        Quality Contribution: Verifies correct level filtering support
        """
        from fs2.core.models.log_level import LogLevel

        assert LogLevel.DEBUG < LogLevel.INFO < LogLevel.WARNING < LogLevel.ERROR


@pytest.mark.unit
class TestLogEntry:
    """Tests for LogEntry frozen dataclass."""

    def test_given_log_entry_when_created_then_has_required_fields(self):
        """
        Purpose: Proves LogEntry has level, message, context, timestamp
        Quality Contribution: Documents required interface
        """
        from fs2.core.models.log_entry import LogEntry
        from fs2.core.models.log_level import LogLevel

        entry = LogEntry(level=LogLevel.INFO, message="test message")

        assert entry.level == LogLevel.INFO
        assert entry.message == "test message"
        assert isinstance(entry.context, dict)
        assert isinstance(entry.timestamp, datetime)

    def test_given_log_entry_when_created_then_context_defaults_to_empty_dict(self):
        """
        Purpose: Proves context defaults to empty dict
        Quality Contribution: Simplifies creation for callers
        """
        from fs2.core.models.log_entry import LogEntry
        from fs2.core.models.log_level import LogLevel

        entry = LogEntry(level=LogLevel.DEBUG, message="test")

        assert entry.context == {}

    def test_given_log_entry_when_created_then_timestamp_is_utc(self):
        """
        Purpose: Proves timestamp uses UTC timezone
        Quality Contribution: Ensures consistent time handling
        """
        from fs2.core.models.log_entry import LogEntry
        from fs2.core.models.log_level import LogLevel

        before = datetime.now(UTC)
        entry = LogEntry(level=LogLevel.INFO, message="test")
        after = datetime.now(UTC)

        # Timestamp should be between before and after
        assert before <= entry.timestamp <= after
        # Timestamp should have timezone info
        assert entry.timestamp.tzinfo is not None

    def test_given_log_entry_when_mutating_message_then_raises_frozen_error(self):
        """
        Purpose: Proves LogEntry is immutable
        Quality Contribution: Prevents accidental state mutation
        """
        from fs2.core.models.log_entry import LogEntry
        from fs2.core.models.log_level import LogLevel

        entry = LogEntry(level=LogLevel.INFO, message="test")

        with pytest.raises(FrozenInstanceError):
            entry.message = "modified"

    def test_given_log_entry_when_mutating_level_then_raises_frozen_error(self):
        """
        Purpose: Proves level cannot be changed after creation
        Quality Contribution: Ensures log integrity
        """
        from fs2.core.models.log_entry import LogEntry
        from fs2.core.models.log_level import LogLevel

        entry = LogEntry(level=LogLevel.INFO, message="test")

        with pytest.raises(FrozenInstanceError):
            entry.level = LogLevel.ERROR

    def test_given_log_entry_with_context_then_context_accessible(self):
        """
        Purpose: Proves context can be provided and accessed
        Quality Contribution: Enables structured logging
        """
        from fs2.core.models.log_entry import LogEntry
        from fs2.core.models.log_level import LogLevel

        entry = LogEntry(
            level=LogLevel.INFO, message="test", context={"user_id": "123"}
        )

        assert entry.context["user_id"] == "123"

    def test_given_log_entry_then_uses_log_level_enum(self):
        """
        Purpose: Proves LogEntry.level is type-safe LogLevel
        Quality Contribution: Enables Phase 3 level filtering
        """
        from fs2.core.models.log_entry import LogEntry
        from fs2.core.models.log_level import LogLevel

        entry = LogEntry(level=LogLevel.WARNING, message="test")

        assert isinstance(entry.level, LogLevel)
        # Can compare levels
        assert entry.level > LogLevel.INFO


@pytest.mark.unit
class TestProcessResult:
    """Tests for ProcessResult frozen dataclass."""

    def test_given_process_result_ok_when_created_then_success_is_true(self):
        """
        Purpose: Proves ok() factory creates successful result
        Quality Contribution: Documents success pattern
        """
        from fs2.core.models.process_result import ProcessResult

        result = ProcessResult.ok(value="processed data")

        assert result.success is True
        assert result.value == "processed data"
        assert result.error is None

    def test_given_process_result_fail_when_created_then_success_is_false(self):
        """
        Purpose: Proves fail() factory creates failed result
        Quality Contribution: Documents failure pattern
        """
        from fs2.core.models.process_result import ProcessResult

        result = ProcessResult.fail(error="Something went wrong")

        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.value is None

    def test_given_process_result_ok_with_metadata_then_metadata_accessible(self):
        """
        Purpose: Proves metadata can be passed via ok()
        Quality Contribution: Enables tracing and timing
        """
        from fs2.core.models.process_result import ProcessResult

        result = ProcessResult.ok(value="data", trace_id="abc-123", duration_ms=42)

        assert result.metadata["trace_id"] == "abc-123"
        assert result.metadata["duration_ms"] == 42

    def test_given_process_result_fail_with_metadata_then_metadata_accessible(self):
        """
        Purpose: Proves metadata can be passed via fail()
        Quality Contribution: Enables error context
        """
        from fs2.core.models.process_result import ProcessResult

        result = ProcessResult.fail(error="Timeout", retry_count=3)

        assert result.metadata["retry_count"] == 3

    def test_given_process_result_when_mutating_success_then_raises_frozen_error(self):
        """
        Purpose: Proves ProcessResult is immutable
        Quality Contribution: Prevents accidental state mutation
        """
        from fs2.core.models.process_result import ProcessResult

        result = ProcessResult.ok(value="data")

        with pytest.raises(FrozenInstanceError):
            result.success = False

    def test_given_process_result_then_defaults_to_empty_metadata(self):
        """
        Purpose: Proves metadata defaults to empty dict
        Quality Contribution: Simplifies creation
        """
        from fs2.core.models.process_result import ProcessResult

        result = ProcessResult(success=True, value="data")

        assert result.metadata == {}

    def test_given_process_result_direct_construction_then_works(self):
        """
        Purpose: Proves direct construction works alongside factories
        Quality Contribution: Flexibility in usage patterns
        """
        from fs2.core.models.process_result import ProcessResult

        result = ProcessResult(
            success=False, error="manual error", metadata={"custom": "data"}
        )

        assert result.success is False
        assert result.error == "manual error"
        assert result.metadata["custom"] == "data"
