# Workshop: SCIP Cross-Language Standardisation

**Type**: Integration Pattern
**Plan**: 038-scip-cross-file-rels
**Spec**: [cross-file-rels-spec.md](../cross-file-rels-spec.md)
**Created**: 2026-03-16
**Status**: Draft

**Related Documents**:
- [scip-exploration.md](../scip-exploration.md) — Empirical output comparison across 4 languages
- [001-scip-language-boot.md](001-scip-language-boot.md) — Per-language boot requirements
- [001-edge-storage.md](001-edge-storage.md) — How edges are stored in the fs2 graph

---

## Purpose

Define the standardisation layer between raw SCIP indexer output and fs2's internal cross-file edge format. Each SCIP indexer produces the same protobuf schema but with language-specific symbol naming, descriptor conventions, and edge density. This workshop specifies exactly what the `SCIPAdapterBase` must normalise so that downstream code (graph storage, MCP output, reports) never sees language-specific differences.

## Key Questions Addressed

- What's universal across all SCIP indexers vs what varies?
- How do we map SCIP symbols to fs2 `node_id` values?
- How do we deduplicate edges (same symbol referenced multiple times)?
- What do we filter out (stdlib, local symbols, self-references)?
- What's the adapter inheritance hierarchy?
- How does the base adapter parse SCIP protobuf?

---

## Empirical Findings: What's Universal vs What Varies

### ✅ Universal (handled by SCIPAdapterBase)

| Aspect | Format | Notes |
|--------|--------|-------|
| **Protobuf schema** | `scip.Index` → `Metadata` + `Document[]` | Identical binary format |
| **Document structure** | `relative_path` + `occurrences[]` | All languages populate both |
| **Occurrence structure** | `range` + `symbol` + `symbol_roles` | Identical fields |
| **Range format** | `[line, col_start, col_end]` or `[l1, c1, l2, c2]` | 0-indexed, standard |
| **SymbolRoles bitmask** | `1=Definition`, `8=ReadAccess/Import` | Standard across all |
| **Local symbols** | `local N` (file-scoped) | Skip for cross-file analysis |
| **Symbol string format** | `<scheme> <manager> <pkg> <version> <descriptor>` | 5-part, space-separated |
| **Descriptor suffixes** | `/` pkg, `#` type, `.` field, `().` method | Standard SCIP spec |
| **Cross-file edge algorithm** | Match def-symbol in file A with ref-symbol in file B | **Identical for all** |

### ⚠️ Varies (handled by per-language SCIPLanguageAdapter)

| Aspect | Python | TypeScript | Go | C# |
|--------|--------|-----------|-----|-----|
| **Scheme** | `scip-python` | `scip-typescript` | `scip-go` | `scip-dotnet` |
| **Manager** | `python` | `npm` | `gomod` | `nuget` |
| **Package** | project name | `.` (local) | module path | `.` (local) |
| **Version** | `0.1.0` | `.` (local) | commit hash | `.` (local) |
| **Language field** | `""` (empty) | `""` (empty) | `"go"` | `"C#"` |
| **Module path in descriptor** | `` `dotted.module.path` `` | `` `file.ts` `` | `` `full/import/path` `` | `Namespace` |
| **Docs in index** | 3 (source files only) | 3 (source files only) | 3 (source files only) | 6 (includes generated) |
| **Edge density** | Low (9 edges / 3 files) | Medium (34) | High (58) | Medium (27) |
| **Parameter symbols** | Yes `(param)` | No | No | No |
| **Init symbols** | Yes `__init__:` | No | No | No |

---

## Adapter Architecture

### Class Hierarchy

```
SCIPAdapterBase (ABC)
│   Owns: protobuf parsing, edge extraction, deduplication, filtering
│   Does NOT own: indexer invocation, project validation
│
├── SCIPPythonAdapter
│   Overrides: symbol_to_node_id(), indexer-specific quirks
│
├── SCIPTypeScriptAdapter
│   Overrides: symbol_to_node_id(), tsconfig handling
│
├── SCIPGoAdapter
│   Overrides: symbol_to_node_id(), module path resolution
│
├── SCIPDotNetAdapter
│   Overrides: symbol_to_node_id(), namespace mapping
│
├── SCIPJavaAdapter (future)
│
├── SCIPRustAdapter (future)
│
└── SCIPFakeAdapter (testing)
    Implements: set_edges() for test injection
```

### Where Each Layer Lives

```
src/fs2/core/adapters/
├── scip_adapter.py              # SCIPAdapterBase ABC
├── scip_adapter_python.py       # Python-specific
├── scip_adapter_typescript.py   # TypeScript/JS-specific
├── scip_adapter_go.py           # Go-specific
├── scip_adapter_dotnet.py       # C#/.NET-specific
├── scip_adapter_fake.py         # Test double
└── exceptions.py                # + SCIPAdapterError hierarchy
```

