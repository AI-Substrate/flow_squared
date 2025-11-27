"""LogAdapter ABC interface.

Defines the logging interface that all implementations must follow.

Architecture:
- This file: ABC definition only
- Implementations: log_adapter_console.py, log_adapter_fake.py, etc.

See: docs/plans/002-project-skele/project-skele-spec.md § AC7
"""

from abc import ABC, abstractmethod
from typing import Any


class LogAdapter(ABC):
    """Abstract base class for logging adapters.

    Defines the logging interface that all implementations must follow.
    Implementations (e.g., ConsoleLogAdapter, FakeLogAdapter) are in separate
    files and may use external SDKs.

    Methods accept **context for structured logging with key-value pairs.

    Per AC7: debug/info/warning/error methods required.
    """

    @abstractmethod
    def debug(self, message: str, **context: Any) -> None:
        """Log a debug message.

        Args:
            message: Log message content
            **context: Additional key-value pairs for structured logging
        """
        ...

    @abstractmethod
    def info(self, message: str, **context: Any) -> None:
        """Log an info message.

        Args:
            message: Log message content
            **context: Additional key-value pairs for structured logging
        """
        ...

    @abstractmethod
    def warning(self, message: str, **context: Any) -> None:
        """Log a warning message.

        Args:
            message: Log message content
            **context: Additional key-value pairs for structured logging
        """
        ...

    @abstractmethod
    def error(self, message: str, **context: Any) -> None:
        """Log an error message.

        Args:
            message: Log message content
            **context: Additional key-value pairs for structured logging
        """
        ...
