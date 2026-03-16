# Cross-File Relationships Guide

fs2 resolves cross-file references between code nodes using [Serena](https://github.com/oraios/serena), an LSP-powered resolution engine backed by Pyright. When enabled, your code graph includes `references` edges showing which functions call which, which classes are imported where, and how your code connects across files.

## Installation

```bash
# Install Serena (provides serena-mcp-server)
uv tool install "serena-agent @ git+https://github.com/oraios/serena.git"

# Verify installation
which serena-mcp-server
```

Cross-file resolution is **enabled by default** when `serena-mcp-server` is on PATH. No additional setup needed — fs2 auto-detects project roots and creates Serena projects on first scan.

## How It Works

During `fs2 scan`, the CrossFileRelsStage:

1. **Detects project roots** by looking for marker files (`pyproject.toml`, `package.json`, `go.mod`, etc.)
2. **Starts a pool of parallel Serena instances** (default: 20) for fast resolution
3. **Shards nodes** across instances using round-robin distribution
4. **Resolves references** via Serena's `find_referencing_symbols` LSP call
5. **Stores edges** in the graph with `edge_type="references"`

On subsequent scans, **unchanged files are skipped** — only modified files are re-resolved, and prior edges for unchanged files are reused.

## Viewing Relationships

### CLI

```bash
$ fs2 get-node "callable:src/service.py:Service.process"
{
  "node_id": "callable:src/service.py:Service.process",
  "name": "process",
  "content": "...",
  ...
  "relationships": {
    "referenced_by": [
      "callable:src/handler.py:Handler.handle",
      "callable:tests/test_service.py:TestService.test_process"
    ],
    "references": [
      "type:src/model.py:Item"
    ]
  }
}
```

### MCP (AI Agents)

The MCP `get_node` tool includes `relationships` at both `min` and `max` detail levels. The `tree` tool shows `(N refs)` per node at `--detail max`.

## Configuration

Add to `.fs2/config.yaml`:

```yaml
cross_file_rels:
  enabled: true              # Set to false to disable entirely
  parallel_instances: 20     # Number of Serena instances (1-50, default 20)
  serena_base_port: 8330     # Starting port for instances (8330-8349 by default)
  timeout_per_node: 5.0      # Seconds per node before giving up
  languages:                 # Languages to resolve
    - python
```

### CLI Flag Overrides

```bash
# Skip cross-file resolution entirely
fs2 scan --no-cross-refs

# Use fewer instances (e.g., on limited hardware)
fs2 scan --cross-refs-instances 5

# Combine with other flags
fs2 scan --no-smart-content --cross-refs-instances 10
```

## Performance Tuning

### Instance Count

Each Serena instance spawns 3 processes (~300MB RAM each):
- 1 Python MCP server
- 1 Python Pyright wrapper
- 1 Node.js Pyright

| Instances | RAM Usage | Speed (3600 nodes) |
|-----------|-----------|-------------------|
| 5 | ~1.5 GB | ~120s |
| 10 | ~3 GB | ~60s |
| 20 (default) | ~6 GB | ~30s |
| 30 | ~9 GB | ~35s (CPU contention) |

**Recommendation**: 20 instances is the sweet spot. Reduce to 5-10 on machines with < 8GB RAM.

### Incremental Resolution

On subsequent scans, only files with changed `content_hash` are re-resolved:
- **First scan**: All callable/type nodes are resolved (~30s for 3600 nodes)
- **Subsequent scans**: Only changed files are resolved; edges for unchanged files are reused
- **No changes**: Near-instant (edges copied from prior graph)

## Troubleshooting

### "serena-mcp-server not found"

Serena isn't installed or not on PATH:
```bash
uv tool install "serena-agent @ git+https://github.com/oraios/serena.git"
```

### "No project roots detected"

No `pyproject.toml`, `package.json`, or other marker files found. Make sure your project has a standard project root marker.

### Port conflicts

If ports 8330-8349 are in use, change the base port:
```yaml
cross_file_rels:
  serena_base_port: 9000
```

### Orphaned Serena processes

If a scan crashes, Serena processes may linger. fs2 auto-cleans orphans on next scan using a PID file (`.fs2/.serena-pool.pid`). You can also manually kill them:
```bash
# Check for orphaned serena processes
ps aux | grep serena-mcp-server
```

## .serena/ Directory

Serena creates a `.serena/` directory at your project root containing `project.yml` and other workspace files. **Add this to your `.gitignore`**:

```gitignore
# Serena workspace (auto-created by fs2 cross-file resolution)
.serena/
```

## Multi-Language Support

Serena supports multiple languages natively. fs2 detects project roots by language-specific marker files:

| Language | Marker File |
|----------|------------|
| Python | `pyproject.toml`, `setup.py`, `setup.cfg`, `Pipfile` |
| TypeScript | `tsconfig.json` |
| JavaScript | `package.json` |
| Go | `go.mod` |
| Rust | `Cargo.toml` |
| Java | `pom.xml`, `build.gradle`, `build.gradle.kts` |

Each detected project root gets its own Serena instance pool. Cross-file references are **within-project only** — no cross-project references in v1.
