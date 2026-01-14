# Cross-File Relationship Extraction for fs2

**Mode**: Full (requires architecture phase)

---

## Research Context

This specification incorporates findings from `research-dossier.md` and `external-research.md` (from 022 experimentation).

**Components affected**:
- GraphStore ABC and implementations (NetworkXGraphStore, FakeGraphStore)
- ScanPipeline stage architecture
- PipelineContext data carrier
- Core models (new EdgeType, CodeEdge)
- MCP-served documentation (`docs/how/user/`, `src/fs2/docs/registry.yaml`)

**Critical dependencies**:
- Tree-sitter language pack (already installed)
- NetworkX DiGraph (already supports edge attributes)

**Modification risks**:
- GraphStore ABC extension requires updating all implementations
- RestrictedUnpickler whitelist needs new model classes
- FakeGraphStore needs significant extension for testing

**Validation confidence**: High - 022 experimentation achieved 100% accuracy for Python/TypeScript imports against 15-entry ground truth.

See `research-dossier.md` for full analysis.

---

## Summary

**WHAT**: Add cross-file relationship detection to fs2's scan pipeline that identifies semantic connections between code elements (imports, function calls, type references, documentation links) and stores them as confidence-scored edges in the graph.

**WHY**: AI agents need to quickly discover context across files - "What imports this module?", "What calls this function?", "Where is this documented?". Currently, fs2 only captures structural containment (file → class → method). Cross-file edges enable agents to navigate semantic relationships and build richer context for code understanding tasks.

---

## Goals

1. **Detect import relationships** between files with high accuracy (target: 95%+ for Python, TypeScript, Go)
2. **Detect explicit node_id references** in markdown/text files with perfect accuracy (1.0 confidence)
3. **Detect raw filename references** in documentation with heuristic confidence (0.4-0.5)
4. **Store relationships as edges** with type classification and confidence scores (0.0-1.0)
5. **Enable relationship queries** via GraphStore - "get all imports for this file", "find incoming references"
6. **Preserve backward compatibility** - existing graphs load without errors; relationship extraction is opt-in or additive
7. **Document for AI agents** - MCP-served guide explaining relationship types, confidence tiers, query patterns, and limitations

---

## Non-Goals

1. **Full type inference** - Resolving `self.auth.validate_token()` to `AuthHandler.validate_token` requires type inference beyond scope
2. **100% method call resolution** - Method calls on untyped receivers will have low/no confidence
3. **Dynamic language semantics** - Ruby `method_missing`, Python `__getattr__` patterns not handled
4. **Runtime relationship discovery** - Only static analysis; no execution tracing
5. **Cross-repository relationships** - Only within single scanned project
6. **JavaScript CommonJS** - `require()` patterns not in initial scope (ES modules only)

---

## Complexity

**Score**: CS-3 (medium)

**Breakdown**:
| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Surface Area (S) | 2 | Many files: GraphStore ABC/impls, models, pipeline stages, tests |
| Integration (I) | 0 | Internal only; Tree-sitter already integrated |
| Data/State (D) | 1 | New model classes; GraphStore method additions; no migrations |
| Novelty (N) | 1 | Mostly well-specified from research; some confidence tuning ambiguity |
| Non-Functional (F) | 1 | Performance considerations for large codebases; no strict requirements |
| Testing/Rollout (T) | 1 | Integration tests required; no feature flags needed |

**Total**: 2+0+1+1+1+1 = **6** → CS-3

**Confidence**: 0.85 (research dossier provides strong foundation; 022 experimentation validated core approaches)

**Assumptions**:
- Tree-sitter queries from 022 experiments can be reused directly
- NetworkX edge attribute support works as documented (validated in research)
- Existing pickle persistence handles new edge attributes transparently
- Performance acceptable for codebases up to 10k files

**Dependencies**:
- tree-sitter-language-pack >= 0.13.0 (installed)
- networkx >= 3.0 (installed)
- 022 experiment fixtures and ground truth available

**Risks**:
- FakeGraphStore rewrite may be larger than estimated
- Language-specific query variations may require more debugging (Ruby/Rust returned 0 in experiments)
- Confidence thresholds may need tuning post-implementation

