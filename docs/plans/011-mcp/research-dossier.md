# Research Report: MCP Server Implementation for fs2

**Generated**: 2025-12-26
**Research Query**: "MCP server with tree, get-node, and search tools using FastMCP, with best practice tool descriptions for AI agents"
**Mode**: Pre-Plan
**Plan Folder**: docs/plans/011-mcp
**FlowSpace**: Not Available
**Findings**: ~45 findings synthesized

---

## Executive Summary

### What It Does
An MCP server for fs2 will expose the existing code graph functionality (tree, get-node, search) via the Model Context Protocol, enabling AI coding agents like Claude to semantically explore and retrieve code structure from indexed repositories.

### Business Purpose
Transform fs2 from a CLI-only tool into an AI-native code intelligence platform that LLM agents can use autonomously. This enables agents to understand codebases structurally rather than just through text grep.

### Key Insights
1. **Existing services are MCP-ready**: TreeService, GetNodeService, and SearchService have clean DI interfaces that can be composed directly in MCP tools
2. **FastMCP is the optimal choice**: Python-native, decorator-based, auto-generates schemas from type hints, handles stdio transport correctly
3. **Tool descriptions are critical**: Well-crafted descriptions drive agent tool selection; include prerequisites, return types, and workflow guidance

### Quick Stats
- **Existing Services**: 3 (TreeService, GetNodeService, SearchService)
- **CLI Commands**: 5 (scan, init, tree, get-node, search)
- **Configuration Objects**: 10+ typed config classes
- **External Dependencies**: None required for MCP (FastMCP is pure Python)
- **Prior Learnings**: Clean Architecture patterns are well-established

---

## How It Currently Works

### Existing CLI Entry Points

| Entry Point | Type | Location | Purpose |
|------------|------|----------|---------|
| `fs2 tree` | CLI | `src/fs2/cli/tree.py` | Display code structure as hierarchical tree |
| `fs2 get-node` | CLI | `src/fs2/cli/get_node.py` | Retrieve single node by ID as JSON |
| `fs2 search` | CLI | `src/fs2/cli/search.py` | Search code graph with text/regex/semantic |
| `fs2 scan` | CLI | `src/fs2/cli/scan.py` | Build code graph from source files |

### Core Services (Reusable for MCP)

```python
# TreeService - tree operations
service = TreeService(config=config, graph_store=graph_store)
tree_nodes = service.build_tree(pattern="Calculator", max_depth=2)

# GetNodeService - node retrieval
service = GetNodeService(config=config, graph_store=graph_store)
node = service.get_node("file:src/main.py")

# SearchService - search operations
service = SearchService(graph_store=graph_store, embedding_adapter=adapter)
results = await service.search(QuerySpec(pattern="auth", mode=SearchMode.AUTO))
```

### Data Flow
```
[Graph File] --> GraphStore.load() --> [In-Memory Graph]
                                              |
                                              v
[MCP Tool Request] --> Service Layer --> [CodeNode/SearchResult]
                                              |
                                              v
                                       [JSON Response to Agent]
```

---

## Architecture & Design for MCP

### Proposed Component Map

```
src/fs2/
├── cli/
│   ├── main.py              # Add 'mcp' command
│   └── mcp.py               # NEW: MCP command entry point
├── core/
│   └── mcp/                  # NEW: MCP server module
│       ├── __init__.py
│       ├── server.py         # FastMCP server + tool definitions
│       ├── tools/            # Tool implementations
│       │   ├── tree.py
│       │   ├── get_node.py
│       │   └── search.py
│       └── models.py         # Pydantic models for tool I/O
```

### FastMCP Integration Pattern

Based on Perplexity research and existing codebase patterns:

