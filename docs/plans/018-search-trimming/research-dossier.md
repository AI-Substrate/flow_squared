# Research Report: Parent Node Score Penalization in Search Results

**Generated**: 2026-01-02T12:00:00Z
**Research Query**: "When searching we sometimes find the node and the file, or we might find the node, its parent node (the class), and the file. In this case we should penalize the score of the parents to stop them from polluting the search results... the node is in the results so the parents should receive some kind of penalty to their scores."
**Mode**: Plan-Associated
**Location**: `docs/plans/018-search-trimming/research-dossier.md`
**FlowSpace**: Available (mcp__flowspace__tree, search, get_node, docs_list, docs_get)
**Findings**: 55+ findings across 7 research dimensions

## Executive Summary

### What It Does
The fs2 search system returns scored results from text, regex, or semantic searches. Currently, when both a child node (e.g., a method) and its parent nodes (class, file) match a search query, **all appear in results without any hierarchy awareness**. This can "pollute" results with redundant parent matches when the more specific child is already present.

### Business Purpose
Parent penalization would improve search result quality by:
1. Surfacing the most specific/relevant matches first
2. Reducing visual clutter from redundant container nodes
3. Maintaining result completeness (parents still visible, just ranked lower)

### Key Insights
1. **No hierarchy awareness exists**: SearchService treats all nodes independently—no parent-child relationship handling
2. **Infrastructure already exists**: `CodeNode.parent_node_id` field and `GraphStore.get_parent()` method enable hierarchy detection
3. **TreeService precedent**: The `_build_root_bucket()` algorithm already implements parent-child deduplication for tree display—this pattern can be adapted for search scoring
4. **Extension point identified**: Insert penalization logic in `SearchService.search()` after matcher returns results, before sorting

### Quick Stats
- **Components**: ~15 files, 8 core classes
- **Dependencies**: GraphStore, 3 Matchers, EmbeddingAdapter
- **Test Coverage**: Good unit coverage, but **no tests for parent-child scoring scenarios**
- **Complexity**: Medium—algorithm exists in TreeService, needs adaptation
- **Prior Learnings**: 15 directly relevant discoveries from previous implementations

## How It Currently Works

### Entry Points
| Entry Point | Type | Location | Purpose |
|------------|------|----------|---------|
| `fs2 search` | CLI | `src/fs2/cli/search.py:search` | User searches from command line |
| `search` tool | MCP | `src/fs2/mcp/server.py:search` | AI agent searches via MCP |

### Core Execution Flow

1. **Query Construction**: User input → `QuerySpec` (pattern, mode, limit, offset, include, exclude)
   - Node/File: `type:src/fs2/core/models/search/query_spec.py:QuerySpec`

2. **Service Initialization**: Create `SearchService` with `GraphStore` and optional `EmbeddingAdapter`
   - Node/File: `type:src/fs2/core/services/search/search_service.py:SearchService`

3. **Mode Routing**: Dispatch to appropriate matcher based on `SearchMode`
   ```python
   if mode == SearchMode.TEXT:
       results = await self._text_matcher.match(spec, nodes)
   elif mode == SearchMode.REGEX:
       results = await self._regex_matcher.match(spec, nodes)
   else:  # SEMANTIC
       results = await self._semantic_matcher.match(spec, nodes)
   ```

4. **Scoring** (per matcher):
   - **TEXT/REGEX**: node_id exact = 1.0, node_id partial = 0.8, content = 0.5
   - **SEMANTIC**: cosine similarity 0.0-1.0, threshold at 0.25

5. **Post-Processing** (current—**NO hierarchy awareness**):
   ```python
   # Apply include/exclude filters
   if spec.include:
       results = [r for r in results if any(re.search(p, r.node_id) for p in spec.include)]
   if spec.exclude:
       results = [r for r in results if not any(re.search(p, r.node_id) for p in spec.exclude)]

   # Sort by score (descending) - ALL nodes treated equally
   results.sort(key=lambda r: r.score, reverse=True)

   # Paginate
   return results[spec.offset : spec.offset + spec.limit]
   ```

6. **Output**: `SearchResult` objects with score, snippet, node_id, line ranges