**Phases** (suggested):
1. Models & GraphStore extension (foundation)
2. Python import extraction (highest value, validated)
3. Node ID + raw filename detection (high confidence, implemented in 022)
4. TypeScript/Go import extraction (validated in experiments)
5. Pipeline integration & CLI options
6. Agent documentation (MCP-served guide for AI agents)

---

## Acceptance Criteria

### AC1: Edge Type Model
**Given** a new EdgeType enum exists
**When** I create an edge with type `EdgeType.IMPORTS`
**Then** the type is serializable, comparable, and preserved through pickle save/load

### AC2: Code Edge Model
**Given** a CodeEdge dataclass with source_node_id, target_node_id, edge_type, confidence
**When** I create an edge with confidence outside 0.0-1.0
**Then** a ValueError is raised with actionable message

### AC3: GraphStore Extension
**Given** an extended GraphStore with `add_relationship_edge()` and `get_relationships()`
**When** I add a relationship edge and query it back
**Then** the edge type, confidence, and source_line are preserved

### AC4: Python Import Detection
**Given** a Python file with `from auth_handler import AuthHandler`
**When** the relationship extraction stage processes it
**Then** an edge is created: source file → IMPORTS → auth_handler.py with confidence >= 0.85

### AC5: Node ID Detection
**Given** a markdown file containing `callable:src/calc.py:Calculator.add`
**When** the relationship extraction stage processes it
**Then** an edge is created with confidence = 1.0 to the exact node_id

### AC6: Raw Filename Detection
**Given** a README.md containing "see `auth_handler.py` for details"
**When** the relationship extraction stage processes it
**Then** an edge is created with confidence 0.4-0.5 to the file node

### AC7: Relationship Query
**Given** a graph with 5 import edges from file A
**When** I call `graph_store.get_relationships("file:A", EdgeType.IMPORTS, direction="outgoing")`
**Then** I receive 5 CodeEdge objects with correct targets

### AC8: Backward Compatibility
**Given** an existing .pickle graph without relationship edges
**When** I load it with the new code
**Then** load succeeds; relationship queries return empty lists

### AC9: Fake Implementation
**Given** FakeGraphStore with relationship edge support
**When** I use it in unit tests with preset relationships
**Then** I can verify extraction logic without real graph operations

### AC10: Integration Test
**Given** the cross-file fixtures from 022 experiments (app_service.py, index.ts, execution-log.md)
**When** I run a full scan with relationship extraction enabled
**Then** at least 10 of 15 ground truth entries are detected (67%+ pass rate)

### AC11: Agent Documentation
**Given** a new MCP-served document `cross-file-relationships.md`
**When** an agent calls `docs_list(tags=["relationships"])`
**Then** the document appears in results with id `cross-file-relationships`

### AC12: Documentation Content
**Given** the cross-file relationships guide
**When** an agent reads it via `docs_get(id="cross-file-relationships")`
**Then** it contains sections on: relationship types, confidence tiers, query patterns, and known limitations

### AC13: Registry Entry
**Given** the docs registry at `src/fs2/docs/registry.yaml`
**When** the documentation is built via `just doc-build`
**Then** the registry contains an entry for `cross-file-relationships` with category `how-to`

---

## Risks & Assumptions

### Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Performance regression on large codebases | High | Medium | Lazy extraction; batch processing; profile early |
| False positives in raw filename detection | Low | High | Low confidence (0.4) signals uncertainty to agents |
| Ruby/Rust queries non-functional | Medium | Confirmed | Defer to P2; document as known gap |
| Pickle whitelist security | Medium | Low | Follow established RestrictedUnpickler pattern |

### Assumptions

1. **Tree-sitter stability**: Tree-sitter 0.23+ API (Query + QueryCursor) is stable
2. **NetworkX edge semantics**: Multi-edge support via attributes works for hierarchical + relationship edges
3. **Agent usage patterns**: Agents will filter by confidence; low-confidence edges are valuable for discovery
4. **Fixture coverage**: 022 fixtures adequately represent real-world patterns

---

## Testing Strategy

