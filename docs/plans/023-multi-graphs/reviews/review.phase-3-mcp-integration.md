# Phase 3: MCP Integration - Code Review Report

**Plan**: [../multi-graphs-plan.md](../multi-graphs-plan.md)
**Dossier**: [../tasks/phase-3-mcp-integration/tasks.md](../tasks/phase-3-mcp-integration/tasks.md)
**Reviewed**: 2026-01-14
**Reviewer**: AI Code Review Agent (plan-7-code-review)
**Testing Approach**: Full TDD

---

## A) Verdict

**APPROVE WITH WARNINGS**

The Phase 3 implementation is complete and correct. All 15 tasks have been implemented and tests pass. However, there are documentation issues with footnote synchronization that should be addressed in a follow-up cleanup.

---

## B) Summary

Phase 3 successfully integrates GraphService with the MCP server layer, enabling agents to query multiple codebases through `graph_name` parameter on existing tools and the new `list_graphs` discovery tool.

**Key Accomplishments**:
- Created `get_graph_service()` singleton following existing RLock pattern
- Implemented `list_graphs` MCP tool for graph discovery
- Added `graph_name` parameter to `tree`, `search`, `get_node` tools
- Created `FakeGraphService` test double for proper test injection
- Added `translate_graph_error()` helper for consistent error translation
- Fixed TreeService._ensure_loaded() to respect pre-loaded stores
- E2E cache invalidation tests validate staleness detection works

**Test Evidence**:
- 154+ MCP tests passing
- 5 E2E cache invalidation tests passing
- All 15 tasks marked complete

---

## C) Checklist

**Testing Approach: Full TDD**

- [x] Tests precede code (RED-GREEN-REFACTOR evidence in execution log)
- [x] Tests as docs (assertions show behavior - TestTreeWithGraphName, TestSearchWithGraphName, TestGetNodeWithGraphName)
- [x] Mock usage matches spec: **Targeted mocks only** - FakeGraphService, FakeGraphStore used; zero unittest.mock
- [x] Negative/edge cases covered (unknown graph error, missing file error)

**Universal**:
- [x] BridgeContext patterns followed (N/A - not VS Code extension work)
- [x] Only in-scope files changed (Phase 3 MCP files only)
- [x] Linters/type checks are clean (modules import successfully)
- [x] Absolute paths used (no hidden context)

---

## D) Findings Table

| ID | Severity | File:Lines | Summary | Recommendation |
|----|----------|------------|---------|----------------|
| DOC-001 | MEDIUM | tasks.md:179-196 | 8 tasks missing log anchors in Notes column (T001, T002, T006, T007, T008, T012, T013, T014) | Add `[log#task-TNNN]` to Notes column for each task |
| DOC-002 | MEDIUM | tasks.md:511-516 | Phase Footnote Stubs don't match Completion Footnotes (stubs say T006/T007 for [^7], completion says T003+T009) | Update stub definitions to match completion footnotes |
| DOC-003 | LOW | execution.log.md | Missing `**Dossier Task**` and `**Plan Task**` metadata headers in log entries | Add structured metadata headers for consistency with Phase 4 |
| IMP-001 | LOW | tree_service.py:129-147 | Bug fix for _ensure_loaded() discovered during E2E testing rather than via TDD | Consider writing regression test first next time |

---

## E) Detailed Findings

### E.0) Cross-Phase Regression Analysis

**N/A** - This is Phase 3; earlier phases (1, 2) were reviewed separately. Phase 3 builds on Phase 2 GraphService without modifying prior phase code.

### E.1) Doctrine & Testing Compliance

**Graph Integrity**: MINOR_ISSUES
- 8 tasks missing log anchors in Notes column
- Phase Footnote Stubs section has stale definitions (planned vs actual implementation diverged)
- Footnote numbers sequential: [^7], [^8], [^9], [^10] for Phase 3

**TDD Compliance**: PASS
- Execution log shows Foundation tasks (T013, T014, T006, T012, T007) before Tests (T001-T005) before Implementation (T008-T011) before Validation (T015)
- RED-GREEN-REFACTOR cycles documented

