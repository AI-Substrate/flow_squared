# fs2 CLI Reference

Complete command-line interface reference for Flowspace2 (fs2).

## Quick Reference

| Command | Purpose | Example |
|---------|---------|---------|
| `fs2 init` | Initialize project config | `fs2 init` |
| `fs2 scan` | Build code graph | `fs2 scan --verbose` |
| `fs2 tree` | Display code structure | `fs2 tree src/core --json` |
| `fs2 search` | Search code graph | `fs2 search "auth" --mode semantic` |
| `fs2 get-node` | Retrieve node by ID | `fs2 get-node "file:src/main.py"` |
| `fs2 mcp` | Start MCP server | `fs2 mcp` |
| `fs2 install` | Install fs2 globally | `fs2 install` |

---

## Global Options

These apply before any command:

### `--graph-file PATH`
Override graph file path (default: `.fs2/graph.pickle`).

```bash
fs2 --graph-file /custom/graph.pickle tree
```

### `--version` / `-V`
Show version and exit.

```bash
fs2 --version
# Output: fs2 v0.1.0 (abc1234)
```

---

## Commands

### fs2 init

Initialize fs2 configuration for a project.

**Synopsis:**
```bash
fs2 init [OPTIONS]
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--force` / `-f` | flag | false | Overwrite existing config |

**Exit Codes:**
- `0` - Success

**Examples:**
```bash
# Initialize new project
fs2 init

# Force overwrite existing config
fs2 init --force
```

**Output:**
Creates `.fs2/config.yaml` with defaults:
```yaml
scan:
  scan_paths: ["."]
  respect_gitignore: true
  max_file_size_kb: 500
  follow_symlinks: false
```

---

### fs2 scan

Scan the codebase and build the code graph.

**Synopsis:**
```bash
fs2 scan [OPTIONS]
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--scan-path` | string | config | Directory to scan (repeatable) |
| `--verbose` / `-v` | flag | false | Show per-file debug output |
| `--no-progress` | flag | false | Disable progress spinner |
| `--progress` | flag | false | Force progress in non-TTY |
| `--no-smart-content` | flag | false | Skip AI summaries |
| `--no-embeddings` | flag | false | Skip embedding generation |

**Exit Codes:**
- `0` - Success
- `1` - User error (missing config, LLM setup)
- `2` - Total failure (all files failed)

**Stages:**
1. **CONFIGURATION** - Load config, setup services
2. **DISCOVERY** - Find files respecting gitignore
3. **PARSING** - Tree-sitter AST extraction
4. **SMART CONTENT** - AI node enrichment (if configured)
5. **EMBEDDINGS** - Vector generation (if configured)
6. **STORAGE** - Persist to graph.pickle

**Examples:**
```bash
# Basic scan
fs2 scan

# Override scan directory
fs2 scan --scan-path src/

# Multiple directories
fs2 scan --scan-path src/ --scan-path lib/

# Verbose with debug output
fs2 scan --verbose

# Fast scan (skip AI enrichment)
fs2 scan --no-smart-content --no-embeddings

# CI/CD with progress
fs2 scan --progress
```

**Environment Variables:**
- `FS2_SCAN__NO_PROGRESS=true` - Disable progress spinner

---

### fs2 tree

Display code structure as a hierarchical tree.

**Synopsis:**
```bash
fs2 tree [PATTERN] [OPTIONS]
```

**Arguments:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `pattern` | string | "." | Filter: path, name, glob, or node_id |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--detail` | min\|max | min | Detail level |
| `--depth` / `-d` | int | 0 | Max depth (0=unlimited) |
| `--verbose` / `-v` | flag | false | Debug logging |
| `--json` | flag | false | Output JSON instead of Rich tree |
| `--file` / `-f` | path | - | Write JSON to file |

**Exit Codes:**
- `0` - Success
- `1` - User error (missing graph/config)
- `2` - System error (corrupted graph)

**Pattern Types:**
- `.` - All nodes
- `src/core` - Path filter
- `Calculator` - Name filter
- `*.py` - Glob pattern
- `file:src/main.py` - Exact node_id

**Output Formats:**

**Rich Tree (default):**
```
📁 src/
  📄 file:src/main.py [1-120]
    ƒ callable:src/main.py:main [10-50]
    📦 type:src/main.py:Calculator [52-100]
      ƒ callable:src/main.py:Calculator.add [55-60]
