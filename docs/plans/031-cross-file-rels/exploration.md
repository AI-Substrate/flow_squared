# Exploration: Cross-File Relationships (031)

## Goal
Add cross-file relationship edges to the fs2 graph so that when you `get_node` you can see what calls it (callers) and what it calls (callees) — enabling call tree walking, dependency tracing, and impact analysis.

## Current fs2 Architecture

### How the Graph Works Today

1. **ScanPipeline** orchestrates: Discovery → Parsing → SmartContent → Embedding → Storage
2. **ParsingStage** calls `ASTParser.parse(path)` per file → produces `CodeNode` objects
3. **StorageStage** adds nodes to `GraphStore`, then creates **parent-child edges** using `node.parent_node_id`
4. **GraphStore** (ABC → `NetworkXGraphStore`) stores a `networkx.DiGraph` with:
   - Nodes keyed by `node_id` with `data=CodeNode`
   - Edges are **only parent→child** containment (file→class→method)
5. **No cross-file edges exist today** — the graph is a forest of trees (files as roots)

### Key Models

- **CodeNode** (frozen dataclass, ~30 fields): `node_id`, `category`, `name`, `qualified_name`, `content`, `signature`, `parent_node_id`, embeddings, etc.
- **node_id format**: `{category}:{file_path}:{qualified_name}` (e.g., `callable:src/foo.py:MyClass.do_thing`)
- **Categories**: `file`, `callable`, `type`, `section`, `block`, `definition`, `other`

### What's Missing

The graph has containment (parent→child) but no cross-file references:
- No import tracking
- No call edges (who calls what)
- No inheritance edges (class hierarchy)
- No dependency edges (file A imports file B)

## FastCode Reference Implementation

FastCode has a mature cross-file relationship system with:

### Architecture (5 key components)

1. **ImportExtractor** (`import_extractor.py`) — Tree-sitter query-based
   - Extracts import statements from Python code
   - Returns dicts: `{module, names, alias, level}` 
   - Handles absolute, relative, aliased, wildcard imports

2. **DefinitionExtractor** (`definition_extractor.py`) — Tree-sitter query-based
   - Extracts class/function definitions with positions
   - Tracks parent relationships (methods within classes)
   - Extracts class bases for inheritance

3. **CallExtractor** (`call_extractor.py`) — Tree-sitter query-based
   - Extracts function calls with **scope tracking** (which function/class contains the call)
   - Distinguishes: `simple` (func()), `attribute` (obj.method()), method calls
   - Extracts instance variable types for enhanced resolution
   - Filters builtins

4. **GlobalIndexBuilder** (`global_index_builder.py`)
   - Builds lookup maps: `file_map` (path→id), `module_map` (dotted.path→id), `export_map` (module→{symbol→id})
   - Enables O(1) symbol resolution

5. **SymbolResolver** (`symbol_resolver.py`)
   - Resolves symbol names to definition IDs
   - Two strategies: local (current file) → imported (via imports)
   - Handles: direct imports, aliases, module prefixes, Class.Method lookups

6. **ModuleResolver** (`module_resolver.py`)
   - Resolves import references to file IDs
   - Handles relative and absolute imports
   - Returns None for third-party (external) modules

7. **CodeGraphBuilder** (`graph_builder.py`) — Orchestrator
   - Builds 3 separate networkx DiGraphs: `dependency_graph`, `inheritance_graph`, `call_graph`
   - Uses all of the above extractors/resolvers
   - Produces edges with metadata (type, call_name, resolution_method, etc.)

### FastCode Graph Types

| Graph | Nodes | Edges | Metadata |
|-------|-------|-------|----------|
| dependency_graph | files | file→file | type="imports", module, level |
| inheritance_graph | classes | child→parent | type="inherits", base_name |
| call_graph | functions/methods/classes | caller→callee | type="calls", call_name, call_type |

### FastCode Querying API
```python
get_dependencies(elem_id)   # files this file imports
get_dependents(elem_id)     # files that import this file
get_subclasses(elem_id)     # classes extending this
get_superclasses(elem_id)   # parent classes
get_callers(elem_id)        # who calls this
get_callees(elem_id)        # what this calls
get_related_elements(id)    # all related within N hops
find_path(source, target)   # shortest path
```

## Key Differences: fs2 vs FastCode

| Aspect | fs2 | FastCode |
|--------|-----|----------|
| Graph library | networkx DiGraph | networkx DiGraph (same!) |
| Node model | CodeNode (frozen dataclass) | CodeElement (mutable) |
| Node ID format | `category:path:name` | `path::parent::name` |
| Tree-sitter | Yes (via ASTParser adapter) | Yes (via TSParser) |
| Edges today | parent→child only | parent→child + imports + calls + inheritance |
| Architecture | Clean Architecture (ABC/impl) | Direct classes |
| Graph count | 1 unified graph | 3 separate graphs |
| Persistence | pickle tuple (metadata, graph) | pickle dict |

## Design Considerations for fs2

### 1. Edge Types — Unified vs Separate Graphs
FastCode uses 3 separate DiGraphs. fs2 should use the **single graph** approach with **typed edges**:
- Already has one DiGraph with parent→child edges
- Add edge attributes: `edge_type="calls"`, `edge_type="imports"`, `edge_type="inherits"`
- This avoids complicating GraphStore with multiple graphs and aligns with current architecture

### 2. What Needs to Change

**GraphStore ABC** — needs cross-file edge methods:
- `add_cross_file_edge(source_id, target_id, edge_type, metadata)` or similar
- `get_callers(node_id)` / `get_callees(node_id)`
- `get_imports(node_id)` / `get_imported_by(node_id)`
- Or: keep `add_edge` generic but add `get_edges_by_type()`

**New Pipeline Stage** — `CrossFileRelStage` between Parsing and SmartContent:
- After all nodes exist, before enrichment
- Extracts imports, calls, definitions per file
- Resolves symbols across files
- Creates cross-file edges in GraphStore

**New Extractors/Resolvers** (adapted from FastCode):
- ImportExtractor (tree-sitter based)
- CallExtractor (tree-sitter based with scope tracking)
- SymbolResolver (local + imported resolution)
- ModuleResolver (import path → file ID resolution)
- GlobalIndexBuilder (lookup maps)

**CodeNode** — potentially add cached relationship fields:
- Or keep edges purely in graph and query on demand

### 3. Surfacing Relationships

When `get_node` returns data, it should include:
```json
{
  "callers": ["callable:src/bar.py:do_work"],
  "callees": ["callable:src/baz.py:Helper.process"],
  "imports": ["file:src/utils.py"],
  "imported_by": ["file:src/main.py"],
  "inherits_from": ["type:src/base.py:BaseClass"],
  "inherited_by": ["type:src/child.py:ChildClass"]
}
```

### 4. Python-Only Initially
FastCode only supports Python. fs2's tree-sitter parser is language-agnostic, but cross-file resolution (imports, modules) is inherently language-specific. Start with Python, design the interface to be language-extensible.

### 5. Scan Performance
FastCode processes all files in one pass per extractor. The new stage should:
- Parse each file once (reuse existing AST if possible)
- Build global index (O(N) files)
- Resolve relationships (O(calls × imports) per file)
- Expect modest overhead for typical codebases

## Open Questions

1. **Edge storage**: Typed edges in the single graph vs separate edge collections?
2. **Incremental updates**: How to update cross-file edges when a single file changes?
3. **Language support**: Python-only first, or design the interface for multi-language from day one?
4. **MCP exposure**: How should `tree`, `search`, `get_node` surface relationship data?
5. **Graph format version**: Bump from 1.0 to 2.0 for backward compatibility?
