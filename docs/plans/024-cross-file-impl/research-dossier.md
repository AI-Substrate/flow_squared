# Research Dossier: Cross-File Relationship Production Implementation

**Generated**: 2026-01-13
**Research Query**: Production implementation of cross-file relationships based on 022 experimentation research
**Mode**: Plan-Associated
**Location**: `docs/plans/024-cross-file-impl/research-dossier.md`
**FlowSpace**: Available
**Findings**: 70+ across 7 research subagents

---

## Executive Summary

### What It Does

Cross-file relationship edges connect nodes in the fs2 graph based on semantic relationships: imports, function calls, type references, documentation links, and raw file references. Each edge has a **confidence score (0.0-1.0)** indicating certainty of the relationship.

### Business Purpose

Enable rapid context discovery for AI agents:
- "What references this file?" - find all documentation, tests, execution logs mentioning code
- "What does this file import?" - understand dependencies
- "What calls this method?" - find call sites across the codebase
- "Where is this documented?" - link code to documentation

### Key Insights

1. **Infrastructure is 80% ready** - NetworkX DiGraph already supports edge attributes; just needs GraphStore ABC extension
2. **Tree-sitter extraction validated** - 100% accuracy for Python/TypeScript imports in 022 experimentation
3. **Two-stage pipeline approach** - RelationshipExtractionStage (post-parsing) + RelationshipStorageStage (pre-storage)
4. **Confidence scoring established** - ChunkMatch pattern for 0.0-1.0 validation with frozen dataclass
5. **Raw filename detection works** - Heuristic approach with 0.4-0.5 confidence implemented in 022

### Quick Stats

| Metric | Value |
|--------|-------|
| Languages validated | 7 (Python, TypeScript, TSX, Go, Java, C, C++) |
| Ground truth accuracy | 67% pass rate, 80% detection rate |
| Import detection accuracy | 100% for Python/TypeScript |
| Node ID detection accuracy | 100% |
| Prior learnings applicable | 15 discoveries from 22 prior plans |

---

## How It Currently Works

### Current Graph Model: Parent-Child Only

**Node ID**: `type:src/fs2/core/repos/graph_store.py:GraphStore`

The current GraphStore ABC defines edges for **structural containment only**:

```python
@abstractmethod
def add_edge(self, parent_id: str, child_id: str) -> None:
    """Add a parent-child edge between two nodes.

    Edge direction: parent → child. This means:
    - successors(parent_id) returns child nodes
    - predecessors(child_id) returns parent nodes
    """
```

**Current edge flow**:
1. ParsingStage extracts CodeNodes with `parent_node_id` field
2. StorageStage creates edges: `graph_store.add_edge(parent_node_id, node_id)`
3. Queries use `get_children()`, `get_parent()` - return CodeNodes, not edges

**No semantic edges exist** - no imports, calls, references, or cross-file relationships.

### NetworkX Infrastructure Already Supports Edge Attributes

**Node ID**: `callable:src/fs2/core/repos/graph_store_impl.py:NetworkXGraphStore.add_edge`

The underlying `networkx.DiGraph` fully supports edge attributes:

```python
# Current (no attributes):
self._graph.add_edge(parent_id, child_id)

# NetworkX capability (unused):
self._graph.add_edge(source_id, target_id,
    edge_type="imports",
    confidence=0.9,
    source_line=15
)
```

**Pickle persistence transparently preserves edge attributes** - no changes needed to save/load.

### Entry Points

| Entry Point | Type | Location | Purpose |
|------------|------|----------|---------|
| `fs2 scan` | CLI Command | `src/fs2/cli/scan.py:40` | Triggers full scan pipeline |
| `ScanPipeline.run()` | Service | `src/fs2/core/services/scan_pipeline.py:57` | Orchestrates all stages |
| `mcp__flowspace__search` | MCP Tool | `src/fs2/mcp/server.py:671` | Queries graph (could query relationships) |