### Data Flow
```
User Query
    │
    ▼
QuerySpec(pattern, mode, ...)
    │
    ▼
SearchService.search()
    │
    ├──► TextMatcher.match()   ─┐
    ├──► RegexMatcher.match()  ─┼──► list[SearchResult]
    └──► SemanticMatcher.match()┘
                │
                ▼
        Sort by score DESC   ◄── INSERTION POINT FOR PENALIZATION
                │
                ▼
        Paginate (offset, limit)
                │
                ▼
        Return results
```

### State Management
- **Stateless**: Each search is independent
- **Graph loaded**: `GraphStore` holds indexed codebase (edges enable parent-child traversal)
- **Embeddings optional**: Only for semantic mode

## Architecture & Design

### Component Map

#### Core Search Components
| Component | Purpose | Node ID |
|-----------|---------|---------|
| `SearchService` | Orchestration, mode routing, post-processing | `type:src/fs2/core/services/search/search_service.py:SearchService` |
| `TextMatcher` | Case-insensitive substring search | `type:src/fs2/core/services/search/text_matcher.py:TextMatcher` |
| `RegexMatcher` | Pattern matching with timeout | `type:src/fs2/core/services/search/regex_matcher.py:RegexMatcher` |
| `SemanticMatcher` | Embedding-based similarity | `type:src/fs2/core/services/search/semantic_matcher.py:SemanticMatcher` |

#### Data Models
| Model | Purpose | Key Fields |
|-------|---------|------------|
| `SearchResult` | Single match | `score`, `node_id`, `match_field`, `snippet` |
| `CodeNode` | Indexed code element | `node_id`, `parent_node_id`, `content`, `embedding` |
| `QuerySpec` | Search parameters | `pattern`, `mode`, `limit`, `include`, `exclude` |

### Design Patterns Identified

1. **Strategy Pattern** (PS-01): Matchers are interchangeable strategies for different search modes
2. **Repository Pattern** (PS-02): `GraphStore` ABC abstracts node storage with `get_parent()`, `get_children()`
3. **Post-Match Centralized Sorting** (PS-06): All matchers return unsorted; `SearchService` handles sort/paginate
4. **Immutable Results** (PS-07): `SearchResult` is frozen dataclass—penalization creates new instances

### System Boundaries
- **Internal**: Search operates on `GraphStore` (in-memory or pickled graph)
- **External**: `EmbeddingAdapter` calls Azure OpenAI for query embedding (semantic mode only)
- **No persistence**: Results are ephemeral; no result caching

## Dependencies & Integration

### What Search Depends On

#### Internal Dependencies
| Dependency | Type | Purpose | Risk if Changed |
|------------|------|---------|-----------------|
| `GraphStore` | Required | Node access, parent-child edges | High—core data source |
| `CodeNode` | Required | Node model with `parent_node_id` | High—contract change breaks all |
| `EmbeddingAdapter` | Optional | Query embedding for semantic | Low—graceful fallback to text |

#### External Dependencies
| Service/Library | Version | Purpose | Criticality |
|-----------------|---------|---------|-------------|
| `numpy` | Any | Cosine similarity calculation | Medium |
| `regex` | Any | Timeout-protected pattern matching | Medium |
| Azure OpenAI | API | Embedding generation | Low (optional) |

### What Depends on Search

#### Direct Consumers
- **CLI** (`src/fs2/cli/search.py`): Formats results for terminal
- **MCP Server** (`src/fs2/mcp/server.py`): Wraps results in envelope for AI agents
- **Contract**: Expects `list[SearchResult]` sorted by score descending

## Quality & Testing

### Current Test Coverage
- **Unit Tests**: Good coverage for matchers, scoring tiers (QT-01 to QT-08)
- **Integration Tests**: Score ordering verified with real graphs (QT-07)
- **E2E Tests**: CLI output format tests exist
- **Gaps**: **No tests for parent-child scoring scenarios** (QT-10)

### Test Strategy Analysis
Tests verify:
- Score range 0.0-1.0 (QT-01)
- Descending sort order (QT-02)
- Field-based scoring tiers: 1.0/0.8/0.5 (QT-03)
- Best-chunk-wins for semantic (QT-06)

