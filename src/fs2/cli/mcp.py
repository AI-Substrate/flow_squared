"""MCP CLI command for fs2.

Starts the FastMCP server on STDIO transport for AI agent integration.

Per Critical Discovery 01: Logging MUST be configured BEFORE any fs2 imports.
This module imports MCPLoggingConfig and calls configure() as its first action
when the mcp() function is invoked.

Usage:
    fs2 mcp              # Start MCP server on STDIO (local install)

    # Zero-install with uvx:
    uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 mcp

Per DYK#3: --config option deferred to future cross-cutting plan.
Uses default config system (.fs2/config.yaml, ~/.config/fs2/config.yaml).

Example Claude Desktop configuration:
    {
      "mcpServers": {
        "fs2": {
          "command": "fs2",
          "args": ["mcp"],
          "cwd": "/path/to/your/project"
        }
      }
    }
"""


def mcp() -> None:
    """Start the MCP server on STDIO transport.

    Launches the FastMCP server that enables AI agents like Claude Desktop
    to use fs2's tree, get_node, and search tools programmatically.

    The server communicates via JSON-RPC over STDIO:
    - stdin: Receives JSON-RPC requests from the AI agent
    - stdout: Sends JSON-RPC responses (100% reserved for protocol)
    - stderr: All logging and diagnostic output

    Prerequisites:
        Codebase must be indexed with 'fs2 scan' first.
        For semantic search: 'fs2 scan --embed' for embeddings.

    Configuration:
        Uses default config system:
        - .fs2/config.yaml (project-level)
        - ~/.config/fs2/config.yaml (user-level)
        - FS2_* environment variables
    """
    # CRITICAL: Configure logging to stderr BEFORE any other imports
    # Per Critical Discovery 01 and Phase 1 implementation
    from fs2.core.adapters.logging_config import MCPLoggingConfig

    MCPLoggingConfig().configure()

    # 046: Pre-create and cache embedding adapter for singleton reuse.
    # Fires background warmup so model is ready before first search.
    _preload_embedding_adapter()

    # NOW safe to import and run the MCP server
    from fs2.mcp.server import mcp as mcp_server

    mcp_server.run()


def _preload_embedding_adapter() -> None:
    """Create embedding adapter at startup and warm model in background.

    Per 046-mcp-embedding-preload:
    1. Creates the adapter via the standard factory
    2. Caches it as a singleton via set_embedding_adapter()
    3. Fires a daemon thread to call adapter.warmup() (non-blocking)

    If embedding is not configured or sentence-transformers is missing,
    this is a silent no-op — search falls back to text mode as before.
    """
    import logging
    import threading

    logger = logging.getLogger(__name__)

    try:
        from fs2.core.adapters.embedding_adapter import (
            create_embedding_adapter_from_config,
        )
        from fs2.core.dependencies import get_config, set_embedding_adapter

        config = get_config()
        adapter = create_embedding_adapter_from_config(config)
        if adapter is None:
            return  # No embedding configured or deps missing — graceful degradation

        set_embedding_adapter(adapter)

        # Fire background warmup (non-blocking)
        thread = threading.Thread(target=adapter.warmup, daemon=True)
        thread.start()
        logger.info("Embedding model warmup started in background")

    except Exception as e:
        logger.warning(f"Embedding preload skipped: {e}")