---

## Architecture & Design

### Pipeline Stage Architecture

**Node ID**: `type:src/fs2/core/services/scan_pipeline.py:ScanPipeline`

Default pipeline stages:
```python
self._stages = [
    DiscoveryStage(),      # File discovery (1)
    ParsingStage(),        # AST parsing (2)
    SmartContentStage(),   # AI summaries (3) - optional
    EmbeddingStage(),      # Vector embeddings (4) - optional
    StorageStage(),        # Graph persistence (5)
]
```

**Recommended insertion points for relationships**:

```
DiscoveryStage → ParsingStage → [RelationshipExtractionStage] → SmartContentStage
                                                                      ↓
StorageStage ← [RelationshipStorageStage] ← EmbeddingStage
```

- **RelationshipExtractionStage** (index 2): Extract relationships from parsed nodes
- **RelationshipStorageStage** (index 4/5): Persist relationships to graph

### PipelineContext Data Carrier

**Node ID**: `type:src/fs2/core/services/pipeline_context.py:PipelineContext`

Current fields available for relationship data:
- `nodes: list[CodeNode]` - parsed nodes with content
- `graph_store: GraphStore` - for edge creation
- `errors: list[str]` - non-raising error collection
- `metrics: dict[str, Any]` - per-stage timing

**Extension needed**:
```python
relationships: list[CodeEdge] = field(default_factory=list)
```

### Component Map

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Cross-File Relationship Pipeline                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────┐   ┌──────────────────┐   ┌────────────────────┐  │
│  │  TreeSitterParser │ → │ RelationshipStage │ → │   GraphStore       │  │
│  │  (existing)       │   │ (NEW)             │   │   (extend)         │  │
│  └──────────────────┘   └──────────────────┘   └────────────────────┘  │
│           │                      │                       │              │
│           ↓                      ↓                       ↓              │
│  ┌──────────────────┐   ┌──────────────────┐   ┌────────────────────┐  │
│  │  CodeNode        │   │  CodeEdge        │   │  NetworkX DiGraph  │  │
│  │  (existing)      │   │  (NEW model)     │   │  (edge attributes) │  │
│  └──────────────────┘   └──────────────────┘   └────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Core Components to Create

| Component | Type | Location | Purpose |
|-----------|------|----------|---------|
| `EdgeType` | Enum | `src/fs2/core/models/edge_type.py` | Type-safe edge categories |
| `CodeEdge` | Model | `src/fs2/core/models/code_edge.py` | Immutable edge representation |
| `RelationshipExtractionStage` | Stage | `src/fs2/core/services/stages/relationship_extraction_stage.py` | Extract relationships |
| `RelationshipStorageStage` | Stage | `src/fs2/core/services/stages/relationship_storage_stage.py` | Store relationships |
| Extended `GraphStore` | ABC | `src/fs2/core/repos/graph_store.py` | Add relationship edge methods |

---

## Design Patterns Identified

### PS-01: String Enum Pattern for Edge Types

**Node ID**: `type:src/fs2/core/models/search/search_mode.py:SearchMode`

Follow the established pattern:
```python
class EdgeType(str, Enum):
    """Graph edge relationship types.

    Inherits from str for JSON serialization and comparison.
    """
    IMPORTS = "imports"
    CALLS = "calls"
    INHERITS = "inherits"
    REFERENCES = "references"
    DOCUMENTS = "documents"
    CONTAINS = "contains"  # existing parent-child
```

### PS-02: Frozen Dataclass with Confidence Validation

**Node ID**: `type:src/fs2/core/models/search/chunk_match.py:ChunkMatch`

Follow ChunkMatch pattern exactly:
```python
@dataclass(frozen=True)
class CodeEdge:
    """Cross-file relationship edge."""
    source_node_id: str
    target_node_id: str
    edge_type: EdgeType
    confidence: float
    source_line: int | None = None
    resolution_rule: str = "unknown"

    def __post_init__(self) -> None:
        if not isinstance(self.edge_type, EdgeType):
            raise TypeError(f"edge_type must be EdgeType enum, got {type(self.edge_type).__name__}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {self.confidence}")
```

