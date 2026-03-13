# Workshop: CLI & MCP Changes for Cross-File Relationships

**Type**: CLI Flow
**Plan**: 031-cross-file-rels
**Spec**: [exploration.md](../exploration.md)
**Created**: 2026-03-12
**Status**: Draft

**Related Documents**:
- [001-edge-storage.md](001-edge-storage.md) — How edges are stored in the DiGraph
- [002-serena-benchmarks.md](002-serena-benchmarks.md) — Serena performance data and config design

---

## Purpose

Define exactly where cross-file relationships appear in the CLI and MCP surfaces. Three concerns:
1. **Scan** — How are cross-file rels triggered during `fs2 scan`?
2. **Browse** — How do consumers see relationships in `tree`, `get-node`, `search`?
3. **MCP** — How do AI agents discover and use relationship data?

---

## 1. Scan CLI Changes

### Current `fs2 scan` Flags

```bash
fs2 scan [OPTIONS]
  --scan-path PATH        # Directory to scan (repeatable)
  --verbose / -v          # Detailed output
  --no-progress           # Disable spinner
  --progress              # Force spinner
  --no-smart-content      # Skip AI summaries
  --no-embeddings         # Skip vector embeddings
```

### New Flags

```bash
fs2 scan [OPTIONS]
  # ... existing flags ...
  --no-cross-refs                    # Skip cross-file relationship extraction
  --cross-refs-instances N           # Override parallel Serena instances (default: 20)
```

### Flag Interaction

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  fs2 scan                                                                    │
│                                                                              │
│  Is serena-mcp-server on PATH?                                               │
│  ├─ NO  → Skip CrossFileRels stage, log info:                                │
│  │        "Cross-file refs: skipped (serena not found).                       │
│  │         Install: uv tool install serena-agent"                             │
│  │                                                                           │
│  └─ YES → Is --no-cross-refs set?                                            │
│           ├─ YES → Skip CrossFileRels stage, log:                             │
│           │        "Cross-file refs: disabled (--no-cross-refs)"              │
│           │                                                                  │
│           └─ NO  → Is config cross_file_rels.enabled = false?                 │
│                    ├─ YES → Skip, log: "Cross-file refs: disabled (config)"   │
│                    └─ NO  → Run CrossFileRelsStage                            │
│                             instances = --cross-refs-instances or config      │
│                             default = 20                                      │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Scan Output — Cross-File Rels Stage Banner

```
$ fs2 scan

  Discovering files...
✓ Found 126 files (324 nodes)

  Parsing files...
✓ Parsed 126 files → 5332 nodes

  Resolving cross-file relationships...                    ← NEW STAGE
  ├ Serena instances: 20
  ├ Nodes to resolve: 3634
  ╰ Progress: ████████████████████████████████████████ 3634/3634 (29s)
✓ Cross-file refs: 9926 references, 3634 nodes resolved (29.1s)

  Generating smart content...
✓ Smart content: 200 enriched, 5132 preserved

  Generating embeddings...
✓ Embeddings: 5332 embedded

  Saving graph...
✓ Graph saved: 5332 nodes, 14478 edges (4552 containment + 9926 cross-file)
```

### Scan Output — Serena Not Available

```
$ fs2 scan

  Discovering files...
✓ Found 126 files (324 nodes)

  Parsing files...
✓ Parsed 126 files → 5332 nodes

ℹ Cross-file refs: skipped (serena-mcp-server not found)
  Install: uv tool install serena-agent

  Generating smart content...
...
```

### Implementation in `scan.py`

```python
# New parameters in scan() function
no_cross_refs: Annotated[
    bool,
    typer.Option(
        "--no-cross-refs",
        help="Skip cross-file relationship extraction",
    ),
] = False,
cross_refs_instances: Annotated[
    int | None,
    typer.Option(
        "--cross-refs-instances",
        help="Number of parallel Serena instances (default: 20)",
    ),
] = None,
```

---

## 2. Get-Node — Viewing Relationships

### Current `fs2 get-node` Output

```
$ fs2 get-node "callable:src/fs2/core/repos/graph_store.py:GraphStore.add_edge"

{
  "node_id": "callable:src/fs2/core/repos/graph_store.py:GraphStore.add_edge",
  "category": "callable",
  "name": "add_edge",
  "qualified_name": "GraphStore.add_edge",
  "content": "...",
  "signature": "def add_edge(self, parent_id: str, child_id: str) -> None:",
  "start_line": 54,
  "end_line": 68,
  ...
}
```

