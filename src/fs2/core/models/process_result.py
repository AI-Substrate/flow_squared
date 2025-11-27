"""Process result domain model.

Provides immutable result type for adapter operations.
Enables explicit success/error handling without exceptions for expected failures.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProcessResult:
    """Result of an adapter operation, representing success or failure.

    This pattern enables:
    - Explicit success/failure handling (no exceptions for expected failures)
    - Rich error information with context
    - Metadata for tracing, timing, or other cross-cutting concerns

    Attributes:
        success: Whether the operation succeeded
        value: The result value (only meaningful if success=True)
        error: Error message (only meaningful if success=False)
        metadata: Additional context (trace_id, timing, etc.)

    Note:
        Like LogEntry.context, the metadata dict is technically mutable.
        See LogEntry Note for details.
    """

    success: bool
    value: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, value: Any, **metadata: Any) -> "ProcessResult":
        """Create a successful result.

        Args:
            value: The result value
            **metadata: Additional context (trace_id, duration_ms, etc.)

        Returns:
            ProcessResult with success=True and provided value
        """
        return cls(success=True, value=value, metadata=metadata)

    @classmethod
    def fail(cls, error: str, **metadata: Any) -> "ProcessResult":
        """Create a failed result.

        Args:
            error: Error message describing what went wrong
            **metadata: Additional context (retry_count, etc.)

        Returns:
            ProcessResult with success=False and provided error
        """
        return cls(success=False, error=error, metadata=metadata)