### PS-03: ABC Adapter Pattern with ConfigurationService

**Node ID**: `type:src/fs2/core/adapters/sample_adapter.py:SampleAdapter`

If creating extractors as adapters:
- ABC file: `relationship_extractor.py`
- Fake: `relationship_extractor_fake.py`
- Impl: `relationship_extractor_treesitter.py`
- Constructor receives `ConfigurationService`, calls `config.require(ScanConfig)` internally

### PS-04: Tree-sitter Query + QueryCursor Pattern

**Reference**: `scripts/cross-files-rels-research/lib/queries.py`

```python
from tree_sitter import Query, QueryCursor
from tree_sitter_language_pack import get_language

IMPORT_QUERIES = {
    "python": """
        (import_statement) @import
        (import_from_statement) @import_from
    """,
    "typescript": """
        (import_statement) @import
    """,
}

def extract_imports(language: str, root_node) -> list[tuple[str, Any]]:
    lang = get_language(language)
    query = Query(lang, IMPORT_QUERIES[language])
    cursor = QueryCursor(query)

    results = []
    for pattern_idx, captures in cursor.matches(root_node):
        for name, nodes in captures.items():
            for node in nodes:
                results.append((name, node))
    return results
```

---

## Confidence Scoring Tiers

From 022 experimentation validation:

| Tier | Score | Applies To | Example |
|------|-------|------------|---------|
| **NODE_ID** | 1.0 | Explicit fs2 node_id in text | `callable:src/calc.py:Calculator.add` |
| **IMPORT** | 0.9 | Top-level import statement | `from auth_handler import AuthHandler` |
| **SELF_CALL** | 0.8 | self.method() or this.method() | `self._validate_credentials()` |
| **CROSS_LANG** | 0.7 | Config file → code reference | Dockerfile COPY |
| **TYPED** | 0.6 | Function-scoped import | `import json` inside function |
| **TYPE_ONLY** | 0.5 | TypeScript type-only import, PascalCase constructor | `import type { Foo }`, `AuthHandler()` |
| **RAW_FILENAME_QUOTED** | 0.5 | Filename in backticks | `` `auth_handler.py` `` |
| **DOT_IMPORT** | 0.4 | Go dot import, raw filename bare | `. "fmt"`, `auth_handler.py` |
| **INFERRED** | 0.3 | Requires inference | `_ "pkg"` |
| **FUZZY** | 0.1 | Markdown prose reference | Class name in comment |

### Confidence Modifiers

| Context | Base | Modifier | Final |
|---------|------|----------|-------|
| Import in function scope | 0.9 | -0.3 | 0.6 |
| TypeScript type-only | 0.9 | -0.4 | 0.5 |
| Python constructor (no `new`) | 0.8 | -0.3 | 0.5 |
| Go NewXxx pattern | 0.8 | -0.2 | 0.6 |

---

## Dependencies & Integration

### What This Depends On

#### Internal Dependencies

| Dependency | Type | Purpose | Risk if Changed |
|------------|------|---------|-----------------|
| `GraphStore` | ABC | Edge storage | CRITICAL - need extension |
| `TreeSitterParser` | Adapter | AST parsing | LOW - stable interface |
| `PipelineContext` | Model | Data flow | MEDIUM - add field |
| `ScanPipeline` | Service | Orchestration | MEDIUM - add stages |
| `CodeNode` | Model | Node data | LOW - read only |

#### External Dependencies

| Package | Version | Purpose | Status |
|---------|---------|---------|--------|
| `tree-sitter` | >=0.23 | Core parsing | Installed |
| `tree-sitter-language-pack` | >=0.13 | 165+ grammars | Installed |
| `networkx` | >=3.0 | Graph storage | Installed |

