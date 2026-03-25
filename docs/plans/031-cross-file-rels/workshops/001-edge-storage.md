# Workshop: Edge Storage for Cross-File Relationships

**Type**: Storage Design
**Plan**: 031-cross-file-rels
**Spec**: [exploration.md](../exploration.md)
**Created**: 2026-03-12
**Status**: Draft

**Related Documents**:
- [Exploration](../exploration.md) — FastCode reference analysis

---

## Purpose

Design how cross-file relationship edges (calls, imports, inheritance) are stored in the fs2 graph alongside existing parent-child containment edges. This drives decisions about graph type, edge format, GraphStore ABC changes, pipeline ordering, and how consumers query relationships.

## Key Questions Addressed

- DiGraph (one edge per pair) vs MultiDiGraph (parallel edges)?
- How are edges typed and what metadata do they carry?
- How does the pipeline sequence ensure all nodes exist before edges are created?
- How does GraphStore ABC evolve without breaking existing consumers?
- How are relationships surfaced through `get_node`, `tree`, and MCP tools?

---

## Overview

Today the fs2 graph is a **forest of containment trees**:

```
file:src/foo.py
├── type:src/foo.py:MyClass
│   ├── callable:src/foo.py:MyClass.__init__
│   └── callable:src/foo.py:MyClass.do_thing    ← LEAF (no outgoing edges)
└── callable:src/foo.py:helper
```

After this feature, the same graph gains **cross-file edges**:

```
file:src/foo.py
├── type:src/foo.py:MyClass
│   ├── callable:src/foo.py:MyClass.__init__
│   │   └── ──calls──▶ callable:src/utils.py:validate
│   └── callable:src/foo.py:MyClass.do_thing
│       └── ──calls──▶ callable:src/bar.py:process
├── callable:src/foo.py:helper
└── ──imports──▶ file:src/utils.py
```

---

## Decision 1: DiGraph with Typed Edges (not MultiDiGraph)

### The Problem

networkx `DiGraph` allows **one edge per (u, v) pair**. A second `add_edge(u, v)` **overwrites** the first. `MultiDiGraph` allows parallel edges but changes the API surface.

### Analysis

```python
# DiGraph: second call OVERWRITES first
g = nx.DiGraph()
g.add_edge('A', 'B', edge_type='child_of')
g.add_edge('A', 'B', edge_type='calls')  # ← child_of is LOST

# MultiDiGraph: both survive
g = nx.MultiDiGraph()
g.add_edge('A', 'B', edge_type='child_of')  # key=0
g.add_edge('A', 'B', edge_type='calls')     # key=1
```

### Can parent-child and cross-file edges collide?

Containment edges go **parent → child** (file → class → method). Cross-file edges go **caller → callee** across files. The question: can a node be both the containment parent of AND the caller of the same target?

```python
# Scenario: file imports its own submodule AND calls it
# file:src/pkg/__init__.py → file:src/pkg/utils.py  (child_of)
# file:src/pkg/__init__.py → file:src/pkg/utils.py  (imports)
```

