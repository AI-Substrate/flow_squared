# Multi-Graph Configuration Guide

Query multiple codebases from a single fs2 installation. Configure external graphs to search across monorepos, shared libraries, or vendor SDKs.

## Overview

By default, fs2 operates on the local project's graph (`.fs2/graph.pickle`). Multi-graph support lets you:

- **Search shared libraries** alongside your main project
- **Navigate monorepo packages** without switching directories
- **Reference vendor SDKs** for dependency exploration
- **Compare implementations** across related codebases

## Prerequisites: Scanning External Repositories

**IMPORTANT**: Before adding an external graph to your config, you must first scan that repository to create its graph file. There are two approaches:

### Approach A: Initialize fs2 in the External Repository (Recommended)

```bash
# Navigate to the external repository
cd /path/to/shared-library

# Initialize fs2 locally
fs2 init

# Scan the repository (creates .fs2/graph.pickle)
fs2 scan

# Optional: faster scan without AI enrichment
fs2 scan --no-smart-content --no-embeddings
```

The graph file is created at `/path/to/shared-library/.fs2/graph.pickle`. Reference this path in your `other_graphs` config.

### Approach B: Scan from Your Project with --scan-path

```bash
# From your main project directory
cd /path/to/my-project

# Scan external directory and save to custom location
fs2 scan \
  --scan-path /path/to/shared-library \
  --graph-file .fs2/graphs/shared-lib.pickle

# Or using relative path
fs2 scan \
  --scan-path ../shared-library \
  --graph-file .fs2/graphs/shared-lib.pickle
```

This creates a graph file within your project at `.fs2/graphs/shared-lib.pickle`.

### Which Approach to Choose?

| Approach | Best For | Graph Location |
|----------|----------|----------------|
| **A: Init in external repo** | Shared team repos, frequently updated | In external repo's `.fs2/` |
| **B: --scan-path** | Third-party code, one-off scans | In your project's `.fs2/graphs/` |

**Key difference**: With Approach A, the external repo "owns" its graph and can update it independently. With Approach B, you control when to rescan.

## Configuration

Add external graphs to your `.fs2/config.yaml`:

```yaml
other_graphs:
  graphs:
    # External repo with its own fs2 setup (Approach A)
    - name: shared-lib
      path: ~/projects/shared/.fs2/graph.pickle
      description: Shared utility library
      source_url: https://github.com/org/shared

    # Scanned into local project (Approach B)
    - name: vendor-sdk
      path: .fs2/graphs/vendor-sdk.pickle
      description: Vendor SDK (scanned locally)
```

### Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Identifier for CLI/MCP. Cannot be "default" (reserved). |
| `path` | Yes | Path to `.pickle` graph file |
| `description` | No | Human-readable description (shown in `list_graphs`) |
| `source_url` | No | URL to source repository (informational) |

### Path Resolution

Paths are resolved relative to the config file directory:

| Path Type | Example | Resolution |
|-----------|---------|------------|
| Absolute | `/home/user/lib/.fs2/graph.pickle` | Used as-is |
| Tilde | `~/projects/lib/.fs2/graph.pickle` | Expands `~` to home directory |
| Relative | `../lib/.fs2/graph.pickle` | Resolved from `.fs2/` directory |

## CLI Usage

Use the `--graph-name` global option to query a specific graph:

```bash
# Query external graph
fs2 --graph-name shared-lib tree
fs2 --graph-name shared-lib search "config"
fs2 --graph-name shared-lib get-node "file:src/utils.py"

# Default graph (no option needed)
fs2 tree
fs2 search "config"
```

### Mutual Exclusivity

The `--graph-name` and `--graph-file` options are mutually exclusive:

```bash
# OK: Use named graph from config
fs2 --graph-name shared-lib tree

# OK: Use explicit graph file
fs2 --graph-file /tmp/custom.pickle tree

# ERROR: Cannot use both
fs2 --graph-name shared-lib --graph-file /tmp/custom.pickle tree
```

## MCP Usage

### Discovering Available Graphs

Use `list_graphs()` to see all configured graphs:

```python
list_graphs()
```

Returns:
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

The `available` field indicates whether the graph file exists and is loadable.

### Querying Specific Graphs

Pass `graph_name` to any query tool:

```python
# Explore structure
tree(pattern=".", graph_name="shared-lib")

# Search code
search(pattern="authentication", graph_name="shared-lib")

# Get specific node
get_node(node_id="class:src/auth.py:AuthService", graph_name="shared-lib")
```

### Default Behavior

- `graph_name=None` (omitted) uses the default local graph
- `graph_name="default"` explicitly uses the local graph (same effect)

## Complete End-to-End Example

**Scenario**: You're working on a Django project and want to reference a shared cache library.

```bash
# Step 1: Scan the external repository (once)
cd /path/to/django-cache-library
fs2 init
fs2 scan --no-smart-content  # Fast scan without AI

# Step 2: Back in your main project, add to config
cd /path/to/my-django-project
```

Edit `.fs2/config.yaml`:
```yaml
other_graphs:
  graphs:
    - name: cache-lib
      path: /path/to/django-cache-library/.fs2/graph.pickle
      description: Django cache utilities
```

```bash
# Step 3: Use the external graph
fs2 --graph-name cache-lib tree
fs2 --graph-name cache-lib search "redis"
```

Via MCP:
```python
# Discover available graphs
list_graphs()

# Search the cache library
search(pattern="cache invalidation", graph_name="cache-lib", mode="semantic")

# Get a specific class
get_node(node_id="class:src/backends/redis.py:RedisCache", graph_name="cache-lib")
```

## Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| `Unknown graph name: 'foo'` | Graph not in config | Add entry to `other_graphs.graphs` in config.yaml |
| `Graph file not found: /path/to/graph.pickle` | Path doesn't exist | Run `fs2 scan` in target repository first |
| `Cannot use both --graph-file and --graph-name` | Mutual exclusivity | Use only one option |
| `Graph name "default" is reserved` | Used "default" as name | Choose a different name |
| `Graph file corrupted` | Invalid pickle file | Re-run `fs2 scan` to regenerate |

### Checking Graph Availability

Use `list_graphs()` to check if configured graphs are accessible:

```python
result = list_graphs()
for graph in result["docs"]:
    if not graph["available"]:
        print(f"Graph '{graph['name']}' not found at {graph['path']}")
```

## Related Documentation

- [CLI Reference](cli.md) - Full CLI options including `--graph-name`
- [MCP Server Guide](mcp-server-guide.md) - Tool reference for `list_graphs`, `tree`, `search`, `get_node`
- [Configuration Guide](configuration-guide.md) - Complete configuration options
- [Scanning Guide](scanning.md) - How to build graph files
