# Writing New Curated Documentation

This guide explains how to add new curated documentation to fs2's bundled `src/fs2/docs/` package. These documents are accessible via MCP tools (`docs_list`, `docs_get`) and ship with the wheel distribution.

## Overview

fs2 has two documentation locations:

| Location | Purpose | Audience |
|----------|---------|----------|
| `docs/how/` | Developer documentation for repo contributors | Developers |
| `src/fs2/docs/` | Curated user/agent documentation, bundled with package | End users, AI agents |

The `src/fs2/docs/` documents are designed for AI agent self-service - agents can discover and read them without network access or external dependencies.

## Adding a New Document

### Step 1: Create the Markdown File

Create your document in `src/fs2/docs/`:

```bash
touch src/fs2/docs/my-guide.md
```

Write agent-friendly content:
- Clear structure with headers
- Practical examples
- Common pitfalls and solutions

### Step 2: Add Registry Entry

Add an entry to `src/fs2/docs/registry.yaml`:

```yaml
documents:
  # ... existing entries ...
  - id: my-guide                    # Slug format: lowercase, hyphens only
    title: "My Guide Title"         # Human-readable title
    summary: "One-line description of what this doc covers and when to read it."
    category: how-to                # Or: reference
    tags:
      - relevant
      - tags
      - for-discovery
    path: my-guide.md               # Relative to src/fs2/docs/
```

### Step 3: Verify Access

Test that your document is discoverable:

```python
from fs2.mcp.server import docs_list, docs_get

# Check it appears in the list
result = docs_list()
assert any(d["id"] == "my-guide" for d in result["docs"])

# Check content loads
doc = docs_get(id="my-guide")
assert doc is not None
assert len(doc["content"]) > 0
```

## Registry Schema

### ID Format

Document IDs must match pattern `^[a-z0-9-]+$`:
- Lowercase letters
- Numbers
- Hyphens only
- No spaces or underscores

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier (slug format) |
| `title` | string | Human-readable title |
| `summary` | string | 1-2 sentences: what it covers + when to use |
| `category` | string | Classification (e.g., "how-to", "reference") |
| `tags` | list | Discovery tags for filtering |
| `path` | string | Relative path to markdown file |

### Summary Best Practices

Summaries should answer two questions:
1. **What** does this document cover?
2. **When** should someone read it?

Good example:
> "Best practices for AI agents using fs2 tools. Read this FIRST when starting to use fs2 MCP server to understand tool selection and search strategies."

## Build Configuration

The `pyproject.toml` includes docs in the wheel:

```toml
[tool.hatch.build.targets.wheel]
include = [
    "src/fs2/docs/**/*.yaml",
    "src/fs2/docs/**/*.md",
]
```

**Important**: Hatch's `packages` directive only includes `.py` files by default. Without these explicit include patterns, markdown and YAML files would be missing from the wheel.

## Maintenance

Per R6.4 in `docs/rules-idioms-architecture/rules.md`, bundled docs require explicit maintenance:

- Changes to configuration schema → review `configuration-guide.md`
- New MCP tools → review `agents.md`
- Changes to registry schema → review `registry.yaml`

## See Also

- [MCP Server Guide](mcp-server-guide.md) - MCP tool setup and usage
- [R6.4 Rule](../rules-idioms-architecture/rules.md#r64-bundled-documentation-maintenance) - Maintenance requirements
