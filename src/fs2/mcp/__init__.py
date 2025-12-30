"""MCP server module for fs2.

This module exposes fs2's code intelligence capabilities through the
Model Context Protocol (MCP), enabling AI coding agents to explore
indexed codebases programmatically.

Architecture:
- This module is a peer to cli/, NOT under core/
- Composes existing services (TreeService, GetNodeService, SearchService)
- Uses FastMCP framework for tool definitions
- STDIO transport only (JSON-RPC over stdin/stdout)

Key Components:
- server.py: FastMCP instance and tool definitions
- dependencies.py: Lazy service initialization with singleton caching

Usage:
    # CLI entry point
    fs2 mcp

    # Or programmatically
    from fs2.mcp.server import mcp
    mcp.run()

See: docs/plans/011-mcp/mcp-spec.md
"""
