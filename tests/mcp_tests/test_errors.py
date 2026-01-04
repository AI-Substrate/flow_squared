"""Tests for error translation at MCP boundary.

Per Critical Discovery 05: Domain exceptions must be translated
to agent-friendly structured responses at the MCP boundary.

Each error response must include:
- type: Exception class name
- message: Human-readable description
- action: Suggested remediation for the agent (or None)
"""

import logging
from pathlib import Path

from fs2.core.adapters.exceptions import (
    GraphNotFoundError,
    GraphStoreError,
)


class TestErrorTranslation:
    """Verify error translation produces agent-friendly responses."""

    def test_graph_not_found_error_translation(self):
        """GraphNotFoundError translates to actionable response.

        Agent should know to run 'fs2 scan' to fix the problem.
        """
        from fs2.mcp.server import translate_error

        exc = GraphNotFoundError(Path(".fs2/graph.pickle"))
        result = translate_error(exc)

        assert result["type"] == "GraphNotFoundError"
        assert (
            "not found" in result["message"].lower()
            or "graph" in result["message"].lower()
        )
        assert result["action"] is not None
        assert "scan" in result["action"].lower()

    def test_graph_store_error_translation(self):
        """GraphStoreError translates with appropriate message."""
        from fs2.mcp.server import translate_error

        exc = GraphStoreError("Failed to load graph: corrupted pickle")
        result = translate_error(exc)

        assert result["type"] == "GraphStoreError"
        assert (
            "corrupted" in result["message"].lower()
            or "failed" in result["message"].lower()
        )

    def test_value_error_translation(self):
        """ValueError translates with regex context."""
        from fs2.mcp.server import translate_error

        exc = ValueError("Invalid regex pattern: [unclosed")
        result = translate_error(exc)

        assert result["type"] == "ValueError"
        assert (
            "regex" in result["message"].lower()
            or "pattern" in result["message"].lower()
        )

    def test_unknown_error_translation(self):
        """Unknown exceptions get generic translation."""
        from fs2.mcp.server import translate_error

        exc = RuntimeError("Something unexpected happened")
        result = translate_error(exc)

        assert result["type"] == "RuntimeError"
        assert result["message"] == "Something unexpected happened"
        # Unknown errors may not have actionable guidance
        assert "action" in result

    def test_error_response_has_required_keys(self):
        """All error responses have type, message, action keys."""
        from fs2.mcp.server import translate_error

        exc = Exception("Test error")
        result = translate_error(exc)

        assert "type" in result
        assert "message" in result
        assert "action" in result


class TestErrorMessages:
    """Verify error messages are agent-friendly."""

    def test_graph_not_found_message_is_actionable(self):
        """GraphNotFoundError provides clear remediation."""
        from fs2.mcp.server import translate_error

        exc = GraphNotFoundError(Path(".fs2/graph.pickle"))
        result = translate_error(exc)

        # Agent should understand what to do
        action = result["action"]
        assert action is not None
        assert "fs2" in action.lower() or "scan" in action.lower()

    def test_exception_chaining_preserved(self):
        """Original exception message is preserved in translation."""
        from fs2.mcp.server import translate_error

        original_message = "Specific error details here"
        exc = GraphStoreError(original_message)
        result = translate_error(exc)

        # Original message should be in the translated message
        assert (
            original_message in result["message"]
            or "specific" in result["message"].lower()
        )


class TestErrorLogging:
    """Verify error translation logs exceptions (OBS-002 fix)."""

    def test_translate_error_logs_original_exception(self, capfd):
        """translate_error logs the original exception with stack trace.

        Per code review OBS-002: Original stack trace should be logged
        before translation for production debugging.

        Note: We use capfd instead of caplog because MCPLoggingConfig
        routes all fs2 logs to stderr without propagation.
        """
        # Re-configure logging to use fresh stderr handler
        import sys

        logger = logging.getLogger("fs2.mcp.server")
        # Remove any old handlers that might point to closed streams
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        # Add fresh handler
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
        logger.addHandler(handler)

        from fs2.mcp.server import translate_error

        exc = GraphNotFoundError(Path(".fs2/graph.pickle"))
        translate_error(exc)

        captured = capfd.readouterr()
        assert (
            "Graph not found" in captured.err or "MCP error translation" in captured.err
        )

    def test_translate_error_logs_all_exception_types(self, capfd):
        """All exception types are logged, not just domain exceptions.

        Even unknown exceptions should be logged for debugging.
        """
        # Re-configure logging to use fresh stderr handler
        import sys

        logger = logging.getLogger("fs2.mcp.server")
        # Remove any old handlers that might point to closed streams
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        # Add fresh handler
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
        logger.addHandler(handler)

        from fs2.mcp.server import translate_error

        exc = RuntimeError("Unexpected failure")
        translate_error(exc)

        captured = capfd.readouterr()
        assert "Unexpected failure" in captured.err