```python
# src/fs2/core/mcp/server.py
import sys
import logging
from fastmcp import FastMCP
from fs2.config.service import FS2ConfigurationService
from fs2.core.repos import NetworkXGraphStore

# CRITICAL: Redirect all logging to stderr (MCP protocol requirement)
logging.basicConfig(stream=sys.stderr, level=logging.INFO)

mcp = FastMCP(
    name="fs2",
    description="Code intelligence server for exploring indexed codebases"
)

# Lazy-load services on first tool call
_config = None
_graph_store = None

def _get_services():
    """Lazy initialization of services."""
    global _config, _graph_store
    if _config is None:
        _config = FS2ConfigurationService()
        _graph_store = NetworkXGraphStore(_config)
        # Load graph
        graph_config = _config.require(GraphConfig)
        _graph_store.load(Path(graph_config.graph_path))
    return _config, _graph_store
```

### Tool Design Following Best Practices

Based on MCP tool description research, each tool should include:

1. **Concise 1-2 sentence description** front-loading critical info
2. **Prerequisites** (e.g., "requires running `fs2 scan` first")
3. **Return type description** (what the agent gets back)
4. **Workflow hints** (when to use this vs. alternatives)

---

## MCP Tool Specifications

### Tool 1: `tree`

**Purpose**: Display code structure as hierarchical tree with filtering and depth limiting.

**Best Practice Tool Description**:
```python
@mcp.tool(
    annotations={
        "title": "Code Tree",
        "readOnlyHint": True,
        "destructiveHint": False,
        "openWorldHint": False,
    }
)
def tree(
    pattern: str = ".",
    max_depth: int = 0,
    detail: Literal["min", "max"] = "min",
) -> list[dict]:
    """Display hierarchical code structure from the indexed graph.

    Filters nodes by path, name, glob pattern, or exact node_id. Returns a
    tree of code elements (files, classes, functions) useful for understanding
    codebase organization before diving into specific code.

    Prerequisites: Run `fs2 scan` first to index the codebase.

    Use this tool FIRST when exploring an unfamiliar codebase to understand
    its structure before searching for specific code.

    Args:
        pattern: Filter pattern - "." for all, path prefix, glob (*.py),
                 or exact node_id. Supports substring matching.
        max_depth: Maximum tree depth (0 = unlimited). Use 1-2 for overview.
        detail: "min" for compact output, "max" includes node_ids for
                subsequent get_node calls.

    Returns:
        List of tree nodes with children, each containing:
        - node_id: Unique identifier (use with get_node for full content)
        - name: Element name
        - category: file|type|callable|section|block
        - start_line/end_line: Location in source file
        - children: Nested child nodes

    Example patterns:
        "src/core"     -> All nodes under src/core/
        "Calculator"   -> All nodes containing "Calculator"
        "*.py"         -> All Python files
        "callable:*"   -> All functions/methods
    """
```

### Tool 2: `get_node`

**Purpose**: Retrieve complete node data by ID, optionally saving to file.

**Best Practice Tool Description**:
```python
@mcp.tool(
    annotations={
        "title": "Get Node",
        "readOnlyHint": True,
        "destructiveHint": False,
        "openWorldHint": False,
    }
)
def get_node(
    node_id: str,
    save_to_file: str | None = None,
) -> dict | None:
    """Retrieve complete code node data by its unique identifier.

    Returns full source content and metadata for a specific code element.
    Use after `tree` to drill into specific nodes identified by node_id.

    Prerequisites: Run `fs2 scan` first. Get node_ids from `tree` with
    detail="max" or from `search` results.

    Args:
        node_id: Exact node identifier in format "{category}:{path}:{name}"
                 Examples: "file:src/main.py", "callable:src/main.py:Calculator.add"
        save_to_file: Optional path to write JSON output. When specified,
                      returns confirmation instead of full content.

    Returns:
        Complete CodeNode dict with:
        - content: Full source code text
        - signature: Declaration line(s)
        - smart_content: AI-generated summary (if indexed with --smart)
        - start_line/end_line: Exact location
        - language: Source language
        - parent_node_id: Parent in hierarchy (for navigation)

        Returns None if node_id not found.

    Workflow:
        1. Use `tree` to find interesting node_ids
        2. Use `get_node` to retrieve full content
        3. Or use `search` to find nodes by content, then `get_node`
    """
```

