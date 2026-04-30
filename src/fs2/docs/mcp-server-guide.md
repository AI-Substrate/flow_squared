# fs2 MCP Server Guide

This guide covers the fs2 MCP server's code intelligence capabilities for use with AI coding assistants.

## Overview

The fs2 MCP server exposes code graph traversal, node retrieval, and semantic search via the Model Context Protocol (MCP). This enables AI agents like Claude, GitHub Copilot, and others to programmatically explore and understand indexed codebases.

**Key Benefits**:
- Structured JSON responses instead of text parsing
- Hierarchical code navigation with `tree`
- Full source retrieval with `get_node`
- Semantic search with `search` (text, regex, or embeddings)

## Prerequisites

Before using the MCP server:

1. **Install fs2**: Ensure `fs2` is installed and available in your PATH
2. **Configure LLM and Embeddings**: You must follow the [Configuration Guide](configuration-guide.md) to set up LLM and embedding settings. Without this, smart content and semantic search will not work.
3. **Index your codebase**: Run `fs2 scan` to create the code graph

```bash
# Initialize config (first time)
fs2 init

# Configure credentials (required for full functionality)
# Edit .fs2/config.yaml with Azure/OpenAI settings
# See: configuration-guide.md

# Index codebase
fs2 scan
```

---

## Client Setup

<!-- T003-T007 content goes here -->

### Claude Code CLI

**CLI Command (Preferred)**:
```bash
# Add fs2 MCP server (user scope = available across all projects)
claude mcp add fs2 --scope user -- fs2 mcp

# Or for current project only
claude mcp add fs2 -- fs2 mcp

# List configured servers
claude mcp list

# Check status inside Claude Code
/mcp
```

**Scopes**:
- `--scope local` (default): Current project only
- `--scope project`: Shared via `.mcp.json` in project root
- `--scope user`: Available across all projects

**Config File** (`~/.claude.json`):
```json
{
  "mcpServers": {
    "fs2": {
      "command": "fs2",
      "args": ["mcp"]
    }
  }
}
```

---

### Claude Desktop

**Config File Locations**:
| Platform | Path |
|----------|------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/claude/claude_desktop_config.json` |

**JSON Config**:
```json
{
  "mcpServers": {
    "fs2": {
      "command": "fs2",
      "args": ["mcp"],
      "cwd": "/path/to/your/project"
    }
  }
}
```

**Important**: The `cwd` field specifies which project directory the MCP server operates in. Set this to your project's root path.

---

### GitHub Copilot (VS Code)

**Workspace Config** (`.vscode/mcp.json` - shareable with team):
```json
{
  "servers": {
    "fs2": {
      "type": "stdio",
      "command": "fs2",
      "args": ["mcp"]
    }
  }
}
```

**User Config via Command Palette**:
1. Open VS Code with GitHub Copilot enabled
2. Command Palette (Ctrl+Shift+P / Cmd+Shift+P)
3. Run "MCP: Add Server"
4. Select "stdio" type
5. Enter command: `fs2`, args: `["mcp"]`

**Note**: GitHub Copilot uses `servers` key (not `mcpServers`).

---

### OpenCode CLI

**CLI Command (Preferred)**:
```bash
# Interactive guided setup
opencode mcp add

# List configured servers
opencode mcp list
# or short form
opencode mcp ls

# Check status in OpenCode TUI
/mcp
```

**Config File Locations**:
- Global: `~/.config/opencode/opencode.json`
- Per-project: `opencode.json` in project directory

**JSON Config**:
```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "fs2": {
      "type": "local",
      "enabled": true,
      "command": ["fs2", "mcp"]
    }
  }
}
```

---

### Codex CLI (OpenAI)

**CLI Command (Preferred)**:
```bash
# Add fs2 MCP server
codex mcp add fs2 -- fs2 mcp

# List configured servers
codex mcp list