```

Note: Text output shows full node_ids for easy copy-paste to `get_node()`.

**JSON (`--json`):**
```json
{
  "tree": [
    {
      "node_id": "file:src/main.py",
      "name": "main.py",
      "category": "file",
      "start_line": 1,
      "end_line": 120,
      "children": [...]
    }
  ]
}
```

**Detail Levels:**
- **min**: node_id, name, category, start_line, end_line, children
- **max**: adds signature, smart_content

**Examples:**
```bash
# Show all files
fs2 tree

# Filter by path
fs2 tree src/core

# Filter by class name
fs2 tree Calculator

# Limit depth
fs2 tree --depth 2

# Full details
fs2 tree --detail max

# JSON to stdout (pipe to jq)
fs2 tree --json | jq '.tree[0].node_id'

# JSON to file
fs2 tree --json --file tree.json

# Combined: filter, JSON, file
fs2 tree Calculator --json --file calc.json
```

---

### fs2 search

Search the code graph with text, regex, or semantic matching.

**Synopsis:**
```bash
fs2 search PATTERN [OPTIONS]
```

**Arguments:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `pattern` | string | required | Search pattern |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--mode` / `-m` | auto\|text\|regex\|semantic | auto | Search mode |
| `--limit` / `-l` | int | 5 | Max results |
| `--offset` / `-o` | int | 0 | Skip N results (pagination) |
| `--detail` / `-d` | min\|max | min | Detail level |
| `--include` | string | - | Filter pattern (glob/regex, repeatable) |
| `--exclude` | string | - | Exclude pattern (glob/regex, repeatable) |
| `--file` / `-f` | path | - | Write JSON to file |

**Exit Codes:**
- `0` - Success
- `1` - User error (missing graph, invalid pattern)
- `2` - System error

**Search Modes:**

| Mode | Description | Example Pattern |
|------|-------------|-----------------|
| `auto` | Intelligent detection | Any |
| `text` | Substring match (case-insensitive) | `ConfigService` |
| `regex` | Regular expression | `def.*test` |
| `semantic` | Conceptual (requires embeddings) | `authentication flow` |

**Output Format (JSON Envelope):**
```json
{
  "meta": {
    "total": 45,
    "showing": {"from": 0, "to": 20, "count": 20},
    "pagination": {"limit": 20, "offset": 0},
    "folders": {"src/": 30, "tests/": 15}
  },
  "results": [
    {
      "node_id": "callable:src/auth.py:login",
      "name": "login",
      "category": "callable",
      "score": 0.95,
      "snippet": "def login(user, password):",
      "start_line": 42,
      "end_line": 78
    }
  ]
}
```

**Default Limit:** 5 results (use `--limit` to increase)

**Detail Levels:**
- **min** (9 fields): node_id, name, category, snippet, start_line, end_line, score, file_path, qualified_name
- **max** (13 fields): adds signature, smart_content, language, parent_node_id

**Filter Patterns:**
- Glob: `*.py`, `src/*.ts`
- Regex: `Calculator.*`, `test_.*`
- Multiple `--include` uses OR logic
- `--exclude` applied after `--include`

