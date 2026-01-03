# Search Result Hierarchy-Aware Scoring (Parent Penalization)

📚 *This specification incorporates findings from `research-dossier.md`*

## Research Context

Based on comprehensive codebase research (55+ findings across 7 dimensions):

- **Components affected**: `SearchService`, `QuerySpec`, `SearchConfig`, test suites
- **Critical dependencies**: `GraphStore.get_parent()`, `CodeNode.parent_node_id` (both already exist)
- **Modification risks**: Low—clear extension point identified in SearchService post-processing
- **Algorithm precedent**: `TreeService._build_root_bucket()` implements parent-child detection
- **Link**: See `research-dossier.md` for full analysis

## Summary

**WHAT**: When search results contain both a code element (e.g., a method) AND its containing parent elements (class, file), reduce the scores of parent nodes so that more specific child matches appear first.

**WHY**: Currently, parent containers "pollute" search results by competing equally with their more specific children. A search for "authenticate" might return both `AuthService.authenticate()` (the method) and `AuthService` (the class) at similar ranks, when the method is clearly the more relevant, specific result.

## Goals

1. **Surface specific matches first**: Child nodes (methods, functions) should rank higher than their parent containers when both match
2. **Reduce result clutter**: Minimize redundant parent nodes appearing alongside their already-matched children
3. **Preserve completeness**: Parents remain in results (just ranked lower)—users can still find them if needed
4. **Maintain configurability**: Enable/disable or tune the penalty strength per search or globally
5. **Respect existing contracts**: Scores remain in [0.0, 1.0] range; no breaking changes to SearchResult model

## Non-Goals

1. **Complete parent removal**: We penalize, not filter—parents remain visible at lower rank
2. **Changing matcher scoring logic**: Penalization happens AFTER matchers score, not within them
3. **Multi-level penalty scaling**: All parents penalized equally (no "grandparent penalized more" logic)
4. **Modifying GraphStore interface**: Use existing `get_parent()` method
5. **Performance optimization**: Accept O(depth × results) cost for correctness; optimize later if needed

## Complexity

**Score**: CS-2 (small)

**Breakdown**:
| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Surface Area (S) | 1 | 4-5 files: SearchService, QuerySpec, SearchConfig, 2 test files |
| Integration (I) | 0 | Internal only—uses existing GraphStore API |
| Data/State (D) | 0 | No schema changes, no migrations |
| Novelty (N) | 0 | Well-specified; algorithm exists in TreeService |
| Non-Functional (F) | 0 | Standard performance requirements |
| Testing/Rollout (T) | 1 | Unit + integration tests required |

**Total**: P = 2 → CS-2 (small)

**Confidence**: 0.85 (high—research provides clear implementation path)

**Assumptions**:
- GraphStore edges are correctly populated during scan (validated by existing tree tests)
- Penalty applies uniformly across all search modes (text, regex, semantic)
- Default penalty factor of 0.2 (80% retention) is appropriate starting point

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
**When** parent penalization is enabled with factor 0.2
**Then** the class `Calculator` score is reduced to 0.64 (0.8 × 0.8) while `Calculator.add` remains at 0.8

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

### AC05: Disabled by Default (Zero Penalty)
**Given** no explicit penalty configuration
**When** search is executed
**Then** no penalization occurs (backward compatibility)

### AC06: Configurable via QuerySpec
**Given** a search request with `parent_penalty=0.3` specified
**When** search is executed
**Then** parent scores are reduced by 30% (multiplied by 0.7)

### AC07: Global Default via SearchConfig
**Given** `SearchConfig.default_parent_penalty=0.2` is configured
**And** no per-search penalty specified
**When** search is executed
**Then** parent penalty of 0.2 is applied

### AC08: Per-Search Overrides Global
**Given** global default is 0.2 and per-search specifies 0.5
**When** search is executed
**Then** penalty of 0.5 is used (per-search wins)

### AC09: Root Nodes Unaffected
**Given** file-level nodes (no parent) appear in results
**When** penalization is applied
**Then** file scores are only penalized if they contain matched children, not inherently

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

1. **[NEEDS CLARIFICATION: CLI Flag]** Should the CLI expose `--parent-penalty <float>` flag, or rely on config-only?

2. **[NEEDS CLARIFICATION: MCP Parameter]** Should the MCP `search` tool expose `parent_penalty` as an optional parameter?

3. **[NEEDS CLARIFICATION: Penalty Direction]** Should the user specify "penalty" (0.2 = reduce by 20%) or "retention" (0.8 = keep 80%)?

## ADR Seeds (Optional)

### Decision Drivers
- Maintain backward compatibility (default disabled)
- Follow existing configuration patterns (QuerySpec + SearchConfig)
- Leverage existing TreeService algorithm rather than reinvent
- Respect [0.0, 1.0] score contract

### Candidate Alternatives
- **A: Multiplicative penalty** (`score × (1 - factor)`)—simple, bounded, reversible
- **B: Subtractive penalty** (`score - factor`)—simpler but can go negative
- **C: Rank-based demotion** (push parents down N positions)—ignores score semantics

### Stakeholders
- fs2 CLI users
- AI agents using MCP search tool
- fs2 maintainers

---

**Specification Version**: 1.0
**Created**: 2026-01-02
**Status**: Draft - Ready for clarification
