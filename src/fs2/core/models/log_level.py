"""Log level enumeration.

Provides type-safe log levels with ordering support for Phase 3's
level filtering feature.
"""

from enum import IntEnum


class LogLevel(IntEnum):
    """Log severity levels, ordered from least to most severe.

    Using IntEnum enables comparison: LogLevel.DEBUG < LogLevel.INFO
    This supports Phase 3's level filtering feature.

    Levels follow Python logging convention (multiples of 10):
    - DEBUG (10): Detailed diagnostic information
    - INFO (20): General operational events
    - WARNING (30): Something unexpected but not critical
    - ERROR (40): Something went wrong that needs attention
    """

    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