**Examples:**
```bash
# Auto-detect mode
fs2 search "authentication"

# Explicit text mode
fs2 search "ConfigService" --mode text

# Regex pattern
fs2 search "def.*test" --mode regex

# Semantic search (requires embeddings)
fs2 search "error handling patterns" --mode semantic

# Limit and pagination
fs2 search "auth" --limit 10
fs2 search "auth" --limit 10 --offset 10  # Page 2

# Filter by file type
fs2 search "handler" --include "*.py"

# Exclude tests
fs2 search "handler" --exclude "test"

# Multiple filters (OR logic)
fs2 search "config" --include "src/" --include "lib/"

# Full details
fs2 search "error" --detail max

# Pipe to jq
fs2 search "auth" | jq '.results[0].node_id'

# Save to file
fs2 search "authentication" --file results.json
```

---

### fs2 get-node

Retrieve a single code node by ID as JSON.

**Synopsis:**
```bash
fs2 get-node NODE_ID [OPTIONS]
```

**Arguments:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `node_id` | string | required | Node ID to retrieve |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--file` / `-f` | path | - | Write JSON to file |

**Exit Codes:**
- `0` - Success
- `1` - User error (missing graph, node not found)
- `2` - System error

**Node ID Format:** `category:path:symbol`
- `file:src/main.py` - File
- `callable:src/main.py:main` - Function
- `class:src/core/adapter.py:LogAdapter` - Class
- `method:src/core/adapter.py:LogAdapter.process` - Method

**Output Format:**
```json
{
  "node_id": "callable:src/main.py:main",
  "name": "main",
  "qualified_name": "main",
  "category": "callable",
  "start_line": 42,
  "end_line": 120,
  "signature": "def main(args: list[str]) -> int:",
  "content": "def main(args: list[str]) -> int:\n    ...",
  "smart_content": "Entry point for the application...",
  "language": "python",
  "parent_node_id": "file:src/main.py"
}
```

**Examples:**
```bash
# Output to stdout
fs2 get-node "file:src/main.py"

# Pipe to jq
fs2 get-node "callable:src/main.py:main" | jq '.signature'

# Save to file
fs2 get-node "file:src/main.py" --file node.json

# Get class definition
fs2 get-node "class:src/core/adapters/log_adapter.py:LogAdapter"
```

---

### fs2 mcp

Start the MCP server for AI agent integration.

**Synopsis:**
```bash
fs2 mcp
```

**Exit Codes:**
- `0` - Normal exit
- `1` - Startup error

**Communication:**
- **stdin**: JSON-RPC requests
- **stdout**: JSON-RPC responses (reserved for protocol)
- **stderr**: Logging and diagnostics

**Prerequisites:**
- Run `fs2 scan` first to index codebase
- For semantic search: `fs2 scan` with embeddings configured

**Available MCP Tools:**
- `tree` - Explore code structure
- `get_node` - Retrieve node by ID
- `search` - Search code graph

**Claude Desktop Config** (`~/.config/claude/claude_desktop_config.json`):
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

**Claude Code CLI:**
```bash
claude mcp add fs2 --scope user -- fs2 mcp
```

**Zero-Install:**
```bash
uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 mcp
```

See [MCP Server Guide](mcp-server-guide.md) for detailed integration docs.

---

### fs2 install / fs2 upgrade

Install or upgrade fs2 as a permanent uv tool.

**Synopsis:**
```bash
fs2 install
fs2 upgrade   # Alias, same behavior
```

**Exit Codes:**
- `0` - Success
- `1` - Error (uv not found, installation failed)

**Behavior:**
- Checks for uv installation
- Installs from `git+https://github.com/AI-Substrate/flow_squared`
- Idempotent (safe to run multiple times)

**Examples:**
```bash
# First-time install via uvx
uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 install

# Check version
fs2 --version

# Upgrade to latest
fs2 upgrade
```

---

## Configuration

### Config File Location
`.fs2/config.yaml` in project root