# Check status in Codex TUI
/mcp
```

**Config File**: `~/.codex/config.toml`

**TOML Config** (note: TOML syntax, not JSON):
```toml
[mcp_servers.fs2]
command = "fs2"
args = ["mcp"]
```

**Important**: Codex uses TOML format with `mcp_servers` (underscore, not `mcpServers`).

---

## Available Tools

<!-- T008-T010 content goes here -->

### list_graphs

List all available graphs (default + configured external graphs).

**When to Use**: Discover what graphs are available before querying. Returns the default local project graph and any configured external graphs from `other_graphs` in config.

**Parameters**: None

**Returns**: Dict with `docs` (list of graph metadata) and `count`:
```json
{
  "docs": [
    {
      "name": "default",
      "path": "/project/.fs2/graph.pickle",
      "available": true
    },
    {
      "name": "shared-lib",
      "path": "/home/user/projects/shared/.fs2/graph.pickle",
      "description": "Shared utility library",
      "source_url": "https://github.com/org/shared",
      "available": true
    }
  ],
  "count": 2
}
```

**Example**:
```python
# See all available graphs
list_graphs()

# Check if external graph is available
result = list_graphs()
for graph in result["docs"]:
    if graph["name"] == "shared-lib":
        print(f"Available: {graph['available']}")
```

See [Multi-Graph Configuration Guide](multi-graphs.md) for setup instructions.

---

### tree

Explore codebase structure as a hierarchical tree.

**When to Use**: Start here to understand what exists in a codebase. Returns files, classes, and functions with their containment relationships.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pattern` | string | `"."` | Filter pattern: `"."` for all, `"ClassName"` for substring match, `"*.py"` for glob |
| `max_depth` | int | `0` | Depth limit: `0` = unlimited, `1` = root only, `2` = roots + children |
| `detail` | string | `"min"` | `"min"` for compact, `"max"` for full metadata |
| `save_to_file` | string | `null` | Optional path to save tree as JSON |
| `graph_name` | string | `null` | Named graph from config (see `list_graphs()`). Default uses local graph. |

**Returns**: List of tree nodes, each containing:
- `node_id`: Unique identifier (use with `get_node` for full source)
- `name`: Display name (e.g., "Calculator", "add")
- `category`: "file" | "class" | "callable" | etc.
- `start_line`, `end_line`: Line range in source file
- `children`: Nested list of child nodes
- `hidden_children_count`: (when `max_depth` limits) count of hidden children
- When `save_to_file` is used: returns dict with `tree` and `saved_to` fields

**Example**:
```python
# See entire codebase structure
tree(pattern=".")

# Find Calculator class and its methods
tree(pattern="Calculator")

# Top-level files only
tree(pattern=".", max_depth=1)

# Detailed output with signatures
tree(pattern="Calculator", detail="max")

# Save to file for later analysis
tree(pattern=".", save_to_file="codebase_tree.json")
```

**Security**: `save_to_file` path must be under the current working directory.

---

### get_node

Retrieve complete source code and metadata for a specific code element.

**When to Use**: After `tree` or `search` to get the complete source code for a node identified by its `node_id`.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `node_id` | string | required | Unique identifier from `tree` or `search` results |
| `save_to_file` | string | `null` | Optional path to save node as JSON |
| `detail` | string | `"min"` | `"min"` for 7 core fields, `"max"` for full metadata |
| `graph_name` | string | `null` | Named graph from config (see `list_graphs()`). Default uses local graph. |

**Returns**: CodeNode dict or `null` if not found:
- `node_id`, `name`, `category`, `content`, `signature`, `start_line`, `end_line`
- Max detail adds: `smart_content`, `language`, `parent_node_id`, `qualified_name`, `ts_kind`

**Example**:
```python
# Get full source for a class
get_node(node_id="class:src/calc.py:Calculator")

# Save to file for later analysis
get_node(node_id="class:src/calc.py:Calculator", save_to_file="calc.json")

# Get detailed metadata
get_node(node_id="callable:src/calc.py:Calculator.add", detail="max")
```

**Security**: `save_to_file` path must be under the current working directory.

---

### search

Search codebase for matching code elements by text, regex, or semantic meaning.