### Tool 3: `search`

**Purpose**: Search code graph using text, regex, or semantic matching.

**Best Practice Tool Description**:
```python
@mcp.tool(
    annotations={
        "title": "Search Code",
        "readOnlyHint": True,
        "destructiveHint": False,
        "openWorldHint": False,
    }
)
async def search(
    pattern: str,
    mode: Literal["auto", "text", "regex", "semantic"] = "auto",
    limit: int = 20,
    offset: int = 0,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    detail: Literal["min", "max"] = "min",
) -> dict:
    """Search the indexed code graph for matching code elements.

    Supports text (substring), regex (pattern), and semantic (meaning-based)
    search. Auto mode detects regex patterns automatically and prefers
    semantic search when embeddings are available.

    Prerequisites: Run `fs2 scan` first. For semantic search, run
    `fs2 scan --embed` to generate embeddings.

    Use this when you know WHAT you're looking for (function name, error
    message, concept). Use `tree` first when exploring structure.

    Args:
        pattern: Search query. For text/regex: literal or pattern.
                 For semantic: natural language description.
        mode: "auto" (recommended), "text", "regex", or "semantic".
              Auto uses regex if pattern has metacharacters, else semantic.
        limit: Max results (default 20). Increase for comprehensive search.
        offset: Skip first N results (for pagination).
        include: Keep only results matching these patterns (path filters).
                 Multiple patterns use OR logic. Example: ["src/", "lib/"]
        exclude: Remove results matching these patterns.
                 Example: ["test", "_test.py"]
        detail: "min" (9 fields) or "max" (13 fields with full content).

    Returns:
        Envelope with:
        - meta: {total, showing, pagination, folders}
        - results: List of matches with node_id, score, snippet, smart_content

        Results sorted by relevance score (descending).

    Search mode guidance:
        - "error handling" -> semantic (conceptual search)
        - "def test_*" -> regex (pattern matching)
        - "calculateTotal" -> text (exact match)
    """
```

---

## STDIO Transport & Logging (Critical)

### The Fundamental Rule

**NEVER write to stdout except JSON-RPC messages.** Any other output corrupts the MCP protocol.

### Implementation Pattern

```python
# src/fs2/cli/mcp.py
import sys
import logging

def mcp_command(
    config_file: str | None = None,
):
    """Start MCP server for AI agent integration.

    Runs the fs2 MCP server using STDIO transport. Connect with
    Claude Desktop or other MCP clients.
    """
    # CRITICAL: Redirect ALL logging to stderr
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(name)s - %(levelname)s - %(message)s"
    )

    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Import after logging configured
    from fs2.core.mcp.server import mcp

    # Optional: Override config file
    if config_file:
        import os
        os.environ["FS2_CONFIG_FILE"] = config_file

    # Run with STDIO transport (FastMCP default)
    mcp.run()
```

### Context Logging for User Visibility

Use FastMCP's Context for agent-visible progress:

```python
from fastmcp import Context

@mcp.tool()
async def search(pattern: str, ctx: Context) -> dict:
    """Search the code graph."""
    await ctx.info(f"Searching for: {pattern}")

    # Long operation
    results = await service.search(spec)

    await ctx.info(f"Found {len(results)} matches")
    return envelope
```

---

## Configuration Integration

### MCP-Specific Config Object

```python
# src/fs2/config/objects.py (addition)

class MCPConfig(BaseModel):
    """Configuration for MCP server.

    Loaded from YAML or environment variables.
    Path: mcp (e.g., FS2_MCP__DEFAULT_LIMIT)

    YAML example:
        ```yaml
        mcp:
          graph_path: ".fs2/graph.pickle"
          default_limit: 20
          log_level: INFO
        ```
    """

    __config_path__: ClassVar[str] = "mcp"

    graph_path: str = ".fs2/graph.pickle"
    default_limit: int = 20
    log_level: str = "INFO"
```

