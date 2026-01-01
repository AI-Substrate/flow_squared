# MCP Server Implementation Plan

**Plan Version**: 1.0.0
**Created**: 2025-12-26
**Spec**: [./mcp-spec.md](./mcp-spec.md)
**Status**: READY

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Technical Context](#technical-context)
3. [Critical Research Findings](#critical-research-findings)
4. [Tool Specifications](#tool-specifications)
5. [Testing Philosophy](#testing-philosophy)
6. [Implementation Phases](#implementation-phases)
   - [Phase 1: Core Infrastructure](#phase-1-core-infrastructure)
   - [Phase 2: Tree Tool Implementation](#phase-2-tree-tool-implementation)
   - [Phase 3: Get-Node Tool Implementation](#phase-3-get-node-tool-implementation)
   - [Phase 4: Search Tool Implementation](#phase-4-search-tool-implementation)
   - [Phase 5: CLI Integration](#phase-5-cli-integration)
   - [Phase 6: Documentation](#phase-6-documentation)
7. [Cross-Cutting Concerns](#cross-cutting-concerns)
8. [Complexity Tracking](#complexity-tracking)
9. [Progress Tracking](#progress-tracking)
10. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

**Problem**: fs2's code intelligence capabilities (tree navigation, node retrieval, semantic search) are only accessible via CLI. AI agents like Claude must rely on text-based grep/glob patterns, losing the structured understanding of codebase architecture.

**Solution Approach**:
- Expose existing services (TreeService, GetNodeService, SearchService) via Model Context Protocol (MCP)
- Use FastMCP framework for Python-native, decorator-based tool definitions
- Implement STDIO transport with strict stdout/stderr separation
- Write agent-optimized tool descriptions with prerequisites and workflow hints

**Expected Outcomes**:
- AI agents can programmatically explore indexed codebases
- Structured JSON responses replace text parsing
- Semantic search enables concept-based code discovery
- Single `fs2 mcp` command starts the server

**Success Metrics**:
- All 15 acceptance criteria pass
- Protocol compliance (no stdout pollution)
- Tool descriptions enable correct agent tool selection

---

## Technical Context

### Current System State

Existing services are MCP-ready with clean dependency injection:

```python
# Canonical service composition pattern (from CLI commands)
config = FS2ConfigurationService()
graph_store = NetworkXGraphStore(config)
service = TreeService(config=config, graph_store=graph_store)
```

### Integration Requirements

| Component | Requirement |
|-----------|-------------|
| FastMCP | Add to pyproject.toml dependencies |
| Services | Compose in MCP tools (no modifications) |
| Graph Store | Lazy load on first tool call |
| Logging | Redirect ALL to stderr before imports |

### Constraints and Limitations

1. **STDIO Protocol**: stdout is 100% reserved for JSON-RPC messages
2. **No CLI Modifications**: tree.py, get_node.py, search.py are read-only
3. **Async Handling**: SearchService is async; tree/get_node are sync
4. **Local Only**: STDIO transport, no HTTP or remote access

### Assumptions

1. Graph file exists when MCP server starts (user ran `fs2 scan`)
2. FastMCP handles JSON-RPC protocol correctly
3. Services have stable public interfaces
4. Python 3.12+ environment

---

## Critical Research Findings

Findings are ordered by impact. All discoveries include code references and affected phases.

### Critical Discovery 01: STDIO Protocol Requires stderr-Only Logging Before First Import

**Impact**: Critical
**Sources**: [Research Dossier, I1-03, R1-01, R1-07]

**Problem**: Any stdout output before MCP server starts corrupts the JSON-RPC protocol. Python's logging module and Rich library output to stdout by default.

**Root Cause**:
- `src/fs2/cli/tree.py` uses `Console()` for Rich output
- Services use `logging.getLogger(__name__)` which defaults to stdout
- FastMCP's `mcp.run()` consumes stdin/stdout exclusively

**Solution**:
```python
# In src/fs2/cli/mcp.py - MUST be first lines
import sys
import logging
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logging.getLogger("fs2").setLevel(logging.WARNING)  # Suppress DEBUG/INFO

# ONLY THEN import MCP server
from fs2.core.mcp.server import mcp
```

**Action Required**: Configure logging to stderr BEFORE any service imports.

**Affects Phases**: Phase 1 (Critical foundation for all subsequent phases)

---

### Critical Discovery 02: Tool Descriptions Drive Agent Tool Selection

**Impact**: Critical
**Sources**: [Research Dossier, I1-04]

**Problem**: Agents choose tools based on descriptions BEFORE examining parameter schemas. Naive descriptions like "Retrieve a code node" don't tell agents WHEN to use the tool.

**Solution**: Each tool description MUST include:
1. 1-2 sentence hook (what it does)
2. Prerequisites ("Run `fs2 scan` first")
3. Workflow hints ("Use after tree() to drill into specific nodes")
4. Return format description

**Example**:
```python
"""Retrieve complete code node data by its unique identifier.

Returns full source content and metadata for a specific code element.
Use after `tree` to drill into specific nodes identified by node_id.

Prerequisites: Run `fs2 scan` first. Get node_ids from `tree` with
detail="max" or from `search` results.
"""
```

**Action Required**: Copy tool descriptions verbatim from research-dossier.md.

**Affects Phases**: Phase 2, 3, 4 (Tool implementations)

---

### High Discovery 03: GraphStore Requires ConfigurationService Injection

**Impact**: High
**Sources**: [Research Dossier, I1-02, R1-04]

**Problem**: `NetworkXGraphStore.__init__(config: ConfigurationService)` expects ConfigurationService, NOT GraphConfig. The service extracts its own config via `config.require(GraphConfig)`.

**Solution**:
```python
# CORRECT - Follow CLI pattern exactly
config = FS2ConfigurationService()
graph_store = NetworkXGraphStore(config)  # Service extracts GraphConfig

# WRONG - Will fail
graph_config = GraphConfig(graph_path=".fs2/graph.pickle")
graph_store = NetworkXGraphStore(graph_config)  # TypeError!
```

**Action Required**: Study `src/fs2/cli/tree.py` lines 92-104 as canonical composition pattern.

**Affects Phases**: Phase 1 (Dependencies module)

---

### High Discovery 04: Async/Sync Pattern Separation

**Impact**: High
**Sources**: [Research Dossier, I1-05, R1-02]

**Problem**: TreeService and GetNodeService are synchronous. SearchService.search() is async. Mixing patterns incorrectly causes hangs or event loop conflicts.

**Solution**:
- `tree` tool: sync function (`def tree(...)`)
- `get_node` tool: sync function (`def get_node(...)`)
- `search` tool: async function (`async def search(...)` with `await service.search()`)

**Action Required**: Verify FastMCP supports both sync and async tool handlers.

**Affects Phases**: Phase 2, 3 (sync), Phase 4 (async)

---

### High Discovery 05: Error Translation at MCP Boundary

**Impact**: High
**Sources**: [Research Dossier, R1-03]

**Problem**: fs2 exceptions include CLI-specific fix instructions (e.g., "Run `fs2 scan` first"). These aren't actionable for MCP agents.

**Solution**: Create error translation layer:
```python
def translate_error(exc: Exception) -> dict:
    if isinstance(exc, GraphNotFoundError):
        return {
            "error": {
                "type": "GraphNotFoundError",
                "message": "Graph not found",
                "action": "Call fs2 scan tool first"  # Agent-friendly
            }
        }
    # ... other exception types
```

**Action Required**: Map all fs2 exceptions to agent-friendly responses.

**Affects Phases**: Phase 1 (Error handling module), Phase 2-4 (Tool implementations)

---

### High Discovery 06: Modification Restrictions on CLI Commands

**Impact**: High
**Sources**: [Research Dossier, R1-08]

**Problem**: Requirements state "Don't modify tree.py, get_node.py, search.py" to prevent breaking CLI users. MCP must use same services but with different composition.

**Solution**: Create separate MCP module `src/fs2/core/mcp/` that:
1. Imports services (not CLI commands)
2. Composes with MCP-specific dependencies (no console)
3. Translates results to agent-friendly format

**Rollback Strategy**: If MCP breaks, delete `src/fs2/core/mcp/` and remove CLI entry point. CLI remains untouched.

**Affects Phases**: All phases (architectural constraint)

---

### High Discovery 07: File Creation Order Depends on Import Chain

**Impact**: High
**Sources**: [I1-08]

**Problem**: FastMCP's decorator syntax requires the mcp instance to exist before tools are defined. Wrong file creation order causes circular import errors.

**Solution**: Create files in this exact order:
1. `src/fs2/core/mcp/__init__.py` (empty)
2. `src/fs2/core/mcp/dependencies.py` (lazy initialization, no mcp import)
3. `src/fs2/core/mcp/server.py` (creates mcp instance, defines tools)
4. `src/fs2/cli/mcp.py` (imports from server)
5. Update `src/fs2/cli/main.py` (register command)

**Affects Phases**: Phase 1 (File structure)

---

### Medium Discovery 08: Test Fixtures Should Use Existing Fakes

**Impact**: Medium
**Sources**: [Research Dossier, I1-07, R1-05]

**Problem**: fs2 uses Fakes (real ABC implementations with controlled data) not mocks. MCP tests should follow this pattern.

**Solution**:
- Use `FakeGraphStore` loaded with fixture data
- Use `FakeEmbeddingAdapter` for search tests
- Use `fastmcp.testing.Client` for in-memory tool testing

**Action Required**: Create `tests/mcp/` directory following existing test patterns.

**Affects Phases**: Phase 2-5 (Testing)

---

## Tool Specifications

This section defines the complete MCP tool specifications including annotations, descriptions, schemas, and agent guidance. These specifications are derived from MCP protocol best practices research (2025-12-26).

### MCP Tool Annotations Reference

The MCP protocol defines 5 standard annotations that help clients understand tool behavior:

| Annotation | Type | Default | Description |
|------------|------|---------|-------------|
| `title` | string | - | Human-readable title for UI display |
| `readOnlyHint` | boolean | `false` | If `true`, tool does not modify its environment |
| `destructiveHint` | boolean | `true` | If `true`, tool may perform destructive updates (only meaningful when `readOnlyHint` is `false`) |
| `idempotentHint` | boolean | `false` | If `true`, repeated calls with same args have no additional effect (only meaningful when `readOnlyHint` is `false`) |
| `openWorldHint` | boolean | `true` | If `true`, tool interacts with external/unpredictable entities |

**Important**: Annotations are advisory hints, not enforcement mechanisms. They should never be used for security-critical decisions.

### Tool Description Best Practices

Per MCP research findings, effective tool descriptions must:

1. **Front-load important information** - First sentence answers "What does this tool do?"
2. **State prerequisites** - What must be done before calling this tool
3. **Include workflow hints** - How this tool relates to other tools in a sequence
4. **Describe return format** - Field names, types, and ordering of results
5. **Document error handling** - Common error conditions and what they mean
6. **Use negative statements** - State what the tool does NOT do to avoid confusion

---

### Tool: `tree`

**Purpose**: Navigate and explore the hierarchical structure of indexed codebases.

#### Annotations

```python
annotations = {
    "title": "Code Tree Explorer",
    "readOnlyHint": True,      # Only reads graph, no modifications
    "destructiveHint": False,  # N/A for read-only
    "idempotentHint": True,    # Same args always return same result
    "openWorldHint": False     # Operates on closed, local graph
}
```

#### Description (Agent-Optimized)

```python
description = """Navigate the hierarchical structure of an indexed codebase.

Returns a tree of code elements (files, classes, functions) with their relationships.
Use this tool FIRST to explore what exists in a codebase before drilling into specifics.

PREREQUISITES:
- Codebase must be indexed with `fs2 scan` first
- Graph file must exist at .fs2/graph.pickle

WORKFLOW:
1. Call tree(pattern=".") to see entire codebase structure
2. Call tree(pattern="ClassName") to filter to specific elements
3. Use node_ids from results with get_node() to retrieve full source code

RETURNS: List of tree nodes, each containing:
- node_id (str): Unique identifier for get_node() lookup
- name (str): Human-readable element name
- category (str): Element type (file, class, callable, etc.)
- start_line, end_line (int): Source location
- children (list): Nested child elements (if max_depth allows)

DOES NOT: Retrieve full source code (use get_node for that).
DOES NOT: Search by content or concept (use search for that).
"""
```

#### Input Schema

```python
@mcp.tool(...)
def tree(
    pattern: Annotated[
        str,
        Field(
            description="Glob pattern to filter nodes. Use '.' for all nodes, "
                       "or a pattern like 'Calculator*' to filter by name.",
            examples=[".", "Calculator", "test_*.py", "src/**"]
        )
    ] = ".",
    max_depth: Annotated[
        int | None,
        Field(
            description="Maximum depth of tree traversal. "
                       "1 = root nodes only, None = unlimited depth.",
            ge=1,
            le=100
        )
    ] = None,
    detail: Annotated[
        Literal["min", "max"],
        Field(
            description="Detail level: 'min' for compact output (node_id, name, category), "
                       "'max' for full metadata including signatures and line numbers."
        )
    ] = "min"
) -> list[dict]:
```

#### Output Schema

```python
# Returns list of TreeNode dicts:
{
    "node_id": str,        # e.g., "class:src/calc.py:Calculator"
    "name": str,           # e.g., "Calculator"
    "category": str,       # e.g., "class", "callable", "file"
    "start_line": int,     # 1-indexed
    "end_line": int,       # 1-indexed
    "children": list[dict] # Nested TreeNode dicts (if depth allows)
    # max detail adds:
    "signature": str | None,
    "smart_content": str | None  # AI-generated summary
}
```

---

### Tool: `get_node`

**Purpose**: Retrieve complete source code and metadata for a specific code element.

#### Annotations

```python
annotations = {
    "title": "Get Code Node",
    "readOnlyHint": True,       # Only reads graph (except save_to_file)
    "destructiveHint": False,   # N/A for read-only
    "idempotentHint": True,     # Same node_id always returns same data
    "openWorldHint": False      # Operates on closed, local graph
}
```

**Note**: When `save_to_file` is used, `readOnlyHint` effectively becomes `False` since the tool writes to the filesystem.

#### Description (Agent-Optimized)

```python
description = """Retrieve complete source code and metadata for a specific code element.

Returns the full CodeNode data including source content, signature, and AI summary.
Use AFTER tree() or search() to get the complete source code for a node.

PREREQUISITES:
- Codebase must be indexed with `fs2 scan` first
- You need a valid node_id (get these from tree() or search() results)

WORKFLOW:
1. Get node_ids from tree() or search() results (node_id always present in both detail levels)
2. Call get_node(node_id="...") to retrieve full source
3. Optionally save to file with save_to_file parameter

RETURNS: CodeNode dict containing:
- node_id (str): The requested identifier
- content (str): FULL source code of the element
- signature (str | None): Function/class signature
- smart_content (str | None): AI-generated summary
- start_line, end_line (int): Source location
- category (str): Element type
- file_path (str): Path to source file

Returns None if node_id does not exist (NOT an error).

DOES NOT: Accept partial node_ids or search patterns.
DOES NOT: Return multiple nodes (use tree or search for that).
"""
```

#### Input Schema

```python
@mcp.tool(...)
def get_node(
    node_id: Annotated[
        str,
        Field(
            description="Unique node identifier from tree() or search() results. "
                       "Format: 'category:path:name' (e.g., 'class:src/calc.py:Calculator')",
            examples=[
                "file:src/calculator.py",
                "class:src/calculator.py:Calculator",
                "callable:src/calculator.py:Calculator.add"
            ]
        )
    ],
    save_to_file: Annotated[
        str | None,
        Field(
            description="Optional file path to save the node as JSON. "
                       "If provided, writes JSON to this path and returns confirmation."
        )
    ] = None
) -> dict | None:
```

#### Output Schema

```python
# Returns CodeNode dict or None:
{
    "node_id": str,
    "name": str,
    "category": str,
    "file_path": str,
    "start_line": int,
    "end_line": int,
    "content": str,           # FULL source code
    "signature": str | None,
    "smart_content": str | None,
    "docstring": str | None,
    "parent_id": str | None
}
# OR None if node_id not found
```

---

### Tool: `search`

**Purpose**: Find code elements by text, regex pattern, or semantic concept.

#### Annotations

```python
annotations = {
    "title": "Code Search",
    "readOnlyHint": True,      # Only reads graph and embeddings
    "destructiveHint": False,  # N/A for read-only
    "idempotentHint": True,    # Same query returns same results
    "openWorldHint": False     # Operates on closed, local graph
}
```

#### Description (Agent-Optimized)

```python
description = """Search for code elements by text pattern, regex, or semantic meaning.

Returns ranked search results with relevance scores and context snippets.
Use to find code by WHAT IT DOES rather than WHERE IT IS.

PREREQUISITES:
- Codebase must be indexed with `fs2 scan` first
- For semantic mode: embeddings must exist (run `fs2 scan --embed`)

SEARCH MODES:
- text: Substring matching in node_id, content, or smart_content
- regex: Regular expression matching (e.g., "def test_.*")
- semantic: Conceptual similarity using embeddings (e.g., "error handling logic")

WORKFLOW:
1. Use search(pattern="...", mode="text") for exact string matching
2. Use search(pattern="...", mode="semantic") for concept-based discovery
3. Use include/exclude to scope results to specific paths
4. Use node_ids from results with get_node() to retrieve full source

RETURNS: Search envelope dict containing:
- meta: {total_count, returned_count, mode, pattern}
- results: List of SearchResult dicts:
  - node_id (str): For get_node() lookup
  - score (float): Relevance 0.0-1.0, higher is better
  - snippet (str): ~50 char context around match
  - match_field (str): Which field matched (content, node_id, smart_content)
  - smart_content (str | None): AI summary of the node

DOES NOT: Return full source code (use get_node for that).
DOES NOT: Modify the codebase or index.
"""
```

#### Input Schema

```python
@mcp.tool(...)
async def search(
    pattern: Annotated[
        str,
        Field(
            description="Search pattern. For text/regex: string to match. "
                       "For semantic: natural language concept description.",
            examples=[
                "ConfigService",
                "def test_.*",
                "error handling and exception logging"
            ]
        )
    ],
    mode: Annotated[
        Literal["text", "regex", "semantic", "auto"],
        Field(
            description="Search mode: 'text' for substring, 'regex' for patterns, "
                       "'semantic' for concept matching, 'auto' to detect."
        )
    ] = "auto",
    limit: Annotated[
        int,
        Field(
            description="Maximum number of results to return.",
            ge=1,
            le=100
        )
    ] = 20,
    include: Annotated[
        list[str] | None,
        Field(
            description="Glob patterns for paths to include (e.g., ['src/**', '*.py']). "
                       "If None, searches all indexed paths."
        )
    ] = None,
    exclude: Annotated[
        list[str] | None,
        Field(
            description="Glob patterns for paths to exclude (e.g., ['test/**', '*_test.py']). "
                       "Exclusions are applied after inclusions."
        )
    ] = None,
    detail: Annotated[
        Literal["min", "max"],
        Field(
            description="Detail level: 'min' for compact results (9 fields), "
                       "'max' for full results including content (13 fields)."
        )
    ] = "min"
) -> dict:
```

#### Output Schema

```python
# Returns search envelope:
{
    "meta": {
        "total_count": int,      # Total matches found
        "returned_count": int,   # Matches returned (respects limit)
        "mode": str,             # Actual mode used
        "pattern": str           # Original pattern
    },
    "results": [
        {
            # Min fields (9):
            "node_id": str,
            "start_line": int,
            "end_line": int,
            "match_start_line": int,
            "match_end_line": int,
            "smart_content": str | None,
            "snippet": str,
            "score": float,      # 0.0-1.0
            "match_field": str,  # "content", "node_id", "smart_content", "embedding"
            # Max fields (add 4 more):
            "content": str | None,
            "matched_lines": list[int] | None,  # text/regex only
            "chunk_offset": tuple[int, int] | None,  # semantic only
            "embedding_chunk_index": int | None  # semantic only
        }
    ]
}
```

---

### Error Response Format

All tools return agent-friendly errors in this format:

```python
{
    "error": {
        "type": str,          # Error class name (e.g., "GraphNotFoundError")
        "message": str,       # Human-readable description
        "action": str | None  # Suggested remediation for the agent
    }
}
```

**Common Errors**:

| Error Type | Message | Action |
|------------|---------|--------|
| `GraphNotFoundError` | "Graph file not found at .fs2/graph.pickle" | "Run `fs2 scan` to index the codebase first" |
| `EmbeddingsNotFoundError` | "No embeddings found for semantic search" | "Run `fs2 scan --embed` to generate embeddings" |
| `InvalidPatternError` | "Invalid regex pattern: [details]" | "Check regex syntax and try again" |
| `NodeNotFoundError` | "Node not found: [node_id]" | "Verify node_id exists using tree() or search()" |

---

## Testing Philosophy

### Testing Approach

**Selected Approach**: Full TDD
**Rationale**: New module with protocol compliance requirements; tests verify correct behavior before implementation

### Test-Driven Development

All phases follow RED-GREEN-REFACTOR:
1. Write comprehensive tests (RED - tests fail)
2. Implement minimal code (GREEN - tests pass)
3. Refactor for quality (REFACTOR - maintain passing tests)

### Focus Areas

- Protocol compliance (stdout/stderr separation)
- Tool schema generation and validation
- Service composition (TreeService, GetNodeService, SearchService integration)
- Error handling and agent-friendly messages
- CLI entry point functionality

### Excluded

- Internal service logic (already tested in existing service tests)
- FastMCP framework internals (trust the library)

### Test Documentation

Every test must include:
```python
"""
Purpose: [what truth this test proves]
Quality Contribution: [how this prevents bugs]
Acceptance Criteria: [measurable assertions]
"""
```

### Mock Usage

**Policy**: Targeted mocks (per spec)

- **Use existing Fakes**: FakeGraphStore, FakeEmbeddingAdapter, FakeConfigurationService
- **Targeted mocks allowed for**: MCP framework transport, STDIO capture
- **Avoid mocking**: Service internals, domain models

---

## Implementation Phases

### Phase 1: Core Infrastructure

**Objective**: Create foundational MCP server module with lazy service initialization and protocol-compliant logging.

**Deliverables**:
- `src/fs2/core/mcp/__init__.py` (module marker)
- `src/fs2/core/mcp/dependencies.py` (lazy service initialization)
- `src/fs2/core/mcp/server.py` (FastMCP instance, no tools yet)
- `pyproject.toml` updated with fastmcp dependency
- `tests/mcp/conftest.py` (shared fixtures)

**Dependencies**: None (foundational phase)

**Risks**:

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| FastMCP incompatible with Python 3.12 | Low | High | Verify version before starting |
| Import order causes stdout pollution | Medium | High | Configure logging first, verify with test |

### Tasks (TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 1.1 | [x] | Write test for stdout isolation | 2 | Test captures stdout during import, asserts empty | [📋](tasks/phase-1-core-infrastructure/execution.log.md#task-t001) | T001 · 3 tests [^3] |
| 1.2 | [x] | Write tests for lazy service initialization | 2 | Tests verify services created on first access, cached after | [📋](tasks/phase-1-core-infrastructure/execution.log.md#task-t002) | T002 · 11 tests [^4] |
| 1.3 | [x] | Add fastmcp to pyproject.toml | 1 | `uv sync` succeeds, fastmcp importable | [📋](tasks/phase-1-core-infrastructure/execution.log.md#task-t004) | T004 · fastmcp>=2.0.0 [^5] |
| 1.4 | [x] | Create src/fs2/mcp/__init__.py | 1 | Empty file, module importable | [📋](tasks/phase-1-core-infrastructure/execution.log.md#task-t005) | T005 · peer to cli/ [^6] |
| 1.5 | [x] | Implement dependencies.py with lazy init | 2 | All tests from 1.2 pass | [📋](tasks/phase-1-core-infrastructure/execution.log.md#task-t006) | T006 · singleton pattern [^7] |
| 1.6 | [x] | Implement server.py with FastMCP instance | 2 | mcp instance created, test from 1.1 passes | [📋](tasks/phase-1-core-infrastructure/execution.log.md#task-t007) | T007 · Critical: logging before imports [^8] |
| 1.7 | [x] | Create tests/mcp_tests/conftest.py with fixtures | 2 | Fixtures provide FakeGraphStore, fake config | [📋](tasks/phase-1-core-infrastructure/execution.log.md#task-t009) | T009 · make_code_node() helper [^9] |
| 1.8 | [x] | Write test for error translation | 2 | fs2 exceptions translate to agent-friendly dicts | [📋](tasks/phase-1-core-infrastructure/execution.log.md#task-t003) | T003 · 7 tests [^10] |
| 1.9 | [x] | Implement error translation in server.py | 2 | All error tests pass | [📋](tasks/phase-1-core-infrastructure/execution.log.md#task-t008) | T008 · translate_error() [^11] |
| 1.10 | [x] | Create MCPLoggingConfig adapter | 2 | All fs2 logs route to stderr | [📋](tasks/phase-1-core-infrastructure/execution.log.md#task-t010) | T010 · stderr-only logging [^12] |

### Test Examples (Write First!)

```python
# tests/mcp/test_dependencies.py
import pytest
from fs2.core.mcp.dependencies import get_services

class TestLazyInitialization:
    """Tests for lazy service initialization pattern."""

    def test_services_not_loaded_on_import(self):
        """
        Purpose: Proves services are lazy-loaded, not at import time
        Quality Contribution: Prevents slow MCP server startup
        Acceptance Criteria:
        - Importing dependencies module does not load graph
        - First call to get_services() loads graph
        """
        from fs2.core.mcp import dependencies
        assert dependencies._graph_store is None

        config, graph_store = get_services()
        assert graph_store is not None

    def test_services_cached_after_first_access(self):
        """
        Purpose: Proves services are singleton per server instance
        Quality Contribution: Prevents repeated graph loading overhead
        Acceptance Criteria: Same instance returned on subsequent calls
        """
        first_call = get_services()
        second_call = get_services()
        assert first_call[1] is second_call[1]  # Same graph_store instance
```

```python
# tests/mcp/test_protocol.py
import sys
from io import StringIO

def test_no_stdout_on_import(monkeypatch):
    """
    Purpose: Proves importing MCP module doesn't pollute stdout
    Quality Contribution: Prevents protocol corruption
    Acceptance Criteria: stdout is empty after import
    """
    captured = StringIO()
    monkeypatch.setattr(sys, 'stdout', captured)

    # Force reimport
    import importlib
    import fs2.core.mcp.server
    importlib.reload(fs2.core.mcp.server)

    assert captured.getvalue() == ""
```

### Non-Happy-Path Coverage

- [x] Missing graph file → agent-friendly error (GraphNotFoundError translation)
- [x] Invalid config file → clear error message (GraphStoreError translation)
- [x] FastMCP import failure → graceful fallback error (general Exception translation)

### Acceptance Criteria

- [x] All 21 tests passing (expanded from original 9)
- [x] No stdout pollution during import
- [x] Services lazy-loaded and cached
- [x] Error translation working
- [x] Module structure correct (fs2/mcp/ as peer to cli/)

---

### Phase 2: Tree Tool Implementation

**Objective**: Implement the `tree` MCP tool with full filtering, depth limiting, and agent-optimized description.

**Deliverables**:
- Tree tool registered in server.py
- tests/mcp/test_tree_tool.py with comprehensive tests
- Tool description copied from research dossier

**Dependencies**: Phase 1 complete

**Risks**:

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| TreeService interface mismatch | Low | Medium | Study CLI tree.py composition |
| Tool description inadequate for agents | Medium | Low | Copy verbatim from research dossier |

### Tasks (TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 2.1 | [x] | Write tests for tree tool basic functionality | 2 | Tests cover: pattern ".", returns hierarchical list | [📋](tasks/phase-2-tree-tool-implementation/execution.log.md#task-t001-t004-tests) | T001: 6 tests [^13] |
| 2.2 | [x] | Write tests for tree tool filtering | 2 | Tests cover: pattern matching, glob patterns | [📋](tasks/phase-2-tree-tool-implementation/execution.log.md#task-t001-t004-tests) | T002: 5 tests [^13] |
| 2.3 | [x] | Write tests for tree tool depth limiting | 2 | Tests cover: max_depth=1 returns only root nodes | [📋](tasks/phase-2-tree-tool-implementation/execution.log.md#task-t001-t004-tests) | T003: 4 tests [^13] |
| 2.4 | [x] | Write tests for tree tool detail levels | 2 | Tests cover: min vs max detail output | [📋](tasks/phase-2-tree-tool-implementation/execution.log.md#task-t001-t004-tests) | T004: 5 tests [^13] |
| 2.5 | [x] | Implement tree tool in server.py | 3 | All tests from 2.1-2.4 pass | [📋](tasks/phase-2-tree-tool-implementation/execution.log.md#task-t005a-t005-impl) | T005+T005a: tree(), _tree_node_to_dict() [^14] |
| 2.6 | [x] | Add agent-optimized description | 1 | Description matches research dossier template | [📋](tasks/phase-2-tree-tool-implementation/execution.log.md#task-t006-agent-description) | T006: WHEN TO USE, WORKFLOW hints [^14] |
| 2.7 | [x] | Add MCP annotations | 1 | readOnlyHint=True, destructiveHint=False | [📋](tasks/phase-2-tree-tool-implementation/execution.log.md#task-t007-mcp-annotations) | T007: ToolAnnotations added [^14] |
| 2.8 | [x] | Write protocol compliance test | 2 | Tool output is valid JSON, no stdout pollution | [📋](tasks/phase-2-tree-tool-implementation/execution.log.md#task-t008-mcp-integration-tests) | T008: 8 async MCP tests [^15] |

### Test Examples (Write First!)

```python
# tests/mcp/test_tree_tool.py
import pytest
from fastmcp.testing import Client
from fs2.core.mcp.server import mcp

@pytest.fixture
def mcp_client(fake_graph_store):
    """In-memory MCP client with loaded graph."""
    # Inject fake graph store
    return Client(mcp)

class TestTreeTool:
    """Tests for tree MCP tool."""

    async def test_tree_returns_hierarchical_list(self, mcp_client):
        """
        Purpose: Proves tree tool returns correct structure
        Quality Contribution: Ensures agents receive expected format
        Acceptance Criteria:
        - Returns list of nodes
        - Each node has node_id, name, category, children
        """
        result = await mcp_client.call_tool("tree", pattern=".")

        assert isinstance(result, list)
        assert len(result) > 0
        for node in result:
            assert "node_id" in node
            assert "name" in node
            assert "category" in node

    async def test_tree_filters_by_pattern(self, mcp_client):
        """
        Purpose: Proves pattern filtering works
        Quality Contribution: Enables targeted codebase exploration
        Acceptance Criteria: Only matching nodes returned
        """
        result = await mcp_client.call_tool("tree", pattern="Calculator")

        for node in result:
            assert "Calculator" in node["node_id"]

    async def test_tree_respects_max_depth(self, mcp_client):
        """
        Purpose: Proves depth limiting works
        Quality Contribution: Prevents overwhelming output
        Acceptance Criteria: max_depth=1 returns only root nodes
        """
        result = await mcp_client.call_tool("tree", pattern=".", max_depth=1)

        for node in result:
            assert node.get("children", []) == []
```

### Acceptance Criteria

- [x] All 28 tests passing (AC1, AC2, AC3 from spec) ✓
- [x] Tool description includes prerequisites and workflow hints ✓
- [x] No stdout pollution ✓
- [x] Detail levels work correctly ✓

**Phase 2 Status**: ✅ COMPLETE (2026-01-01) - 28 tests, 54 total MCP tests

---

### Phase 3: Get-Node Tool Implementation

**Objective**: Implement the `get_node` MCP tool with file save option and not-found handling.

**Deliverables**:
- Get-node tool registered in server.py
- tests/mcp/test_get_node_tool.py with comprehensive tests

**Dependencies**: Phase 1 complete (can run parallel with Phase 2)

**Risks**:

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| File write permission issues | Low | Medium | Use temp directory for tests |
| Large node content exceeds response size | Low | Low | Document limitation |

### Tasks (TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 3.1 | [x] | Write tests for get_node retrieval | 2 | Tests cover: valid node_id returns full CodeNode | [📋](tasks/phase-3-get-node-tool-implementation/execution.log.md#task-t001-t003-tdd-test-suite) | 19 TDD tests [^16] |
| 3.2 | [x] | Write tests for get_node not found | 2 | Tests cover: invalid node_id returns None | [📋](tasks/phase-3-get-node-tool-implementation/execution.log.md#task-t001-t003-tdd-test-suite) | [^16] |
| 3.3 | [x] | Write tests for get_node save to file | 2 | Tests cover: save_to_file writes JSON | [📋](tasks/phase-3-get-node-tool-implementation/execution.log.md#task-t001-t003-tdd-test-suite) | Use tmp_path fixture [^16] |
| 3.4 | [x] | Implement get_node tool in server.py | 3 | All tests from 3.1-3.3 pass | [📋](tasks/phase-3-get-node-tool-implementation/execution.log.md#task-t004-implement-get_node-tool) | Sync function [^17] |
| 3.5 | [x] | Add agent-optimized description | 1 | Description matches research dossier template | [📋](tasks/phase-3-get-node-tool-implementation/execution.log.md#task-t005-agent-description) | [^17] |
| 3.6 | [x] | Add MCP annotations | 1 | readOnlyHint=True (mostly), openWorldHint=True for file save | [📋](tasks/phase-3-get-node-tool-implementation/execution.log.md#task-t006-mcp-annotations) | [^17] |
| 3.7 | [x] | Write protocol compliance test | 2 | Tool output is valid JSON | [📋](tasks/phase-3-get-node-tool-implementation/execution.log.md#task-t007-protocol-tests) | 7 MCP tests [^18] |

### Test Examples (Write First!)

```python
# tests/mcp/test_get_node_tool.py
class TestGetNodeTool:
    """Tests for get_node MCP tool."""

    async def test_get_node_returns_full_content(self, mcp_client, known_node_id):
        """
        Purpose: Proves get_node returns complete CodeNode data
        Quality Contribution: Enables agents to access full source code
        Acceptance Criteria:
        - Returns dict with content, signature, smart_content
        - content field contains actual source code
        """
        result = await mcp_client.call_tool("get_node", node_id=known_node_id)

        assert result is not None
        assert "content" in result
        assert "signature" in result
        assert "start_line" in result
        assert "end_line" in result

    async def test_get_node_not_found_returns_none(self, mcp_client):
        """
        Purpose: Proves missing nodes return None (not error)
        Quality Contribution: Enables graceful agent handling
        Acceptance Criteria: Returns None, not exception
        """
        result = await mcp_client.call_tool("get_node", node_id="nonexistent:path:name")

        assert result is None

    async def test_get_node_save_to_file(self, mcp_client, known_node_id, tmp_path):
        """
        Purpose: Proves file save option works
        Quality Contribution: Enables agents to persist node data
        Acceptance Criteria:
        - File created at specified path
        - Contains valid JSON
        - Returns confirmation message
        """
        output_path = tmp_path / "node.json"
        result = await mcp_client.call_tool(
            "get_node",
            node_id=known_node_id,
            save_to_file=str(output_path)
        )

        assert output_path.exists()
        import json
        data = json.loads(output_path.read_text())
        assert "content" in data
```

### Acceptance Criteria

- [x] All 26 tests passing (AC4, AC5, AC6 from spec)
- [x] None returned for missing nodes (not error)
- [x] File save creates valid JSON
- [x] No stdout pollution

**Phase 3 Status**: ✅ COMPLETE (2026-01-01) - 26 tests, 80 total MCP tests

---

### Phase 4: Search Tool Implementation

**Objective**: Implement the async `search` MCP tool with all search modes and filters.

**Deliverables**:
- Search tool registered in server.py (async)
- tests/mcp/test_search_tool.py with comprehensive tests

**Dependencies**: Phase 1 complete

**Risks**:

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Async event loop conflicts | Medium | High | Test in isolated async context |
| Semantic search requires embeddings | Low | Medium | Document prerequisite in description |

### Tasks (TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 4.1 | [x] | Write tests for search text mode | 2 | Tests cover: substring matching | [📋](tasks/phase-4-search-tool-implementation/execution.log.md#task-t001-t005-tdd-test-suite) | 6 tests [^19] |
| 4.2 | [x] | Write tests for search regex mode | 2 | Tests cover: pattern matching | [📋](tasks/phase-4-search-tool-implementation/execution.log.md#task-t001-t005-tdd-test-suite) | 4 tests [^19] |
| 4.3 | [x] | Write tests for search semantic mode | 3 | Tests cover: concept matching (requires embeddings) | [📋](tasks/phase-4-search-tool-implementation/execution.log.md#task-t001-t005-tdd-test-suite) | 4 tests, FakeEmbeddingAdapter [^19] |
| 4.4 | [x] | Write tests for search include/exclude filters | 2 | Tests cover: path filtering | [📋](tasks/phase-4-search-tool-implementation/execution.log.md#task-t001-t005-tdd-test-suite) | 5 tests [^19] |
| 4.5 | [x] | Write tests for search pagination | 2 | Tests cover: limit and offset | [📋](tasks/phase-4-search-tool-implementation/execution.log.md#task-t001-t005-tdd-test-suite) | 4 tests [^19] |
| 4.6 | [x] | Implement search tool in server.py | 3 | All tests from 4.1-4.5 pass | [📋](tasks/phase-4-search-tool-implementation/execution.log.md#task-t006c-implement-search-tool) | 34 tests passing [^20] |
| 4.7 | [x] | Add agent-optimized description | 1 | Description matches research dossier | [📋](tasks/phase-4-search-tool-implementation/execution.log.md#task-t006c-implement-search-tool) | WHEN TO USE, WORKFLOW [^20] |
| 4.8 | [x] | Add MCP annotations | 1 | readOnlyHint=True | [📋](tasks/phase-4-search-tool-implementation/execution.log.md#task-t006c-implement-search-tool) | openWorldHint=True (DYK#8) [^20] |
| 4.9 | [x] | Write async handling test | 2 | Tool works in async context without event loop conflicts | [📋](tasks/phase-4-search-tool-implementation/execution.log.md#task-t006c-implement-search-tool) | 6 protocol tests [^20] |

### Test Examples (Write First!)

```python
# tests/mcp/test_search_tool.py
class TestSearchTool:
    """Tests for search MCP tool."""

    async def test_search_text_mode(self, mcp_client):
        """
        Purpose: Proves text search returns substring matches
        Quality Contribution: Enables exact string finding
        Acceptance Criteria:
        - Returns envelope with meta and results
        - Results contain pattern as substring
        """
        result = await mcp_client.call_tool(
            "search",
            pattern="config",
            mode="text"
        )

        assert "meta" in result
        assert "results" in result
        for match in result["results"]:
            assert "config" in match["snippet"].lower() or "config" in match["node_id"].lower()

    async def test_search_regex_mode(self, mcp_client):
        """
        Purpose: Proves regex search works
        Quality Contribution: Enables pattern-based code discovery
        Acceptance Criteria: Results match regex pattern
        """
        result = await mcp_client.call_tool(
            "search",
            pattern="def test_.*",
            mode="regex"
        )

        assert "results" in result

    async def test_search_include_exclude_filters(self, mcp_client):
        """
        Purpose: Proves path filters work
        Quality Contribution: Enables scoped search
        Acceptance Criteria:
        - Results from include paths only
        - No results from exclude paths
        """
        result = await mcp_client.call_tool(
            "search",
            pattern="service",
            include=["src/"],
            exclude=["test"]
        )

        for match in result["results"]:
            assert "src/" in match["node_id"]
            assert "test" not in match["node_id"].lower()
```

### Acceptance Criteria

- [ ] All 9 tests passing (AC7, AC8, AC9, AC10 from spec)
- [ ] Async handling works correctly
- [ ] Search envelope format correct
- [ ] No stdout pollution

---

### Phase 5: CLI Integration

**Objective**: Add `fs2 mcp` command to start the MCP server.

**Deliverables**:
- `src/fs2/cli/mcp.py` (CLI entry point)
- Updated `src/fs2/cli/main.py` (command registration)
- tests/cli/test_mcp_command.py

**Dependencies**: Phase 1-4 complete

**Risks**:

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Command conflicts with existing CLI | Low | Low | Use unique name "mcp" |

### Tasks (TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 5.1 | [ ] | Write tests for CLI entry point | 2 | Tests cover: command starts server | - | |
| 5.2 | [ ] | Write tests for --config option | 2 | Tests cover: custom config path | - | |
| 5.3 | [ ] | Create src/fs2/cli/mcp.py | 2 | CLI entry point with logging config | - | Configure stderr FIRST |
| 5.4 | [ ] | Register command in main.py | 1 | `fs2 mcp --help` works | - | |
| 5.5 | [ ] | Write protocol compliance test | 2 | CLI doesn't pollute stdout | - | AC13 |
| 5.6 | [ ] | Write tool descriptions test | 2 | Tool listing shows correct descriptions | - | AC15 |

### Test Examples (Write First!)

```python
# tests/cli/test_mcp_command.py
from typer.testing import CliRunner
from fs2.cli.main import app

runner = CliRunner()

def test_mcp_command_exists():
    """
    Purpose: Proves mcp command is registered
    Quality Contribution: Ensures discoverability
    """
    result = runner.invoke(app, ["mcp", "--help"])
    assert result.exit_code == 0
    assert "MCP server" in result.output

def test_mcp_command_config_option():
    """
    Purpose: Proves --config option works
    Quality Contribution: Enables custom configuration
    """
    result = runner.invoke(app, ["mcp", "--help"])
    assert "--config" in result.output
```

### Acceptance Criteria

- [ ] All 6 tests passing (AC11, AC12, AC13, AC15 from spec)
- [ ] `fs2 mcp` starts server
- [ ] `fs2 mcp --config` works
- [ ] No stdout pollution

---

### Phase 6: Documentation

**Objective**: Document MCP server for users following hybrid strategy (README + docs/how/).

**Deliverables**:
- Updated README.md with quick-start section
- `docs/how/mcp-server-guide.md` with detailed documentation

**Dependencies**: Phase 1-5 complete

### Discovery & Placement Decision

**Existing docs/how/ structure**:
```
docs/how/
├── adding-services-adapters.md
├── architecture.md
├── configuration.md
├── di.md
├── embeddings/
│   ├── 1-overview.md
│   ├── 2-configuration.md
│   └── 3-providers.md
├── llm-adapter-extension.md
├── llm-service-setup.md
├── scanning.md
├── tdd.md
└── wormhole-mcp-guide.md
```

**Decision**: Create single file `docs/how/mcp-server-guide.md` (follows existing pattern for focused topics)

### Tasks (Lightweight Approach for Documentation)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 6.1 | [ ] | Update README.md with MCP quick-start | 2 | Section added with command and Claude Desktop config | - | /workspaces/flow_squared/README.md |
| 6.2 | [ ] | Create docs/how/mcp-server-guide.md | 3 | Detailed tool docs, troubleshooting, architecture | - | /workspaces/flow_squared/docs/how/mcp-server-guide.md |
| 6.3 | [ ] | Verify documentation accuracy | 1 | All commands and configs work as documented | - | Manual verification |

### Content Outlines

**README.md section**:
```markdown
## MCP Server (AI Agent Integration)

Start the MCP server for Claude Desktop or other MCP clients:

​```bash
fs2 mcp
​```

Claude Desktop configuration (`~/.config/claude/claude_desktop_config.json`):
​```json
{
  "mcpServers": {
    "fs2": {
      "command": "fs2",
      "args": ["mcp"],
      "cwd": "/path/to/your/project"
    }
  }
}
​```

See [MCP Server Guide](docs/how/mcp-server-guide.md) for detailed documentation.
```

**docs/how/mcp-server-guide.md**:
- Introduction and motivation
- Available tools (tree, get_node, search) with full parameter docs
- Claude Desktop configuration
- Troubleshooting guide
- Architecture overview

### Acceptance Criteria

- [ ] README.md has MCP quick-start section
- [ ] docs/how/mcp-server-guide.md is complete
- [ ] All documented commands work correctly

---

## Cross-Cutting Concerns

### Security Considerations

- **Input validation**: All tool parameters validated by Pydantic (via FastMCP)
- **File access**: get_node save_to_file restricted to specified path
- **No authentication**: Local STDIO transport, no remote access

### Observability

- **Logging**: All logs to stderr, suppressed to WARNING in MCP context
- **Errors**: Translated to agent-friendly JSON format
- **No metrics**: Local tool, no telemetry

### Documentation

- **Location**: Hybrid (README.md quick-start + docs/how/mcp-server-guide.md)
- **Target audience**: AI agent developers, Claude Desktop users
- **Maintenance**: Update when tools change

---

## Complexity Tracking

| Component | CS | Label | Breakdown (S,I,D,N,F,T) | Justification | Mitigation |
|-----------|-----|-------|------------------------|---------------|------------|
| Overall Feature | 2 | Small | S=1,I=1,D=0,N=0,F=1,T=1 | Well-researched, existing services, new module | Full TDD, per-tool testing |
| STDIO Protocol | 3 | Medium | S=0,I=0,D=0,N=1,F=2,T=1 | Protocol compliance critical | Early testing, capture stdout |
| Async Search | 3 | Medium | S=1,I=1,D=0,N=1,F=1,T=1 | Event loop handling | Isolated async tests |

---

## Progress Tracking

### Phase Completion Checklist

- [x] Phase 1: Core Infrastructure - COMPLETE (10/10 tasks, 21 tests passing)
- [x] Phase 2: Tree Tool Implementation - COMPLETE (8/8 tasks, 28 tests passing)
- [x] Phase 3: Get-Node Tool Implementation - COMPLETE (7/7 tasks, 26 tests passing)
- [x] Phase 4: Search Tool Implementation - COMPLETE (9/9 tasks, 34 tests passing, 114 total MCP tests)
- [ ] Phase 5: CLI Integration - PENDING
- [ ] Phase 6: Documentation - PENDING

Overall Progress: 4/6 phases (67%)

### STOP Rule

**IMPORTANT**: This plan must be complete before creating tasks. After writing this plan:
1. Run `/plan-4-complete-the-plan` to validate readiness
2. Only proceed to `/plan-5-phase-tasks-and-brief` after validation passes

---

## Change Footnotes Ledger

**NOTE**: This section is populated during implementation by plan-6a-update-progress.

**Footnote Numbering Authority**: plan-6a-update-progress is the **single source of truth** for footnote numbering across the entire plan.

### Phase 1: Core Infrastructure (Complete)

[^3]: Task 1.1 (T001) - Stdout isolation tests
  - `file:tests/mcp_tests/test_protocol.py`
  - `class:tests/mcp_tests/test_protocol.py:TestProtocolCompliance`
  - `method:tests/mcp_tests/test_protocol.py:TestProtocolCompliance.test_no_stdout_on_import`
  - `method:tests/mcp_tests/test_protocol.py:TestProtocolCompliance.test_logging_goes_to_stderr`
  - `method:tests/mcp_tests/test_protocol.py:TestProtocolCompliance.test_mcp_instance_exists`

[^4]: Task 1.2 (T002) - Lazy service initialization tests
  - `file:tests/mcp_tests/test_dependencies.py`
  - `class:tests/mcp_tests/test_dependencies.py:TestLazyInitialization`
  - `class:tests/mcp_tests/test_dependencies.py:TestDependencyInjection`
  - `method:tests/mcp_tests/test_dependencies.py:TestLazyInitialization.test_config_none_before_first_access`
  - `method:tests/mcp_tests/test_dependencies.py:TestLazyInitialization.test_config_created_on_first_access`
  - `method:tests/mcp_tests/test_dependencies.py:TestLazyInitialization.test_config_cached_after_first_access`
  - `method:tests/mcp_tests/test_dependencies.py:TestLazyInitialization.test_graph_store_none_before_first_access`
  - `method:tests/mcp_tests/test_dependencies.py:TestLazyInitialization.test_graph_store_created_on_first_access`
  - `method:tests/mcp_tests/test_dependencies.py:TestLazyInitialization.test_graph_store_cached_after_first_access`
  - `method:tests/mcp_tests/test_dependencies.py:TestLazyInitialization.test_graph_store_receives_config`
  - `method:tests/mcp_tests/test_dependencies.py:TestLazyInitialization.test_reset_services_clears_cache`
  - `method:tests/mcp_tests/test_dependencies.py:TestDependencyInjection.test_set_config_allows_fake_injection`
  - `method:tests/mcp_tests/test_dependencies.py:TestDependencyInjection.test_set_graph_store_allows_fake_injection`
  - `method:tests/mcp_tests/test_dependencies.py:TestDependencyInjection.test_fake_injection_bypasses_creation`

[^5]: Task 1.3 (T004) - FastMCP dependency
  - `file:pyproject.toml` (added fastmcp>=2.0.0)
  - Discovery: FastMCP v2.14.1 installed, API differs from researched v0.4.0

[^6]: Task 1.4 (T005) - MCP module structure
  - `file:src/fs2/mcp/__init__.py`
  - Architecture: fs2/mcp/ as peer to cli/, NOT under core/

[^7]: Task 1.5 (T006) - Lazy service initialization implementation
  - `file:src/fs2/mcp/dependencies.py`
  - `function:src/fs2/mcp/dependencies.py:get_config`
  - `function:src/fs2/mcp/dependencies.py:set_config`
  - `function:src/fs2/mcp/dependencies.py:get_graph_store`
  - `function:src/fs2/mcp/dependencies.py:set_graph_store`
  - `function:src/fs2/mcp/dependencies.py:reset_services`
  - Discovery: NetworkXGraphStore in graph_store_impl.py, not graph_store_networkx.py

[^8]: Task 1.6 (T007) - FastMCP server instance
  - `file:src/fs2/mcp/server.py`
  - `builtin:src/fs2/mcp/server.py:mcp` (FastMCP instance)
  - CRITICAL: MCPLoggingConfig().configure() called BEFORE any fs2 imports
  - Discovery: tests/mcp/ renamed to tests/mcp_tests/ to avoid shadowing mcp package

[^9]: Task 1.7 (T009) - Test fixtures
  - `file:tests/mcp_tests/__init__.py`
  - `file:tests/mcp_tests/conftest.py`
  - `function:tests/mcp_tests/conftest.py:make_code_node`
  - `function:tests/mcp_tests/conftest.py:fake_config` (fixture)
  - `function:tests/mcp_tests/conftest.py:fake_graph_store` (fixture)
  - `function:tests/mcp_tests/conftest.py:fake_embedding_adapter` (fixture)
  - `function:tests/mcp_tests/conftest.py:sample_node` (fixture)
  - Discovery: CodeNode has many required fields; make_code_node() helper created

[^10]: Task 1.8 (T003) - Error translation tests
  - `file:tests/mcp_tests/test_errors.py`
  - `class:tests/mcp_tests/test_errors.py:TestErrorTranslation`
  - `method:tests/mcp_tests/test_errors.py:TestErrorTranslation.test_graph_not_found_error_translation`
  - `method:tests/mcp_tests/test_errors.py:TestErrorTranslation.test_graph_store_error_translation`
  - `method:tests/mcp_tests/test_errors.py:TestErrorTranslation.test_value_error_translation`
  - `method:tests/mcp_tests/test_errors.py:TestErrorTranslation.test_unknown_error_translation`
  - `method:tests/mcp_tests/test_errors.py:TestErrorTranslation.test_error_response_has_required_keys`
  - `method:tests/mcp_tests/test_errors.py:TestErrorTranslation.test_graph_not_found_message_is_actionable`
  - `method:tests/mcp_tests/test_errors.py:TestErrorTranslation.test_exception_chaining_preserved`

[^11]: Task 1.9 (T008) - Error translation implementation
  - `function:src/fs2/mcp/server.py:translate_error`
  - Handles: GraphNotFoundError, GraphStoreError, ValueError, generic Exception
  - Returns: {type, message, action} dict for agent-friendly responses

[^12]: Task 1.10 (T010) - MCPLoggingConfig adapter
  - `file:src/fs2/core/adapters/logging_config.py`
  - `class:src/fs2/core/adapters/logging_config.py:LoggingConfigAdapter` (ABC)
  - `class:src/fs2/core/adapters/logging_config.py:MCPLoggingConfig`
  - `class:src/fs2/core/adapters/logging_config.py:DefaultLoggingConfig`
  - `method:src/fs2/core/adapters/logging_config.py:MCPLoggingConfig.configure`
  - Routes all fs2 loggers to stderr for STDIO protocol compliance

[^13]: Phase 2 Tasks 2.1-2.4 (T001-T004) - Tree tool TDD test suite
  - `file:tests/mcp_tests/test_tree_tool.py`
  - `file:tests/mcp_tests/conftest.py` (mcp_client, tree_test_graph_store fixtures)
  - 20 tests across 4 test classes: TestTreeToolBasicFunctionality (6), TestTreeToolPatternFiltering (5), TestTreeToolDepthLimiting (4), TestTreeToolDetailLevels (5)
  - Full TDD approach: tests written before implementation (RED phase)

[^14]: Phase 2 Tasks 2.5-2.7 (T005, T005a, T006, T007) - Tree tool implementation
  - `function:src/fs2/mcp/server.py:tree` - Main tree tool function
  - `function:src/fs2/mcp/server.py:_tree_node_to_dict` - TreeNode to dict converter
  - Agent-optimized docstring with WHEN TO USE, PREREQUISITES, WORKFLOW sections
  - MCP annotations: readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False

[^15]: Phase 2 Task 2.8 (T000, T008) - MCP protocol integration tests
  - `file:tests/mcp_tests/conftest.py` - mcp_client async fixture
  - 8 async tests in TestMCPProtocolIntegration class
  - Tests via actual MCP protocol (client.call_tool), not direct Python calls
  - Validates: tool registration, JSON serialization, parameter handling, annotations

### Phase 3: Get-Node Tool Implementation (Complete)

[^16]: Phase 3 Tasks 3.1-3.3 - TDD tests written (19 tests)
  - `method:tests/mcp_tests/test_get_node_tool.py:TestGetNodeRetrieval.*`
  - `method:tests/mcp_tests/test_get_node_tool.py:TestGetNodeNotFound.*`
  - `method:tests/mcp_tests/test_get_node_tool.py:TestGetNodeSaveToFile.*`

[^17]: Phase 3 Tasks 3.4-3.6 - get_node() implemented with helper funcs
  - `method:src/fs2/mcp/server.py:get_node`
  - `method:src/fs2/mcp/server.py:_code_node_to_dict`
  - `method:src/fs2/mcp/server.py:_validate_save_path`

[^18]: Phase 3 Task 3.7 - MCP protocol tests (7 tests)
  - `method:tests/mcp_tests/test_get_node_tool.py:TestGetNodeMCPProtocol.*`

### Phase 4: Search Tool Implementation (Complete)

[^19]: Phase 4 Tasks 4.1-4.5 - TDD tests written (34 tests total)
  - `class:tests/mcp_tests/test_search_tool.py:TestSearchToolTextMode` - 6 tests
  - `class:tests/mcp_tests/test_search_tool.py:TestSearchToolRegexMode` - 4 tests
  - `class:tests/mcp_tests/test_search_tool.py:TestSearchToolSemanticMode` - 4 tests
  - `class:tests/mcp_tests/test_search_tool.py:TestSearchToolFilters` - 5 tests
  - `class:tests/mcp_tests/test_search_tool.py:TestSearchToolPagination` - 4 tests
  - `class:tests/mcp_tests/test_search_tool.py:TestSearchToolCore` - 5 tests
  - `class:tests/mcp_tests/test_search_tool.py:TestSearchToolMCPProtocol` - 6 tests

[^20]: Phase 4 Tasks 4.6-4.9 - search() tool implemented
  - `function:src/fs2/mcp/server.py:search` - Main async search tool
  - `function:src/fs2/mcp/server.py:_build_search_envelope` - Envelope builder using SearchResultMeta
  - `function:src/fs2/mcp/dependencies.py:get_embedding_adapter` - Embedding adapter singleton
  - `function:src/fs2/mcp/dependencies.py:set_embedding_adapter` - Embedding adapter setter
  - `function:tests/mcp_tests/conftest.py:search_test_graph_store` - Search test fixture
  - `function:tests/mcp_tests/conftest.py:search_semantic_graph_store` - Semantic search fixture
  - `function:tests/mcp_tests/conftest.py:search_mcp_client` - MCP client fixture with embeddings
  - MCP annotations: readOnlyHint=True, openWorldHint=True (DYK#8)
  - Exception handlers: SearchError, EmbeddingAdapter errors (DYK#9, DYK#10)