- **Approach**: Full TDD
- **Rationale**: Complex logic with GraphStore ABC extension, confidence scoring validation, and multi-language extraction requires comprehensive test coverage per fs2 constitution (>80%).
- **Focus Areas**:
  - EdgeType enum serialization and comparison
  - CodeEdge confidence validation (0.0-1.0 bounds)
  - GraphStore relationship methods (add/query/persistence)
  - Per-language import extraction (Python, TypeScript, Go)
  - Node ID detection in markdown
  - Raw filename heuristic detection
  - Backward compatibility with existing graphs
- **Excluded**: Performance benchmarking (deferred to post-implementation profiling)
- **Mock Usage**: Targeted mocks only
  - Reuse existing fakes (FakeGraphStore, FakeConfigurationService)
  - New mocks require explicit human sign-off
  - Prefer ABC-inheriting fakes per constitution

---

## Documentation Strategy

- **Location**: Hybrid (README + docs/how/)
- **Rationale**: Detailed MCP-served guide for agents, with brief README mention for discoverability.
- **Content Split**:
  - **README.md**: Brief section noting cross-file relationship support with link to full guide
  - **docs/how/user/cross-file-relationships.md**: Full 7-section MCP-served guide
- **Target Audience**: AI agents using fs2 MCP tools
- **Maintenance**: Update guide when new relationship types or languages are added

---

## Open Questions

All questions resolved in clarification session 2026-01-13:

1. ~~**CLI flag**~~ → **RESOLVED**: Always-on (no flag needed)
2. ~~**MCP exposure**~~ → **RESOLVED**: New `relationships(node_id, direction)` tool
3. ~~**Constructor confidence**~~ → **RESOLVED**: 0.8 if imported, 0.5 otherwise
4. ~~**Edge direction**~~ → **RESOLVED**: Source → Target (X imports Y = edge X→Y)

---

## ADR Seeds (Optional)

### ADR-001: Relationship Edge Storage Strategy

**Decision Drivers**:
- Must coexist with hierarchical parent-child edges
- Must support confidence scores and metadata
- Must preserve through pickle serialization
- Query performance for "all relationships of type X"

**Candidate Alternatives**:
- A: Store as NetworkX edge attributes on same graph (discriminate by `is_relationship=True`)
- B: Separate NetworkX graph for relationships only
- C: Store in CodeNode as `relationships` tuple field

**Stakeholders**: Architecture, future MCP tool consumers

### ADR-002: Extraction Stage Placement

**Decision Drivers**:
- Need access to parsed CodeNode content
- Relationships may inform smart content generation
- Storage must happen before graph persistence

**Candidate Alternatives**:
- A: Single combined stage post-parsing
- B: Two stages (extraction post-parsing, storage pre-persistence)
- C: Extend ParsingStage to extract relationships inline

**Stakeholders**: Pipeline maintainers

---

## External Research

**Incorporated**:
- `docs/plans/022-cross-file-rels/external-research.md` - Tree-sitter approach validation, confidence scoring design, heuristic patterns

**Key Findings**:
- Option 1 (Tree-sitter + own resolver) is recommended for pip-only, multi-language support
- Confidence-scored edges make system "honest about ambiguity"
- Constructor/type-hint patterns enable 80/20 member resolution
- Stack-graphs archived (maintenance risk); graph-sitter limited to 3 languages

**Applied To**:
- Goals (confidence scoring requirement)
- Non-Goals (type inference explicitly excluded)
- Complexity (validated I=0 for internal-only)
- Acceptance Criteria (confidence thresholds)

---

## Unresolved Research

**Topics**: None - all external research opportunities from 022 were addressed.

The 022 experimentation phase thoroughly validated:
- Tree-sitter import extraction (100% accuracy Python/TypeScript)
- Node ID detection (100% accuracy)
- Raw filename detection (heuristic approach implemented)
- Confidence scoring tiers

No additional external research required before architecture phase.

---

## Documentation Deliverable

### MCP-Served Agent Guide

**File**: `docs/how/user/cross-file-relationships.md`