### What Depends on This

Cross-file relationships enable:
- MCP search tool enhancements (query by relationship)
- Agent context discovery (find related code)
- Test coverage analysis (find tests calling method)
- Documentation linkage (find docs referencing code)

---

## Quality & Testing

### Testing Strategy from QT Findings

**Pattern**: FakeGraphStore with call history + error simulation

```python
class FakeRelationshipExtractor:
    def __init__(self):
        self.call_history: list[dict] = []
        self.simulate_error_for: set[str] = set()
        self._preset_relationships: dict[str, list[CodeEdge]] = {}

    def set_relationships(self, node_id: str, edges: list[CodeEdge]):
        """Pre-configure results for testing."""
        self._preset_relationships[node_id] = edges

    def extract(self, node: CodeNode) -> list[CodeEdge]:
        self.call_history.append({"method": "extract", "node_id": node.node_id})
        if "extract" in self.simulate_error_for:
            raise RelationshipExtractionError("Simulated error")
        return self._preset_relationships.get(node.node_id, [])
```

### Available Test Fixtures

| Fixture | Location | Content |
|---------|----------|---------|
| Python with imports | `tests/fixtures/samples/python/app_service.py` | Cross-file imports |
| TypeScript imports | `tests/fixtures/samples/javascript/index.ts` | ES module imports |
| Execution log | `tests/fixtures/samples/markdown/execution-log.md` | Node ID references |
| 21 language samples | `tests/fixtures/samples/` | Various patterns |

### Integration Test Pattern

```python
def test_given_python_imports_when_extract_then_creates_edges(
    scanned_fixtures_graph
):
    """Test full pipeline with real import extraction."""
    # Load graph with relationship extraction enabled
    graph = scanned_fixtures_graph.graph_store

    # Query relationships for app_service.py
    source = "file:tests/fixtures/samples/python/app_service.py"
    edges = graph.get_relationships(source, EdgeType.IMPORTS)

    # Verify expected imports
    targets = {e.target_node_id for e in edges}
    assert "file:tests/fixtures/samples/python/auth_handler.py" in targets
    assert "file:tests/fixtures/samples/python/data_parser.py" in targets

    # Verify confidence
    for edge in edges:
        assert 0.85 <= edge.confidence <= 0.95  # Import tier
```

---

## Prior Learnings (From Previous Implementations)

**IMPORTANT**: These discoveries from 22 completed plans contain critical gotchas and patterns.

### PL-01: Tree-Sitter Named Nodes Are Structural Foundation
**Source**: `docs/plans/001-universal-ast-parser/tree-sitter-research.md`
**Type**: Core Pattern

> "Named nodes represent grammar rules (e.g., function_declaration, class_definition). Anonymous nodes are literal tokens. For structural parsing, walk only named nodes."

**Action**: Use `node.is_named` filter when extracting imports/calls. Skip punctuation nodes.

---

### PL-02: Tree-Sitter Child Access Performance
**Source**: `docs/plans/003-fs2-base/tasks/phase-3/execution.log.md`
**Type**: Performance Gotcha

> "Use `.children` not `.child(i)` - TreeSitterParser uses `for child in node.children` for O(n) vs O(n²) access."

**Action**: Always iterate `for child in node.children`. Never use index access in loops.

---

### PL-03: Graph Edge Implementation Pattern
**Source**: `docs/plans/011-mcp/tasks/phase-2-tree-tool-implementation/execution.log.md`
**Type**: Implementation Pattern

> "FakeGraphStore edges: Must call `add_edge()` to set up parent→child relationships."

**Action**: Use `graph_store.add_edge()` for relationships. Infrastructure is proven.

---

### PL-05: Schema Extension with Nullable Fields
**Source**: `docs/plans/008-smart-content/tasks/phase-6/execution.log.md`
**Type**: Backward Compatibility