### Full Config Example
```yaml
scan:
  scan_paths:
    - "."
  respect_gitignore: true
  max_file_size_kb: 500
  follow_symlinks: false

# Optional: AI summaries
llm:
  provider: azure
  azure:
    endpoint: "${FS2_AZURE__LLM__ENDPOINT}"
    api_key: "${FS2_AZURE__LLM__API_KEY}"
    deployment_name: "gpt-4"

# Optional: Semantic search embeddings
embedding:
  mode: azure
  dimensions: 1024
  azure:
    endpoint: "${FS2_AZURE__EMBEDDING__ENDPOINT}"
    api_key: "${FS2_AZURE__EMBEDDING__API_KEY}"
    deployment_name: "text-embedding-3-small"
```

### Environment Variable Override
Prefix: `FS2_`, nested with `__`

```bash
# Override scan paths
export FS2_SCAN__SCAN_PATHS='["./src", "./tests"]'

# Disable progress
export FS2_SCAN__NO_PROGRESS=true

# Override graph path
export FS2_GRAPH__GRAPH_PATH=/custom/graph.pickle
```

### Precedence (highest to lowest)
1. CLI flags
2. Environment variables
3. Config file
4. Defaults

---

## Output Patterns

### JSON to Stdout (for piping)
```bash
# Search results to jq
fs2 search "auth" | jq '.results[] | .node_id'

# Tree to jq
fs2 tree --json | jq '.tree[0].children | length'

# Node to jq
fs2 get-node "file:src/main.py" | jq '.signature'
```

### JSON to File
```bash
# Save search results
fs2 search "auth" --file results.json

# Save tree
fs2 tree --json --file tree.json

# Save node
fs2 get-node "file:src/main.py" --file node.json
```

**File Output Behavior:**
- stdout is empty (JSON goes to file only)
- Confirmation printed to stderr: `✓ Wrote results to results.json`
- Path validated (must be under current directory)
- Parent directories created automatically

### Exit Codes Summary

| Code | Meaning | Examples |
|------|---------|----------|
| 0 | Success | Command completed |
| 1 | User error | Missing config, node not found, invalid args |
| 2 | System error | Corrupted graph, filesystem issues |

---

## Troubleshooting

### "No configuration found"
```bash
# Solution: Initialize config
fs2 init
```

### "No graph found"
```bash
# Solution: Run scan first
fs2 scan
```

### "Node not found"
```bash
# Solution: Verify node_id format
fs2 tree --json | jq '.tree[].node_id'  # List valid IDs
```

### "Path escapes working directory"
```bash
# Problem: --file ../outside.json
# Solution: Use path under current directory
fs2 search "test" --file ./results.json
```

### JSON output polluted with text
```bash
# Problem: Logging going to stdout
# Solution: Check for --verbose flag, use 2>/dev/null
fs2 search "auth" 2>/dev/null | jq
```

### Semantic search returns no results
```bash
# Solution: Ensure embeddings are generated
fs2 scan  # With embedding config
```

---

## Common Workflows

### Initial Project Setup
```bash
fs2 init                    # Create config
fs2 scan                    # Build graph
fs2 tree                    # Explore structure
```

### Explore a Class
```bash
fs2 tree Calculator         # Find class
fs2 get-node "class:src/calc.py:Calculator" | jq  # Get details
```

### Find All Test Files
```bash
fs2 search "test" --include "*.py" --exclude "fixture"
```

### Semantic Code Search
```bash
# First, ensure embeddings
fs2 scan  # With embedding config

# Then search conceptually
fs2 search "authentication flow" --mode semantic
```

### Export for Analysis
```bash
# Full tree
fs2 tree --json --file full_tree.json

# Search results
fs2 search "error" --detail max --file errors.json
```

### AI Agent Integration
```bash
fs2 mcp  # Start server, configure in Claude Desktop
```

---

## See Also

- [Scanning Guide](scanning.md) - Detailed scan configuration
- [MCP Server Guide](mcp-server-guide.md) - AI agent integration
- [Configuration Guide](configuration.md) - Full config reference
- [Embeddings Guide](embeddings/) - Semantic search setup
