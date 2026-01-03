# Scanning Guide

Flowspace2 scans your codebase using tree-sitter to build a queryable code graph. This guide covers configuration, node types, and troubleshooting.

## Quick Start

```bash
# Initialize fs2 in your project
fs2 init

# Run the scan
fs2 scan

# Verbose output (per-file progress)
fs2 scan --verbose
```

## Configuration

Configuration is stored in `.fs2/config.yaml`:

```yaml
scan:
  # Directories to scan (relative paths)
  scan_paths:
    - "./src"
    - "./lib"

  # Respect .gitignore patterns (recommended)
  respect_gitignore: true

  # Maximum file size to parse (KB)
  max_file_size_kb: 500

  # Follow symbolic links (default: false)
  follow_symlinks: false
```

### Environment Variables

Override config via environment variables:

```bash
# Override scan paths
export FS2_SCAN__SCAN_PATHS='["./src", "./tests"]'

# Disable gitignore
export FS2_SCAN__RESPECT_GITIGNORE=false

# Disable progress spinner
export FS2_SCAN__NO_PROGRESS=true
```

### CLI Flags

```bash
# Verbose mode - shows per-file progress
fs2 scan --verbose
fs2 scan -v

# Disable progress spinner
fs2 scan --no-progress

# Force progress spinner (even in non-TTY)
fs2 scan --progress
```

## Output

Scan results are saved to `.fs2/graph.pickle` as a NetworkX graph.

```
$ fs2 scan
Discovering files...
Parsing 127 files...

✓ Scanned 127 files, created 543 nodes
  Graph saved to .fs2/graph.pickle
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (including partial success with some errors) |
| 1 | Configuration error (e.g., missing config file) |
| 2 | Total failure (all files errored) |

## Node Types

The scanner extracts these node types from your code:

| Node Type | Description | Example |
|-----------|-------------|---------|
| `file` | Source file | `src/main.py` |
| `module` | Module-level container | `main` |
| `class` | Class definition | `Calculator` |
| `method` | Method inside a class | `add`, `subtract` |
| `function` | Top-level function | `main()` |

### Node ID Format

Node IDs follow the format: `{type}:{path}:{symbol}`

Examples:
- `file:src/calc.py` - File node
- `class:src/calc.py:Calculator` - Class node
- `method:src/calc.py:Calculator.add` - Method node
- `function:src/utils.py:helper` - Function node

### Hierarchy

Nodes form a parent-child hierarchy:

```
file:src/calc.py
├── class:src/calc.py:Calculator
│   ├── method:src/calc.py:Calculator.add
│   └── method:src/calc.py:Calculator.subtract
└── function:src/calc.py:main
```

## Supported Languages

The scanner uses tree-sitter-language-pack for multi-language support:

| Language | Extensions |
|----------|------------|
| Python | `.py`, `.pyi` |
| TypeScript | `.ts`, `.tsx` |
| JavaScript | `.js`, `.jsx`, `.mjs` |
| Rust | `.rs` |
| Go | `.go` |
| Java | `.java` |
| C/C++ | `.c`, `.cpp`, `.cc`, `.h`, `.hpp` |
| Markdown | `.md` |
| YAML | `.yaml`, `.yml` |
| TOML | `.toml` |
| JSON | `.json` |
| And many more... |

## Gitignore Handling

When `respect_gitignore: true` (default):

1. Root `.gitignore` patterns apply to entire project
2. Nested `.gitignore` files apply to their subtrees only
3. Standard patterns: `node_modules/`, `__pycache__/`, `.git/`, etc.

```
project/
├── .gitignore          # *.log, node_modules/
├── src/
│   └── vendor/
│       └── .gitignore  # *.generated.py (only in vendor/)
```

## Troubleshooting

### "No configuration found"

```
Error: No configuration found.
  Run fs2 init first to create .fs2/config.yaml
```

**Solution**: Run `fs2 init` to create the config file.

### "Scanned 0 files"

Check your `scan_paths`:
- Ensure paths exist and contain files
- Check `.gitignore` isn't excluding everything
- Try `respect_gitignore: false` to debug

### Parse Errors

Some files may fail to parse:
- Binary files are automatically skipped
- Files with encoding issues show warnings
- Syntax errors in source files are logged but don't stop the scan

The scan continues despite individual file errors.

### Large Scans

For large codebases (>50 files), a progress spinner shows:
- "Discovering files..." during file enumeration
- "Parsing N files..." during AST extraction

Use `--verbose` for detailed per-file output.

## Graph Format

The graph is stored as a pickled NetworkX DiGraph with format versioning:

```python
import pickle
from pathlib import Path

# Load the graph
graph_file = Path(".fs2/graph.pickle")
with open(graph_file, "rb") as f:
    metadata, graph = pickle.load(f)

# Check format version
print(metadata["format_version"])  # "1.0"

# Access nodes
for node_id in graph.nodes:
    node = graph.nodes[node_id]["data"]
    print(f"{node.node_type}: {node.name}")

# Access edges (parent -> child relationships)
for parent, child in graph.edges:
    print(f"{parent} -> {child}")
```

### Node Data

Each node contains a `CodeNode` dataclass:

```python
@dataclass(frozen=True)
class CodeNode:
    node_id: str          # "method:src/calc.py:Calculator.add"
    node_type: str        # "method"
    name: str             # "add"
    file_path: str        # "/abs/path/src/calc.py"
    start_line: int       # 10
    end_line: int         # 15
    content: str          # Full source code
    parent_node_id: str | None  # "class:src/calc.py:Calculator"
    # ... additional fields for smart_content, embeddings (future)
```

## Architecture

The scanning pipeline follows Clean Architecture:

```
CLI (scan.py)
    │
    ▼
ScanPipeline (orchestrator)
    │
    ├── DiscoveryStage → FileSystemScanner (adapter)
    ├── ParsingStage   → TreeSitterParser (adapter)
    └── StorageStage   → NetworkXGraphStore (repo)
```

See [Architecture](architecture.md) for more details.
