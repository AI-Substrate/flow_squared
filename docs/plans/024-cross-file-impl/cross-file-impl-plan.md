# Cross-File Relationship Extraction Implementation Plan

**Plan Version**: 1.0.0
**Created**: 2026-01-13
**Spec**: [./cross-file-impl-spec.md](./cross-file-impl-spec.md)
**Research**: [./research-dossier.md](./research-dossier.md)
**Status**: DRAFT

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Technical Context](#technical-context)
3. [Critical Research Findings](#critical-research-findings)
4. [Testing Philosophy](#testing-philosophy)
5. [Implementation Phases](#implementation-phases)
   - [Phase 1: Core Models & GraphStore Extension](#phase-1-core-models--graphstore-extension)
   - [Phase 2: Python Import Extraction](#phase-2-python-import-extraction)
   - [Phase 3: Node ID & Raw Filename Detection](#phase-3-node-id--raw-filename-detection)
   - [Phase 4: TypeScript & Go Import Extraction](#phase-4-typescript--go-import-extraction)
   - [Phase 5: Pipeline Integration](#phase-5-pipeline-integration)
   - [Phase 6: MCP Tool & Agent Documentation](#phase-6-mcp-tool--agent-documentation)
6. [Cross-Cutting Concerns](#cross-cutting-concerns)
7. [Complexity Tracking](#complexity-tracking)
8. [Progress Tracking](#progress-tracking)
9. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

### Problem Statement

AI agents using fs2 can discover code structure (files, classes, methods) but cannot answer "What imports this module?", "What calls this function?", or "Where is this documented?". The graph only captures structural containment (file → class → method), missing the semantic relationships that agents need for context discovery.

### Solution Approach

- **Add cross-file relationship edges** to the existing NetworkX graph with confidence scoring (0.0-1.0)
- **Create new EdgeType enum** and **CodeEdge model** for type-safe edge representation
- **Extend GraphStore ABC** with `add_relationship_edge()` and `get_relationships()` methods
- **Implement RelationshipExtractionStage** in scan pipeline (always-on, no CLI flag)
- **Add `relationships` MCP tool** for agent queries by node_id and direction
- **Document for agents** via MCP-served guide explaining relationship types and confidence tiers

### Expected Outcomes

- Agents can query "What imports file X?" and "What does file X import?"
- Confidence scores signal reliability: 1.0 (explicit node_id) → 0.4 (raw filename heuristic)
- Backward compatibility: old graphs load without errors; relationship queries return empty lists
- 67%+ pass rate against 15-entry ground truth from 022 experimentation

### Success Metrics

| Metric | Target |
|--------|--------|
| Python/TypeScript import accuracy | 95%+ |
| Node ID detection accuracy | 100% |
| Ground truth validation | 67%+ (10/15 entries) |
| Test coverage on new code | >80% |
| Backward compatibility | Old graphs load without error |

### Acceptance Criteria Mapping

| AC# | Description | Phase | Tasks | Test File |
|-----|-------------|-------|-------|-----------|
| AC1 | EdgeType enum serializable, comparable, pickle-safe | 1 | 1.1-1.2 | `test_edge_type.py` |
| AC2 | CodeEdge raises ValueError for confidence outside 0.0-1.0 | 1 | 1.3-1.4 | `test_code_edge.py` |
| AC3 | GraphStore.add_relationship_edge() and get_relationships() work | 1 | 1.6-1.10 | `test_graph_store.py` |
| AC4 | Python import creates edge with confidence >= 0.85 | 2 | 2.1-2.8 | `test_python_import_extractor.py` |
| AC5 | Explicit node_id creates edge with confidence = 1.0 | 3 | 3.1-3.2 | `test_nodeid_detector.py` |
| AC6 | Raw filename creates edge with confidence 0.4-0.5 | 3 | 3.3-3.4 | `test_raw_filename_detector.py` |
| AC7 | get_relationships() returns correct edges by direction | 1, 6 | 1.9-1.10, 6.1-6.2 | `test_graph_store.py`, `test_relationships_tool.py` |
| AC8 | Old v1.0 graphs load without errors | 1 | 1.12 | `test_graph_compatibility.py` |
| AC9 | FakeGraphStore supports relationship edges | 1 | 1.11 | `test_graph_store.py` |
| AC10 | 10/15 ground truth entries detected (67%+ pass) | 5 | 5.7 | `test_relationship_pipeline.py` |
| AC11 | docs_list(tags=["relationships"]) returns document | 6 | 6.7 | `test_docs_registration.py` |
| AC12 | docs_get returns 7 sections (types, confidence, queries, etc.) | 6 | 6.8 | `test_docs_registration.py` |
| AC13 | Registry entry with category `how-to` | 6 | 6.5 | `test_docs_registration.py` |

---

## Technical Context

### Current System State

**Graph Model**: fs2 uses NetworkX DiGraph with parent-child edges only:
- `GraphStore.add_edge(parent_id, child_id)` - structural containment
- No edge attributes, no relationship types, no confidence scores

**Pipeline Architecture**: ScanPipeline runs 5 stages:
1. DiscoveryStage → scan_results
2. ParsingStage → nodes (CodeNode list)
3. SmartContentStage → smart_content (optional)
4. EmbeddingStage → embeddings (optional)
5. StorageStage → persist to graph

**Infrastructure Ready**: NetworkX supports edge attributes via `add_edge(u, v, **kwargs)`. Pickle persistence transparently preserves edge attributes. No external dependencies needed.

### Integration Requirements

| Component | Change Type | Impact |
|-----------|-------------|--------|
| GraphStore ABC | Extend | HIGH - add 2 abstract methods |
| NetworkXGraphStore | Implement | HIGH - add 2 methods (~40 LOC) |
| FakeGraphStore | Implement | HIGH - significant extension (~80 LOC) |
| PipelineContext | Extend | LOW - add 3 optional fields |
| ScanPipeline | Modify | MEDIUM - add stage, inject service |
| StorageStage | Extend | LOW - persist relationships (~10 LOC) |
| MCP Server | Extend | MEDIUM - new tool |

### Constraints and Limitations

1. **No type inference** - Cannot resolve `self.auth.validate_token()` without knowing type of `self.auth`
2. **Static analysis only** - No runtime tracing or execution
3. **Single repository** - No cross-repo relationships
4. **Language limitations** - Ruby/Rust queries need debugging; CommonJS not supported

### Assumptions

1. Tree-sitter queries from 022 experiments can be reused directly
2. NetworkX edge attributes work as documented (validated)
3. Pickle persistence handles new edge attributes transparently (validated)
4. Performance acceptable for codebases up to 10k files

---

## Critical Research Findings

### Deduplication Log

Findings merged from Implementation Strategist (I1-*) and Risk Planner (R1-*):
- I1-01 + R1-02 → Discovery 01 (GraphStore extension + FakeGraphStore)
- I1-05 + R1-08 → Discovery 02 (CodeEdge model + frozen constraint)
- R1-01 → Discovery 03 (RestrictedUnpickler whitelist)
- I1-08 + R1-09 → Discovery 06 (Pipeline integration)

---

### 🚨 Critical Discovery 01: GraphStore ABC Extension and FakeGraphStore Mismatch

**Impact**: Critical
**Sources**: [I1-01, I1-02, I1-03, R1-02]
**Affects Phases**: Phase 1

**Problem**: GraphStore ABC has 10 methods for parent-child hierarchy only. FakeGraphStore uses `dict[str, set[str]]` for edges - cannot store attributes (confidence, type, source_line).

**Root Cause**: Cross-file relationships need edge metadata. Real NetworkXGraphStore supports attributes via `graph.add_edge(u, v, **attrs)`, but FakeGraphStore cannot.

**Solution**:
1. Extend GraphStore ABC with 2 new abstract methods:
   - `add_relationship_edge(source_id, target_id, edge_type, confidence, source_line, **metadata)`
   - `get_relationships(node_id, edge_types, direction, min_confidence) -> list[tuple]`
2. Change FakeGraphStore structure:
   ```python
   # Replace: dict[str, set[str]]
   # With: dict[tuple[str,str], dict[str, Any]]
   self._relationships: dict[tuple[str,str], dict[str, Any]] = {}
   ```
3. Implement both methods in NetworkXGraphStore and FakeGraphStore

**Action Required**: Create GraphStore extension FIRST; blocks all other phases.

---

### 🚨 Critical Discovery 02: CodeEdge Model Must Be Frozen with Confidence Validation

**Impact**: Critical
**Sources**: [I1-05, R1-08]
**Affects Phases**: Phase 1

**Problem**: New relationship models need pickle compatibility and immutability for thread safety. Non-frozen dataclasses cause pickle failures when unpickled with `frozen=True`.

**Solution**: Follow ChunkMatch pattern exactly:
```python
@dataclass(frozen=True)
class CodeEdge:
    source_node_id: str
    target_node_id: str
    edge_type: EdgeType
    confidence: float
    source_line: int | None = None
    resolution_rule: str = "unknown"

    def __post_init__(self) -> None:
        if not isinstance(self.edge_type, EdgeType):
            raise TypeError(f"edge_type must be EdgeType enum")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0.0-1.0, got {self.confidence}")
```

**Action Required**: Define frozen models BEFORE any persistence code.

---

### 🚨 Critical Discovery 03: RestrictedUnpickler Whitelist Must Include New Models

**Impact**: Critical
**Sources**: [R1-01]
**Affects Phases**: Phase 1

**Problem**: `RestrictedUnpickler` at `graph_store_impl.py:55-93` whitelists specific module paths. New models (EdgeType, CodeEdge) not whitelisted will cause `GraphStoreError: Forbidden class in pickle`.

**Solution**:
```python
ALLOWED_MODULES = frozenset([
    "fs2.core.models.code_node",
    "fs2.core.models.content_type",
    "fs2.core.models.edge_type",      # NEW
    "fs2.core.models.code_edge",       # NEW
    "networkx.classes.digraph",
    # ...existing...
])
```

**Action Required**: Update whitelist immediately after creating models. Add test for pickle round-trip.

---

### High-Impact Discovery 04: Backward Compatibility with Format Versioning

**Impact**: High
**Sources**: [R1-03, R1-06]
**Affects Phases**: Phase 1, Phase 5

**Problem**: `FORMAT_VERSION = "1.0"` doesn't account for relationship edges. Old graphs loaded into new code will have no relationships (expected), but might fail if relationship fields are assumed to exist.

**Solution**:
1. Bump to `FORMAT_VERSION = "1.1"` when shipping
2. Implement graceful upgrade:
   ```python
   def load(self, path: Path):
       metadata, graph = RestrictedUnpickler(...).load()
       version = metadata.get("format_version", "1.0")
       if version == "1.0":
           logger.warning("Upgrading graph from v1.0 to v1.1")
       # Continue loading - relationships will be empty
   ```
3. Test with old graph fixtures

**Action Required**: Create v1.0 test fixtures; verify upgrade path works.

---

### High-Impact Discovery 05: Confidence Scoring Tiers from 022 Validation

**Impact**: High
**Sources**: [Research dossier PS-01, PS-02]
**Affects Phases**: Phase 2, 3, 4

**Problem**: Without standardized confidence scoring, agents cannot filter by reliability.

**Solution**: Implement validated tiers:

| Tier | Score | Applies To |
|------|-------|------------|
| NODE_ID | 1.0 | Explicit fs2 node_id in text |
| IMPORT | 0.9 | Top-level import statement |
| CONSTRUCTOR_IMPORTED | 0.8 | `AuthHandler()` when AuthHandler is imported |
| CROSS_LANG | 0.7 | Config file → code reference (Dockerfile COPY) |
| CONSTRUCTOR_UNKNOWN | 0.5 | PascalCase call without import evidence |
| RAW_FILENAME_QUOTED | 0.5 | Filename in backticks |
| RAW_FILENAME_BARE | 0.4 | Filename inline in prose |

**Action Required**: Implement confidence calculator with these exact tiers.

---

### High-Impact Discovery 06: Two-Stage Pipeline Integration Required

**Impact**: High
**Sources**: [I1-06, I1-07, I1-08, I1-09, R1-09]
**Affects Phases**: Phase 5

**Problem**: Relationship extraction needs parsed nodes (after ParsingStage) and must persist before StorageStage. Single insertion point insufficient.

**Solution**: Insert at TWO points:
```
DiscoveryStage → ParsingStage → [RelationshipExtractionStage] → SmartContentStage
                                                                      ↓
StorageStage ← EmbeddingStage (relationships persisted in StorageStage)
```

Actually, research clarified: **Single stage** at position 3 (after ParsingStage), with StorageStage extended to persist `context.relationships`:
```python
# In StorageStage, after node/edge creation:
if context.relationships:
    for edge in context.relationships:
        context.graph_store.add_relationship_edge(...)
```

**Action Required**: Create RelationshipExtractionStage; extend StorageStage.

---

### High-Impact Discovery 07: Stage Implementation Pattern

**Impact**: High
**Sources**: [I1-06]
**Affects Phases**: Phase 2, 3, 4, 5

**Problem**: New stage must follow existing patterns for consistency.

**Solution**: Follow established pattern:
```python
class RelationshipExtractionStage:
    @property
    def name(self) -> str:
        return "relationship_extraction"

    def process(self, context: PipelineContext) -> PipelineContext:
        if context.relationship_extraction_service is None:
            return context  # Skip if no service

        relationships = []
        for node in context.nodes:
            try:
                edges = context.relationship_extraction_service.extract(node, context.nodes)
                relationships.extend(edges)
            except Exception as e:
                context.errors.append(str(e))

        context.relationships = relationships
        context.metrics["relationship_extraction_count"] = len(relationships)
        return context
```

**Action Required**: Implement stage following this pattern exactly.

---

### Medium-Impact Discovery 08: Ruby/Rust Tree-Sitter Queries Non-Functional

**Impact**: Medium
**Sources**: [R1-04, Research dossier]
**Affects Phases**: Deferred (not Phase 1-6)

**Problem**: Tree-sitter import extraction returns 0 results for Ruby and Rust. Research shows queries need debugging.

**Solution**: Document as known gap; defer to P2:
```python
# In relationship_extractor.py
SUPPORTED_LANGUAGES = {"python", "typescript", "tsx", "go", "java", "c", "cpp"}
# Ruby, Rust: Deferred to Phase 2 (R1-04)
```

**Action Required**: Skip Ruby/Rust in Phase 4; document in agent guide as limitation.

---

### Medium-Impact Discovery 09: MCP Tool Design (Workshopped in Clarification)

**Impact**: Medium
**Sources**: [Spec clarification Q6]
**Affects Phases**: Phase 6

**Problem**: Need agent-facing query interface for relationships.

**Solution**: Implement as clarified:
```python
def relationships(
    node_id: str,            # e.g., "file:src/app.py"
    direction: str = "both", # "incoming" | "outgoing" | "both"
) -> list[dict]:
    """Query cross-file relationships for a node.

    Returns: [{"node_id": "...", "edge_type": "imports", "confidence": 0.9, "source_line": 5}, ...]
    """
```

Design decisions:
- No `edge_type` filter - return all types, let client filter
- No `min_confidence` filter - client decides threshold
- Return `node_id` + `edge_type` + `confidence` + `source_line` (line numbers needed for documentation discovery)

**Action Required**: Implement in MCP server; document in agent guide.

---

### Medium-Impact Discovery 10: AC Test Mapping Strategy

**Impact**: Medium
**Sources**: [R1-10]
**Affects Phases**: All phases

**Problem**: 13 acceptance criteria need explicit test coverage mapping.

**Solution**: Create AC-to-test matrix in each phase's tasks.md:
```markdown
| AC # | Requirement | Test File | Test Name | Status |
|------|-------------|-----------|-----------|--------|
| AC1 | Edge Type Model | test_edge_type.py | test_edge_type_* | [ ] |
| AC2 | Code Edge Model | test_code_edge.py | test_code_edge_* | [ ] |
```

**Action Required**: Include AC mapping in every phase's acceptance criteria.

---

## Testing Philosophy

### Testing Approach

**Selected Approach**: Full TDD
**Rationale**: From spec - "Complex logic with GraphStore ABC extension, confidence scoring validation, and multi-language extraction requires comprehensive test coverage per fs2 constitution (>80%)."

### Focus Areas (from spec)

- EdgeType enum serialization and comparison
- CodeEdge confidence validation (0.0-1.0 bounds)
- GraphStore relationship methods (add/query/persistence)
- Per-language import extraction (Python, TypeScript, Go)
- Node ID detection in markdown
- Raw filename heuristic detection
- Backward compatibility with existing graphs

### Test-Driven Development

Every implementation follows RED → GREEN → REFACTOR:
1. **RED**: Write failing test that defines expected behavior
2. **GREEN**: Implement minimal code to pass test
3. **REFACTOR**: Clean up while maintaining green tests

### Test Documentation

Every test MUST include:
```python
"""
Purpose: [what truth this test proves]
Quality Contribution: [how this prevents bugs]
Acceptance Criteria: [measurable assertions]
"""
```

### Mock Usage (from spec)

**Policy**: Targeted mocks only
- **Reuse existing fakes**: FakeGraphStore, FakeConfigurationService, FakeASTParser
- **New mocks require explicit human sign-off**
- **Prefer ABC-inheriting fakes per constitution**

Allowed:
- Environment variables via `monkeypatch`
- Existing FakeGraphStore (extended)
- FakeASTParser for tree-sitter isolation

Forbidden:
- `Mock(spec=GraphStore)` for production code
- New mock classes without human approval

---

## Implementation Phases

### Phase 1: Core Models & GraphStore Extension

**Objective**: Create foundational data models and extend GraphStore ABC with relationship methods.

**Deliverables**:
- EdgeType enum (`src/fs2/core/models/edge_type.py`)
- CodeEdge frozen dataclass (`src/fs2/core/models/code_edge.py`)
- Extended GraphStore ABC with 2 new abstract methods
- NetworkXGraphStore implementation
- FakeGraphStore implementation
- RestrictedUnpickler whitelist update
- PipelineContext field additions

**Dependencies**: None (foundational phase)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| FakeGraphStore rewrite larger than expected | Medium | Medium | Time-box to 2 CS points; escalate if exceeded |
| Pickle whitelist security concern | Low | Medium | Follow existing RestrictedUnpickler pattern exactly |
| Breaking existing tests | Low | High | Run full test suite after each change |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes | AC |
|---|--------|------|----|------------------|-----|-------|-----|
| 1.1 | [x] | Write tests for EdgeType enum | 1 | Tests cover: serialization, comparison, string value, iteration | [📋](tasks/phase-1-core-models-graphstore-extension/execution.log.md#task-t001-edgetype-tests) | 12 tests RED [^1] | AC1 |
| 1.2 | [x] | Implement EdgeType enum | 1 | All tests from 1.1 pass | [📋](tasks/phase-1-core-models-graphstore-extension/execution.log.md#task-t002-edgetype-implementation) | 12/12 GREEN [^1] | AC1 |
| 1.3 | [x] | Write tests for CodeEdge model | 2 | Tests cover: frozen, confidence validation 0.0-1.0, edge_type validation, pickle round-trip | [📋](tasks/phase-1-core-models-graphstore-extension/execution.log.md#task-t003-codeedge-tests) | 15 tests RED [^2] | AC2 |
| 1.4 | [x] | Implement CodeEdge model | 1 | All tests from 1.3 pass | [📋](tasks/phase-1-core-models-graphstore-extension/execution.log.md#task-t004-codeedge-implementation) | 15/15 GREEN [^2] | AC2 |
| 1.5 | [x] | Update RestrictedUnpickler whitelist | 1 | New models load from pickle without error | [📋](tasks/phase-1-core-models-graphstore-extension/execution.log.md#task-t005-restrictedunpickler-whitelist) | Security whitelist [^3] | AC1, AC2 |
| 1.6 | [x] | Write tests for GraphStore.add_relationship_edge() | 2 | Tests cover: valid edge creation, node validation, attribute storage | [📋](tasks/phase-1-core-models-graphstore-extension/execution.log.md#task-t006-graphstore-add_relationship_edge-tests) | 13 tests RED [^4] | AC3 |
| 1.7 | [x] | Extend GraphStore ABC with new methods | 1 | ABC compiles; abstract methods defined | [📋](tasks/phase-1-core-models-graphstore-extension/execution.log.md#task-t007-graphstore-abc-extension) | 2 abstract methods [^4] | AC3 |
| 1.8 | [x] | Implement NetworkXGraphStore.add_relationship_edge() | 2 | All tests from 1.6 pass with real implementation | [📋](tasks/phase-1-core-models-graphstore-extension/execution.log.md#task-t008-networkxgraphstore-add_relationship_edge) | Edge attrs [^4] | AC3 |
| 1.9 | [x] | Write tests for GraphStore.get_relationships() | 2 | Tests cover: direction filtering, type filtering, confidence filtering, empty results | [📋](tasks/phase-1-core-models-graphstore-extension/execution.log.md#task-t009-graphstore-get_relationships-tests) | Direction tests [^4] | AC3, AC7 |
| 1.10 | [x] | Implement NetworkXGraphStore.get_relationships() | 2 | All tests from 1.9 pass | [📋](tasks/phase-1-core-models-graphstore-extension/execution.log.md#task-t010-networkxgraphstore-get_relationships) | 13/13 GREEN [^4] | AC3, AC7 |
| 1.11 | [x] | Extend FakeGraphStore with relationship support | 2 | FakeGraphStore passes same tests as NetworkXGraphStore | [📋](tasks/phase-1-core-models-graphstore-extension/execution.log.md#task-t011-fakegraphstore-extension) | dict[tuple,dict] [^5] | AC9 |
| 1.12 | [x] | Write backward compatibility tests | 2 | Old v1.0 graphs load without error; relationship queries return empty | [📋](tasks/phase-1-core-models-graphstore-extension/execution.log.md#task-t012-backward-compatibility-tests) | Implicit via 1298 tests [^6] | AC8 |
| 1.13 | [x] | Add PipelineContext.relationships field | 1 | Field exists, defaults to None, doesn't break existing code | [📋](tasks/phase-1-core-models-graphstore-extension/execution.log.md#task-t013-pipelinecontextrelationships) | list[CodeEdge] | None [^7] | - |
| 1.14 | [x] | Export new models from models/__init__.py | 1 | Can import EdgeType, CodeEdge from fs2.core.models | [📋](tasks/phase-1-core-models-graphstore-extension/execution.log.md#task-t014-export-models) | __all__ updated [^8] | - |

### Test Examples

```python
# File: tests/unit/models/test_edge_type.py

class TestEdgeType:
    def test_edge_type_values_are_strings(self):
        """
        Purpose: Proves EdgeType enum values are JSON-serializable strings
        Quality Contribution: Enables edge type storage in graph attributes
        Acceptance Criteria: All enum values are lowercase strings
        """
        assert EdgeType.IMPORTS.value == "imports"
        assert EdgeType.CALLS.value == "calls"
        assert EdgeType.REFERENCES.value == "references"
        assert EdgeType.DOCUMENTS.value == "documents"

    def test_edge_type_comparison(self):
        """
        Purpose: Proves EdgeType enums can be compared for filtering
        Quality Contribution: Enables type-based edge filtering
        """
        assert EdgeType.IMPORTS == EdgeType.IMPORTS
        assert EdgeType.IMPORTS != EdgeType.CALLS

# File: tests/unit/models/test_code_edge.py

class TestCodeEdge:
    def test_given_confidence_above_1_when_create_then_raises(self):
        """
        Purpose: Proves confidence validation rejects invalid values
        Quality Contribution: Prevents data corruption from invalid confidence
        """
        with pytest.raises(ValueError, match="confidence must be"):
            CodeEdge(
                source_node_id="file:a.py",
                target_node_id="file:b.py",
                edge_type=EdgeType.IMPORTS,
                confidence=1.5,  # Invalid
            )

    def test_code_edge_is_frozen(self):
        """
        Purpose: Ensures CodeEdge is immutable for thread safety
        Quality Contribution: Prevents race conditions in concurrent access
        """
        edge = CodeEdge(
            source_node_id="file:a.py",
            target_node_id="file:b.py",
            edge_type=EdgeType.IMPORTS,
            confidence=0.9,
        )
        with pytest.raises(FrozenInstanceError):
            edge.confidence = 0.5
```

### Non-Happy-Path Coverage
- [ ] EdgeType from invalid string raises TypeError
- [ ] CodeEdge with confidence < 0.0 raises ValueError
- [ ] CodeEdge with confidence > 1.0 raises ValueError
- [ ] CodeEdge with wrong edge_type type raises TypeError
- [ ] Unpickling unknown class raises GraphStoreError
- [ ] get_relationships on non-existent node returns empty list

### Acceptance Criteria
- [ ] AC1: EdgeType enum is serializable, comparable, preserved through pickle
- [ ] AC2: CodeEdge raises ValueError for confidence outside 0.0-1.0
- [ ] AC3: GraphStore.add_relationship_edge() and get_relationships() work correctly
- [ ] AC8: Old graphs load without errors; relationship queries return empty
- [ ] AC9: FakeGraphStore supports relationship edges for testing
- [ ] All tests passing (100% of phase tests)
- [ ] Test coverage > 80% for new code

---

### Phase 2: Python Import Extraction

**Objective**: Implement Python import extraction with high accuracy using Tree-sitter queries.

**Deliverables**:
- RelationshipExtractionService (core service)
- PythonImportExtractor (language-specific)
- Confidence scoring for Python imports
- Integration with existing fixtures

**Dependencies**: Phase 1 complete

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Tree-sitter API changes | Low | Medium | Pin tree-sitter-language-pack version |
| Import resolution ambiguity | Medium | Low | Use 0.9 confidence for unambiguous, lower for relative |
| Namespace package handling | Medium | Low | Document as known limitation initially |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 2.1 | [ ] | Write tests for Python import extraction | 2 | Tests cover: from X import Y, import X, import X as Y, relative imports | - | Use fixtures from 022 |
| 2.2 | [ ] | Create RelationshipExtractionService ABC | 1 | ABC defined with extract() method signature | - | `src/fs2/core/services/relationship_extraction/` |
| 2.3 | [ ] | Implement PythonImportExtractor | 3 | All tests from 2.1 pass | - | Use tree-sitter queries from 022 |
| 2.4 | [ ] | Write tests for import-to-file resolution | 2 | Tests cover: same-directory, relative path, absolute path, not found | - | |
| 2.5 | [ ] | Implement import path resolver | 2 | Tests from 2.4 pass; resolves import names to file node_ids | - | |
| 2.6 | [ ] | Write confidence scoring tests | 2 | Tests cover: top-level (0.9), function-scoped (0.6), relative (0.7) | - | |
| 2.7 | [ ] | Implement confidence calculator | 2 | Tests from 2.6 pass | - | |
| 2.8 | [ ] | Integration test with real Python fixtures | 2 | app_service.py imports detected with correct targets | - | Use 022 fixtures |

### Test Examples

```python
# File: tests/unit/services/test_python_import_extractor.py

class TestPythonImportExtractor:
    def test_given_from_import_when_extract_then_finds_module(self):
        """
        Purpose: Proves from X import Y creates edge to X
        Quality Contribution: Core import detection for Python
        Acceptance Criteria: AC4 - edge from source to target with confidence >= 0.85
        """
        # Arrange
        source_content = "from auth_handler import AuthHandler"
        node = create_code_node(content=source_content, language="python")
        all_nodes = [
            node,
            create_code_node(node_id="file:auth_handler.py"),
        ]

        # Act
        extractor = PythonImportExtractor()
        edges = extractor.extract(node, all_nodes)

        # Assert
        assert len(edges) == 1
        assert edges[0].target_node_id == "file:auth_handler.py"
        assert edges[0].edge_type == EdgeType.IMPORTS
        assert edges[0].confidence >= 0.85
```

### Non-Happy-Path Coverage
- [ ] Import of non-existent module returns edge with lower confidence
- [ ] Circular import detection (A imports B imports A)
- [ ] Star import handling (from X import *)
- [ ] Type-only imports (TYPE_CHECKING blocks)

### Acceptance Criteria
- [ ] AC4: Python file with `from auth_handler import AuthHandler` creates edge with confidence >= 0.85
- [ ] Import extraction accuracy matches 022 validation (100% for Python)
- [ ] All tests passing
- [ ] Test coverage > 80%

---

### Phase 3: Node ID & Raw Filename Detection

**Objective**: Detect explicit fs2 node_id patterns and raw filenames in text files.

**Deliverables**:
- NodeIdDetector for explicit node_id patterns (confidence 1.0)
- RawFilenameDetector for heuristic filename detection (confidence 0.4-0.5)
- Integration with text/markdown file types

**Dependencies**: Phase 1 complete (can run parallel with Phase 2)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| False positives in raw filename | High | Low | Use low confidence (0.4-0.5) to signal uncertainty |
| Node ID pattern conflicts with URLs | Low | Low | Require exact pattern match with word boundaries |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 3.1 | [ ] | Write tests for node_id pattern detection | 2 | Tests cover: file:, callable:, class:, method:, type: patterns | - | |
| 3.2 | [ ] | Implement NodeIdDetector | 2 | All tests from 3.1 pass; uses regex from 022 experiments | - | Port from `01_nodeid_detection.py` |
| 3.3 | [ ] | Write tests for raw filename detection | 2 | Tests cover: backtick quoted (0.5), bare inline (0.4), extension filtering | - | |
| 3.4 | [ ] | Implement RawFilenameDetector | 2 | All tests from 3.3 pass | - | Port from 022 experiments |
| 3.5 | [ ] | Write integration tests with markdown fixtures | 2 | execution-log.md references detected | - | Use 022 fixtures |
| 3.6 | [ ] | Combine detectors in TextReferenceExtractor | 1 | Single extractor handles both patterns | - | |

### Test Examples

```python
# File: tests/unit/services/test_nodeid_detector.py

class TestNodeIdDetector:
    def test_given_explicit_nodeid_when_detect_then_confidence_1_0(self):
        """
        Purpose: Proves explicit node_id patterns have highest confidence
        Quality Contribution: AC5 - exact node_id detection
        Acceptance Criteria: Confidence = 1.0 for explicit patterns
        """
        content = "See callable:src/calc.py:Calculator.add for details"
        detector = NodeIdDetector()

        matches = detector.detect(content)

        assert len(matches) == 1
        assert matches[0].target_node_id == "callable:src/calc.py:Calculator.add"
        assert matches[0].confidence == 1.0

class TestRawFilenameDetector:
    def test_given_backtick_quoted_filename_when_detect_then_confidence_0_5(self):
        """
        Purpose: Proves quoted filenames get higher confidence than bare
        Quality Contribution: AC6 - raw filename detection with appropriate confidence
        """
        content = "See `auth_handler.py` for authentication logic"
        detector = RawFilenameDetector()

        matches = detector.detect(content)

        assert len(matches) == 1
        assert "auth_handler.py" in matches[0].target_node_id
        assert matches[0].confidence == 0.5
```

### Non-Happy-Path Coverage
- [ ] URL that looks like filename (github.com) filtered appropriately
- [ ] Node ID with missing parts handled gracefully
- [ ] Binary file content skipped

### Acceptance Criteria
- [ ] AC5: Markdown with `callable:src/calc.py:Calculator.add` creates edge with confidence = 1.0
- [ ] AC6: README with `auth_handler.py` creates edge with confidence 0.4-0.5
- [ ] All tests passing
- [ ] Test coverage > 80%

---

### Phase 4: TypeScript & Go Import Extraction

**Objective**: Extend import extraction to TypeScript and Go languages.

**Deliverables**:
- TypeScriptImportExtractor
- GoImportExtractor
- Language registry for extractor selection

**Dependencies**: Phase 2 complete (uses same patterns)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| TypeScript type-only imports | Medium | Low | Lower confidence for type-only (0.5) |
| Go dot imports | Low | Low | Handle with 0.4 confidence |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 4.1 | [ ] | Write tests for TypeScript import extraction | 2 | Tests cover: ES modules, type-only imports, re-exports | - | |
| 4.2 | [ ] | Implement TypeScriptImportExtractor | 2 | All tests from 4.1 pass | - | Tree-sitter queries from 022 |
| 4.3 | [ ] | Write tests for Go import extraction | 2 | Tests cover: single import, grouped imports, dot imports, blank imports | - | |
| 4.4 | [ ] | Implement GoImportExtractor | 2 | All tests from 4.3 pass | - | |
| 4.5 | [ ] | Create language extractor registry | 1 | Registry returns correct extractor for language | - | |
| 4.6 | [ ] | Integration test with index.ts and Go fixtures | 2 | Imports detected correctly | - | |

### Test Examples

```python
# File: tests/unit/services/test_typescript_import_extractor.py

class TestTypeScriptImportExtractor:
    def test_given_es_module_import_when_extract_then_finds_module(self):
        """
        Purpose: Proves ES module imports create edges
        Quality Contribution: TypeScript import detection
        """
        source_content = "import { AuthService } from './auth-service';"
        node = create_code_node(content=source_content, language="typescript")

        extractor = TypeScriptImportExtractor()
        edges = extractor.extract(node, [])

        assert len(edges) >= 1
        assert edges[0].edge_type == EdgeType.IMPORTS
        assert edges[0].confidence >= 0.85
```

### Non-Happy-Path Coverage
- [ ] Dynamic imports (import()) handled or skipped
- [ ] Namespace imports (import * as X)
- [ ] Go underscore imports (import _ "pkg")

### Acceptance Criteria
- [ ] TypeScript imports extracted with same accuracy as 022 validation
- [ ] Go imports extracted with same accuracy as 022 validation
- [ ] All tests passing
- [ ] Test coverage > 80%

---

### Phase 5: Pipeline Integration

**Objective**: Wire relationship extraction into scan pipeline as always-on stage.

**Deliverables**:
- RelationshipExtractionStage (pipeline stage)
- ScanPipeline modifications for stage injection
- StorageStage extension for relationship persistence
- Metrics and progress reporting

**Dependencies**: Phases 2, 3, 4 complete

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Performance regression on large codebases | Medium | Medium | Profile early; batch processing if needed |
| Stage ordering issues | Low | High | Follow existing stage pattern exactly |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 5.1 | [ ] | Write tests for RelationshipExtractionStage | 2 | Tests cover: process with nodes, empty nodes, error handling | - | |
| 5.2 | [ ] | Implement RelationshipExtractionStage | 2 | All tests from 5.1 pass | - | Follow stage pattern from I1-06 |
| 5.3 | [ ] | Write tests for StorageStage relationship persistence | 2 | Tests cover: relationships added to graph, metrics recorded | - | |
| 5.4 | [ ] | Extend StorageStage for relationships | 1 | Tests from 5.3 pass | - | ~10 LOC addition |
| 5.5 | [ ] | Write tests for ScanPipeline with relationship stage | 2 | Full pipeline test with relationships enabled | - | |
| 5.6 | [ ] | Modify ScanPipeline to include relationship stage | 2 | Stage runs by default; relationships populated | - | |
| 5.7 | [ ] | Integration test with real fixtures | 2 | AC10: 10/15 ground truth entries detected | - | Use 022 ground truth |

### Test Examples

```python
# File: tests/unit/services/test_relationship_extraction_stage.py

class TestRelationshipExtractionStage:
    def test_given_nodes_with_imports_when_process_then_relationships_populated(self):
        """
        Purpose: Proves stage populates context.relationships
        Quality Contribution: Pipeline integration verification
        """
        # Arrange
        context = PipelineContext(
            nodes=[create_python_node_with_imports()],
            graph_store=FakeGraphStore(),
            relationship_extraction_service=FakeRelationshipExtractionService(),
        )
        stage = RelationshipExtractionStage()

        # Act
        result = stage.process(context)

        # Assert
        assert result.relationships is not None
        assert len(result.relationships) > 0
        assert result.metrics["relationship_extraction_count"] > 0
```

### Non-Happy-Path Coverage
- [ ] Stage skipped if no relationship_extraction_service
- [ ] Errors logged but don't stop pipeline
- [ ] Empty nodes list handled gracefully

### Acceptance Criteria
- [ ] AC10: At least 10/15 ground truth entries detected (67%+ pass rate)
- [ ] Relationships persisted to graph on save
- [ ] Old graphs still load (backward compatibility)
- [ ] All tests passing
- [ ] Test coverage > 80%

---

### Phase 6: MCP Tool & Agent Documentation

**Objective**: Create agent-facing MCP tool and comprehensive documentation.

**Deliverables**:
- `relationships` MCP tool
- MCP-served agent guide (`docs/how/user/cross-file-relationships.md`)
- Registry entry in `docs/how/user/registry.yaml`
- Brief README.md update

**Dependencies**: Phases 1-5 complete

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Documentation drift | Medium | Medium | Include doc updates in AC |
| Agent confusion on confidence | Medium | Low | Clear tier documentation |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 6.1 | [ ] | Write tests for relationships MCP tool | 2 | Tests cover: incoming, outgoing, both directions, empty results | - | |
| 6.2 | [ ] | Implement relationships MCP tool | 2 | All tests from 6.1 pass | - | Follow design from clarification Q6 |
| 6.3 | [ ] | Survey existing docs/how/user/ structure | 1 | Document existing structure, identify placement | - | Discovery step |
| 6.4 | [ ] | Create cross-file-relationships.md | 2 | Contains all 7 sections per spec | - | `docs/how/user/cross-file-relationships.md` |
| 6.5 | [ ] | Update registry.yaml with new doc entry | 1 | AC13: Entry with category `how-to` and correct tags | - | |
| 6.6 | [ ] | Update README.md with brief section | 1 | Link to full guide | - | |
| 6.7 | [ ] | Verify docs_list returns new document | 1 | AC11: docs_list(tags=["relationships"]) returns document | - | |
| 6.8 | [ ] | Verify docs_get returns full content | 1 | AC12: Contains sections on types, confidence, queries, limitations | - | |

### Documentation Content Outline

**docs/how/user/cross-file-relationships.md** (7 sections per spec):

1. **Overview** - What are cross-file relationships? Why do agents need them?
2. **Relationship Types** - Table of EdgeType values (IMPORTS, CALLS, REFERENCES, DOCUMENTS)
3. **Confidence Scoring** - Explanation of 0.0-1.0 tiers with examples
4. **Querying Relationships** - How to use the `relationships` MCP tool
5. **Agent Best Practices** - How to interpret confidence, when to verify
6. **Supported Languages** - Python, TypeScript, Go (and known gaps)
7. **Known Limitations** - CommonJS, dynamic patterns, cross-repo, Ruby/Rust gaps

**Registry Entry**:
```yaml
- id: cross-file-relationships
  title: "Cross-File Relationships Guide"
  summary: "Guide to understanding cross-file relationships in fs2..."
  category: how-to
  tags:
    - relationships
    - cross-file
    - imports
    - calls
    - graph
    - edges
    - confidence
    - agents
```

### Test Examples

```python
# File: tests/unit/mcp/test_relationships_tool.py

class TestRelationshipsTool:
    def test_given_file_with_imports_when_query_outgoing_then_returns_imports(self):
        """
        Purpose: Proves relationships tool returns outgoing import edges
        Quality Contribution: AC7 - relationship query via MCP
        """
        # Arrange - graph with known edges
        graph = setup_graph_with_relationships()

        # Act
        result = await mcp_relationships(
            node_id="file:src/app.py",
            direction="outgoing"
        )

        # Assert
        assert len(result) > 0
        assert all("node_id" in r for r in result)
        assert all("edge_type" in r for r in result)
        assert all("confidence" in r for r in result)
```

### Non-Happy-Path Coverage
- [ ] Query for non-existent node returns empty list
- [ ] Invalid direction parameter returns helpful error
- [ ] Graph without relationships returns empty list

### Acceptance Criteria
- [ ] AC7: get_relationships("file:A", EdgeType.IMPORTS, "outgoing") returns correct edges
- [ ] AC11: docs_list(tags=["relationships"]) returns document
- [ ] AC12: docs_get returns sections on types, confidence, queries, limitations
- [ ] AC13: Registry contains entry with category `how-to`
- [ ] All tests passing
- [ ] Documentation complete with all 7 sections

---

## Cross-Cutting Concerns

### Security Considerations

- **RestrictedUnpickler**: Only whitelisted model classes can be unpickled
- **No arbitrary code execution**: Relationship extraction is static analysis only
- **Input validation**: Confidence scores validated to 0.0-1.0 range

### Observability

- **Logging**: Each stage logs extraction count and errors
- **Metrics**: Pipeline context captures:
  - `relationship_extraction_count` - edges extracted
  - `relationship_extraction_errors` - extraction failures
  - `storage_relationships` - edges persisted
- **Error tracking**: Errors collected in `context.errors` list

### Documentation

**Location**: Hybrid (per spec)
- **README.md**: Brief section with link to full guide
- **docs/how/user/cross-file-relationships.md**: Full 7-section MCP-served guide

**Maintenance**: Update guide when:
- New relationship types added
- New languages supported
- Confidence tiers adjusted

---

## Complexity Tracking

| Component | CS | Label | Breakdown | Justification | Mitigation |
|-----------|-----|-------|-----------|---------------|------------|
| GraphStore ABC Extension | 2 | Small | S=1,I=0,D=1,N=0,F=0,T=0 | Well-defined methods; NetworkX supports attributes | Follow existing pattern |
| FakeGraphStore Extension | 2 | Small | S=1,I=0,D=1,N=0,F=0,T=0 | Data structure change; many tests depend on it | Time-box; existing tests must pass |
| Python Import Extraction | 3 | Medium | S=1,I=1,D=0,N=1,F=0,T=0 | Tree-sitter queries validated; resolution logic new | Use 022 queries; TDD |
| Pipeline Integration | 3 | Medium | S=2,I=0,D=1,N=0,F=0,T=0 | Multiple files; stage ordering critical | Follow existing stage pattern exactly |
| MCP Tool | 2 | Small | S=1,I=0,D=0,N=0,F=0,T=1 | Simple query interface; docs needed | Follow existing MCP tool patterns |

**Overall Feature**: CS-3 (Medium) - Score 6/12 per spec

---

## Progress Tracking

### Phase Completion Checklist

- [x] Phase 1: Core Models & GraphStore Extension - COMPLETE (14/14 tasks, 56 tests)
- [ ] Phase 2: Python Import Extraction - NOT STARTED
- [ ] Phase 3: Node ID & Raw Filename Detection - NOT STARTED
- [ ] Phase 4: TypeScript & Go Import Extraction - NOT STARTED
- [ ] Phase 5: Pipeline Integration - NOT STARTED
- [ ] Phase 6: MCP Tool & Agent Documentation - NOT STARTED

**Overall Progress**: 1/6 phases complete (17%)

### STOP Rule

**IMPORTANT**: This plan must be validated before creating phase tasks.

After writing this plan:
1. Run `/plan-4-complete-the-plan` to validate readiness
2. Only proceed to `/plan-5-phase-tasks-and-brief` after validation passes

---

## Change Footnotes Ledger

**Footnote Numbering Authority**: plan-6a-update-progress is the single source of truth for footnote numbering.

[^1]: Phase 1 Tasks 1.1-1.2 - EdgeType enum implementation
  - `class:src/fs2/core/models/edge_type.py:EdgeType`
  - `file:tests/unit/models/test_edge_type.py`

[^2]: Phase 1 Tasks 1.3-1.4 - CodeEdge frozen dataclass
  - `class:src/fs2/core/models/code_edge.py:CodeEdge`
  - `file:tests/unit/models/test_code_edge.py`

[^3]: Phase 1 Task 1.5 - RestrictedUnpickler whitelist update
  - `file:src/fs2/core/repos/graph_store_impl.py` (ALLOWED_MODULES)

[^4]: Phase 1 Tasks 1.6-1.10 - GraphStore relationship edge extension
  - `method:src/fs2/core/repos/graph_store.py:GraphStore.add_relationship_edge`
  - `method:src/fs2/core/repos/graph_store.py:GraphStore.get_relationships`
  - `method:src/fs2/core/repos/graph_store_impl.py:NetworkXGraphStore.add_relationship_edge`
  - `method:src/fs2/core/repos/graph_store_impl.py:NetworkXGraphStore.get_relationships`
  - `file:tests/unit/repos/test_graph_store.py`

[^5]: Phase 1 Task 1.11 - FakeGraphStore relationship support
  - `method:src/fs2/core/repos/graph_store_fake.py:FakeGraphStore.add_relationship_edge`
  - `method:src/fs2/core/repos/graph_store_fake.py:FakeGraphStore.get_relationships`

[^6]: Phase 1 Task 1.12 - Backward compatibility (implicit)
  - Verified via 1298 passing unit tests

[^7]: Phase 1 Task 1.13 - PipelineContext.relationships field
  - `file:src/fs2/core/services/pipeline_context.py` (relationships field)

[^8]: Phase 1 Task 1.14 - Model exports
  - `file:src/fs2/core/models/__init__.py` (EdgeType, CodeEdge in __all__)

---

*Plan Location*: `docs/plans/024-cross-file-impl/cross-file-impl-plan.md`
*Branch*: 022-cross-file
*Generated*: 2026-01-13