> "Empty content skip - Check if node has content. If no content, skip."

**Action**: Add `relationships: tuple[CodeEdge, ...] | None = None` to maintain pickle compatibility.

---

### PL-06: TDD RED-GREEN-REFACTOR Discipline
**Source**: Multiple execution logs (003, 008, 009, 010, 011)
**Type**: Process Pattern

> All phases used "RED Phase (tests fail) → GREEN Phase (implementation) → REFACTOR Phase"

**Action**: Write failing tests first for each extraction type. Document evidence.

---

### PL-12: Language-Specific Handler Strategy
**Source**: `docs/plans/008-smart-content/tasks/phase-6/execution.log.md`
**Type**: Multi-Language Pattern

> "Rust trait/impl items not recognized. Added language-specific container type logic."

**Action**: Implement language-specific extractors (PythonImportExtractor, TypeScriptImportExtractor) with shared interface.

---

### PL-15: Full node_id Display for Agents
**Source**: `docs/plans/019-tree-folder-navigation/tasks/phase-2/execution.log.md`
**Type**: Agent UX

> "Changed from showing just name (`calculator.py`) to full node_id (`file:src/calculator.py`). Agents can copy-paste directly."

**Action**: Cross-file edge output should use full node_ids: `file:src/a.py → imports → class:src/b.py:MyClass`

---

## Modification Considerations

### Safe to Modify

1. **PipelineContext** - Add `relationships` field with default factory
2. **scan.py CLI** - Add stage configuration options
3. **models/__init__.py** - Add new exports

### Modify with Caution

1. **GraphStore ABC** - Adding new abstract methods requires updating ALL implementations (NetworkX + Fake)
2. **StorageStage** - May need coordination with new RelationshipStorageStage
3. **Pickle whitelist** - Must add new model classes for deserialization

### Danger Zones

1. **NetworkXGraphStore.save/load** - Core persistence, well-tested
2. **TreeSitterParser._extract_nodes** - Complex recursive logic
3. **CodeNode creation** - Many downstream dependencies

### Extension Points