**Mock Usage Compliance**: PASS
- Zero instances of unittest.mock, MagicMock, @patch
- FakeGraphService and FakeGraphStore used (approved per plan)
- Policy: Targeted mocks only - COMPLIANT

### E.2) Quality & Safety Analysis

**Safety Score: 98/100** (CRITICAL: 0, HIGH: 0, MEDIUM: 2, LOW: 2)

**Correctness**: PASS
- `translate_graph_error()` correctly translates UnknownGraphError and GraphFileNotFoundError to ToolError
- `get_graph_store(graph_name)` correctly delegates to GraphService
- Thread safety maintained via RLock pattern

**Security**: PASS
- No new attack vectors introduced
- Graph files loaded via existing RestrictedUnpickler boundary
- No secrets or credentials in code

**Performance**: PASS
- `list_graphs()` uses Path.exists() without loading pickles (per Finding 08)
- Cache hit returns same instance
- Staleness detection uses mtime+size comparison (efficient)

**Observability**: PASS
- Error messages include available graph names for guidance
- Logging at debug level for cache hits/misses

---

## F) Coverage Map

**Acceptance Criteria → Test Mapping**:

| Criterion | Test | Confidence |
|-----------|------|------------|
| AC7: list_graphs returns all graphs | test_list_graphs_returns_default_and_configured | 100% |
| AC8: graph_name parameter on tree/search/get_node | TestTreeWithGraphName, TestSearchWithGraphName, TestGetNodeWithGraphName | 100% |
| AC9: Backward compatible (None=default) | test_graph_name_none_uses_default (all tools) | 100% |
| Thread safety | test_concurrent_access_no_race | 100% |
| Unknown graph error | test_graph_name_unknown_error | 100% |

**Overall Coverage Confidence**: 95%

---

## G) Commands Executed

```bash
# Phase 3 tests
uv run pytest tests/mcp_tests/test_tree_tool.py -v --tb=short
uv run pytest tests/mcp_tests/test_search_tool.py -v --tb=short
uv run pytest tests/mcp_tests/test_get_node_tool.py -v --tb=short
uv run pytest tests/mcp_tests/test_list_graphs.py -v --tb=short
uv run pytest tests/mcp_tests/test_dependencies.py -v --tb=short
uv run pytest tests/mcp_tests/test_cache_invalidation.py -v --tb=short

# All MCP tests (regression)
uv run pytest tests/mcp_tests/ -v --tb=short
# Result: 193 passed, 5 skipped
```

---

## H) Decision & Next Steps

**Decision**: APPROVE WITH WARNINGS

The implementation is correct and complete. The following documentation cleanup is recommended:

1. **Optional cleanup**: Update Phase Footnote Stubs to match Completion Footnotes
2. **Optional cleanup**: Add log anchors to Notes column for tasks T001, T002, T006-T008, T012-T014
3. **Optional cleanup**: Add structured metadata headers to execution log entries

These are documentation hygiene issues that don't affect functionality. The code may proceed to Phase 4.

---

## I) Footnotes Audit

| Diff Path | Footnote Tag | Node ID in Plan |
|-----------|--------------|-----------------|
| src/fs2/mcp/server.py | [^7], [^8], [^9] | function:src/fs2/mcp/server.py:tree, function:src/fs2/mcp/server.py:search, function:src/fs2/mcp/server.py:get_node |
| src/fs2/mcp/dependencies.py | [^6], [^7] | function:src/fs2/mcp/dependencies.py:get_graph_service |
| src/fs2/core/services/graph_service_fake.py | (T013) | class:src/fs2/core/services/graph_service_fake.py:FakeGraphService |
| src/fs2/core/services/tree_service.py | [^10] | method:src/fs2/core/services/tree_service.py:TreeService._ensure_loaded |
| tests/mcp_tests/test_cache_invalidation.py | [^10] | file:tests/mcp_tests/test_cache_invalidation.py |

---

*Generated by plan-7-code-review on 2026-01-14*
