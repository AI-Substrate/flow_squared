"""fs2 agents-start-here -- Orientation for AI agents and new users.

State-adaptive command that detects the current project setup state and
provides relevant next-step guidance. Designed for LLM agent consumption.

5 Project States:
1. Nothing: No .fs2/ → points to fs2 init
2. Initialized, no providers: Config exists, no llm/embedding → scan or configure
3. Initialized, with providers: Config + providers, no graph → doctor then scan
4. Scanned, no providers: Config + graph, no providers → MCP setup
5. Fully configured: Config + graph + providers → MCP setup

Per Plan 026: Agent Onboarding CLI Commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from fs2.config.loaders import load_yaml_config

console = Console()


@dataclass
class ProjectState:
    """Detected project state for adaptive output."""

    initialized: bool = False
    has_providers: bool = False
    has_graph: bool = False


def agents_start_here() -> None:
    """Get started with fs2 -- orientation for AI agents and new users.

    Detects project state and provides step-by-step guidance.
    Works before fs2 init (no config required).

    Examples:
        fs2 agents-start-here       Show setup status and next steps
    """
    state = _detect_project_state()
    _render_header()
    _render_status(state)
    _render_next_step(state)
    _render_docs_hint(state)


def _detect_project_state() -> ProjectState:
    """Detect current project setup state from filesystem."""
    config_path = Path.cwd() / ".fs2" / "config.yaml"

    if not config_path.exists():
        return ProjectState()

    config = load_yaml_config(config_path)

    # Check for providers (Finding 03: isinstance guard before .get())
    llm_section = config.get("llm")
    has_llm = isinstance(llm_section, dict) and bool(llm_section.get("provider"))

    embedding_section = config.get("embedding")
    has_embedding = isinstance(embedding_section, dict) and bool(
        embedding_section.get("mode") or embedding_section.get("provider")
    )

    has_providers = has_llm or has_embedding

    # Check for graph file (Finding 07: respect config override)
    graph_section = config.get("graph")
    if isinstance(graph_section, dict) and graph_section.get("graph_path"):
        graph_path = Path.cwd() / graph_section["graph_path"]
    else:
        graph_path = Path.cwd() / ".fs2" / "graph.pickle"

    has_graph = graph_path.exists()

    return ProjectState(
        initialized=True,
        has_providers=has_providers,
        has_graph=has_graph,
    )


def _render_header() -> None:
    """Render the fs2 description header."""
    console.print()
    console.print("[bold]fs2 -- Code Intelligence for Your Codebase[/bold]")
    console.print()
    console.print(
        "fs2 indexes your codebase into a searchable graph of code symbols. "
        "It provides tree navigation, text/regex/semantic search, and AI-powered "
        "smart content summaries. Connect via MCP for native tool access."
    )
    console.print()


def _render_status(state: ProjectState) -> None:
    """Render project status checklist."""
    console.print("[bold]Project Status[/bold]")

    if not state.initialized:
        console.print("  [ ] Initialized (not initialized -- run fs2 init)")
        console.print("  [ ] Providers configured")
        console.print("  [ ] Codebase scanned")
        console.print("  [ ] MCP connected")
    else:
        console.print("  [x] Initialized")
        if state.has_providers:
            console.print("  [x] Providers configured")
        else:
            console.print(
                "  [ ] Providers configured (optional -- enables smart content + semantic search)"
            )
        if state.has_graph:
            console.print("  [x] Codebase scanned")
        else:
            console.print("  [ ] Codebase scanned")
        console.print("  [ ] MCP connected")

    console.print()


def _render_next_step(state: ProjectState) -> None:
    """Render the appropriate next step based on state."""
    console.print("[bold]Next Step[/bold]")

    if not state.initialized:
        # State 1: Nothing set up
        console.print("  Run: fs2 init")
        console.print("  This creates .fs2/config.yaml with default settings.")
    elif not state.has_graph and not state.has_providers:
        # State 2: Initialized, no providers, no graph
        console.print("  Option A: Run fs2 scan (basic code search, no AI features)")
        console.print(
            "  Option B: Configure providers first for smart content + semantic search"
        )
        console.print("    Read: fs2 docs configuration-guide")
    elif not state.has_graph and state.has_providers:
        # State 3: Initialized with providers, no graph
        console.print("  Run: fs2 doctor (validate provider configuration)")
        console.print("  Then: fs2 scan (index your codebase)")
    elif state.has_graph:
        # State 4 or 5: Scanned (with or without providers)
        console.print("  Set up MCP for native tool access.")
        console.print("  Read: fs2 docs mcp-server-guide")

    console.print()


def _render_docs_hint(state: ProjectState) -> None:
    """Render documentation browsing hints."""
    console.print("[bold]Browse Documentation[/bold]")
    console.print("  fs2 docs                    List all available documents")
    console.print(
        "  fs2 docs agents             Agent usage guide (read after MCP setup)"
    )
    console.print("  fs2 docs configuration-guide  Provider setup (Azure, OpenAI)")
    console.print("  fs2 docs mcp-server-guide   MCP server setup instructions")
    console.print()
