"""fs2 docs -- Browse bundled documentation via CLI.

Provides CLI access to the same documentation available through MCP tools
(docs_list, docs_get). Breaks the bootstrap paradox: agents can read fs2
docs before MCP is connected.

Modes:
- List mode (no args): Shows all documents grouped by category
- Read mode (doc_id): Shows full document content
- JSON mode (--json): Outputs structured JSON matching MCP format

Per Plan 026: Agent Onboarding CLI Commands.
"""

from __future__ import annotations

import json
from itertools import groupby
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown

console = Console()
stderr_console = Console(stderr=True)


def docs(
    doc_id: Annotated[
        str | None,
        typer.Argument(help="Document ID to read (omit to list all)"),
    ] = None,
    category: Annotated[
        str | None,
        typer.Option("--category", "-c", help="Filter by category"),
    ] = None,
    tags: Annotated[
        str | None,
        typer.Option("--tags", "-t", help="Filter by tags (comma-separated)"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """Browse fs2 documentation.

    Run without arguments to list all available documents.
    Pass a document ID to read its full content.

    Examples:
        fs2 docs                    List all documents
        fs2 docs agents             Read the agent guidance doc
        fs2 docs --json             List as JSON (MCP-compatible)
        fs2 docs agents --json      Read as JSON (MCP-compatible)
        fs2 docs -c reference       List reference docs only
        fs2 docs -t config          List docs tagged 'config'
    """
    from fs2.core.dependencies import get_docs_service

    service = get_docs_service()

    if doc_id is None:
        _list_docs(service, category, tags, json_output)
    else:
        _read_doc(service, doc_id, json_output)


def _list_docs(service, category, tags, json_output):
    """List available documents, optionally filtered."""
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    documents = service.list_documents(category=category, tags=tag_list)

    if json_output:
        data = {
            "docs": [
                {
                    "id": doc.id,
                    "title": doc.title,
                    "summary": doc.summary,
                    "category": doc.category,
                    "tags": list(doc.tags),
                }
                for doc in documents
            ],
            "count": len(documents),
        }
        print(json.dumps(data, indent=2))  # noqa: T201
        return

    if not documents:
        console.print("No documents found matching filters.")
        return

    # Group by category, sorted
    sorted_docs = sorted(documents, key=lambda d: d.category)
    for cat, group in groupby(sorted_docs, key=lambda d: d.category):
        console.print(f"\n[bold]{cat}[/bold]")
        for doc in group:
            console.print(f"  {doc.id:<25} {doc.title}")

    console.print("\n[dim]Use [bold]fs2 docs <id>[/bold] to read a document.[/dim]")


def _read_doc(service, doc_id, json_output):
    """Read and display a specific document."""
    doc = service.get_document(doc_id)

    if doc is None:
        # Show available IDs to help the user
        all_docs = service.list_documents()
        available = ", ".join(d.id for d in all_docs)
        stderr_console.print(
            f"[red]Error:[/red] Document '{doc_id}' not found.\n"
            f"Available documents: {available}"
        )
        raise typer.Exit(1)

    if json_output:
        data = {
            "id": doc.metadata.id,
            "title": doc.metadata.title,
            "content": doc.content,
            "metadata": {
                "id": doc.metadata.id,
                "title": doc.metadata.title,
                "summary": doc.metadata.summary,
                "category": doc.metadata.category,
                "tags": list(doc.metadata.tags),
            },
        }
        print(json.dumps(data, indent=2))  # noqa: T201
        return

    console.print(Markdown(doc.content))
