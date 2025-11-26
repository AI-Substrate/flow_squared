# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
├── cli/                    # Presentation layer (Typer + Rich)
├── core/
│   ├── models/             # Domain models (dataclasses, shared types)
│   ├── services/           # Composition layer (business logic)
│   ├── adapters/           # External SDK wrappers
│   │   └── protocols.py    # Adapter interfaces
│   └── repos/              # Data access
│       └── protocols.py    # Repository interfaces
└── config/                 # Pydantic settings
```

### Dependency Flow Rules

**ALLOWED** (left → right):
- `cli` → `services`
- `services` → `adapters/protocols`, `repos/protocols`, `models`
- `adapters/*_impl` → external SDKs
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

See `docs/how/wormhole-mcp-guide.md` for detailed documentation.

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