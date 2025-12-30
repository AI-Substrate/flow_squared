"""Logging configuration adapters for different runtime modes.

Provides explicit configuration of Python's global logging system.
Called at CLI entry points BEFORE any other imports to ensure
all loggers use the correct output stream.

Architecture:
- LoggingConfigAdapter: ABC defining configure() interface
- MCPLoggingConfig: Routes all fs2 logs to stderr (MCP protocol requirement)
- DefaultLoggingConfig: Standard console logging (Rich-enabled)

Per Critical Discovery 01: MCP protocol uses stdout exclusively for JSON-RPC.
ALL logging must route to stderr to avoid protocol corruption.

Usage:
    # In CLI entry point for MCP
    from fs2.core.adapters.logging_config import MCPLoggingConfig
    MCPLoggingConfig().configure()  # BEFORE any other fs2 imports

    # Then safe to import MCP server
    from fs2.mcp.server import mcp
"""

import logging
import sys
from abc import ABC, abstractmethod


class LoggingConfigAdapter(ABC):
    """Abstract base for logging configuration.

    Implementations configure Python's global logging system
    for different runtime modes (MCP, CLI, testing).
    """

    @abstractmethod
    def configure(self) -> None:
        """Apply logging configuration.

        Must be called BEFORE any other fs2 imports to ensure
        all loggers created at module level use the correct config.
        """
        ...


class MCPLoggingConfig(LoggingConfigAdapter):
    """Configure logging for MCP server mode.

    MCP protocol uses stdout exclusively for JSON-RPC messages.
    ALL logging MUST route to stderr to avoid protocol corruption.

    This adapter:
    1. Clears any existing handlers on root logger
    2. Configures stderr-only logging for all fs2.* loggers
    3. Sets appropriate log level and format

    Per Perplexity research: Claude Desktop captures stderr to
    `mcp-server-{name}.log` files, so logging is preserved for debugging.
    """

    def __init__(self, level: int = logging.INFO) -> None:
        """Initialize with optional log level.

        Args:
            level: Logging level (default: INFO).
        """
        self._level = level

    def configure(self) -> None:
        """Configure stderr-only logging for MCP mode.

        Clears existing handlers and sets up stderr logging
        for the fs2 logger hierarchy.
        """
        # Clear any existing handlers on root logger
        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)

        # Create stderr handler
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(self._level)

        # Simple format for MCP logs (captured to mcp-server-*.log)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        stderr_handler.setFormatter(formatter)

        # Configure fs2 logger hierarchy
        fs2_logger = logging.getLogger("fs2")
        fs2_logger.setLevel(self._level)
        fs2_logger.addHandler(stderr_handler)

        # Prevent propagation to root (avoid duplicate logs)
        fs2_logger.propagate = False


class DefaultLoggingConfig(LoggingConfigAdapter):
    """Configure standard logging for CLI mode.

    Uses default Python logging with stdout/stderr split:
    - DEBUG/INFO to stdout
    - WARNING/ERROR to stderr

    This is the normal configuration when NOT in MCP mode.
    """

    def __init__(self, level: int = logging.INFO) -> None:
        """Initialize with optional log level.

        Args:
            level: Logging level (default: INFO).
        """
        self._level = level

    def configure(self) -> None:
        """Configure standard logging for CLI mode."""
        logging.basicConfig(
            level=self._level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