---

## SCIPAdapterBase: The Standardisation Layer

### Core Responsibilities

```python
class SCIPAdapterBase(ABC):
    """Base adapter that standardises SCIP output for fs2.

    Subclasses only override:
    1. symbol_to_node_id() — map SCIP symbol string to fs2 node_id
    2. language_name() — return language identifier
    3. should_skip_document() — filter generated/unwanted files
    """

    # ── Public API (called by CrossFileRelsStage) ──────────

    def extract_cross_file_edges(
        self,
        index_path: str,
        known_node_ids: set[str],
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """Parse index.scip and return fs2 edge tuples.

        Returns:
            List of (source_node_id, target_node_id, {"edge_type": "references"})
            where both source and target exist in known_node_ids.
        """
        index = self._load_index(index_path)
        raw_edges = self._extract_raw_edges(index)
        mapped_edges = self._map_to_node_ids(raw_edges, known_node_ids)
        deduped = self._deduplicate(mapped_edges)
        return deduped

    # ── Protobuf parsing (universal) ───────────────────────

    def _load_index(self, path: str) -> scip_pb2.Index:
        """Load and parse .scip protobuf file."""
        index = scip_pb2.Index()
        with open(path, "rb") as f:
            index.ParseFromString(f.read())
        return index

    def _extract_raw_edges(
        self, index: scip_pb2.Index
    ) -> list[tuple[str, str, str]]:
        """Extract (ref_file, def_file, symbol) triples.

        Algorithm (universal across all languages):
        1. Walk all documents + occurrences
        2. Build definitions map: symbol → file
        3. Build references map: symbol → [files]
        4. Yield edges where ref_file ≠ def_file
        """
        definitions: dict[str, str] = {}   # symbol → relative_path
        references: dict[str, list[str]] = {}  # symbol → [relative_paths]

        for doc in index.documents:
            if self.should_skip_document(doc):
                continue
            rel_path = doc.relative_path

            for occ in doc.occurrences:
                sym = occ.symbol

                # Skip file-scoped local symbols
                if sym.startswith("local "):
                    continue

                if occ.symbol_roles & 1:  # Definition bit
                    definitions[sym] = rel_path
                else:
                    references.setdefault(sym, []).append(rel_path)

        edges = []
        for sym, ref_files in references.items():
            if sym in definitions:
                def_file = definitions[sym]
                for ref_file in ref_files:
                    if ref_file != def_file:
                        edges.append((ref_file, def_file, sym))
        return edges

    # ── Symbol → node_id mapping (per-language override) ───

    @abstractmethod
    def symbol_to_node_id(
        self, symbol: str, file_path: str
    ) -> str | None:
        """Map a SCIP symbol + file to an fs2 node_id.

        This is the KEY standardisation point. Each language's
        symbol naming convention must be translated to fs2's
        node_id format: "category:relative_path:SymbolName"

        Returns None if the symbol cannot be mapped.
        """
        ...

    # ── Filtering (per-language override) ──────────────────

    def should_skip_document(self, doc) -> bool:
        """Override to skip generated/unwanted documents.

        Default: skip nothing. C# overrides to skip
        GlobalUsings.g.cs and similar generated files.
        """
        return False

    # ── Deduplication (universal) ──────────────────────────

    def _deduplicate(
        self, edges: list[tuple[str, str, dict]]
    ) -> list[tuple[str, str, dict]]:
        """Remove duplicate edges (same source→target pair)."""
        seen: set[tuple[str, str]] = set()
        result = []
        for src, tgt, data in edges:
            key = (src, tgt)
            if key not in seen:
                seen.add(key)
                result.append((src, tgt, data))
        return result
```

---

## Symbol-to-Node-ID Mapping: The Critical Standardisation

This is where language-specific differences concentrate. Each adapter must translate SCIP's symbol string + file path into fs2's `node_id` format.

### fs2 node_id Format

```
category:relative_path:SymbolName
```

Examples:
```
callable:src/fs2/core/services/scan_service.py:ScanService.scan
class:src/fs2/core/models/code_node.py:CodeNode
file:src/fs2/core/models/code_node.py
```

### SCIP Symbol → fs2 node_id Translation

#### Python

```
SCIP symbol:
  scip-python python my-project 0.1.0 `my_project.services.scan_service`/ScanService#scan().

Parsing:
  descriptor = `my_project.services.scan_service`/ScanService#scan().
  module_path = my_project.services.scan_service → src/my_project/services/scan_service.py
  class_name = ScanService (from #)
  method_name = scan (from ().)

fs2 node_id:
  callable:src/my_project/services/scan_service.py:ScanService.scan
```

