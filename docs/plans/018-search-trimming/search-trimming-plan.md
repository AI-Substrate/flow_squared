# Search Result Hierarchy-Aware Scoring Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-01-03
**Spec**: [./search-trimming-spec.md](./search-trimming-spec.md)
**Research**: [./research-dossier.md](./research-dossier.md)
**Status**: READY

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Critical Research Findings](#critical-research-findings)
3. [Implementation](#implementation)
4. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

**Problem**: When search results contain both a code element (method) and its parent containers (class, file), all appear at similar ranks, "polluting" results with redundant parent matches.

**Solution**: Implement parent penalization in `SearchService.search()` post-processing that walks the graph hierarchy via `GraphStore.get_parent()` and reduces parent scores by a configurable factor (default 0.25) when their children are also in results. Exact matches (score 1.0) are immune.

**Expected Outcome**: More specific child matches surface first; parents remain visible but ranked lower. Configuration via `SearchConfig.parent_penalty` or `FS2_SEARCH__PARENT_PENALTY` env var.

---

## Critical Research Findings

*Per research-dossier.md (55+ findings synthesized):*

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | No hierarchy awareness in SearchService—all nodes scored independently | Implement `_apply_parent_penalty()` in post-processing |
| 02 | Critical | TreeService `_build_root_bucket()` has ancestor-walking algorithm | Adapt pattern: walk up via `get_parent()`, collect ancestors in result set |
| 03 | High | `GraphStore.get_parent()` exists and returns parent CodeNode | Use for hierarchy traversal (not `parent_node_id` field directly per PL-04) |
| 04 | High | Score range [0.0, 1.0] is contractual—validated in tests | Clamp penalized scores: `max(0.0, score * (1 - factor))` |
| 05 | High | No tests for parent-child scoring scenarios (gap QT-10) | Write TDD tests FIRST with 3-level hierarchy fixtures |
| 06 | High | `SearchResult` is frozen dataclass | Use `dataclasses.replace()` to create modified copies |
| 07 | High | GraphStoreProtocol only has `get_all_nodes()` | Extend protocol to include `get_parent()` method |
| 08 | Medium | Penalization must happen AFTER matchers, BEFORE sort (PL-11) | Insert at line ~200 in `SearchService.search()` |
| 09 | Medium | Conservative defaults avoid hiding results (PL-15) | Use 0.25 penalty (75% retention) as default |
| 10 | Medium | Existing `FakeGraphStore` supports parent-child edges | Use for test fixtures with `add_edge()` |

---

## Implementation

**Objective**: Add hierarchy-aware score penalization to search results, enabled by default (0.25), configurable via SearchConfig.

**Testing Approach**: Full TDD
**Mock Usage**: Fakes only (FakeGraphStore with parent-child edges)

### Tasks

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Notes |
|--------|-----|------|----|------|--------------|------------------|------------|-------|
| [ ] | T001 | Add `parent_penalty` field to SearchConfig | 1 | Config | -- | `/workspaces/flow_squared/src/fs2/config/objects.py` | Field exists with default 0.25, validated 0.0-1.0 | AC06, AC07 |
| [ ] | T002 | Write TDD tests for parent penalization (RED) | 2 | Test | T001 | `/workspaces/flow_squared/tests/unit/services/test_search_service.py` | Tests exist, fail initially; cover AC01-AC05, AC09-AC10 | 3-level hierarchy fixture |
| [ ] | T003 | Extend GraphStoreProtocol with `get_parent()` | 1 | Core | -- | `/workspaces/flow_squared/src/fs2/core/services/search/search_service.py` | Protocol includes `get_parent(node_id) -> CodeNode \| None` | Finding 07 |
| [ ] | T004 | Implement `_find_ancestors_in_results()` helper | 2 | Core | T003 | `/workspaces/flow_squared/src/fs2/core/services/search/search_service.py` | Walks graph via `get_parent()`, returns ancestor node_ids in result set | Finding 02, PL-04 |
| [ ] | T005 | Implement `_apply_parent_penalty()` method | 2 | Core | T004 | `/workspaces/flow_squared/src/fs2/core/services/search/search_service.py` | Penalizes parents, skips score=1.0, clamps to [0,1] | AC01, AC04, AC05 |
| [ ] | T006 | Integrate penalization into `search()` method | 2 | Core | T005, T001 | `/workspaces/flow_squared/src/fs2/core/services/search/search_service.py` | Called after matchers, before sort; uses config | Finding 08 |
| [ ] | T007 | Verify all TDD tests pass (GREEN) | 1 | Test | T006 | `/workspaces/flow_squared/tests/unit/services/test_search_service.py` | All AC01-AC10 tests pass | |
| [ ] | T008 | Write integration test with real graph hierarchy | 2 | Test | T007 | `/workspaces/flow_squared/tests/integration/test_search_integration.py` | Method > class > file ordering verified | AC02, AC03 |
| [ ] | T009 | Test env var override `FS2_SEARCH__PARENT_PENALTY` | 1 | Test | T001 | `/workspaces/flow_squared/tests/unit/config/test_config.py` | Env var overrides config file value | AC08 |
| [ ] | T010 | Verify semantic search mode works with penalization | 1 | Test | T007 | `/workspaces/flow_squared/tests/unit/services/test_search_service.py` | Semantic results also penalized correctly | AC10 |

### Test Fixtures (for T002)

```python
# 3-level hierarchy fixture for parent penalization tests
@pytest.fixture
def parent_penalty_graph_store(fake_config_service):
    """Graph with file → class → method hierarchy, all matching 'auth'."""
    store = FakeGraphStore(fake_config_service)

    file_node = make_code_node(
        node_id="file:src/auth.py",
        category="file",
        name="auth.py",
        content="# Authentication module with authenticate function",
    )
    class_node = make_code_node(
        node_id="class:src/auth.py:AuthService",
        category="type",
        name="AuthService",
        content="class AuthService: handles authentication",
        parent_node_id="file:src/auth.py",
    )
    method_node = make_code_node(
        node_id="callable:src/auth.py:AuthService.authenticate",
        category="callable",
        name="authenticate",
        content="def authenticate(self, user, password): verify credentials",
        parent_node_id="class:src/auth.py:AuthService",
    )

    store.set_nodes([file_node, class_node, method_node])
    store.add_edge("file:src/auth.py", "class:src/auth.py:AuthService")
    store.add_edge("class:src/auth.py:AuthService", "callable:src/auth.py:AuthService.authenticate")

    return store
```

### Test Examples (T002 - Write First!)

```python
class TestParentPenalization:
    """Tests for parent score penalization (AC01-AC10)."""

    @pytest.mark.asyncio
    async def test_parent_penalized_when_child_in_results(self, parent_penalty_graph_store):
        """
        Purpose: Proves parent scores are reduced when children also match (AC01)
        Quality Contribution: Ensures specific matches surface first
        Acceptance Criteria:
        - Parent score reduced by penalty factor
        - Child score unchanged
        - Score order: method > class > file
        """
        service = SearchService(graph_store=parent_penalty_graph_store)
        # Configure 0.25 penalty (75% retention)

        results = await service.search(QuerySpec(pattern="auth", mode=SearchMode.TEXT))

        # Find each node's result
        method_result = next(r for r in results if "authenticate" in r.node_id)
        class_result = next(r for r in results if "AuthService" in r.node_id and "callable" not in r.node_id)
        file_result = next(r for r in results if r.node_id.startswith("file:"))

        # Method unchanged, class penalized, file penalized
        assert method_result.score == 0.5  # Content match, no penalty
        assert class_result.score == 0.5 * 0.75  # Penalized (has child in results)
        assert file_result.score == 0.5 * 0.75  # Penalized (has descendant in results)

        # Verify ordering
        assert results[0].node_id == method_result.node_id

    @pytest.mark.asyncio
    async def test_exact_match_immune_to_penalty(self, parent_penalty_graph_store):
        """
        Purpose: Proves score 1.0 nodes are never penalized (AC05)
        Quality Contribution: Preserves user intent for exact searches
        Acceptance Criteria: Score 1.0 remains 1.0 even with child in results
        """
        # Search for exact class name
        results = await service.search(QuerySpec(pattern="AuthService", mode=SearchMode.TEXT))

        class_result = next(r for r in results if "AuthService" in r.node_id and "callable" not in r.node_id)

        # Exact node_id match = 1.0, should be immune
        if class_result.score == 1.0:
            assert class_result.score == 1.0  # Not penalized

    @pytest.mark.asyncio
    async def test_penalty_disabled_with_zero(self, parent_penalty_graph_store):
        """
        Purpose: Proves penalty can be disabled via config (AC09)
        Quality Contribution: Allows opt-out for users who want original behavior
        """
        # Configure penalty = 0.0
        results = await service.search(QuerySpec(pattern="auth", mode=SearchMode.TEXT))

        # All scores should be unmodified
        for result in results:
            assert result.score in [0.5, 0.8, 1.0]  # Original tier scores
```

### Acceptance Criteria

- [ ] AC01: Parent score reduced when child present (0.8 → 0.6 with 0.25 penalty)
- [ ] AC02: Child ranks higher than penalized parent in sorted results
- [ ] AC03: Multi-level hierarchy works (file and class both penalized when method matches)
- [ ] AC04: Scores remain in [0.0, 1.0] range after penalization
- [ ] AC05: Score 1.0 (exact match) immune to penalty
- [ ] AC06: Enabled by default with 0.25 penalty
- [ ] AC07: Configurable via `SearchConfig.parent_penalty`
- [ ] AC08: Configurable via `FS2_SEARCH__PARENT_PENALTY` env var
- [ ] AC09: Disabled when `parent_penalty=0.0`
- [ ] AC10: Works across text, regex, and semantic modes

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Over-penalization hides relevant parents | Low | Medium | Conservative 0.25 default; user can adjust |
| Performance regression on large results | Low | Low | O(depth) per result; depth typically 2-3 |
| Edge cases in hierarchy detection | Low | Medium | Reuse battle-tested TreeService pattern |

---

## Change Footnotes Ledger

[^1]: [To be added during implementation via plan-6a]
[^2]: [To be added during implementation via plan-6a]
[^3]: [To be added during implementation via plan-6a]

---

**Next steps:**
- **Ready to implement**: `/plan-6-implement-phase --plan "docs/plans/018-search-trimming/search-trimming-plan.md"`
- **Optional validation**: `/plan-4-complete-the-plan` (recommended for final check)
