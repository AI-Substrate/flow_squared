"""Tests for MCP protocol compliance - stdout isolation.

Per Critical Discovery 01: STDIO protocol requires stderr-only logging.
Any stdout during import breaks MCP JSON-RPC communication.

These tests verify that:
1. Importing fs2.mcp.server produces zero stdout output
2. Logging goes to stderr, not stdout
"""

import sys
from io import StringIO


class TestProtocolCompliance:
    """Verify MCP protocol requirements."""

    def test_no_stdout_on_import(self, monkeypatch):
        """Importing fs2.mcp.server produces zero stdout output.

        This is CRITICAL for MCP protocol compliance. The JSON-RPC
        transport uses stdout exclusively for protocol messages.
        Any other output (logs, Rich formatting, print statements)
        will corrupt the protocol stream.

        Per Critical Discovery 01.
        """
        # Capture stdout
        captured = StringIO()
        monkeypatch.setattr(sys, "stdout", captured)

        # Force reimport to test import-time behavior
        # Remove cached module if present
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("fs2.mcp"):
                del sys.modules[mod_name]

        # Import should produce ZERO stdout
        import fs2.mcp.server  # noqa: F401

        assert captured.getvalue() == "", (
            f"Expected zero stdout on import, got: {captured.getvalue()!r}"
        )

    def test_logging_goes_to_stderr(self, monkeypatch, capfd):
        """Verify logging output goes to stderr, not stdout.

        Per Critical Discovery 01: All logging must use stderr.
        """
        import logging

        # Clear any cached modules
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("fs2.mcp"):
                del sys.modules[mod_name]

        import fs2.mcp.server  # noqa: F401

        # Trigger a log message
        logger = logging.getLogger("fs2.mcp")
        logger.warning("Test log message")

        captured = capfd.readouterr()
        assert captured.out == "", "Logs should not appear on stdout"
        # stderr may or may not have the message depending on log level config
        # but stdout MUST be empty

    def test_mcp_instance_exists(self):
        """Verify the mcp FastMCP instance is created.

        The server module must expose an `mcp` attribute that is
        a FastMCP instance for tool registration.
        """
        # Clear any cached modules
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("fs2.mcp"):
                del sys.modules[mod_name]

        # Verify it's a FastMCP instance
        from fastmcp import FastMCP

        from fs2.mcp.server import mcp

        assert isinstance(mcp, FastMCP), f"Expected FastMCP instance, got {type(mcp)}"
