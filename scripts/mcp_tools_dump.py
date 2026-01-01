#!/usr/bin/env python3
"""Dump all MCP tools with their properties for human inspection.

This script connects to the fs2 MCP server and displays all registered tools
with their descriptions, parameters, and annotations - exactly what an AI agent
would see when connecting to the server.

Usage:
    uv run python scripts/mcp_tools_dump.py           # Show all tools
    uv run python scripts/mcp_tools_dump.py tree      # Show only 'tree' tool
    just mcp-dump                                      # Show all tools
    just mcp-dump tree                                 # Show only 'tree' tool
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree


console = Console()


def format_json_schema_type(schema: dict[str, Any]) -> str:
    """Convert JSON schema type to human-readable string."""
    if not schema:
        return "any"

    type_str = schema.get("type", "any")

    # Handle anyOf (e.g., string | null)
    if "anyOf" in schema:
        types = []
        for option in schema["anyOf"]:
            if option.get("type") == "null":
                types.append("null")
            else:
                types.append(format_json_schema_type(option))
        return " | ".join(types)

    # Handle enum
    if "enum" in schema:
        return f"Literal{schema['enum']}"

    # Handle array
    if type_str == "array":
        items = schema.get("items", {})
        item_type = format_json_schema_type(items)
        return f"list[{item_type}]"

    # Handle object
    if type_str == "object":
        return "dict"

    return type_str


def render_parameters(input_schema: dict[str, Any] | None) -> Table:
    """Render tool parameters as a Rich table."""
    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        expand=True,
    )
    table.add_column("Parameter", style="green", no_wrap=True)
    table.add_column("Type", style="yellow", no_wrap=True)
    table.add_column("Required", style="magenta", no_wrap=True, justify="center")
    table.add_column("Default", style="blue", no_wrap=True)
    table.add_column("Description", style="white")

    if not input_schema:
        table.add_row("(none)", "-", "-", "-", "No parameters")
        return table

    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))

    for name, prop in properties.items():
        type_str = format_json_schema_type(prop)
        is_required = name in required
        default = prop.get("default", "-")
        if default != "-":
            default = json.dumps(default)
        description = prop.get("description", "-")

        # Truncate long descriptions
        if len(description) > 80:
            description = description[:77] + "..."

        table.add_row(
            name,
            type_str,
            "[green]Yes[/]" if is_required else "[dim]No[/]",
            str(default),
            description,
        )

    return table


def render_annotations(annotations: Any) -> Table:
    """Render tool annotations as a Rich table."""
    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        expand=False,
    )
    table.add_column("Hint", style="green", no_wrap=True)
    table.add_column("Value", style="yellow", no_wrap=True)
    table.add_column("Meaning", style="dim white")

    if not annotations:
        table.add_row("(none)", "-", "No annotations provided")
        return table

    # Standard MCP annotations
    hint_meanings = {
        "title": "Human-readable display name",
        "readOnlyHint": "True = tool only reads, no modifications",
        "destructiveHint": "True = may perform destructive updates",
        "idempotentHint": "True = repeated calls have no additional effect",
        "openWorldHint": "True = interacts with external/unpredictable entities",
    }

    # Get annotation values (handle both dict and object)
    if hasattr(annotations, "title"):
        # Object-style access
        hints = {
            "title": getattr(annotations, "title", None),
            "readOnlyHint": getattr(annotations, "readOnlyHint", None),
            "destructiveHint": getattr(annotations, "destructiveHint", None),
            "idempotentHint": getattr(annotations, "idempotentHint", None),
            "openWorldHint": getattr(annotations, "openWorldHint", None),
        }
    else:
        # Dict-style access
        hints = {
            "title": annotations.get("title"),
            "readOnlyHint": annotations.get("readOnlyHint"),
            "destructiveHint": annotations.get("destructiveHint"),
            "idempotentHint": annotations.get("idempotentHint"),
            "openWorldHint": annotations.get("openWorldHint"),
        }

    for hint_name, meaning in hint_meanings.items():
        value = hints.get(hint_name)
        if value is not None:
            # Color code boolean values
            if isinstance(value, bool):
                value_str = "[green]True[/]" if value else "[red]False[/]"
            else:
                value_str = str(value)
            table.add_row(hint_name, value_str, meaning)

    return table


def render_tool(tool: Any, index: int, total: int) -> Panel:
    """Render a single tool as a Rich panel."""
    # Build content tree
    tree = Tree(f"[bold cyan]{tool.name}[/]")

    # Description
    description = tool.description or "(no description)"
    desc_branch = tree.add("[bold]Description[/]")
    # Render as markdown for proper formatting
    desc_branch.add(Markdown(description))

    # Parameters
    params_branch = tree.add("[bold]Parameters[/]")
    params_table = render_parameters(tool.inputSchema)
    params_branch.add(params_table)

    # Annotations
    annotations_branch = tree.add("[bold]Annotations (Hints)[/]")
    annotations_table = render_annotations(tool.annotations)
    annotations_branch.add(annotations_table)

    return Panel(
        tree,
        title=f"[bold white]Tool {index}/{total}: [cyan]{tool.name}[/][/]",
        border_style="blue",
        expand=True,
    )


async def dump_tools(tool_filter: str | None = None) -> None:
    """Connect to MCP server and dump tools.

    Args:
        tool_filter: Optional tool name to filter by. If None, shows all tools.
    """
    # Import server after setting up (avoids logging issues)
    from fastmcp.client import Client

    from fs2.mcp.server import mcp

    console.print()
    filter_msg = f" (filter: [cyan]{tool_filter}[/])" if tool_filter else ""
    console.print(
        Panel(
            "[bold]fs2 MCP Server - Tool Inspection[/]\n\n"
            "This shows all tools visible to AI agents connecting to the MCP server.\n"
            "Each tool includes its description, parameters, and behavioral hints.",
            title=f"[bold cyan]MCP Tools Dump[/]{filter_msg}",
            border_style="green",
        )
    )
    console.print()

    # Connect to server
    async with Client(mcp) as client:
        all_tools = await client.list_tools()

        # Filter tools if requested
        if tool_filter:
            tools = [t for t in all_tools if t.name == tool_filter]
            if not tools:
                console.print(
                    f"[red]Tool '[bold]{tool_filter}[/]' not found.[/]\n"
                    f"Available tools: {', '.join(t.name for t in all_tools)}"
                )
                return
        else:
            tools = all_tools

        if not tools:
            console.print("[yellow]No tools registered in the MCP server.[/]")
            return

        console.print(f"[bold green]Found {len(tools)} tool(s)[/]\n")

        # Render each tool
        for i, tool in enumerate(tools, 1):
            panel = render_tool(tool, i, len(tools))
            console.print(panel)
            console.print()

    # Summary
    console.print(
        Panel(
            f"[bold]Showing: {len(tools)} tool(s)[/]\n\n"
            "These are the tools an AI agent will discover when connecting to:\n"
            "[cyan]fs2 mcp[/]",
            title="[bold]Summary[/]",
            border_style="dim",
        )
    )


def main() -> None:
    """Entry point."""
    # Parse optional tool name filter from command line
    tool_filter = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(dump_tools(tool_filter))


if __name__ == "__main__":
    main()
