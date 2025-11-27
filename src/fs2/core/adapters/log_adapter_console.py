"""ConsoleLogAdapter - Development logging to stdout/stderr.

Per Phase 3: Logger Adapter Implementation.
Per Plan AC7: LogAdapter ABC with debug/info/warning/error.

Architecture:
- Inherits from LogAdapter ABC
- Receives ConfigurationService via constructor (no concept leakage)
- Writes to stdout (info/debug/warning) and stderr (error)
- Format: YYYY-MM-DD HH:MM:SS LEVEL: message key=value

CRITICAL: Logging methods must never propagate exceptions (industry standard).
Internal errors are silently swallowed to prevent logging from crashing callers.
"""

import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fs2.config.objects import LogAdapterConfig
from fs2.core.adapters.log_adapter import LogAdapter
from fs2.core.models.log_entry import LogEntry
from fs2.core.models.log_level import LogLevel

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService


class ConsoleLogAdapter(LogAdapter):
    """Console logging adapter for development use.

    Writes log messages to stdout (debug/info/warning) or stderr (error).
    Supports structured context via **kwargs.
    Implements level filtering via LogAdapterConfig.min_level.

    Usage:
        ```python
        config = FakeConfigurationService(LogAdapterConfig(min_level="INFO"))
        logger = ConsoleLogAdapter(config)
        logger.info("Processing", trace_id="123")
        # Output: 2025-11-27 14:32:01 INFO: Processing trace_id=123
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

    def debug(self, message: str, **context: Any) -> None:
        """Log a debug message to stdout if level >= DEBUG."""
        self._log(LogLevel.DEBUG, message, context, sys.stdout)

    def info(self, message: str, **context: Any) -> None:
        """Log an info message to stdout if level >= INFO."""
        self._log(LogLevel.INFO, message, context, sys.stdout)

    def warning(self, message: str, **context: Any) -> None:
        """Log a warning message to stdout if level >= WARNING."""
        self._log(LogLevel.WARNING, message, context, sys.stdout)

    def error(self, message: str, **context: Any) -> None:
        """Log an error message to stderr if level >= ERROR."""
        self._log(LogLevel.ERROR, message, context, sys.stderr)

    def _log(
        self, level: LogLevel, message: str, context: dict[str, Any], stream: Any
    ) -> None:
        """Internal logging implementation with error swallowing.

        Args:
            level: Log level for this message
            message: Log message content
            context: Additional key-value context
            stream: Output stream (sys.stdout or sys.stderr)

        Note:
            All exceptions are silently swallowed. Logging must never
            crash the caller, even if formatting or I/O fails.
        """
        try:
            # Check level filtering
            if level < self._min_level:
                return

            # Create entry and format
            entry = LogEntry(level=level, message=message, context=context)
            formatted = self._format_entry(entry)

            # Output
            print(formatted, file=stream)
        except Exception:
            # Silent swallow - logging must never crash caller
            pass

    def _format_entry(self, entry: LogEntry) -> str:
        """Format a LogEntry to string.

        Format: YYYY-MM-DD HH:MM:SS LEVEL: message key=value key2=value2

        Args:
            entry: LogEntry to format

        Returns:
            Formatted log line
        """
        # Format timestamp (local time for readability)
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

        # Format context as key=value pairs
        context_str = ""
        if entry.context:
            context_parts = [f"{k}={v}" for k, v in entry.context.items()]
            context_str = " " + " ".join(context_parts)

        return f"{timestamp} {entry.level.name}: {entry.message}{context_str}"