### Known Issues & Technical Debt
| Issue | Severity | Location | Impact |
|-------|----------|----------|--------|
| No parent-child awareness | Medium | `SearchService.search()` | Result pollution |
| ReDoS in include/exclude | Low | Filters use `re.search()` | Tech debt (PL-10) |
| No performance benchmarks | Low | Tests | Can't detect regression |

### Performance Characteristics
- **O(n)** regardless of limit (intentional—search-all-then-sort for quality) (PL-11)
- Parent traversal would add O(depth) per result for `get_parent()` calls
- Depth typically 2-3 (file → class → method)

## Modification Considerations

### ✅ Safe to Modify
1. **`SearchService.search()` post-processing**: Well-isolated, clear insertion point after matchers return
2. **`QuerySpec` fields**: Adding optional `parent_penalty: float` follows existing pattern
3. **`SearchConfig`**: Adding configuration follows established pattern (DE-06)

### ⚠️ Modify with Caution
1. **Score calculation in matchers**: Field-based scoring is tested with exact values (0.8, 0.5)—penalization should be POST-scoring
2. **`SearchResult` model**: Frozen dataclass—use `dataclasses.replace()` to create modified copies

### 🚫 Danger Zones
1. **GraphStore interface**: Many consumers depend on current contract
2. **Score semantics**: Breaking 0.0-1.0 range would violate existing contracts (IC-02)

### Extension Points
1. **Primary**: Insert after line ~200 in `SearchService.search()`, before `results.sort()`
2. **Configuration**: Add to `QuerySpec` for per-search control, or `SearchConfig` for global default
3. **Algorithm**: Adapt `TreeService._build_root_bucket()` pattern (DE-07)

## Prior Learnings (From Previous Implementations)

**IMPORTANT**: These are discoveries from previous work in this codebase. They represent institutional knowledge—gotchas, unexpected behaviors, and insights that past implementations uncovered.

### 📚 Prior Learning PL-01: Score Hierarchy - Highest Wins
**Source**: `docs/plans/010-search/tasks/phase-2-textregex-matchers/tasks.md`
**Original Type**: `decision`
**What They Found**: Multi-field match scoring uses 'highest wins' strategy. No score accumulation across fields.
**Action for Current Work**: Parent penalization should be multiplicative (reduce parent score), not additive/subtractive accumulation.

---

### 📚 Prior Learning PL-03: Root Bucket Algorithm - The Precedent
**Source**: `docs/plans/004-tree-command/tasks/phase-1-core-tree-command-with-path-filtering/tasks.md`
**Original Type**: `decision`
**What They Found**: "When child and parent both match, only parent should be root" - TreeService removes children from display when ancestor also matches.
**Action for Current Work**: **CRITICAL** - This algorithm can be inverted for search: instead of removing children, penalize parents when children also match.

---

### 📚 Prior Learning PL-04: Use GraphStore API, Not parent_node_id Directly
**Source**: `docs/plans/004-tree-command/tree-command-plan.md`
**Original Type**: `decision`
**What They Found**: Graph edges are parent→child direction. Always use `get_children()` for traversal, not parent_node_id field directly.
**Action for Current Work**: Use `graph_store.get_parent()` for penalization detection, not field iteration.

---

### 📚 Prior Learning PL-06: Score Clamping to 0.0
**Source**: `docs/plans/010-search/tasks/phase-3-semantic-matcher/tasks.md`
**Original Type**: `decision`
**What They Found**: Cosine similarity can return negative values—clamp to 0.
**Action for Current Work**: Apply floor after penalization: `max(0.0, score * penalty_factor)`.

---

### 📚 Prior Learning PL-11: Search-All-Then-Sort Design
**Source**: `docs/plans/011-mcp/tasks/phase-4-search-tool-implementation/tasks.md`
**Original Type**: `decision`
**What They Found**: Pagination is O(n) regardless of limit—intentional for result quality. Early-exit would miss higher-scoring matches.
**Action for Current Work**: **CRITICAL** - Apply parent penalization AFTER scoring, as part of ranking phase. Don't filter parents early.

---