### Config File Parameter Handling

```python
# CLI command with --config option
@app.command(name="mcp")
def mcp(
    config: Annotated[
        Path | None,
        typer.Option(
            "--config", "-c",
            help="Path to config file (default: .fs2/config.yaml)"
        ),
    ] = None,
) -> None:
    """Start MCP server for AI agent integration."""
    # Override default config path if specified
    if config:
        os.environ["FS2_CONFIG_DIR"] = str(config.parent)

    from fs2.core.mcp.server import run_server
    run_server()
```

---

## Tool Annotations (Agent Hints)

### Standard MCP Annotations

```python
from fastmcp import ToolAnnotations

@mcp.tool(
    annotations=ToolAnnotations(
        title="Search Code",           # UI display name
        readOnlyHint=True,            # No side effects
        destructiveHint=False,        # Safe to call
        idempotentHint=True,          # Same result on repeat
        openWorldHint=False,          # Local system only
    )
)
```

### What Each Annotation Communicates

| Annotation | Value | Agent Behavior |
|------------|-------|----------------|
| `readOnlyHint=True` | All fs2 tools | Agent knows these are safe to call freely |
| `destructiveHint=False` | All fs2 tools | No confirmation needed |
| `idempotentHint=True` | All fs2 tools | Can retry on failure |
| `openWorldHint=False` | All fs2 tools | No external API calls |

---

## Dependencies & Integration

### Required Dependencies

```toml
# pyproject.toml addition
dependencies = [
    # ... existing ...
    "fastmcp>=0.4.0",  # MCP server framework
]
```

### FastMCP Version Considerations

- FastMCP 0.4+ has stable API
- Uses pydantic for schema generation (already in fs2)
- Handles STDIO transport correctly
- Supports async tools (needed for SearchService)

---

## Quality & Testing

### Test Strategy for MCP Tools

```python
# tests/mcp/test_tools.py
import pytest
from fastmcp.testing import Client
from fs2.core.mcp.server import mcp

@pytest.fixture
def mcp_client():
    """In-memory MCP client for testing."""
    return Client(mcp)

async def test_tree_tool(mcp_client, indexed_graph):
    """Test tree tool returns expected structure."""
    result = await mcp_client.call_tool("tree", pattern="src/")
    assert isinstance(result, list)
    assert all("node_id" in node for node in result)

async def test_search_tool(mcp_client, indexed_graph):
    """Test search returns envelope with results."""
    result = await mcp_client.call_tool("search", pattern="Calculator")
    assert "meta" in result
    assert "results" in result
```

### MCP Protocol Compliance Tests

```python
async def test_no_stdout_pollution(capsys, mcp_client):
    """Verify tools don't write to stdout."""
    await mcp_client.call_tool("tree", pattern=".")
    captured = capsys.readouterr()
    assert captured.out == ""  # Only stderr allowed
```

---

## Modification Considerations

### Safe to Modify
- **CLI main.py**: Add `mcp` command registration
- **New mcp/ module**: Entirely new code
- **pyproject.toml**: Add fastmcp dependency

### Modify with Caution
- **Config objects**: Adding MCPConfig is safe, but ensure __config_path__ is unique
- **Services**: Should NOT be modified - compose them in MCP tools

### Danger Zones
- **Existing CLI commands**: Don't modify tree.py, get_node.py, search.py
- **Service layer internals**: MCP tools should only call public methods

---

## Prior Learnings (Institutional Knowledge)

### PL-01: stderr for JSON Output Pattern
**Source**: `src/fs2/cli/get_node.py`
**Type**: Pattern/Convention
**Original**: Console(stderr=True) for errors, raw print() for JSON
**Relevance**: Same pattern needed for MCP - but in MCP, NO stdout at all except JSON-RPC

### PL-02: Lazy Graph Loading
**Source**: TreeService, GetNodeService
**Type**: Performance Pattern
**Original**: `_ensure_loaded()` pattern with `_loaded` flag
**Relevance**: MCP server should use same lazy loading to avoid startup cost

