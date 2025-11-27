"""Domain models as frozen dataclasses.

Public API:
- LogLevel: Log severity levels (IntEnum)
- LogEntry: Immutable log entry with level, message, context, timestamp
- ProcessResult: Result type for adapter operations with ok()/fail() factories
"""

from fs2.core.models.log_entry import LogEntry
from fs2.core.models.log_level import LogLevel
from fs2.core.models.process_result import ProcessResult

__all__ = ["LogLevel", "LogEntry", "ProcessResult"]