**Python adapter logic**:
```python
def symbol_to_node_id(self, symbol: str, file_path: str) -> str | None:
    parsed = self._parse_symbol(symbol)
    if not parsed:
        return None

    descriptor = parsed["descriptor"]

    # Extract symbol name from descriptor
    # Pattern: `module.path`/Class#method().
    name_parts = []
    for segment in descriptor.split("/"):
        segment = segment.strip("`")
        if "#" in segment:
            # Class: "ClassName#" or "ClassName#method()."
            class_part, rest = segment.split("#", 1)
            if class_part:
                name_parts.append(class_part)
            if rest:
                method = rest.rstrip("().")
                if method:
                    name_parts.append(method)
        elif segment.endswith("()."):
            # Function: "func_name()."
            name_parts.append(segment.rstrip("()."))

    if not name_parts:
        return None

    symbol_name = ".".join(name_parts)
    # Try both callable: and class: categories
    for category in ("callable", "class", "type"):
        candidate = f"{category}:{file_path}:{symbol_name}"
        if candidate in self._known_ids:
            return candidate
    return None
```

#### TypeScript

```
SCIP symbol:
  scip-typescript npm . . `service.ts`/TaskService#addTask().

Parsing:
  descriptor = `service.ts`/TaskService#addTask().
  file = service.ts (from backtick-quoted segment)
  class = TaskService (from #)
  method = addTask (from ().)

fs2 node_id:
  callable:service.ts:TaskService.addTask
```

#### Go

```
SCIP symbol:
  scip-go gomod example.com/taskapp hash `example.com/taskapp/service`/TaskService#AddTask().

Parsing:
  descriptor = `example.com/taskapp/service`/TaskService#AddTask().
  package_path = example.com/taskapp/service → service/ (strip module prefix)
  type = TaskService (from #)
  method = AddTask (from ().)

fs2 node_id:
  callable:service/service.go:TaskService.AddTask
```

**Go-specific challenge**: SCIP uses import paths, not file paths. The adapter must resolve import path → file path using the project's package structure.

#### C#

```
SCIP symbol:
  scip-dotnet nuget . . TaskApp/TaskService#AddTask().

Parsing:
  descriptor = TaskApp/TaskService#AddTask().
  namespace = TaskApp (from /)
  class = TaskService (from #)
  method = AddTask (from ().)

fs2 node_id:
  callable:Service.cs:TaskService.AddTask
```

**C#-specific challenge**: SCIP uses namespace paths, not file paths. The adapter must resolve namespace → file path using the index's `Document.relative_path`.

---

## Edge Filtering Rules (Universal)

All adapters apply these filters through `SCIPAdapterBase`:

```python
def _map_to_node_ids(
    self,
    raw_edges: list[tuple[str, str, str]],
    known_node_ids: set[str],
) -> list[tuple[str, str, dict]]:
    """Map raw SCIP edges to fs2 edges, filtering unknowns."""
    result = []
    for ref_file, def_file, symbol in raw_edges:
        # 1. Skip stdlib/external symbols
        #    (these won't map to any known_node_id anyway)

        # 2. Map SCIP symbol to fs2 node_id
        source_id = self._file_to_node_id(ref_file, known_node_ids)
        target_id = self.symbol_to_node_id(symbol, def_file)

        # 3. Skip if either side doesn't exist in graph
        if not source_id or source_id not in known_node_ids:
            continue
        if not target_id or target_id not in known_node_ids:
            continue

        # 4. Skip self-references
        if source_id == target_id:
            continue

        # 5. Skip containment edges (parent→child already in graph)
        #    These are file→class or class→method — already edges
        # (handled by checking edge_type in graph store)

        result.append((source_id, target_id, {"edge_type": "references"}))
    return result
```

### What Gets Filtered Out

| Filter | Reason | Example |
|--------|--------|---------|
| `local N` symbols | File-scoped, no cross-file meaning | `local 0`, `local 14` |
| Stdlib symbols | Not in our graph | `scip-python python python-stdlib 3.11 builtins/str#` |
| External package symbols | Not in our graph | `scip-go gomod github.com/golang/go/src go1.22 fmt/` |
| Self-references | Noise | Function referencing itself |
| Unmapped symbols | Can't find in fs2 graph | Generated code, macros |
| Duplicate edges | Same source→target pair | Multiple refs to same symbol |

---

## Edge Density Normalisation

Different indexers produce different edge counts for equivalent code:

| Language | Raw Edges | After Dedup | After Node Filter | Reason |
|----------|-----------|------------|-------------------|--------|
| Python | 9 | ~6 | ~4 | Conservative — only explicit references |
| TypeScript | 34 | ~15 | ~8 | Includes type references, property accesses |
| Go | 58 | ~20 | ~12 | Includes package-level imports + all usages |
| C# | 27 | ~12 | ~6 | Includes namespace references |

**Key insight**: The deduplication + node filter stages bring all languages to comparable edge counts. The `SCIPAdapterBase` handles this — per-language adapters don't need to worry about it.

---

## Protobuf Dependency Strategy

### Option A: Generated Bindings (Recommended)

```python
# Generate once, commit to repo
# From SCIP proto schema → scip_pb2.py
# pip install protobuf grpcio-tools
# python -m grpc_tools.protoc --python_out=. scip.proto

# Location: src/fs2/core/adapters/scip_pb2.py (generated)
```

**Why**: Single file, no runtime proto compilation, works offline.

### Option B: Runtime Protobuf

```python
# Load proto at runtime — more fragile, needs proto file on disk
from google.protobuf import descriptor_pool
```

**Decision**: **Option A** — generate bindings once, commit `scip_pb2.py`.

### pyproject.toml Addition

```toml
[project]
dependencies = [
    # ... existing deps ...
    "protobuf>=4.25",  # For SCIP index parsing
]
```

---

## Testing Strategy

### SCIPAdapterBase Tests (unit, no indexer needed)

```python
def test_extract_edges_from_protobuf():
    """Build a scip_pb2.Index in memory, verify edge extraction."""
    index = scip_pb2.Index()
    # Add documents with known def/ref symbols
    # Assert correct edges extracted

def test_local_symbols_filtered():
    """Verify 'local N' symbols are skipped."""

def test_self_references_filtered():
    """Verify same-file def+ref doesn't create edge."""

def test_deduplication():
    """Verify duplicate source→target pairs collapsed."""

def test_unknown_nodes_filtered():
    """Verify edges to symbols not in known_node_ids are dropped."""
```

### Per-Language Adapter Tests (unit, with fixture .scip files)

```python
def test_python_symbol_to_node_id():
    """Verify Python SCIP symbol maps to correct fs2 node_id."""
    adapter = SCIPPythonAdapter()
    node_id = adapter.symbol_to_node_id(
        "scip-python python pkg 0.1 `pkg.module`/MyClass#method().",
        "module.py"
    )
    assert node_id == "callable:module.py:MyClass.method"

def test_typescript_symbol_to_node_id():
    """Verify TypeScript SCIP symbol maps to correct fs2 node_id."""

def test_go_symbol_to_node_id():
    """Verify Go SCIP symbol maps — import path → file path."""

def test_dotnet_symbol_to_node_id():
    """Verify C# SCIP symbol maps — namespace → file path."""
```

### Integration Tests (need indexer installed, marked slow)

```python
@pytest.mark.slow
def test_python_fixture_end_to_end():
    """Run scip-python on cross_file_sample, verify edges."""
    # Uses tests/fixtures/cross_file_sample/
    # Runs scip-python, parses index.scip, checks edges match expected

@pytest.mark.slow
def test_typescript_fixture_end_to_end():
    """Run scip-typescript on scripts/scip/fixtures/typescript/."""
```

---

## Migration Path from Serena

### Phase 1: Add SCIP alongside Serena (non-breaking)

```yaml
# .fs2/config.yaml
cross_file_rels:
  provider: serena    # or "scip" — new option
  # Serena config (existing):
  parallel_instances: 15
  serena_base_port: 8330
  # SCIP config (new):
  scip:
    projects:
      - type: python
        path: .
```

### Phase 2: Default to SCIP for new projects

```yaml
cross_file_rels:
  provider: scip    # new default
```

### Phase 3: Deprecate Serena (future)

- Print deprecation warning when `provider: serena`
- Remove in next major version

---

## Open Questions

### Q1: File-level vs symbol-level edges?

**RESOLVED**: Symbol-level when possible (fs2 has `callable:` and `class:` nodes), fall back to `file:` level when symbol can't be resolved. This matches the current Serena approach.

### Q2: Should we store the SCIP symbol string in edge metadata?

**OPEN**: Options:
- **A**: Just `{"edge_type": "references"}` (current approach, minimal)
- **B**: `{"edge_type": "references", "scip_symbol": "scip-python ..."}` (debuggable)
- **C**: `{"edge_type": "references", "ref_kind": "call|import|type"}` (richer semantics)

Option A is simplest and matches current Serena. Option B helps debugging. Option C requires parsing symbol descriptors to infer kind.

### Q3: One index.scip per project or merged?

**RESOLVED**: One `index.scip` per project. Each language adapter runs its indexer against one project root, producing one index file. The `CrossFileRelsStage` iterates over configured projects.

### Q4: Where to store index.scip files?

**OPEN**: Options:
- **A**: `.fs2/scip/{project-slug}/index.scip` (alongside graph.pickle)
- **B**: Temp directory, deleted after edge extraction
- **C**: In-memory only (stream protobuf, don't save)

Option A enables caching/re-use. Option B is cleanest. Option C is most efficient but can't debug.
