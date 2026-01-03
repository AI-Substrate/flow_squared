# Search Result Hierarchy-Aware Scoring (Parent Penalization)

**Mode**: Simple

📚 *This specification incorporates findings from `research-dossier.md`*

## Research Context

Based on comprehensive codebase research (55+ findings across 7 dimensions):

- **Components affected**: `SearchService`, `QuerySpec`, `SearchConfig`, test suites
- **Critical dependencies**: `GraphStore.get_parent()`, `CodeNode.parent_node_id` (both already exist)
- **Modification risks**: Low—clear extension point identified in SearchService post-processing
- **Algorithm precedent**: `TreeService._build_root_bucket()` implements parent-child detection
- **Link**: See `research-dossier.md` for full analysis

## Summary

**WHAT**: When search results contain both a code element (e.g., a method) AND its containing parent elements (class, file), automatically reduce the scores of parent nodes so that more specific child matches appear first. Enabled by default with a 0.25 penalty factor (parents retain 75% of score). Exact matches (score 1.0) are immune to penalization.

**WHY**: Currently, parent containers "pollute" search results by competing equally with their more specific children. A search for "authenticate" might return both `AuthService.authenticate()` (the method) and `AuthService` (the class) at similar ranks, when the method is clearly the more relevant, specific result.

## Goals

1. **Surface specific matches first**: Child nodes (methods, functions) should rank higher than their parent containers when both match
2. **Reduce result clutter**: Minimize redundant parent nodes appearing alongside their already-matched children
3. **Preserve completeness**: Parents remain in results (just ranked lower)—users can still find them if needed
4. **Respect user intent**: Exact node_id matches (score 1.0) are never penalized—user explicitly searched for that node
5. **Maintain configurability**: Tune the penalty strength per search or globally; disable by setting to 0.0
6. **Respect existing contracts**: Scores remain in [0.0, 1.0] range; no breaking changes to SearchResult model

## Non-Goals

1. **Complete parent removal**: We penalize, not filter—parents remain visible at lower rank
2. **Changing matcher scoring logic**: Penalization happens AFTER matchers score, not within them
3. **Multi-level penalty scaling**: All parents penalized equally (no "grandparent penalized more" logic)
4. **Performance optimization**: Accept O(depth × results) cost for correctness; optimize later if needed
5. **New relationship types**: This spec covers parent-child only; call graphs, inheritance etc. are future work

## Complexity

**Score**: CS-2 (small)

**Breakdown**:
| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Surface Area (S) | 1 | 5-6 files: SearchService, QuerySpec, SearchConfig, GraphStoreProtocol, test files |
| Integration (I) | 0 | Internal only—extends existing GraphStore API |
| Data/State (D) | 0 | No schema changes, no migrations |
| Novelty (N) | 0 | Well-specified; algorithm pattern exists in TreeService |
| Non-Functional (F) | 0 | Standard performance requirements |
| Testing/Rollout (T) | 1 | Unit + integration tests required |

**Total**: P = 2 → CS-2 (small)

**Confidence**: 0.85 (high—research provides clear implementation path)

**Assumptions**:
- GraphStore edges are correctly populated during scan (validated by existing tree tests)
- Penalty applies uniformly across all search modes (text, regex, semantic)
- Default penalty factor of 0.25 (75% retention) is appropriate starting point
- Exact matches (score 1.0) should never be penalized (user intent preservation)

**Dependencies**:
- None external—all infrastructure exists

**Risks**:
- Over-penalization could hide relevant parent matches (mitigated by conservative default)
- Performance regression on large result sets (mitigated by typical depth of 2-3)

**Phases**:
1. Add configuration options (QuerySpec field, SearchConfig default)
2. Implement parent detection and penalty logic in SearchService
3. Add comprehensive test coverage
4. Update CLI/MCP documentation

## Acceptance Criteria

### AC01: Parent Penalization Applied When Child Present
**Given** a search returns both a method `Calculator.add` (score 0.8) and its parent class `Calculator` (score 0.8)
**When** parent penalization is applied with default factor 0.25
**Then** the class `Calculator` score is reduced to 0.6 (0.8 × 0.75) while `Calculator.add` remains at 0.8

### AC02: Child Ranks Higher Than Penalized Parent
**Given** search results contain matching parent and child nodes with equal initial scores
**When** results are sorted after penalization
**Then** child node appears before parent node in final results

