"""MCP server module for fs2.

Provides the FastMCP server instance for AI agent integration.
All logging is configured to use stderr BEFORE any fs2 imports
to ensure zero stdout pollution (MCP protocol requirement).

Architecture:
- MCPLoggingConfig configures stderr-only logging FIRST
- FastMCP instance created with name "fs2"
- translate_error() converts domain exceptions to agent-friendly responses

Per Critical Discovery 01: STDIO protocol requires stderr-only logging.
Per Critical Discovery 05: Error translation at MCP boundary.
Per Critical Discovery 07: Logging config BEFORE imports.

Usage:
    # CLI entry point
    from fs2.mcp.server import mcp
    mcp.run()

    # Error translation
    from fs2.mcp.server import translate_error
    try:
        ...
    except Exception as e:
        return translate_error(e)
"""

# CRITICAL: Configure logging BEFORE any fs2 imports
# This ensures all loggers created at module level use stderr
from fs2.core.adapters.logging_config import MCPLoggingConfig

MCPLoggingConfig().configure()

# Emit startup log to confirm logging is active (goes to stderr)
import logging

logging.getLogger(__name__).info("MCP logging configured: all output routed to stderr")

# NOW safe to import FastMCP and other fs2 modules
from typing import Any

logger = logging.getLogger(__name__)

from fastmcp import FastMCP

from fs2.core.adapters.exceptions import (
    GraphNotFoundError,
    GraphStoreError,
)

# Create FastMCP server instance
# Note: Tools will be added in Phase 2-4
mcp = FastMCP(
    name="fs2",
    instructions=(
        "fs2 (Flowspace2) is a code intelligence tool for exploring and "
        "querying code repositories. Use the available tools to search, "
        "navigate, and understand codebases."
    ),
)


def translate_error(exc: Exception) -> dict[str, Any]:
    """Translate domain exceptions to agent-friendly responses.

    Converts fs2 exceptions into structured dictionaries with:
    - type: Exception class name
    - message: Human-readable description
    - action: Suggested remediation (or None)

    Per Critical Discovery 05: Error translation at MCP boundary.

    Args:
        exc: Any exception from fs2 operations.

    Returns:
        Dict with type, message, and action keys.

    Example:
        >>> translate_error(GraphNotFoundError(Path(".fs2/graph.pickle")))
        {
            'type': 'GraphNotFoundError',
            'message': "Graph not found at .fs2/graph.pickle. Run 'fs2 scan' first.",
            'action': "Run 'fs2 scan' to create the graph."
        }
    """
    # Log original exception for debugging (goes to stderr per MCP config)
    logger.error("MCP error translation: %s", exc, exc_info=True)

    error_type = type(exc).__name__
    message = str(exc)
    action: str | None = None

    # Specific error handling with actionable guidance
    if isinstance(exc, GraphNotFoundError):
        action = "Run 'fs2 scan' to create the graph."

    elif isinstance(exc, GraphStoreError):
        action = "The graph file may be corrupted. Try running 'fs2 scan' to regenerate it."

    elif isinstance(exc, ValueError):
        # Often regex or pattern errors
        if "regex" in message.lower() or "pattern" in message.lower():
            action = "Check the search pattern for valid regex syntax."
        else:
            action = "Verify the input parameters are valid."

    return {
        "type": error_type,
        "message": message,
        "action": action,
    }
