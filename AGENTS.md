# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

# CRITICAL: DOGFOOD fs2 - NO EXCEPTIONS

**This is a NO-FAIL requirement.** You MUST use fs2 MCP tools (`mcp__flowspace__*`) as your PRIMARY method for exploring and searching this codebase.

## MANDATORY Tool Selection

| When you need to... | USE THIS (fs2) | NOT THIS |
|---------------------|----------------|----------|
| Find where something is implemented | `mcp__flowspace__search(pattern="...", mode="text")` | ❌ `Grep` |
| Understand code structure | `mcp__flowspace__tree(pattern="...")` | ❌ `Glob` / `ls` |
| Find a class/function | `mcp__flowspace__tree(pattern="ClassName")` | ❌ `Grep "class ClassName"` |
| Get source code of a symbol | `mcp__flowspace__get_node(node_id="...")` | ❌ `Read` (for discovery) |
| Search by concept/meaning | `mcp__flowspace__search(pattern="...", mode="semantic")` | ❌ Not possible otherwise |
| Find pattern matches | `mcp__flowspace__search(pattern="...", mode="regex")` | ❌ `Grep` |

## When Traditional Tools ARE Acceptable

- `Read`: When you already know the exact file path and need full content
- `Glob`: When searching for files by extension/name pattern only (not code content)
- `Grep`: ONLY for searching non-code files (markdown, config, etc.) or when fs2 graph is unavailable

## WHY This Matters

We are building fs2. Using it ourselves:
1. **Tests that it actually works** - We catch bugs and UX issues
2. **Validates the design** - If it's awkward to use, we need to fix it
3. **Builds muscle memory** - We understand our users' experience
4. **Finds gaps** - Missing features become obvious when we need them

## Quick Reference

```python
# FIRST: See what's in an area
mcp__flowspace__tree(pattern="adapters/")

# Find something by name
mcp__flowspace__tree(pattern="GraphStore")

# Search for text/pattern in code
mcp__flowspace__search(pattern="def save", mode="text")

# Get full source after finding node_id
mcp__flowspace__get_node(node_id="class:src/fs2/core/repos/graph_store_impl.py:NetworkXGraphStore")
```

**If you catch yourself reaching for Grep/Glob to search code - STOP and use fs2 instead.**

--- 

## Project Identity

> **Flowspace2** (short: **fs2**) — A ground-up rebuild of Flowspace with Clean Architecture

| Attribute | Value |
|-----------|-------|
| **Name** | Flowspace2 |
| **Short Name** | fs2 |
| **Env Prefix** | `FS2_` |
| **Config Dir** | `.fs2/` |
| **Package Manager** | `uv` |

## Project Overview

Flowspace2 is a Python project implementing Clean Architecture principles. The codebase enforces strict dependency boundaries where **Services** compose **Adapters** and **Repositories** through interface injection, with zero concept leakage from infrastructure to business logic.

**Key Dependencies**:
- `pydantic` / `pydantic-settings` — Configuration and validation
- `typer` — CLI argument parsing
- `rich` — Terminal formatting
- `pytest` — Testing
- `uv` — Package manager

## Development Environment

This project uses a devcontainer with Python 3.12 on Debian Bullseye.

### Setup Commands
```bash
# Install uv (already in devcontainer)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Python dependencies (when requirements.txt exists)
pip3 install --user -r requirements.txt
```

### MCP Tools Available
The devcontainer configures two MCP servers:
- **flowspace** — Code search and indexing (`flowspace mcp`)
- **wormhole** — Workspace utilities (`npx github:AI-Substrate/wormhole mcp --workspace .`)

## Architecture

### Clean Architecture Layers

```
src/
└── fs2/                        # Named package (import fs2.*)
    ├── cli/                    # Presentation layer (Typer + Rich)
    ├── core/
    │   ├── models/             # Domain models (frozen dataclasses)
    │   │   ├── log_level.py    # LogLevel IntEnum
    │   │   ├── log_entry.py    # LogEntry frozen dataclass
    │   │   └── process_result.py # ProcessResult with ok()/fail()
    │   ├── services/           # Composition layer (business logic)
    │   ├── adapters/           # External SDK wrappers
    │   │   ├── log_adapter.py      # LogAdapter ABC
    │   │   ├── console_adapter.py  # ConsoleAdapter ABC
    │   │   ├── sample_adapter.py   # SampleAdapter ABC (canonical example)
    │   │   ├── exceptions.py       # AdapterError hierarchy
    │   │   └── *_impl.py           # Implementations (e.g., log_adapter_console.py)
    │   └── repos/              # Data access
    │       └── protocols.py    # Repository interfaces
    └── config/                 # Pydantic settings
```