**When to Use**: Find code by content, pattern, or conceptual meaning when you don't know the exact location.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pattern` | string | required | Search pattern (text, regex, or natural language) |
| `mode` | string | `"auto"` | `"text"`, `"regex"`, `"semantic"`, or `"auto"` |
| `limit` | int | `20` | Maximum results to return (1-100) |
| `offset` | int | `0` | Skip results for pagination |
| `include` | list | `null` | Regex patterns to include (e.g., `["src/.*"]`) |
| `exclude` | list | `null` | Regex patterns to exclude (e.g., `["test.*"]`) |
| `detail` | string | `"min"` | `"min"` for 9 fields, `"max"` for 13 fields |
| `save_to_file` | string | `null` | Optional path to save results as JSON |
| `graph_name` | string | `null` | Named graph from config (see `list_graphs()`). Default uses local graph. |

**Search Modes**:
| Mode | Use When | Example |
|------|----------|---------|
| `text` | Exact substring matching | `"ConfigService"` |
| `regex` | Pattern matching | `"def test_.*"` |
| `semantic` | Conceptual search (requires embeddings) | `"error handling logic"` |
| `auto` | Let fs2 decide based on pattern | Any |

**Returns**: Envelope with `meta` and `results`:
```json
{
  "meta": {
    "total": 47,
    "showing": {"from": 0, "to": 20, "count": 20},
    "pagination": {"limit": 20, "offset": 0},
    "folders": {"src/": 30, "tests/": 17}
  },
  "results": [
    {
      "node_id": "...",
      "score": 0.92,
      "snippet": "...",
      "smart_content": "..."
    }
  ]
}
```
When `save_to_file` is used, adds `saved_to` field with absolute path.

**Example**:
```python
# Text search
search(pattern="ConfigService", mode="text")

# Regex search for test functions
search(pattern="def test_.*", mode="regex")

# Semantic search (requires embeddings)
search(pattern="authentication and authorization logic", mode="semantic")

# Filtered search
search(pattern="error", include=["src/.*"], exclude=["test.*"])

# Save results to file for later analysis
search(pattern="error handling", save_to_file="errors.json")
```

**Security**: `save_to_file` path must be under the current working directory.

---

## Troubleshooting

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "Graph not found" | Codebase not indexed | Run `fs2 scan` to create the graph |
| "Embeddings not found" | Semantic search without embeddings | Run `fs2 scan --embed` |
| "Invalid regex pattern" | Malformed regex | Check pattern syntax |
| "Path escapes working directory" | `save_to_file` path security | Use relative path under current directory |
| "Missing configuration: GraphConfig" | (Older fs2 versions only) `graph:` section absent from `.fs2/config.yaml` and the auto-registration mechanism wasn't yet in place. Note: `list_graphs` succeeds while `tree`/`get_node`/`search` fail | Upgrade fs2, or add `graph: { graph_path: ".fs2/graph.pickle" }` to your `.fs2/config.yaml`. Modern fs2 auto-registers `GraphConfig` defaults so this error should not occur. |

### Verifying Setup

```bash
# Check fs2 is installed
fs2 --version

# Check graph exists
ls -la .fs2/graph.pickle

# Test MCP server starts
fs2 mcp --help

# List available tools (inside Claude Code)
/mcp
```

### Protocol Notes

- The MCP server uses STDIO transport (stdin/stdout for JSON-RPC)
- All logging goes to stderr to avoid protocol corruption
- The server reads configuration from `.fs2/config.yaml` or `~/.config/fs2/config.yaml`

---

## When to Use fs2 vs. Traditional Search

| Task | fs2 Tool | Alternative |
|------|----------|-------------|
| Explore codebase structure | `tree` | `find` / `ls -R` |
| Get file outline | `tree(pattern="file:path")` | `grep` patterns |
| Find class/function by name | `tree(pattern="Name")` | `grep` |
| Get full source code | `get_node` | `cat` |
| Find text in code | `search(mode="text")` | `grep` |
| Find regex pattern | `search(mode="regex")` | `grep -E` |
| Conceptual code discovery | `search(mode="semantic")` | Manual reading |
| Understand architecture | `tree(detail="max")` | Documentation |

**Prefer fs2 when**:
- You need structured, hierarchical understanding
- You want semantic/conceptual search
- You're exploring an unfamiliar codebase
- You need precise node IDs for follow-up queries

**Use traditional tools when**:
- Searching in comments, strings, or non-code files
- Simple file/path pattern matching
- Quick one-off text searches