### PL-03: Clean Architecture Service Composition
**Source**: All CLI commands
**Type**: Architecture Pattern
**Original**:
```python
config = FS2ConfigurationService()
graph_store = NetworkXGraphStore(config)
service = TreeService(config=config, graph_store=graph_store)
```
**Relevance**: MCP tools should compose services identically

---

## Critical Discoveries

### Critical Finding 01: STDIO Transport Requires stderr-Only Logging
**Impact**: Critical
**Source**: Perplexity research
**What**: Any stdout output breaks MCP protocol
**Required Action**: All logging MUST use stderr; all print() calls forbidden in MCP code

### Critical Finding 02: Tool Descriptions Drive Agent Selection
**Impact**: Critical
**Source**: Perplexity research
**What**: Agents choose tools based on descriptions BEFORE examining schemas
**Required Action**: Write descriptions for agents, not humans. Include prerequisites and workflow hints.

### Critical Finding 03: Existing Services Are MCP-Ready
**Impact**: High (Positive)
**Source**: Codebase analysis
**What**: TreeService, GetNodeService, SearchService have clean interfaces
**Required Action**: Compose services in MCP tools, don't duplicate logic

---

## Recommendations

### If Implementing This System

1. **Create new `src/fs2/core/mcp/` module** - don't pollute existing code
2. **Use lazy service initialization** - avoid startup cost when server starts
3. **Write agent-oriented tool descriptions** - front-load critical info, include prerequisites
4. **Add fastmcp to dependencies** - it's well-maintained and handles STDIO correctly
5. **Configure logging before imports** - ensure stderr redirection happens first

### Suggested File Structure

```
src/fs2/
├── cli/
│   ├── main.py              # Add: app.command(name="mcp")(mcp_command)
│   └── mcp.py               # NEW: CLI entry point with config handling
├── core/
│   └── mcp/
│       ├── __init__.py
│       ├── server.py        # FastMCP instance + run_server()
│       ├── tools.py         # Tool definitions with descriptions
│       └── dependencies.py  # Lazy service initialization
└── config/
    └── objects.py           # Add: MCPConfig class
```

### Implementation Order

1. Add `fastmcp` to pyproject.toml
2. Create `src/fs2/core/mcp/server.py` with FastMCP instance
3. Implement `tree` tool (simplest, tests composition pattern)
4. Implement `get_node` tool (tests file output option)
5. Implement `search` tool (tests async, most complex)
6. Add CLI entry point `fs2 mcp`
7. Add MCPConfig for optional configuration
8. Write tests using fastmcp.testing.Client

---

## External Research Opportunities

### Research Opportunity 1: FastMCP Advanced Patterns

**Why Needed**: Determine optimal patterns for:
- Error handling and agent-friendly error messages
- Progress reporting for long operations
- Resource registration (if we want to expose raw graph access)

**Ready-to-use prompt:**
```
/deepresearch "FastMCP advanced patterns for production MCP servers:
1. Error handling that helps agents recover
2. Progress reporting for operations >5 seconds
3. Resource vs Tool tradeoffs
4. Testing strategies with fastmcp.testing
Context: Python 3.12, fs2 code intelligence tool, existing async services"
```

### Research Opportunity 2: Claude Desktop MCP Integration

**Why Needed**: Understand exact configuration format for Claude Desktop clients

**Ready-to-use prompt:**
```
/deepresearch "Claude Desktop MCP server configuration 2025:
1. Exact JSON config format for STDIO servers
2. Environment variable passing
3. Working directory handling
4. Debugging connection issues
Context: Python MCP server using FastMCP, started via 'fs2 mcp' command"
```

---

## Next Steps

- Run `/plan-1b-specify "MCP server for fs2"` to create formal specification
- Or `/plan-3-architect` to proceed directly to implementation planning

---

**Research Complete**: 2025-12-26
**Report Location**: docs/plans/011-mcp/research-dossier.md