### 📚 Prior Learning PL-15: Conservative Defaults
**Source**: `docs/plans/010-search/tasks/phase-3-semantic-matcher/tasks.md`
**Original Type**: `decision`
**What They Found**: min_similarity lowered from 0.5 to 0.25—0.5 was too aggressive and hid relevant results.
**Action for Current Work**: Default parent penalty should be conservative (e.g., 0.8-0.9 multiplier) to avoid burying relevant parent matches.

### Prior Learnings Summary

| ID | Type | Key Insight | Action |
|----|------|-------------|--------|
| PL-01 | decision | Highest score wins, no accumulation | Use multiplicative penalty |
| PL-03 | decision | Root bucket algorithm exists | Adapt for score penalization |
| PL-04 | decision | Use GraphStore API for hierarchy | Use `get_parent()` not field |
| PL-06 | decision | Clamp scores to 0.0 minimum | `max(0.0, penalized_score)` |
| PL-11 | decision | Search-all-then-sort for quality | Penalize AFTER scoring |
| PL-15 | decision | Conservative thresholds | Use 0.8-0.9 penalty factor |

## Critical Discoveries

### 🚨 Critical Finding 01: No Hierarchy Awareness in Search
**Impact**: Critical
**Source**: IA-02, IA-09
**Node IDs**: `type:src/fs2/core/services/search/search_service.py:SearchService`
**What**: SearchService treats all nodes independently. No deduplication, no parent-child score adjustment.
**Why It Matters**: This is the root cause of the "pollution" problem—parents and children compete equally.
**Required Action**: Implement parent penalization in SearchService.search() post-processing.

---

### 🚨 Critical Finding 02: TreeService Has the Algorithm
**Impact**: Critical
**Source**: IA-06, DE-07, PL-03
**Node IDs**: `callable:src/fs2/core/services/tree_service.py:TreeService._build_root_bucket`
**What**: TreeService already implements parent-child detection via ancestor walking.
**Why It Matters**: The algorithm exists—adapt it rather than invent from scratch.
**Required Action**: Extract and adapt `_build_root_bucket()` logic for score penalization.

---

### 🚨 Critical Finding 03: GraphStore.get_parent() Ready to Use
**Impact**: High
**Source**: IA-05, DC-04, IC-05
**Node IDs**: `type:src/fs2/core/repos/graph_store.py:GraphStore`
**What**: `get_parent(node_id)` method exists and returns parent CodeNode.
**Why It Matters**: Infrastructure for hierarchy traversal is already in place.
**Required Action**: Use this method in penalization logic.

---

### 🚨 Critical Finding 04: Score Range is Contractual
**Impact**: High
**Source**: IC-02, QT-01, PL-06
**Node IDs**: `type:src/fs2/core/models/search/chunk_match.py:ChunkMatch`
**What**: Scores must be in [0.0, 1.0] range—this is validated and tested.
**Why It Matters**: Any penalty logic must respect this bound.
**Required Action**: Clamp penalized scores: `max(0.0, score * factor)`.

---

### 🚨 Critical Finding 05: No Tests for Parent-Child Scenarios
**Impact**: High
**Source**: QT-10
**Node IDs**: N/A
**What**: No tests verify behavior when both parent and child appear in results.
**Why It Matters**: Can't safely implement feature without test coverage.
**Required Action**: Write tests for parent-child scoring scenarios before implementation.

## Supporting Documentation

### Related Documentation
- `docs/plans/010-search/search-spec.md` - Original search specification
- `docs/plans/010-search/research/hybrid-search-scoring.md` - RRF and scoring research
- `docs/how/cli.md` - CLI output format documentation

### Key Code Comments
From `RegexMatcher._find_best_field_match()`:
```python
# Score priorities (DYK-P2-03):
# - Exact full node_id match = 1.0
# - Partial node_id match = 0.8
# - content/smart_content matches = 0.5
```

From `TreeService._build_root_bucket()`:
```python
"""Build root bucket by removing children when ancestor also matched.
When both a parent and child match the pattern, only keep the parent
in the root bucket."""
```

## Recommendations

### If Modifying This System (Implementing Parent Penalization)