### New: Relationship Fields in Output

Cross-file edges are stored in the graph (per [001-edge-storage](001-edge-storage.md)). The `get-node` output surfaces them.

#### CLI Output (JSON)

```
$ fs2 get-node "callable:src/fs2/core/repos/graph_store.py:GraphStore.add_edge"

{
  "node_id": "callable:src/fs2/core/repos/graph_store.py:GraphStore.add_edge",
  "category": "callable",
  "name": "add_edge",
  ...
  "relationships": {
    "referenced_by": [
      "callable:src/fs2/core/services/stages/storage_stage.py:StorageStage.process",
      "callable:tests/unit/repos/test_graph_store_impl.py:TestNetworkXGraphStoreNodeOperations.test_add_edge_creates_parent_child_relationship",
      "callable:src/fs2/core/repos/graph_store_fake.py:FakeGraphStore.add_edge"
    ]
  }
}
```

#### When No Relationships Exist

The `relationships` field is **omitted** (not `null`, not `{}`) when the node has no cross-file edges. This keeps output compact for nodes without relationships and avoids noise.

#### MCP `get_node` Tool Output

Same as CLI. The `_code_node_to_dict` function gains a `graph_store` parameter:

```python
def _code_node_to_dict(
    node: CodeNode,
    detail: Literal["min", "max"] = "min",
    graph_store: GraphStore | None = None,   # NEW
) -> dict[str, Any]:
    result = {
        "node_id": node.node_id,
        "name": node.name,
        "category": node.category,
        "content": node.content,
        "signature": node.signature,
        "start_line": node.start_line,
        "end_line": node.end_line,
    }

    if detail == "max":
        result["smart_content"] = node.smart_content
        result["language"] = node.language
        result["parent_node_id"] = node.parent_node_id
        result["qualified_name"] = node.qualified_name
        result["ts_kind"] = node.ts_kind

    # NEW: Include relationships when graph_store is available
    if graph_store is not None:
        edges = graph_store.get_edges(node.node_id, direction="both")
        typed_edges = [(nid, data) for nid, data in edges if data.get("edge_type")]
        if typed_edges:
            rels = {}
            for connected_id, data in typed_edges:
                edge_type = data["edge_type"]
                # Determine direction
                if connected_id in [nid for nid, _ in
                    graph_store.get_edges(node.node_id, direction="incoming")]:
                    key = f"referenced_by"
                else:
                    key = f"references"
                if edge_type not in rels:
                    rels[key] = []
                rels[key].append(connected_id)
            result["relationships"] = rels

    return result
```

### Detail Levels

| Detail | Fields | Relationships |
|--------|--------|---------------|
| `min` | 7 core fields | ✅ Included (if they exist) |
| `max` | 12 fields | ✅ Included (if they exist) |

Relationships are **always included** at both detail levels — they're the primary value-add of this feature and agents need them for call tree walking.

---

## 3. Tree — No Changes (Containment Only)

### Decision: Tree stays structural

```
$ fs2 tree src/fs2/core/repos/

📁 src/fs2/core/repos/
├── 📄 file:src/fs2/core/repos/graph_store.py [1-181]
│   └── 📦 type:src/fs2/core/repos/graph_store.py:GraphStore [20-179]
│       ├── ƒ callable:...GraphStore.add_node [40-50]
│       ├── ƒ callable:...GraphStore.add_edge [54-68]     ← NO cross-file edges shown
│       └── ƒ callable:...GraphStore.get_node [69-79]
├── 📄 file:src/fs2/core/repos/graph_store_impl.py [1-393]
...
```

**Why**: Tree shows **containment hierarchy** (file → class → method). Cross-file edges would make it a graph, not a tree. Agents use `get_node` to drill into a specific node and see its relationships.

The workflow:
1. `tree` to find the node
2. `get_node` to see its code + relationships
3. Follow relationship node_ids back to `get_node`

---

## 4. Search — No Changes

Search results return matched nodes. Relationships are a property of individual nodes, not search results. If you need relationships, take the `node_id` from search results and call `get_node`.

---

