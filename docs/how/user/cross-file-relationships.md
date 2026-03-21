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
