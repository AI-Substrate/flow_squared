# Cross-File Relationships Guide

fs2 resolves cross-file references between code nodes using [SCIP](https://github.com/sourcegraph/scip) (Source Code Intelligence Protocol) indexers. When enabled, your code graph includes `references` edges showing which functions call which, which classes are imported where, and how your code connects across files.

## Supported Languages

| Language | Indexer | Install |
|----------|---------|---------|
| Python | scip-python | `npm install -g @sourcegraph/scip-python` |
| TypeScript | scip-typescript | `npm install -g @sourcegraph/scip-typescript` |
| JavaScript | scip-typescript | `npm install -g @sourcegraph/scip-typescript` |
| Go | scip-go | `go install github.com/sourcegraph/scip-go/cmd/scip-go@latest` |
| C#/.NET | scip-dotnet | `dotnet tool install --global scip-dotnet` |

## Quick Start

```bash
# 1. Discover language projects in your repo
fs2 discover-projects

# 2. Add detected projects to config
fs2 add-project 1 2 3    # or: fs2 add-project --all

# 3. Scan with cross-file resolution
fs2 scan
```

## How It Works

During `fs2 scan`, the CrossFileRelsStage:

1. **Reads project config** from `.fs2/config.yaml` (or auto-discovers from marker files)
2. **Runs SCIP indexers** offline for each configured project (e.g., `scip-python index .`)
3. **Parses the SCIP index** (protobuf binary) to extract symbol definitions and references
4. **Matches cross-file edges** by linking references in file A to definitions in file B
5. **Stores edges** in the graph with `edge_type="references"`

SCIP indexers run offline — no servers, no ports, no memory pools.

## Viewing Relationships

### CLI

```bash
$ fs2 get-node "callable:src/service.py:Service.process"
{
  "node_id": "callable:src/service.py:Service.process",
  "name": "process",
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

projects:
  entries:
    - type: python
      path: .
    - type: typescript
      path: frontend
      project_file: tsconfig.json
  auto_discover: true        # Fall back to marker detection when entries is empty
  scip_cache_dir: .fs2/scip  # Cached index files
```

### CLI Flag Overrides

```bash
# Skip cross-file resolution entirely
fs2 scan --no-cross-refs
```

## Project Discovery

fs2 detects project roots by language-specific marker files:

| Language | Marker File |
|----------|------------|
| Python | `pyproject.toml`, `setup.py`, `setup.cfg`, `Pipfile` |
| TypeScript | `tsconfig.json` |
| JavaScript | `package.json` |
| Go | `go.mod` |
| C# | `.csproj`, `.sln` |
| Rust | `Cargo.toml` |
| Java | `pom.xml`, `build.gradle`, `build.gradle.kts` |
| Ruby | `Gemfile` |

Use `fs2 discover-projects` to see all detected projects with indexer availability status.

## Troubleshooting

### "scip-python not found"

Install the indexer for your language:
```bash
npm install -g @sourcegraph/scip-python
```

### "No project roots detected"

No marker files found. Make sure your project has a standard project root marker (pyproject.toml, package.json, go.mod, etc.).

### "0 edges" after scanning

Check these in order:
1. **Indexer installed?** — Run `fs2 discover-projects` and check the Indexer column (✅ vs ❌)
2. **Project configured?** — Check `.fs2/config.yaml` has a `projects.entries` section with the right type and path
3. **Path correct?** — The `path` field is relative to the repo root (where `.fs2/` lives). Use `.` for the repo root, `frontend` for a subdirectory
4. **Index produced?** — Check `.fs2/scip/` for cached `index.scip` files. If empty, the indexer failed silently
5. **C# needs build** — Run `dotnet build` before scanning C# projects

### Scan produces edges but `get-node` shows no relationships

Edges are stored between nodes that exist in the graph. If tree-sitter didn't parse a file (e.g., unsupported language, file too large), its nodes won't exist and edges to/from it are dropped by StorageStage.

---

## For AI Agents

### Helping Users Set Up Cross-File Relationships

When a user wants cross-file references, guide them through this workflow:

1. **Check indexer availability**: Run `fs2 discover-projects --json` and inspect the `indexer_installed` field
2. **Install missing indexers**: Show the install command from the table above
3. **Add projects to config**: Run `fs2 add-project --all` or select specific numbers
4. **Scan**: Run `fs2 scan --no-smart-content --no-embeddings` for a fast first scan

### Config Path Rules

The `path` field in `projects.entries` is **relative to the repo root** (the directory containing `.fs2/`):

```yaml
projects:
  entries:
    - type: python
      path: .                    # Project IS the repo root
    - type: typescript
      path: frontend             # Project is in <repo>/frontend/
    - type: python
      path: services/auth        # Project is in <repo>/services/auth/
```

**Important**: Paths resolve against the repo root, NOT the current working directory. If the user runs `fs2 scan --scan-path src/`, the project paths still resolve from the repo root.

### Reading Relationships from the Graph

Use `get_node` to see cross-file relationships:
```
get_node(node_id="callable:src/service.py:MyService.process")
→ relationships.referenced_by = ["callable:src/handler.py:Handler.handle"]
→ relationships.references = ["type:src/model.py:Item"]
```

Use `tree` with `detail="max"` to see reference counts:
```
tree(pattern="src/service.py")
→ Shows "(3 refs)" next to nodes that have cross-file references
```

### Auto-Discovery

If no `projects.entries` are configured and `auto_discover: true` (the default), the stage automatically discovers projects from marker files during scan. This means cross-file refs can work with zero config for simple single-language repos.