### AC03: Multi-Level Hierarchy Handled
**Given** search matches a method, its containing class, AND the containing file
**When** parent penalization is applied
**Then** both the class and file are penalized (method's grandparent is also a parent of a result)

### AC04: Score Bounds Respected
**Given** any combination of initial scores and penalty factors
**When** penalization is applied
**Then** all resulting scores remain in [0.0, 1.0] range

### AC05: Exact Match Immunity (Score 1.0)
**Given** a parent node has score 1.0 (exact node_id match)
**And** its child is also in the results
**When** penalization is applied
**Then** the parent score remains 1.0 (never penalized—user explicitly searched for this node)

### AC06: Enabled by Default (0.25 Penalty)
**Given** no explicit penalty configuration
**When** search is executed
**Then** parent penalization is applied with default factor 0.25

### AC07: Configurable via SearchConfig
**Given** `SearchConfig.parent_penalty=0.25` is configured (the default)
**When** search is executed
**Then** parent penalty of 0.25 is applied

### AC08: Configurable via Environment Variable
**Given** `FS2_SEARCH__PARENT_PENALTY=0.5` is set
**When** search is executed
**Then** parent penalty of 0.5 is applied (env overrides config file)

### AC09: Disable via Zero Penalty
**Given** `parent_penalty=0.0` is configured
**When** search is executed
**Then** no penalization occurs (opt-out)

### AC10: Works Across All Search Modes
**Given** text, regex, and semantic search modes
**When** parent penalization is enabled
**Then** penalty is applied uniformly regardless of mode

## Risks & Assumptions

### Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Over-penalization hides relevant parents | Medium | Low | Conservative 0.2 default; configurable |
| Performance regression on large graphs | Low | Low | O(depth) per result; depth typically 2-3 |
| Edge cases in hierarchy detection | Medium | Low | Leverage battle-tested TreeService algorithm |

### Assumptions

1. **Graph edges are correct**: Parent-child relationships were correctly indexed during `fs2 scan`
2. **Uniform penalty is sufficient**: Different penalty levels per hierarchy depth not needed
3. **Multiplicative penalty is appropriate**: `score × (1 - penalty)` vs subtractive approach
4. **Existing tests remain valid**: No changes to base scoring behavior

## Open Questions

~~1. **[RESOLVED: CLI Flag]** Config-only; no `--parent-penalty` CLI flag~~

~~2. **[RESOLVED: MCP Parameter]** Config-only; no MCP parameter~~

~~3. **[RESOLVED: Penalty Direction]** Using "penalty" semantics (0.25 = reduce by 25%, parent retains 75%)~~

**All questions resolved.** Configuration via:
- `.fs2/config.yaml`: `search.parent_penalty: 0.25`
- Environment variable: `FS2_SEARCH__PARENT_PENALTY=0.5`

## Implementation Approach

### Graph-Based Parent Traversal

Parent detection MUST use `GraphStore.get_parent()` to walk the graph edges, NOT the `parent_node_id` field directly. This ensures:
1. Consistency with graph edge semantics
2. Future-proofing for other relationship types (call graphs, inheritance)
3. Follows prior learning PL-04

**Protocol Extension Required**:
```python
# Current (insufficient)
class GraphStoreProtocol(Protocol):
    def get_all_nodes(self) -> list[CodeNode]: ...

# Extended (add get_parent)
class GraphStoreProtocol(Protocol):
    def get_all_nodes(self) -> list[CodeNode]: ...
    def get_parent(self, node_id: str) -> CodeNode | None: ...  # NEW
```

**Ancestor Detection Algorithm**:
```python
def _find_ancestors_in_results(
    self,
    node_id: str,
    result_ids: set[str]
) -> set[str]:
    """Walk UP parent chain via GraphStore edges.

    Returns set of ancestor node_ids that are also in the result set.
    Handles multi-level: file → class → method walks up 2 levels.
    """
    ancestors = set()
    current = self._graph_store.get_parent(node_id)
    while current:
        if current.node_id in result_ids:
            ancestors.add(current.node_id)
        current = self._graph_store.get_parent(current.node_id)
    return ancestors
```

**Penalization Flow**:
```python
def _apply_parent_penalty(self, results: list[SearchResult], factor: float) -> list[SearchResult]:
    result_ids = {r.node_id for r in results}

    # Find all nodes that are ancestors of other results
    parents_to_penalize = set()
    for result in results:
        ancestors = self._find_ancestors_in_results(result.node_id, result_ids)
        parents_to_penalize.update(ancestors)

    # Apply penalty (skip exact matches)
    penalized = []
    for result in results:
        if result.node_id in parents_to_penalize and result.score < 1.0:
            new_score = max(0.0, result.score * (1.0 - factor))
            result = dataclasses.replace(result, score=new_score)
        penalized.append(result)

    return penalized
```

## Testing Strategy

- **Approach**: Full TDD
- **Rationale**: Algorithm-heavy scoring/hierarchy logic; 11 ACs to verify; research identified testing gap (no parent-child scoring tests exist)
- **Focus Areas**:
  - Parent detection via graph traversal (AC01, AC03)
  - Score penalization math and bounds (AC01, AC04)
  - Exact match immunity (AC05)
  - Configuration precedence (AC06-AC10)
  - Cross-mode consistency (AC11)
- **Excluded**: CLI/MCP parameter parsing (covered by existing tests)
- **Mock Usage**: Fakes only (no mocks) — use `FakeGraphStore` with parent-child edges pre-wired
- **Test Fixtures**:
  - Extend `tree_test_graph_store` pattern (already has parent-child edges)
  - Create 3-level hierarchy: file → class → method
  - Use `add_edge()` to wire parent-child relationships
- **Repeatable Test Scenario**:
  - Search "authenticate" on nodes: `file:src/auth.py`, `class:src/auth.py:AuthService`, `callable:src/auth.py:AuthService.authenticate`
  - All three match on content (score 0.5 each before penalization)
  - Verify after penalization: method > class > file in result order

## Documentation Strategy

- **Location**: None (no new documentation required)
- **Rationale**: Internal scoring improvement that works automatically with sensible default (0.25)
- **Self-Documenting**: Config option visible via `fs2 search --help` and MCP tool schema
- **Target Audience**: N/A
- **Maintenance**: N/A

## ADR Seeds (Optional)

### Decision Drivers
- Use graph edges for relationship traversal (future-proof)
- Maintain backward compatibility (default enabled with conservative 0.25)
- Follow existing configuration patterns (QuerySpec + SearchConfig)
- Leverage existing TreeService algorithm pattern
- Respect [0.0, 1.0] score contract
- Preserve exact match intent (score 1.0 immunity)

### Candidate Alternatives
- **A: Multiplicative penalty** (`score × (1 - factor)`)—simple, bounded, reversible ✓ CHOSEN
- **B: Subtractive penalty** (`score - factor`)—simpler but can go negative
- **C: Rank-based demotion** (push parents down N positions)—ignores score semantics

### Stakeholders
- fs2 CLI users
- AI agents using MCP search tool
- fs2 maintainers

---

## Clarifications

### Session 2026-01-03

**Q1: Workflow Mode**
- **Answer**: A (Simple)
- **Rationale**: CS-2 complexity, clear implementation path from research, ~5-6 files touched

**Q2: Testing Strategy**
- **Answer**: A (Full TDD)
- **Rationale**: Algorithm-heavy scoring/hierarchy logic; 11 ACs to verify; research identified testing gap

**Q3: Mock Usage Policy**
- **Answer**: A (Fakes only, no mocks)
- **Rationale**: Codebase uses `FakeGraphStore` pattern per constitution; extend `tree_test_graph_store` fixture with parent-child edges

**Q4: Documentation Strategy**
- **Answer**: D (No new documentation)
- **Rationale**: Internal scoring improvement; default 0.25 works automatically; config option self-documenting via `--help` / MCP schema

**Q5: CLI & MCP Parameter Exposure**
- **Answer**: D (Config-only)
- **Rationale**: Keep interfaces clean; power users can override via `FS2_SEARCH__PARENT_PENALTY` env var or `.fs2/config.yaml`

---

**Specification Version**: 1.4
**Created**: 2026-01-02
**Updated**: 2026-01-03
**Status**: Ready for architecture

**Changelog**:
- **v1.4**: Clarification complete; config-only (no CLI/MCP params); reduced to 10 ACs; added Testing/Documentation Strategy
- **v1.3**: Added Mode: Simple; began clarification session
- **v1.2**: Added Implementation Approach section with graph-based parent traversal; GraphStoreProtocol extension required
- **v1.1**: Default penalty 0.25; AC05 exact match immunity; 11 ACs total