## 5. MCP Tool Changes Summary

### Modified Tools

| Tool | Change |
|------|--------|
| `get_node` | Add `relationships` field to output (when edges exist) |

### Unchanged Tools

| Tool | Why Unchanged |
|------|---------------|
| `tree` | Containment only, cross-file edges don't belong |
| `search` | Returns match metadata, not relationship data |
| `list_graphs` | No change needed |
| `docs_list` / `docs_get` | No change needed |

### Future Tool (Not in Scope)

A dedicated `get_edges` tool may be added later for explicit relationship queries:

```python
# Future — NOT in initial implementation
def get_edges(
    node_id: str,
    direction: Literal["incoming", "outgoing", "both"] = "both",
    edge_type: str | None = None,
    graph_name: str | None = None,
) -> list[dict[str, Any]]:
    """Query cross-file relationship edges for a node."""
```

This is deferred because `get_node` with `relationships` covers the common case. A dedicated tool is warranted when agents need to walk multi-hop call trees efficiently.

---

## 6. Config YAML Changes

### New Section in `.fs2/config.yaml`

```yaml
# ─── Cross-File Relationships ─────────────────────────────
# Resolves call/reference relationships between code nodes using LSP.
# Requires: uv tool install serena-agent
# Enabled by default when serena-mcp-server is available.

cross_file_rels:
  enabled: true              # Set to false to disable entirely
  parallel_instances: 20     # Serena instances (1-50, default 20)
  serena_base_port: 8330     # Starting port for instances
  timeout_per_node: 5.0      # Seconds per node before giving up
  languages:                 # Languages to resolve
    - python
```

### Precedence (same as existing config)

```
CLI flag (--no-cross-refs)  >  config.yaml  >  default (enabled)
```

### Config Object in `config/objects.py`

```python
class CrossFileRelsConfig(BaseModel):
    """Configuration for cross-file relationship extraction.

    Path: cross_file_rels (e.g., FS2_CROSS_FILE_RELS__PARALLEL_INSTANCES)
    """

    __config_path__: ClassVar[str] = "cross_file_rels"

    enabled: bool = True
    parallel_instances: int = 20
    serena_base_port: int = 8330
    timeout_per_node: float = 5.0
    languages: list[str] = ["python"]

    @field_validator("parallel_instances")
    @classmethod
    def validate_parallel_instances(cls, v: int) -> int:
        if v < 1 or v > 50:
            raise ValueError("parallel_instances must be between 1 and 50")
        return v
```

---

## 7. Quick Reference — What Changes Where

```
src/
└── fs2/
    ├── cli/
    │   └── scan.py              ← New flags: --no-cross-refs, --cross-refs-instances
    ├── config/
    │   └── objects.py           ← New: CrossFileRelsConfig
    ├── core/
    │   ├── repos/
    │   │   ├── graph_store.py   ← New: get_edges() method on ABC
    │   │   ├── graph_store_impl.py  ← Implement get_edges()
    │   │   └── graph_store_fake.py  ← Implement get_edges()
    │   └── services/
    │       ├── stages/
    │       │   └── NEW: cross_file_rels_stage.py
    │       └── scan_pipeline.py ← Add CrossFileRelsStage to default stages
    └── mcp/
        └── server.py            ← get_node adds relationships to output
```

---

## Open Questions

### Q1: Should `relationships` be at both min and max detail?

**RESOLVED**: Yes. Relationships are the primary output of this feature. Omitting them at `min` detail would make the feature invisible to agents using default settings. The field is compact (list of node_id strings) and only present when edges exist.

### Q2: Should we add a `--cross-refs` flag (positive form)?

**RESOLVED**: No. Follow existing convention — `--no-smart-content` and `--no-embeddings` are the patterns. The feature is on by default, you opt out with `--no-cross-refs`. There's no need for `--cross-refs` since it's the default.

### Q3: Should relationships include edge metadata (call_name, etc.)?

**RESOLVED**: Not in v1. Keep it to `referenced_by: [node_ids]`. The node_ids are enough for agents to follow the chain. If they need the call expression text, they can read the source. This keeps the output compact.

### Q4: Should `tree --detail max` show a ref count?

**OPEN**: Could add `(3 refs)` after the line range in tree max detail. Low cost, useful signal. Deferred to implementation — easy to add if it feels right.
