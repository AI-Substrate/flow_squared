"""Log entry domain model.

Provides immutable log entry representation for structured logging.
Per Finding 06: Frozen dataclasses for domain models.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fs2.core.models.log_level import LogLevel


@dataclass(frozen=True)
class LogEntry:
    """Immutable log entry domain model.

    Attributes:
        level: Log level (type-safe LogLevel enum)
        message: Log message content
        context: Additional key-value context
        timestamp: When the entry was created (auto-generated, UTC)

    Note:
        The `context` dict contents are technically mutable even though the
        dataclass is frozen. Frozen only prevents reassigning `self.context`,
        not modifying the dict's contents. For POC scope this is acceptable;
        consider MappingProxyType wrapper if true immutability is needed later.
    """

    level: LogLevel
    message: str
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
