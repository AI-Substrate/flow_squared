"""
Stub for sensai.util.logging.

Provides LogTime context manager for timing code blocks.
"""

from __future__ import annotations

import logging
import time


class LogTime:
    """
    Context manager for timing code blocks and logging the duration.

    Usage:
        with LogTime("Operation name", logger=log):
            do_something()
    """

    def __init__(
        self,
        name: str,
        logger: logging.Logger | None = None,
        log_level: int = logging.INFO,
    ) -> None:
        """
        Initialize LogTime.

        Args:
            name: Name of the operation being timed
            logger: Logger to use (defaults to root logger)
            log_level: Log level to use (defaults to INFO)
        """
        self.name = name
        self.logger = logger or logging.getLogger()
        self.log_level = log_level
        self.start_time: float = 0.0
        self.duration: float = 0.0

    def __enter__(self) -> "LogTime":
        """Start timing."""
        self.start_time = time.time()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """End timing and log the duration."""
        self.duration = time.time() - self.start_time
        self.logger.log(
            self.log_level,
            "%s completed in %.2f seconds",
            self.name,
            self.duration,
        )
