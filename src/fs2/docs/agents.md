# fs2 MCP Integration for AI Agents

This document provides guidance for AI coding assistants on how to effectively use the fs2 MCP server for code exploration and understanding.

## Overview

fs2 (Flowspace2) is a code intelligence tool that provides structured access to indexed codebases. When available via MCP, agents can use three tools to explore, retrieve, and search code.

## Available Tools

### `tree` - Explore Codebase Structure

**Purpose**: Navigate the hierarchical structure of an indexed codebase.

**When to Use**:
- Starting exploration of an unfamiliar codebase
- Finding classes, functions, or files by name pattern
- Understanding the containment hierarchy (files → classes → methods)
- Getting an overview before drilling into specifics

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pattern` | string | `"."` | Filter: `"."` for all, `"src/fs2/"` for folder, `"ClassName"` for substring, `"*.py"` for glob |
| `max_depth` | int | `0` | `0` = unlimited, `1` = top-level folders only, `2` = folders + contents |
| `detail` | string | `"min"` | `"min"` = compact, `"max"` = includes signatures and AI summaries |
| `format` | string | `"text"` | `"text"` = compact tree view (default), `"json"` = structured data |

**Returns**: Dict with format-specific content:
- `format="text"`: `{"format": "text", "content": "...", "count": N}` - compact tree view
- `format="json"`: `{"format": "json", "tree": [...], "count": N}` - list of tree nodes

**Folder Navigation** (progressive disclosure):
- `tree(pattern=".", max_depth=1)` → Top-level folders only (📁 docs/, src/, tests/)
- `tree(pattern=".", max_depth=2)` → Folders + their immediate contents
- `tree(pattern="src/fs2/cli/")` → Contents of specific folder path
- Folder nodes have `category: "folder"` and `node_id` with trailing slash (e.g., `src/fs2/`)

---

### `get_node` - Retrieve Complete Source Code

**Purpose**: Get the full source code and metadata for a specific code element.

**When to Use**:
- After finding a `node_id` from `tree` or `search` results
- When you need to read the actual implementation
- To save node data to a file for later analysis

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `node_id` | string | required | Unique identifier from `tree` or `search` |
| `save_to_file` | string | `null` | Optional path to save as JSON (under cwd only) |
| `detail` | string | `"min"` | `"min"` = 7 fields, `"max"` = 12 fields |

**Returns**: CodeNode dict with `content` (full source), `signature`, `start_line`, `end_line`, etc. Returns `null` if not found.

---

### `search` - Find Code by Content or Meaning

**Purpose**: Search for code by text, regex pattern, or semantic meaning.

**When to Use**:
- Finding code that contains specific text
- Searching with regex patterns (e.g., `"def test_.*"`)
- Conceptual discovery (e.g., "error handling logic") with semantic mode
- Filtering results to specific paths

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pattern` | string | required | Search pattern (text, regex, or natural language) |
| `mode` | string | `"auto"` | `"text"`, `"regex"`, `"semantic"`, or `"auto"` |
| `limit` | int | `20` | Maximum results (1-100) |
| `offset` | int | `0` | Skip results for pagination |
| `include` | list | `null` | Regex patterns for paths to include |
| `exclude` | list | `null` | Regex patterns for paths to exclude |
| `detail` | string | `"min"` | `"min"` = 9 fields, `"max"` = 13 fields |

**Returns**: Envelope with `meta` (total, pagination, folder distribution) and `results` (node_id, score, snippet).

**Search Modes**:
- `text`: Substring matching (case-insensitive)
- `regex`: Regular expression pattern matching
- `semantic`: Conceptual similarity via embeddings (requires `fs2 scan --embed`)
- `auto`: Automatically selects best mode based on pattern

---

## Recommended Workflows

### Exploring a New Codebase

```python
# 1. Get top-level folder structure
tree(pattern=".", max_depth=1)
# → 📁 docs/, 📁 src/, 📁 tests/ with children counts

# 2. Drill into a folder
tree(pattern=".", max_depth=2)
# → Shows folders + their immediate contents

# 3. Filter to specific folder path
tree(pattern="src/fs2/cli/")
# → Contents of the cli folder with files and symbols

# 4. Find specific class by name
tree(pattern="TreeService", detail="max")

# 5. Get full source
get_node(node_id="class:src/core/services/tree_service.py:TreeService")
```

### Finding Code by Concept

```python
# Semantic search (most flexible)
search(pattern="authentication and authorization", mode="semantic")

# Text search for specific terms
search(pattern="validate_token", mode="text")

# Regex for patterns
search(pattern="def test_.*config", mode="regex")
```

### Understanding a Class

```python
# Get class with methods visible
tree(pattern="ClassName", detail="max")

# Get specific method source
get_node(node_id="callable:path/to/file.py:ClassName.method_name")
```

### Scoped Investigation

```python
# Search only in source, exclude tests
search(pattern="error", include=["src/.*"], exclude=["test.*"])

# Find all tests for a feature
search(pattern="test.*auth", mode="regex", include=["tests/.*"])
```

---

## When to Use fs2 vs. Traditional Tools

| Task | Use fs2 | Use Traditional Tools |
|------|---------|----------------------|
| Explore codebase structure | `tree` | - |
| Find class/function definitions | `tree(pattern="Name")` | `Grep` for simple cases |
| Get complete source code | `get_node` | `Read` (if you have the path) |
| Semantic/conceptual search | `search(mode="semantic")` | Not available |
| Text search in code | `search(mode="text")` | `Grep` |
| Regex pattern search | `search(mode="regex")` | `Grep` |
| Search in non-code files | - | `Grep` |
| Find files by path pattern | - | `Glob` |

**Prefer fs2 when**:
- You need structured, hierarchical code understanding
- You want semantic/conceptual search
- You're exploring an unfamiliar codebase
- You need `node_id` for precise follow-up queries

**Use traditional tools when**:
- Searching in comments, strings, or documentation
- Simple file path pattern matching
- Quick one-off text searches
- Reading files you already know the path to

---

## Error Handling

Common errors and their solutions:

| Error | Cause | Solution |
|-------|-------|----------|
| "Graph not found" | Codebase not indexed | Run `fs2 scan` first |
| "Embeddings not found" | Semantic mode without embeddings | Run `fs2 scan --embed` |
| "Invalid regex pattern" | Malformed regex | Check pattern syntax |
| `null` from `get_node` | Node ID doesn't exist | Verify ID from fresh `tree`/`search` |

---

## Best Practices

1. **Start with `tree`** - Get oriented before searching
2. **Use `node_id`** - Results include IDs for precise follow-up
3. **Match mode to intent** - Text for exact, regex for patterns, semantic for concepts
4. **Filter with include/exclude** - Scope searches to relevant areas
5. **Check prerequisites** - Ensure `fs2 scan` (and `--embed` for semantic) was run