### Adapter File Naming Convention

Each adapter follows a consistent naming pattern:
- **ABC file**: `{name}_adapter.py` (e.g., `log_adapter.py`)
- **Implementation files**: `{name}_adapter_{impl}.py` (e.g., `log_adapter_console.py`, `log_adapter_fake.py`)
- **Exceptions**: `exceptions.py` (shared by all adapters)

### Dependency Flow Rules

**ALLOWED** (left → right):
- `cli` → `services`
- `services` → `adapters/*_adapter.py` (ABCs), `repos/protocols`, `models`
- `adapters/*_impl.py` → external SDKs
- `repos/*_impl` → databases/APIs

**FORBIDDEN** (right → left):
- `adapters` → `services` ❌
- `repos` → `services` ❌
- External SDK types leaking into `services` ❌

### Configuration

- **Env prefix**: `FS2_` (e.g., `FS2_AZURE__OPENAI__ENDPOINT`)
- **Config file**: `.fs2/config.yaml`
- **Precedence**: programmatic → env vars → YAML → .env → defaults

### FlowSpace Integration
The project uses FlowSpace for code indexing:
- Config: `.flowspace/config.yaml`
- Registry: `.flowspace/registry.yaml`

## Key Design Decisions

- **ABC interfaces**: Use `abc.ABC` with `@abstractmethod` for explicit contracts (runtime enforcement)
- **Fakes over mocks**: Implement test doubles as real interface implementations (inherit from ABC)
- **Actionable errors**: All exceptions include fix instructions
- **Tests as documentation**: Canonical tests demonstrate composition patterns


## Wormhole MCP Server (Code Intelligence)

The Wormhole MCP server provides VS Code LSP integration for semantic code navigation. Use these tools for intelligent code exploration instead of text-based grep when appropriate.

### When to Use Wormhole vs. Traditional Search

| Task | Tool | Why |
|------|------|-----|
| Find class/method definitions | `search_symbol_search` | Semantic, not text match |
| Get file structure/outline | `search_symbol_search` (document mode) | Shows all symbols organized |
| Find who calls a method | `symbol_calls` (incoming) | Traces actual call sites |
| Find what a method calls | `symbol_calls` (outgoing) | Traces dependencies |
| Find all usages of a symbol | `symbol_navigate` (references) | All references, not just text |
| Find interface implementations | `symbol_navigate` (implementations) | Semantic inheritance |
| Check for errors/warnings | `diagnostic_collect` | Real-time compiler feedback |
| Safe rename across codebase | `symbol_rename` | LSP-powered refactoring |
| Find text in comments/strings | `Grep` | Text content, not symbols |
| Find files by name pattern | `Glob` | File paths, not code |

### Quick Reference

```bash
# Symbol search (workspace)
search_symbol_search: query="Converter", kinds="Class", limit=20

# Document outline
search_symbol_search: mode="document", path="/absolute/path/to/file.dart"

# Call hierarchy (who calls this?)
symbol_calls: path="/abs/path.dart", symbol="ClassName.method", direction="incoming"

# Find references
symbol_navigate: path="/abs/path.dart", symbol="ClassName", action="references"

# Find implementations
symbol_navigate: path="/abs/path.dart", symbol="InterfaceName", action="implementations"

# Check diagnostics
diagnostic_collect: (no params for workspace-wide)
```

### Critical Notes

1. **Relative paths supported** - Resolved against workspace root (e.g., `lib/services/converter.dart`)
2. **Use qualified symbol names** - `ClassName.methodName` when ambiguous
3. **Check bridge health first** - Run `bridge_status` if tools aren't responding
4. **Prefer Wormhole for code structure** - Use Grep/Glob only for text/file searches

See `docs/how/user/wormhole-mcp-guide.md` for detailed documentation.

## FlowSpace MCP Server (Semantic Code Search)

FlowSpace provides AI-powered semantic search across indexed repositories. Use `mcp__flowspace__list_repos` to see available repos.

### Search Methods

| Method | Use When | Example |
|--------|----------|---------|
| `embed` | Conceptual/semantic queries | "authentication flow", "error handling" |
| `text` | Exact string matches | `Language.DART`, `class MyClass` |
| `regex` | Pattern matching | `class.*Server`, `def test_.*` |
| `auto` | Let FlowSpace decide (default) | Any query |

### Research Process

1. **Start broad** (semantic): `query(pattern="Dart language support", method="embed", limit=10)`
2. **Narrow with text**: `query(pattern="Language.DART", method="text")`
3. **Find patterns**: `query(pattern="class.*LanguageServer", method="regex")`
4. **Generate docs**: `document_code(pattern="DartLanguageServer", relationships=true)`