**Registry Entry** (for `docs/how/user/registry.yaml`):
```yaml
- id: cross-file-relationships
  title: "Cross-File Relationships Guide"
  summary: "Guide to understanding cross-file relationships in fs2. Covers imports, calls, documentation references, confidence scoring, and how to query relationship edges."
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

**Content Sections**:

1. **Overview** - What are cross-file relationships? Why do agents need them?
2. **Relationship Types** - Table of EdgeType values (IMPORTS, CALLS, REFERENCES, DOCUMENTS)
3. **Confidence Scoring** - Explanation of 0.0-1.0 tiers with examples:
   - 1.0: Explicit node_id reference
   - 0.9: Top-level import statement
   - 0.5-0.7: Constructor patterns, type hints
   - 0.4-0.5: Raw filename in documentation
   - 0.1-0.3: Fuzzy matches
4. **Querying Relationships** - How to use relationship data via MCP tools
5. **Agent Best Practices** - How to interpret confidence, when to verify, filtering strategies
6. **Supported Languages** - Which languages have relationship extraction (Python, TypeScript, Go)
7. **Known Limitations** - What doesn't work (CommonJS, dynamic patterns, cross-repo)

**Build Process**:
```bash
# After creating docs/how/user/cross-file-relationships.md and updating registry.yaml:
just doc-build  # Copies to src/fs2/docs/
```

---

## Clarifications

### Session 2026-01-13

**Q1: Workflow Mode**
- **Answer**: B (Full)
- **Rationale**: CS-3 complexity with 6 phases, GraphStore ABC modification, and 13 acceptance criteria warrants full planning workflow with all gates.

**Q2: Testing Strategy**
- **Answer**: A (Full TDD)
- **Rationale**: Complex logic with GraphStore ABC extension, confidence scoring validation, and multi-language extraction requires comprehensive test coverage per fs2 constitution (>80%).

**Q3: Mock Usage Policy**
- **Answer**: B (Allow targeted mocks)
- **Rationale**: Reuse existing fakes (FakeGraphStore, etc.) but require human approval before introducing any new mocks. Prefer ABC-inheriting fakes per constitution.
- **Constraint**: New mocks require explicit human sign-off during implementation.

**Q4: Documentation Strategy**
- **Answer**: C (Hybrid - README + docs/how/)
- **Rationale**: Follow spec - detailed MCP-served guide in docs/how/user/ for agents, with brief mention in main README for discoverability.
- **Content Split**:
  - **README.md**: Brief section noting cross-file relationship support with link to full guide
  - **docs/how/user/cross-file-relationships.md**: Full 7-section guide (types, confidence tiers, queries, limitations)

**Q5: CLI Flag for Relationship Extraction**
- **Answer**: A (Always-on)
- **Rationale**: Completeness guaranteed without user needing to remember flags; ~10-20% scan overhead acceptable for relationship value.

**Q6: MCP Exposure**
- **Answer**: B (New `relationships` tool)
- **Rationale**: Dedicated tool keeps concerns separate from existing search/get_node.
- **Tool Design** (workshopped):
  ```python
  relationships(
      node_id: str,            # e.g., "file:src/app.py"
      direction: str = "both", # "incoming" | "outgoing" | "both"
  ) -> list[dict]
  # Returns: [{"node_id": "...", "edge_type": "imports", "confidence": 0.9, "source_line": 5}, ...]
  ```
- **Simplifications**:
  - No `edge_type` filter - return all types, let client filter
  - No `min_confidence` filter - client decides threshold
  - Return `node_id` + `edge_type` + `confidence` + `source_line` (line numbers needed for documentation discovery - navigating to exact reference location in markdown files)

**Q7: Python Constructor Confidence**
- **Answer**: C (0.8 if imported, 0.5 otherwise)
- **Rationale**: Match JS/TS `new` keyword confidence when we have import evidence; stay conservative for unknown PascalCase calls.

**Q8: Edge Direction Semantics**
- **Answer**: A (Source → Target)
- **Rationale**: Natural reading - "X imports Y" creates edge X→Y. Outgoing edges from a file = what it depends on; incoming = what depends on it.

---

*Spec Location*: `docs/plans/024-cross-file-impl/cross-file-impl-spec.md`
*Branch*: 022-cross-file
*Generated*: 2026-01-13
