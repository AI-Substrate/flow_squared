#!/usr/bin/env python3
"""
Serena MCP harness — talk to a running Serena MCP server over streamable-http.

Start the server first:
    serena-mcp-server --project fs2 --transport streamable-http \
        --host 127.0.0.1 --port 8321 \
        --open-web-dashboard false --enable-web-dashboard false

Run exploration:
    uv run python scripts/serena-explore/harness.py

Interactive mode:
    uv run python scripts/serena-explore/harness.py --interactive
"""

from __future__ import annotations

import asyncio
import json
import sys

from fastmcp import Client


SERVER_URL = "http://127.0.0.1:8321/mcp/"


async def call_tool(client: Client, name: str, args: dict | None = None, max_chars: int = 4000):
    """Call a tool and print the result."""
    print(f"\n{'─'*60}")
    print(f"  {name}({json.dumps(args or {})})")
    print(f"{'─'*60}")
    try:
        result = await client.call_tool(name, args or {})
        if hasattr(result, 'content'):
            for item in result.content:
                text = getattr(item, 'text', repr(item))
                if len(text) > max_chars:
                    print(text[:max_chars] + f"\n... ({len(text)} chars)")
                else:
                    print(text)
        else:
            print(repr(result)[:max_chars])
        return result
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")
        return None


async def main():
    print(f"Connecting to Serena MCP at {SERVER_URL}")

    async with Client(SERVER_URL) as client:
        # List tools
        tools = await client.list_tools()
        print(f"\n  {len(tools)} tools available:")
        for t in sorted(tools, key=lambda x: x.name):
            print(f"    {t.name:40s} {(t.description or '')[:60]}")

        print(f"\n{'='*60}")
        print(f"  CROSS-FILE RELATIONSHIP EXPLORATION")
        print(f"{'='*60}")

        # Find GraphStore and its structure
        await call_tool(client, "find_symbol", {
            "name_path_pattern": "GraphStore", "depth": 1,
        })

        # Who references GraphStore? (cross-file!)
        await call_tool(client, "find_referencing_symbols", {
            "name_path": "GraphStore",
            "relative_path": "src/fs2/core/repos/graph_store.py",
        })

        # Who references add_edge specifically?
        await call_tool(client, "find_referencing_symbols", {
            "name_path": "GraphStore/add_edge",
            "relative_path": "src/fs2/core/repos/graph_store.py",
        })

        # Who calls CodeNode?
        await call_tool(client, "find_referencing_symbols", {
            "name_path": "CodeNode",
            "relative_path": "src/fs2/core/models/code_node.py",
        })

        # Interactive mode
        if "--interactive" in sys.argv:
            print(f"\n{'='*60}")
            print("  INTERACTIVE MODE")
            print("  Format: tool_name {\"arg\": \"val\"}")
            print("  Type 'quit' to exit")
            print(f"{'='*60}")
            while True:
                try:
                    line = input("\nserena> ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if line in ("quit", "exit", "q"):
                    break
                if not line:
                    continue
                parts = line.split(" ", 1)
                name = parts[0]
                args = json.loads(parts[1]) if len(parts) > 1 else {}
                await call_tool(client, name, args)


if __name__ == "__main__":
    asyncio.run(main())
