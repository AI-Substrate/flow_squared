# fs2 Agent Guide

> **FlowSpace2 (fs2)** — Code intelligence for AI agents. Scan codebases into searchable graphs, then search by text, regex, or meaning.

This guide is for agents and humans who want to **use** fs2 on their projects — not develop fs2 itself.

---

## Quick Start (60 seconds)

```bash
# Install (permanent — adds 'fs2' to PATH)
uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 install

# Navigate to your project
cd /path/to/your/project

# Initialize + scan
fs2 init          # Creates .fs2/config.yaml
fs2 scan          # Builds the code graph

# Search
fs2 search "authentication"        # Auto-detects best search mode
fs2 tree "src/"                    # Browse structure
fs2 get-node "class:src/auth.py:AuthService"  # Full source code
```

---

## Install

| Method | Command | When |
|--------|---------|------|
| **Permanent** | `uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 install` | Daily use |
| **Zero-install** | `uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 scan` | One-off / CI |
| **Specific branch** | `uvx --from "git+https://github.com/AI-Substrate/flow_squared@branch-name" fs2 install` | Testing PRs |
| **Upgrade** | `fs2 upgrade` | After install |

**Requires**: Python 3.12+ and [uv](https://docs.astral.sh/uv/).

---

## MCP Server Setup

The MCP server gives Claude direct access to fs2 tools (tree, search, get-node).

### Claude Code (CLI)

```bash
# All projects (recommended)
claude mcp add fs2 --scope user -- fs2 mcp

# Single project only
claude mcp add fs2 -- fs2 mcp

# Verify
claude mcp list
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

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

### MCP Tools

| Tool | What It Does |
|------|-------------|
| `tree(pattern="src/")` | Browse code structure |
| `search(pattern="auth flow", mode="semantic")` | Find code by meaning |
| `get_node(node_id="class:src/auth.py:Auth")` | Get full source code |
| `list_graphs()` | Show available graphs |
| `docs_list()` / `docs_get(id)` | Browse fs2 docs |

**Important**: Run `fs2 scan` before starting the MCP server.

---

## Scanning

```bash
fs2 scan                                        # Full scan (parse + embeddings)
fs2 scan --no-smart-content --no-embeddings      # Fast: structure only
fs2 scan --no-smart-content                      # Structure + embeddings (no LLM needed)
fs2 scan --force                                 # Force full rescan
```

### What You Get

```
file:src/auth.py
├── type:src/auth.py:AuthService           ← class
│   ├── callable:src/auth.py:AuthService.login   ← method
│   └── callable:src/auth.py:AuthService.logout
└── callable:src/auth.py:hash_password           ← function

file:docs/guide.md
├── section:docs/guide.md:Getting Started        ← H2 section
├── section:docs/guide.md:Configuration
└── section:docs/guide.md:API Reference
```

**Node categories**: `file`, `callable`, `type`, `section`, `block`

**Languages**: Python, JS/TS, Rust, Go, Java, C/C++, Ruby, Markdown, YAML, JSON, HCL, and 30+ more.

**Markdown splitting**: `.md` files are split at `##` headings automatically. Each H2 section becomes a searchable node.

### Config

Edit `.fs2/config.yaml`:

```yaml
scan:
  scan_paths:
    - .                    # Default
    - ../shared-lib        # Scan additional paths
  ignore_patterns:
    - "*.generated.*"
    - "vendor/"
  max_file_size_kb: 512
  respect_gitignore: true
```

---

## Searching

### Modes

| Mode | When | Example |
|------|------|---------|
| **auto** (default) | Let fs2 decide | `fs2 search "auth flow"` |
| **semantic** | Conceptual queries | `fs2 search "how errors are handled" -m semantic` |
| **text** | Exact substring | `fs2 search "def login" -m text` |
| **regex** | Pattern match | `fs2 search "class.*Service" -m regex` |

### Options

```bash
fs2 search "pattern" --limit 20           # More results
fs2 search "pattern" --include "*.py"     # Only Python files
fs2 search "pattern" --exclude "tests/"   # Skip tests
fs2 search "pattern" --detail max         # Include signatures
```

### Tips

1. **Semantic for concepts**: `"how is auth handled"`, `"error recovery logic"`
2. **Text for symbols**: `"AuthService"`, `"def process_batch"`
3. **Regex for patterns**: `"class.*Adapter"`, `"def test_.*"`
4. **Get the node**: After search, use `fs2 get-node <node_id>` for full source
5. **Tree for exploration**: `fs2 tree "src/"` when you don't know what to search for

---

## Tree

```bash
fs2 tree                       # All files
fs2 tree "src/"                # Under src/
fs2 tree "AuthService"         # Find by name
fs2 tree "." --depth 1         # Top-level only
fs2 tree "." --detail max      # Include signatures
fs2 tree "." --json            # JSON output
```

---

## Multi-Graph

Query multiple codebases from one project — reference libraries, shared packages, or related repos.

### Setup

Add to `.fs2/config.yaml`:

```yaml
other_graphs:
  graphs:
    - name: shared-lib
      path: /path/to/shared-lib/.fs2/graph.pickle
      description: "Shared utility library"
    - name: api-server
      path: ~/projects/api/.fs2/graph.pickle
      description: "Backend API"
```

### Usage

```bash
fs2 list-graphs                                    # Show all graphs
fs2 search "UserService" --graph-name shared-lib   # Search external graph
fs2 tree "src/" --graph-name api-server            # Browse external graph
```

MCP tools accept `graph_name` too:

```python
search(pattern="auth", mode="semantic", graph_name="shared-lib")
tree(pattern="src/", graph_name="api-server")
```

**Each project must be scanned independently** (`cd /that/project && fs2 scan`). fs2 reads the graph — it doesn't rescan external projects.

---

## CLAUDE.md Integration

Add this to your project's `CLAUDE.md` so agents know fs2 is available:

```markdown
## Code Intelligence (fs2)

This project is indexed with fs2. Use MCP tools for code exploration.

### Workflow
1. `tree(pattern="src/")` — see what exists
2. `search(pattern="concept", mode="semantic")` — find by meaning
3. `get_node(node_id="...")` — read full source

### Scanning
Run `fs2 scan` after major code changes to update the index.
```

---

## Best Practices

### Scanning
- **Scan once, search many** — scanning is slow; search/tree/get-node are instant
- **Skip what you don't need** — `--no-smart-content --no-embeddings` for fast structural scans
- **Rescan after major changes** — existing embeddings are preserved incrementally
- **Use `.gitignore`** — fs2 respects it by default

### Searching
- **Semantic search is the killer feature** — use it for conceptual queries
- **Text search for precision** — when you know the exact name
- **Always get the node** — search finds it, `get-node` reads it

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Graph not found` | Run `fs2 scan` in the project |
| Semantic search returns nothing | Run `fs2 scan` (embeddings are on by default) |
| MCP not connecting | Check `claude mcp list`; ensure `fs2 scan` was run |
| Stale results | Run `fs2 scan` to refresh |
| External graph not found | Check `path` in config points to `.fs2/graph.pickle` |
| `fs2: command not found` | Run `fs2 install` |

---

## Commands

| Command | Purpose |
|---------|---------|
| `fs2 init` | Create config |
| `fs2 scan` | Build/update graph |
| `fs2 tree [PATTERN]` | Browse structure |
| `fs2 search PATTERN` | Search code |
| `fs2 get-node NODE_ID` | Get full source |
| `fs2 list-graphs` | Show graphs |
| `fs2 mcp` | Start MCP server |
| `fs2 watch` | Auto-rescan on changes |
| `fs2 doctor` | Diagnose issues |
| `fs2 install` | Install permanently |
| `fs2 upgrade` | Upgrade to latest |
