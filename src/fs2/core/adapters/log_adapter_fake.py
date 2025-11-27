"""FakeLogAdapter - Test double for logging assertions.

Per Phase 3: Logger Adapter Implementation.
Per Plan AC7: LogAdapter ABC with debug/info/warning/error.

Architecture:
- Inherits from LogAdapter ABC
- Receives ConfigurationService via constructor (no concept leakage)
- Captures all log messages as LogEntry instances
- Provides .messages property for test assertions

CRITICAL: Logging methods must never propagate exceptions (industry standard).
Internal errors are silently swallowed to prevent logging from crashing callers.
"""

from typing import TYPE_CHECKING, Any

from fs2.config.objects import LogAdapterConfig
from fs2.core.adapters.log_adapter import LogAdapter
from fs2.core.models.log_entry import LogEntry
from fs2.core.models.log_level import LogLevel

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService


class FakeLogAdapter(LogAdapter):
    """Test double for LogAdapter that captures messages.

    Stores all log messages as LogEntry instances for test assertions.
    Implements level filtering via LogAdapterConfig.min_level.

    Usage:
        ```python
        config = FakeConfigurationService(LogAdapterConfig(min_level="DEBUG"))
        logger = FakeLogAdapter(config)

        # Use in service
        service = SomeService(logger=logger)
        service.do_work()

        # Assert on captured messages
        assert len(logger.messages) == 2
        assert logger.messages[0].level == LogLevel.INFO
        assert "Started" in logger.messages[0].message
        ```
    """

    def __init__(self, config: "ConfigurationService") -> None:
        """Initialize with ConfigurationService registry.

        Args:
            config: ConfigurationService registry (NOT LogAdapterConfig).
                    Adapter will call config.require(LogAdapterConfig) internally.

        Raises:
            MissingConfigurationError: If LogAdapterConfig not in registry.
        """
        self._config = config.require(LogAdapterConfig)
        self._min_level = LogLevel[self._config.min_level.upper()]
        self._messages: list[LogEntry] = []

    @property
    def messages(self) -> list[LogEntry]:
        """Access captured log messages for test assertions.

        Returns:
            List of LogEntry instances captured since creation.
        """
        return self._messages

    def debug(self, message: str, **context: Any) -> None:
        """Log a debug message if level >= DEBUG."""
        self._log(LogLevel.DEBUG, message, context)

    def info(self, message: str, **context: Any) -> None:
        """Log an info message if level >= INFO."""
        self._log(LogLevel.INFO, message, context)

    def warning(self, message: str, **context: Any) -> None:
        """Log a warning message if level >= WARNING."""
        self._log(LogLevel.WARNING, message, context)

    def error(self, message: str, **context: Any) -> None:
        """Log an error message if level >= ERROR."""
        self._log(LogLevel.ERROR, message, context)

    def _log(self, level: LogLevel, message: str, context: dict[str, Any]) -> None:
        """Internal logging implementation with error swallowing.

        Args:
            level: Log level for this message
            message: Log message content
            context: Additional key-value context

        Note:
            All exceptions are silently swallowed. Logging must never
            crash the caller, even if LogEntry creation fails.
        """
        try:
            # Check level filtering
            if level < self._min_level:
                return

            # Create and store entry
            entry = LogEntry(level=level, message=message, context=context)
            self._messages.append(entry)
        except Exception:
            # Silent swallow - logging must never crash caller
            pass