1. **Start with tests**: Create test fixtures with parent-child hierarchies (QT-05 pattern)
2. **Insert at right point**: After matcher call, before `results.sort()` in SearchService
3. **Use existing algorithm**: Adapt TreeService's ancestor-walking logic
4. **Conservative default**: Use 0.8-0.9 multiplier to avoid over-penalization
5. **Make configurable**: Add `parent_penalty: float` to QuerySpec for caller control

### Recommended Implementation Approach

```python
# Pseudocode for SearchService.search() modification
async def search(self, spec: QuerySpec) -> list[SearchResult]:
    # ... existing matcher dispatch ...

    # NEW: Apply parent penalization if enabled
    if spec.parent_penalty > 0.0:
        results = self._apply_parent_penalty(results, spec.parent_penalty)

    # ... existing filter, sort, paginate ...

def _apply_parent_penalty(
    self,
    results: list[SearchResult],
    penalty_factor: float
) -> list[SearchResult]:
    """Penalize parent scores when their children are also in results."""
    result_node_ids = {r.node_id for r in results}

    # Build map of which results are parents of other results
    parent_of_result = set()
    for result in results:
        # Walk up parent chain
        parent_id = self._get_parent_node_id(result.node_id)
        while parent_id:
            if parent_id in result_node_ids:
                parent_of_result.add(parent_id)
            parent_id = self._get_parent_node_id(parent_id)

    # Apply penalty to parent nodes
    penalized = []
    for result in results:
        if result.node_id in parent_of_result:
            new_score = max(0.0, result.score * (1.0 - penalty_factor))
            result = dataclasses.replace(result, score=new_score)
        penalized.append(result)

    return penalized
```

### Configuration Options

| Option | Location | Default | Description |
|--------|----------|---------|-------------|
| `parent_penalty` | `QuerySpec` | `0.0` | Per-search penalty factor (0.0 = disabled) |
| `default_parent_penalty` | `SearchConfig` | `0.2` | Global default when not specified |

### Testing Strategy

1. **Unit test**: Parent and child both match, verify child ranks higher after penalty
2. **Unit test**: Three-level hierarchy (file → class → method), verify ordering
3. **Unit test**: Penalty respects 0.0-1.0 bounds
4. **Integration test**: Real graph with hierarchy, verify practical behavior
5. **Edge case**: Node without parent (file), verify no penalty applied

## External Research Opportunities

No external research gaps identified during codebase exploration. The implementation approach is well-understood based on:
- Existing TreeService algorithm (DE-07)
- Clear scoring contracts (IC-02)
- Prior learnings about conservative defaults (PL-15)

## Appendix: File Inventory

### Core Files
| File | Purpose | Lines |
|------|---------|-------|
| `src/fs2/core/services/search/search_service.py` | Orchestration, post-processing | ~250 |
| `src/fs2/core/services/search/regex_matcher.py` | Pattern matching, field scoring | ~200 |
| `src/fs2/core/services/search/semantic_matcher.py` | Embedding similarity | ~180 |
| `src/fs2/core/services/tree_service.py` | **Has root bucket algorithm** | ~300 |
| `src/fs2/core/models/search/search_result.py` | Result model with score | ~80 |
| `src/fs2/core/models/code_node.py` | Node with parent_node_id | ~150 |
| `src/fs2/core/repos/graph_store.py` | GraphStore ABC with get_parent | ~100 |

### Test Files
| File | Purpose |
|------|---------|
| `tests/unit/services/test_search_service.py` | Service orchestration tests |
| `tests/unit/services/test_regex_matcher.py` | Scoring tier tests |
| `tests/unit/services/test_semantic_matcher.py` | Chunk/similarity tests |
| `tests/mcp_tests/test_search_tool.py` | MCP integration tests |

### Configuration Files
| File | Relevance |
|------|-----------|
| `src/fs2/config/objects.py` | `SearchConfig` class |
| `.fs2/config.yaml` | User configuration |

## Next Steps

**Research Complete.** Ready to proceed with specification.

- **Next step**: Run `/plan-1b-specify "Parent node score penalization for search results"` to create specification
- **Alternative**: Run `/plan-2-clarify` if implementation approach needs clarification

---

**Research Complete**: 2026-01-02
**Report Location**: `docs/plans/018-search-trimming/research-dossier.md`