1. **New PipelineStage** - Implement `name` property and `process()` method
2. **New model in models/** - Follow frozen dataclass pattern
3. **GraphStore methods** - Add to ABC then implement in NetworkX + Fake

---

## Critical Discoveries

### CD-01: NetworkX Supports Edge Attributes Natively
**Impact**: Critical (enables entire feature)
**Source**: IA-02 finding

The underlying `networkx.DiGraph` supports arbitrary edge attributes via `add_edge(u, v, **kwargs)`. Current implementation passes NO attributes, but infrastructure is 100% ready.

**Required Action**: Extend `add_edge()` wrapper to accept and pass through attributes.

---

### CD-02: Two-Stage Pipeline Insertion Required
**Impact**: Critical (architecture decision)
**Source**: DC-07, DC-08 findings

Must insert stages at TWO points:
1. Post-parsing for extraction (when content is available)
2. Pre-storage for persistence (after all enrichment)

**Required Action**: Create both `RelationshipExtractionStage` and `RelationshipStorageStage`.

---

### CD-03: FakeGraphStore Needs Significant Extension
**Impact**: High (testing dependency)
**Source**: IA-06 finding

Current FakeGraphStore uses `set[str]` for edges - no attribute support. Needs new storage: `dict[tuple[str, str], dict]` for relationship edges with metadata.

**Required Action**: Extend FakeGraphStore with `add_relationship_edge()` and `get_relationships()`.

---

### CD-04: RestrictedUnpickler Whitelist Update
**Impact**: Medium (security consideration)
**Source**: IA-07 finding

When CodeEdge/EdgeType models are pickled, must add to whitelist:
- `"fs2.core.models.edge_type"`
- `"fs2.core.models.code_edge"`
- `"enum"` (base class)

**Required Action**: Update ALLOWED_MODULES in RestrictedUnpickler after model creation.

---

## Recommendations

### If Implementing This Feature

1. **Start with models** - Create EdgeType enum and CodeEdge dataclass first (foundation)
2. **Extend GraphStore ABC** - Add `add_relationship_edge()` and `get_relationships()`
3. **Update FakeGraphStore** - Enable testing before production implementation
4. **Create extraction stage** - Language-specific extractors with shared interface
5. **Add to pipeline** - Wire stages into ScanPipeline with configuration flag
6. **Integration tests** - Use existing cross-file fixtures from 022 experimentation

### Priority Order

1. **P0: GraphStore extension** - Blocking all other work
2. **P0: EdgeType + CodeEdge models** - Foundation for edges
3. **P1: Python import extraction** - Most common language, validated in 022
4. **P1: Node ID detection** - High confidence (1.0), immediate value
5. **P2: TypeScript import extraction** - Second most common, validated
6. **P2: Raw filename detection** - Already implemented in 022 experiments
7. **P3: Call extraction** - More complex, partial validation

### Testing Strategy

1. **Unit tests per extractor** - Test each language in isolation
2. **Integration tests** - Full pipeline on fixtures
3. **TDD discipline** - RED → GREEN → REFACTOR for each component
4. **Fixture validation** - Run against 022 ground truth (15 entries)

---

## External Research Opportunities

No additional external research required - 022 experimentation validated all approaches:
- Tree-sitter import extraction: 100% accuracy
- Node ID detection: 100% accuracy
- Raw filename heuristics: Implemented and tested
- Confidence scoring: Validated against ground truth

---

## Appendix: File Inventory

### Files to Create

| File | Purpose | Lines (est) |
|------|---------|-------------|
| `src/fs2/core/models/edge_type.py` | EdgeType enum | ~30 |
| `src/fs2/core/models/code_edge.py` | CodeEdge model | ~60 |
| `src/fs2/core/services/stages/relationship_extraction_stage.py` | Extraction stage | ~150 |
| `src/fs2/core/services/stages/relationship_storage_stage.py` | Storage stage | ~80 |
| `tests/unit/models/test_edge_type.py` | EdgeType tests | ~50 |
| `tests/unit/models/test_code_edge.py` | CodeEdge tests | ~80 |
| `tests/unit/services/test_relationship_extraction_stage.py` | Extraction tests | ~200 |
| `tests/integration/test_relationship_pipeline.py` | Integration tests | ~150 |

### Files to Modify

| File | Change | Impact |
|------|--------|--------|
| `src/fs2/core/repos/graph_store.py` | Add relationship methods | HIGH |
| `src/fs2/core/repos/graph_store_impl.py` | Implement relationship methods | HIGH |
| `src/fs2/core/repos/graph_store_fake.py` | Implement relationship methods | HIGH |
| `src/fs2/core/services/pipeline_context.py` | Add relationships field | LOW |
| `src/fs2/core/services/scan_pipeline.py` | Add stages to default list | MEDIUM |
| `src/fs2/core/models/__init__.py` | Export new models | LOW |

### Reference Files (from 022)

| File | Purpose |
|------|---------|
| `scripts/cross-files-rels-research/lib/queries.py` | Tree-sitter query patterns |
| `scripts/cross-files-rels-research/lib/extractors.py` | Import extraction logic |
| `scripts/cross-files-rels-research/lib/resolver.py` | Confidence scoring |
| `scripts/cross-files-rels-research/experiments/01_nodeid_detection.py` | Node ID + raw filename detection |
| `docs/plans/022-cross-file-rels/experimentation-dossier.md` | Validation results |

---

## Next Steps

1. Run `/plan-1b-specify` to create formal specification from this research
2. Create phase-based implementation plan via `/plan-3-architect`
3. Begin TDD implementation starting with models and GraphStore extension

---

**Research Complete**: 2026-01-13
**Report Location**: `docs/plans/024-cross-file-impl/research-dossier.md`