### Quick Reference

```python
# List repos
mcp__flowspace__list_repos()

# Semantic search across all repos
query(pattern="how config is loaded", limit=10, repo="all", method="embed")

# Exact text in specific repo
query(pattern="Language.DART", limit=5, repo="serena", method="text")

# Regex pattern
query(pattern="class.*Tool", limit=20, repo="serena", method="regex")

# Generate markdown documentation
document_code(pattern="ClassName", relationships=true, children=true)
```

### Node ID Formats

Results include `node_id` fields for precise references:
- `file:path/to/file.py` — File level
- `class:path/to/file.py:ClassName` — Class
- `method:path/to/file.py:ClassName.method` — Method
- `content:path/to/doc.md` — Content/documentation

### Output Formats

- `json` — Programmatic processing (default)
- `pretty` — Human-readable with details
- `table` — Quick scanning
- `report` — Executive summary with statistics

## fs2 MCP Server (Dogfooding)

This project uses its own fs2 MCP server for code exploration. **Use fs2 to work on fs2** - eat our own dogfood.

### Setup

```bash
# Add fs2 MCP server (user scope for all projects)
claude mcp add fs2 --scope user -- fs2 mcp

# Verify it's configured
claude mcp list
```

### When to Use fs2 MCP vs. Traditional Tools

| Task | fs2 Tool | Alternative |
|------|----------|-------------|
| Explore codebase structure | `mcp__fs2__tree(pattern=".")` | `Glob` / `ls` |
| Find class/function by name | `mcp__fs2__tree(pattern="ClassName")` | `Grep` |
| Get full source of a node | `mcp__fs2__get_node(node_id="...")` | `Read` |
| Semantic code search | `mcp__fs2__search(pattern="...", mode="semantic")` | Not available |
| Text search in code | `mcp__fs2__search(pattern="...", mode="text")` | `Grep` |
| Regex pattern search | `mcp__fs2__search(pattern="def.*test", mode="regex")` | `Grep` |

### Recommended Workflows

**Understanding a new area of the codebase:**
```python
# 1. See what exists
mcp__fs2__tree(pattern="adapters")

# 2. Drill into a specific class
mcp__fs2__tree(pattern="EmbeddingAdapter", detail="max")

# 3. Get full source
mcp__fs2__get_node(node_id="class:src/fs2/core/adapters/embedding_adapter.py:EmbeddingAdapter")
```

**Finding code by concept:**
```python
# Semantic search (requires embeddings)
mcp__fs2__search(pattern="error handling and exception translation", mode="semantic")

# Text search
mcp__fs2__search(pattern="translate_error", mode="text")
```

**Exploring service dependencies:**
```python
# Find all services
mcp__fs2__tree(pattern="Service", detail="max")

# Get specific service implementation
mcp__fs2__get_node(node_id="class:src/fs2/core/services/tree_service.py:TreeService")
```

### Prerequisites

Before using fs2 MCP, ensure the graph is indexed:
```bash
# From project root
fs2 scan
```

See <a>MCP Server Guide</a> for full tool documentation.

## Agent Workflow Notes

- **Code reviews run in a separate agent context.** Always provide **full absolute file paths** (e.g., `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/cli/projects.py`) when referencing files for review, since the review agent has no shared state with the implementation agent.

## minih Agent Harness

This project uses [minih](https://github.com/AI-Substrate/minih) for declarative agent-driven code reviews and quality checks.

### Setup

```bash
# minih is installed globally (or via npx)
export GH_TOKEN=$(gh auth token)

# Run the code-review agent
minih run code-review --param context="Review description here"

# Check agent health
minih doctor

# Validate last run output
minih validate code-review
```

### Agent Definitions

Agents live in `agents/` following minih conventions:
- `agents/_shared/preamble.md` — shared context injected into every agent
- `agents/code-review/` — structured code review with domain compliance and difficulty reporting

### Difficulty Ledger

The difficulty ledger at `harness/difficulty-ledger.md` tracks friction reported by minih agents. Every agent run produces a `retrospective.difficulties` array with structured friction reports (MH-001, MH-002, etc.). These feed into the ledger for tracking and resolution.

**Workflow:**
1. minih agents report difficulties in their output JSON
2. Review agent output: `minih last-run code-review | jq '.data.reportPath'`
3. Update `harness/difficulty-ledger.md` with new MH entries
4. Update `agents/_shared/preamble.md` Known Difficulties table so future agents see mitigations

See [MCP Server Guide](docs/how/user/mcp-server-guide.md) for full tool documentation.