This is **possible** but **rare**. Parent-child edges today are between file→class→method (containment hierarchy). Import/call edges are between functions in different files. The overlap case is `__init__.py` importing a sibling module that's also represented as a child — unlikely with fs2's flat file model (files aren't children of other files).

### Decision: **Stay with DiGraph**

| Factor | DiGraph | MultiDiGraph |
|--------|---------|--------------|
| Existing code compatibility | ✅ Zero changes | ❌ All `get_children`, `get_parent`, `predecessors`, `successors` break |
| Pickle compatibility | ✅ Same module whitelist | ❌ Must add `networkx.classes.multidigraph` |
| API simplicity | ✅ `g.edges[u, v]` returns dict | ❌ `g.edges[u, v, key]` adds key dimension |
| Performance | ✅ O(1) edge lookup | ⚠️ O(k) where k = parallel edges |
| Collision risk | ⚠️ Overwrites on same (u,v) pair | ✅ No collisions |
| Pickle size | ✅ Baseline | ⚠️ ~1.2x larger |

**Why this is safe**: Parent-child edges are `parent → child` (downward in containment tree). Cross-file edges are between nodes in **different subtrees** (different files). The same (u, v) pair won't have both a parent-child edge and a cross-file edge because:
1. Parent-child edges connect file→class→method within one file
2. Cross-file edges connect callable→callable across files
3. If a theoretical collision exists, the cross-file edge is more valuable (containment is recoverable from `parent_node_id`)

**Mitigation**: If we ever hit a collision, the edge data includes `edge_type` — we could detect and log it. A future migration to MultiDiGraph is straightforward.

---

## Decision 2: Edge Data Schema

### Edge Types

Every edge carries an `edge_type` attribute. Existing parent-child edges get no attribute (backward compatible — `edge_type` defaults to `None`/absent).

```python
# Existing parent-child edge (NO CHANGE to current behavior)
graph.add_edge(parent_id, child_id)
# edge data: {}  (empty — backward compatible)

# New cross-file edges
graph.add_edge(source_id, target_id, edge_type="calls", ...)
graph.add_edge(source_id, target_id, edge_type="imports", ...)
graph.add_edge(source_id, target_id, edge_type="inherits", ...)
```

### Edge Metadata by Type

```python
# "calls" edge — function/method calls another function/method
{
    "edge_type": "calls",
    "call_name": "validate",           # name at call site
    "call_type": "simple",             # "simple" | "attribute" | "method"
}

# "imports" edge — file imports another file
{
    "edge_type": "imports",
    "module": "utils",                 # import target
    "level": 0,                        # 0=absolute, 1+=relative
}

# "inherits" edge — class extends another class
{
    "edge_type": "inherits",
    "base_name": "BaseClass",          # name in source code
}
```

### Why Minimal Metadata

FastCode stores `resolution_method`, `node_text`, `file_path`, etc. on edges. We keep it minimal because:
1. Both endpoints are full CodeNode objects — everything is queryable from the nodes
2. Edge metadata inflates pickle size (multiplied by edge count)
3. `call_name`/`module`/`base_name` is enough to understand the relationship at a glance
4. Resolution method is a debugging concern, not a consumer concern

---

## Decision 3: Pipeline Sequence

### The Constraint

Cross-file edges require **all nodes to exist first**. You can't create an edge `A → B` if B hasn't been parsed yet. This means relationship extraction must happen **after** all files are parsed.

### Current Pipeline

```
Discovery → Parsing → SmartContent → Embedding → Storage
```

### New Pipeline

```
Discovery → Parsing → CrossFileRels → SmartContent → Embedding → Storage
```

### Why After Parsing, Before SmartContent

```
┌──────────────┐     ┌──────────┐     ┌──────────────┐     ┌──────────────┐
│  Discovery   │ ──▶ │ Parsing  │ ──▶ │ CrossFileRels │ ──▶ │ SmartContent │ ──▶ ...
│              │     │          │     │               │     │              │
│ finds files  │     │ produces │     │ ALL nodes     │     │ can reference│
│              │     │ CodeNodes│     │ exist; create │     │ relationships│
│              │     │          │     │ edges between │     │ in summaries │
│              │     │          │     │ them          │     │              │
└──────────────┘     └──────────┘     └───────────────┘     └──────────────┘
```

1. **After Parsing** — all nodes exist in `context.nodes`
2. **Before SmartContent** — smart content can reference "this function is called by X" (future enhancement)
3. **Before Embedding** — embeddings don't need relationship info
4. **Before Storage** — edges are created in-memory, then persisted together

### CrossFileRelsStage Design

```python
class CrossFileRelsStage(PipelineStage):
    """Pipeline stage that creates cross-file relationship edges.
    
    Requires all nodes to exist (runs after ParsingStage).
    Creates edges in-memory for StorageStage to persist.
    """
    
    @property
    def name(self) -> str:
        return "cross_file_rels"
    
    def process(self, context: PipelineContext) -> PipelineContext:
        # 1. Build index: node_id → CodeNode, file_path → [nodes]
        # 2. For Python files: extract imports, calls, definitions
        # 3. Resolve symbols across files
        # 4. Create edges in context (not in graph_store yet)
        # 5. Record metrics
        return context
```

### Where Are Edges Stored During Pipeline?

**Option A**: Add edges directly to `context.graph_store` (current `add_edge` pattern)
- ❌ StorageStage calls `clear()` then rebuilds — our edges would be lost

**Option B**: Accumulate edges in `context` and let StorageStage write them
- ✅ Consistent with how nodes flow through the pipeline
- Need to add `context.edges: list[tuple[str, str, dict]]` to PipelineContext

**Decision: Option B** — Add `cross_file_edges` to PipelineContext:

```python
@dataclass
class PipelineContext:
    # ... existing fields ...
    
    # Cross-file relationship edges (populated by CrossFileRelsStage)
    # Each tuple: (source_id, target_id, edge_data_dict)
    cross_file_edges: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)
```

StorageStage then writes these after parent-child edges:

```python
class StorageStage:
    def process(self, context):
        # ... existing node + parent-child edge code ...
        
        # NEW: Write cross-file relationship edges
        cross_file_count = 0
        for source_id, target_id, edge_data in context.cross_file_edges:
            if source_id in [n.node_id for n in context.nodes] and \
               target_id in [n.node_id for n in context.nodes]:
                context.graph_store.add_edge(source_id, target_id, **edge_data)
                cross_file_count += 1
        
        context.metrics["storage_cross_file_edges"] = cross_file_count
```

---

## Decision 4: GraphStore ABC Changes

### New Methods

The GraphStore ABC needs methods to query relationships by type. The key design question: specific methods (`get_callers`, `get_callees`) vs generic (`get_edges_by_type`)?

**Decision: Start generic, add convenience later.**

```python
class GraphStore(ABC):
    # ... existing methods ...
    
    @abstractmethod
    def add_edge(self, parent_id: str, child_id: str, **edge_data: Any) -> None:
        """Add an edge between two nodes with optional metadata.
        
        For parent-child containment: add_edge(parent, child)
        For cross-file: add_edge(source, target, edge_type="calls", ...)
        
        Args:
            parent_id: Source node ID.
            child_id: Target node ID.
            **edge_data: Optional edge attributes (edge_type, call_name, etc.)
        """
        ...
    
    @abstractmethod
    def get_edges(
        self,
        node_id: str,
        direction: str = "outgoing",
        edge_type: str | None = None,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Get edges connected to a node, optionally filtered by type.
        
        Args:
            node_id: The node to query edges for.
            direction: "outgoing" (successors), "incoming" (predecessors), or "both".
            edge_type: Filter to specific edge type (e.g., "calls", "imports").
                       None returns all edges.
        
        Returns:
            List of (connected_node_id, edge_data) tuples.
        """
        ...
```

### Backward Compatibility

The existing `add_edge(parent_id, child_id)` signature is preserved — `**edge_data` is optional. Existing callers (StorageStage) don't pass edge data, so nothing breaks.

The `get_children` and `get_parent` methods remain unchanged — they return ALL successors/predecessors regardless of edge type. This is correct because:
- `get_children` is used by TreeService to build containment trees
- Cross-file edges point to nodes in **other files**, so they won't appear in a file's containment tree
- The new `get_edges(direction="incoming", edge_type="calls")` is how you'd specifically query callers

### Implementation in NetworkXGraphStore

```python
def add_edge(self, parent_id: str, child_id: str, **edge_data: Any) -> None:
    if parent_id not in self._graph:
        raise GraphStoreError(f"Node not found: {parent_id}")
    if child_id not in self._graph:
        raise GraphStoreError(f"Node not found: {child_id}")
    self._graph.add_edge(parent_id, child_id, **edge_data)

def get_edges(
    self,
    node_id: str,
    direction: str = "outgoing",
    edge_type: str | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    if node_id not in self._graph:
        return []
    
    results = []
    
    if direction in ("outgoing", "both"):
        for succ in self._graph.successors(node_id):
            data = dict(self._graph.edges[node_id, succ])
            if edge_type is None or data.get("edge_type") == edge_type:
                results.append((succ, data))
    
    if direction in ("incoming", "both"):
        for pred in self._graph.predecessors(node_id):
            data = dict(self._graph.edges[pred, node_id])
            if edge_type is None or data.get("edge_type") == edge_type:
                results.append((pred, data))
    
    return results
```

### Performance Characteristics

Benchmarked on a DiGraph with 1000 nodes:

| Operation | Time | Notes |
|-----------|------|-------|
| `predecessors(n)` + filter | 0.19µs per call | O(in-degree) — fast |
| Full edge scan with filter | 10ms per 1000 edges | Only needed for global queries |
| `get_edges(n, "incoming", "calls")` | O(in-degree of n) | Typical: 1-5 predecessors |

This is fast enough. No index needed for typical query patterns.

---

## Decision 5: Surfacing Relationships

### In `get_node` (MCP tool)

When detail is `"max"`, include relationship edges:

```python
def _code_node_to_dict(node, detail, graph_store=None):
    result = {
        "node_id": node.node_id,
        "name": node.name,
        # ... existing fields ...
    }
    
    if detail == "max" and graph_store is not None:
        # Add relationship edges
        edges = graph_store.get_edges(node.node_id, direction="both")
        if edges:
            # Group by direction and type
            incoming = {}
            outgoing = {}
            for connected_id, data in edges:
                edge_type = data.get("edge_type")
                if edge_type:  # Skip parent-child (no edge_type)
                    # Determine direction
                    # ... group into incoming/outgoing by edge_type
                    pass
            
            if incoming:
                result["incoming_edges"] = incoming
            if outgoing:
                result["outgoing_edges"] = outgoing
    
    return result
```

Example output:

```json
{
    "node_id": "callable:src/fs2/core/services/tree_service.py:TreeService.build_tree",
    "name": "build_tree",
    "category": "callable",
    "content": "...",
    "signature": "def build_tree(self, ...) -> list[TreeNode]:",
    "start_line": 89,
    "end_line": 165,
    "smart_content": "Builds a filtered tree of TreeNode objects from the graph...",
    "language": "python",
    "parent_node_id": "type:src/fs2/core/services/tree_service.py:TreeService",
    "incoming_edges": {
        "calls": [
            "callable:src/fs2/mcp/server.py:tree"
        ]
    },
    "outgoing_edges": {
        "calls": [
            "callable:src/fs2/core/repos/graph_store.py:GraphStore.get_all_nodes",
            "callable:src/fs2/core/services/tree_service.py:TreeService._filter_nodes"
        ]
    }
}
```

### In `tree` (MCP tool)

Tree output stays focused on containment hierarchy. Cross-file edges are NOT shown in tree — they're a property of individual nodes, queried via `get_node`.

**Rationale**: Tree is about structure. Relationships are about behavior. Mixing them makes tree output noisy and confusing.

### Future: Dedicated `get_edges` MCP tool

If consumers need to walk call trees or trace dependencies, a dedicated tool would be more ergonomic than overloading `get_node`:

```python
# Future MCP tool
get_edges(node_id="callable:src/foo.py:main", edge_type="calls", direction="outgoing")
```

This is out of scope for the initial implementation but the GraphStore API supports it.

---

## Decision 6: Graph Format Version

### Current Format

```python
# v1.0 — pickle tuple
(metadata, nx.DiGraph)
```

### New Format

Same format, but bump version to signal that cross-file edges may be present:

```python
FORMAT_VERSION = "1.1"  # Was "1.0"
```

**Why 1.1 not 2.0**: The format is identical — it's still `(metadata, DiGraph)`. The only change is that edges may now carry `edge_type` attributes. Old code reading a 1.1 graph will still work — it just won't know about edge types. The existing version mismatch warning is sufficient.

---

## Edge Creation Flow (End-to-End)

```
1. ParsingStage produces CodeNodes
   └── context.nodes = [file:a.py, callable:a.py:foo, file:b.py, callable:b.py:bar, ...]

2. CrossFileRelsStage runs
   ├── Builds node index: {node_id → CodeNode, file_path → [nodes]}
   ├── For each file node:
   │   ├── Gets source code from node.content
   │   ├── Extracts imports (tree-sitter)  → [{module: "b", names: ["bar"], ...}]
   │   ├── Extracts calls (tree-sitter)    → [{call_name: "bar", scope_id: "function::foo", ...}]
   │   └── Extracts definitions            → [{name: "foo", type: "function", ...}]
   ├── Builds global symbol index
   │   ├── module_map: {"a" → "file:a.py", "b" → "file:b.py"}
   │   └── export_map: {"a" → {"foo": "callable:a.py:foo"}, "b" → {"bar": "callable:b.py:bar"}}
   ├── Resolves relationships
   │   ├── foo() calls bar() → resolve "bar" via imports → "callable:b.py:bar"
   │   └── a.py imports b   → resolve "b" → "file:b.py"
   └── Creates edges in context
       ├── context.cross_file_edges.append(("callable:a.py:foo", "callable:b.py:bar", {"edge_type": "calls", "call_name": "bar"}))
       └── context.cross_file_edges.append(("file:a.py", "file:b.py", {"edge_type": "imports", "module": "b"}))

3. SmartContent + Embedding stages run (unchanged)

4. StorageStage writes everything
   ├── add_node() for all nodes
   ├── add_edge(parent, child) for containment (existing)
   └── add_edge(src, tgt, **data) for cross-file edges (NEW)
```

---

## Open Questions

### Q1: Should `get_children` filter out cross-file edges?

**RESOLVED**: No. `get_children` returns successors, which for containment trees are children. Cross-file edges point to nodes in other files, so they won't appear in a single file's containment tree. The only theoretical collision case (file importing a child module) is handled by the DiGraph single-edge-per-pair rule — and in that case the parent-child relationship is the one already stored. See Decision 1 for analysis.

### Q2: Should we re-parse files in CrossFileRelsStage or reuse existing ASTs?

**RESOLVED**: Re-parse. The AST is not stored between stages (ParsingStage produces CodeNodes, not ASTs). Re-parsing Python files is cheap (~1-5ms per file). The CrossFileRelsStage uses its own tree-sitter queries (import/call extraction) which are different from the structural parsing queries.

### Q3: What about TypeScript, Go, etc.?

**OPEN**: Initial implementation is Python-only. The CrossFileRelsStage should check `node.language == "python"` and skip others. The extractor/resolver interfaces should be designed for language extensibility (e.g., `ImportExtractor` ABC with `PythonImportExtractor` impl), but only Python is implemented in v1.

### Q4: How do we handle unresolved symbols?

**RESOLVED**: Skip them. If a call can't be resolved (third-party library, dynamic dispatch, metaprogramming), no edge is created. This matches FastCode's approach. We log at debug level for diagnostics. The graph shows what we can confidently link, not everything.

### Q5: What about intra-file call edges?

**RESOLVED**: Yes, include them. If `foo()` calls `bar()` in the same file, that's a valid "calls" edge. The name "cross-file" is about the capability (linking across files), but intra-file calls are equally valuable for call tree walking. These won't collide with parent-child edges because containment is file→class→method, not function→function.

---

## Summary of Decisions

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Graph type | DiGraph (keep current) | No breaking changes, collision risk minimal |
| 2 | Edge schema | `edge_type` + minimal metadata | Endpoints carry full data, edges are lightweight |
| 3 | Pipeline position | After Parsing, before SmartContent | All nodes must exist; edges flow via context |
| 4 | GraphStore changes | Add `**edge_data` to `add_edge`, add `get_edges()` | Backward compatible, generic interface |
| 5 | Surfacing | `get_node` max detail includes edges | Tree stays structural, get_node shows relationships |
| 6 | Format version | 1.0 → 1.1 | Same format, edges may carry attributes |
