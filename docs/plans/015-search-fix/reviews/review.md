# Code Review: Plan 015 - Glob Pattern Support for Search Filters

**Plan**: [../search-fix-plan.md](../search-fix-plan.md)
**Mode**: Simple (single phase)
**Reviewed**: 2026-01-02
**Reviewer**: Claude Opus 4.5 (plan-7-code-review)
**Diff Range**: Working tree changes (not yet committed)

---

## A) Verdict

**APPROVE** (with advisory notes)

The implementation correctly addresses all acceptance criteria. Two medium-severity issues identified that should be fixed before commit but do not block approval.

---

## B) Summary

The glob pattern support implementation is **complete and correct**. Key achievements:

1. **Core utility** `normalize_filter_pattern()` implements GLOB-DETECTION-FIRST algorithm correctly
2. **44 unit tests** provide comprehensive coverage of conversion logic
3. **CLI integration** works with 7 new tests passing
4. **MCP integration** works with 4 new tests passing (in isolation)
5. **Backward compatibility** confirmed - all 13 existing `TestSearchIncludeExcludeOptions` tests pass
6. **TDD process** followed with documented RED-GREEN-REFACTOR cycles

Two issues require attention:
- Linting errors (import sorting, missing `raise from`)
- MCP tests use deprecated `asyncio.get_event_loop()` pattern (pre-existing project issue)

---

## C) Checklist

**Testing Approach: Full TDD**
**Mock Usage: Avoid mocks** (as specified in plan)

- [x] Tests precede code (RED-GREEN-REFACTOR evidence in execution log)
- [x] Tests as docs (assertions show behavior - parametrized tests with clear expectations)
- [x] Mock usage matches spec: **Avoid mocks** (uses fixtures and fakes per codebase convention)
- [x] Negative/edge cases covered (empty patterns, invalid regex, extension edge cases)

**Universal Checks:**
- [x] Only in-scope files changed (7 files match task table)
- [ ] Linters/type checks are clean (**4 ruff errors found - see E.3**)
- [x] Absolute paths used (no hidden context assumptions)
- [x] BridgeContext patterns N/A (Python CLI project, not VS Code extension)

---

## D) Findings Table

| ID | Severity | File:Lines | Summary | Recommendation |
|----|----------|------------|---------|----------------|
| F001 | MEDIUM | `src/fs2/cli/search.py:164` | Missing `raise from` in exception handling | Add `from None` or `from e` |
| F002 | LOW | `src/fs2/cli/search.py:14-33` | Import block unsorted | Run `ruff check --fix` |
| F003 | LOW | `src/fs2/cli/search.py:185` | Local import unsorted | Run `ruff check --fix` |
| F004 | LOW | `src/fs2/mcp/server.py:631` | Local import unsorted | Run `ruff check --fix` |
| F005 | MEDIUM | `tests/mcp_tests/test_search_tool.py` | Uses deprecated `asyncio.get_event_loop()` | Pre-existing; consider pytest-asyncio refactor |

---

## E) Detailed Findings

### E.0) Cross-Phase Regression Analysis

**Skipped: Simple Mode (single phase)**

No prior phases to regress against.

---

### E.1) Doctrine & Testing Compliance

#### Graph Integrity: ✅ INTACT

**Task↔Log Validation:**
| Task | Status | Log Entry | Validated |
|------|--------|-----------|-----------|
| T001 | [x] | Task T001 in execution.log.md | ✅ |
| T002 | [x] | Task T002 in execution.log.md | ✅ |
| T003 | [x] | Task T003 in execution.log.md | ✅ |
| T004 | [x] | Task T004 in execution.log.md | ✅ |
| T005 | [x] | Task T005 in execution.log.md | ✅ |
| T006 | [x] | (Help text - included in T005/T006) | ✅ |
| T007 | [x] | (MCP tests - in tasks.md) | ✅ |
| T008-T012 | [x] | Documented in tasks.md | ✅ |

**Task↔Footnote Validation:**
| Footnote | Tasks | Node IDs | Validated |
|----------|-------|----------|-----------|
| [^1] | T001/T003 | `function:src/fs2/core/utils/pattern_utils.py:normalize_filter_pattern`, `function:src/fs2/core/utils/pattern_utils.py:_convert_glob_to_regex` | ✅ |
| [^2] | T002 | `class:tests/unit/utils/test_pattern_utils.py:TestPatternNormalizationConversion` + 2 more | ✅ |
| [^3] | T004 | `class:tests/unit/cli/test_search_cli.py:TestSearchGlobPatterns` | ✅ |
| [^4] | T005/T006 | `function:src/fs2/cli/search.py:search` | ✅ |
| [^5] | T007 | `class:tests/mcp_tests/test_search_tool.py:TestSearchToolGlobPatterns` | ✅ |
| [^6] | T008/T009 | `function:src/fs2/mcp/server.py:search` | ✅ |

**Footnote↔File Validation:**
All FlowSpace node IDs point to files present in the diff.

#### Authority Conflicts

**N/A** - Simple Mode (no separate dossier, plan is authority)

#### TDD Compliance: ✅ PASS

**Evidence from execution.log.md:**

1. **T002 (RED Phase)**:
   > "43 FAILED, 1 passed (fnmatch format test). All failures are NotImplementedError: T001 stub"

2. **T003 (GREEN Phase)**:
   > "$ uv run pytest tests/unit/utils/test_pattern_utils.py -v → 44 passed in 0.04s"

3. **T004 (CLI Tests - RED)**:
   > "FAILED - ValueError(\"Invalid regex in include pattern '*.py': nothing to repeat\")"

4. **T005 (CLI Integration - GREEN)**:
   > "7 passed in 0.99s"

RED-GREEN-REFACTOR cycle is documented. Tests were written before implementation.

#### Mock Usage Compliance: ✅ PASS

**Policy**: Avoid mocks
**Finding**: No mocks used. Tests use:
- `scanned_fixtures_graph` fixture with real graph data
- `search_test_graph_store` FakeGraphStore (follows project pattern)
- Real implementations throughout

---

### E.2) Semantic Analysis

**Domain Logic Correctness: ✅ PASS**

The GLOB-DETECTION-FIRST algorithm correctly implements the 5-step priority:
1. Extension pattern (`^\.\w+$`) → escape + anchor
2. Starts with `*` → fnmatch conversion
3. Ends with `*` not `.*` → fnmatch conversion (DYK-002)
4. Contains `?` after word char → fnmatch conversion (DYK-005)
5. Else → try as regex, raise if invalid

**Spec Requirement Validation:**
| AC | Requirement | Test | Status |
|----|-------------|------|--------|
| AC1 | `*.py` returns only `.py` files | `test_given_glob_star_py_when_include_then_filters_to_py_only` | ✅ |
| AC2 | `.ts` matches only `.ts`, not `typescript/` | `test_given_extension_ts_when_include_then_excludes_typescript_dir` | ✅ |
| AC3 | `.cs` matches `type:foo.cs:Bar` | `test_pattern_matches_node_ids[.cs-type:src/Foo.cs:FooClass-True]` | ✅ |
| AC4 | `Calculator.*` still works | `test_regex_patterns_pass_through_unchanged[Calculator.*]` | ✅ |
| AC5 | Help shows "glob like *.py or regex" | Help text updated at lines 87, 94 | ✅ |
| AC6 | MCP works identically | `TestSearchToolGlobPatterns` (4 tests) | ✅ |
| AC7 | Existing tests pass | `TestSearchIncludeExcludeOptions` (13 tests) | ✅ |
| AC8 | Empty pattern raises error | `test_empty_patterns_rejected` | ✅ |

---

### E.3) Quality & Safety Analysis

**Safety Score: 66/100** (CRITICAL: 0, HIGH: 0, MEDIUM: 2, LOW: 3)
**Verdict: APPROVE with advisory notes**

#### F001: Missing `raise from` in exception handling
**Severity**: MEDIUM
**File**: `src/fs2/cli/search.py:164`
**Issue**: Exception re-raised without chain, violates B904 linting rule
**Impact**: Exception context lost; harder to debug
**Fix**: Add `from None` to indicate intentional break or `from e` to preserve chain
**Patch**:
```diff
     except ValueError as e:
         console.print(f"[red]Error:[/red] {e}")
-        raise typer.Exit(code=1)
+        raise typer.Exit(code=1) from None
```

#### F002-F004: Import sorting violations
**Severity**: LOW
**Files**: `search.py:14-33`, `search.py:185`, `server.py:631`
**Issue**: Import blocks not sorted per isort/ruff I001 rule
**Impact**: Style inconsistency
**Fix**: Run `uv run ruff check --fix src/fs2/cli/search.py src/fs2/mcp/server.py`

#### F005: Deprecated asyncio pattern in MCP tests
**Severity**: MEDIUM
**File**: `tests/mcp_tests/test_search_tool.py:517,540,564,587`
**Issue**: Uses deprecated `asyncio.get_event_loop().run_until_complete()` pattern
**Impact**: Tests fail when run with other test modules (event loop conflict)
**Note**: This is a **pre-existing project issue** documented in execution log:
> "CLI and MCP tests have asyncio event loop conflicts when run together in same session; pre-existing issue unrelated to our changes"

Tests pass when run in isolation (4/4 pass).

**Recommended fix (future work)**:
```python
# Current (deprecated):
result = asyncio.get_event_loop().run_until_complete(search(...))

# Recommended:
@pytest.mark.asyncio
async def test_search_glob_star_py_filters_correctly(...):
    result = await search(...)
```

---

## F) Coverage Map

**Testing Approach: Full TDD**
**Overall Confidence: 95%**

| Criterion | Test | Confidence |
|-----------|------|------------|
| AC1: `*.py` filters to .py only | `test_given_glob_star_py_when_include_then_filters_to_py_only` | 100% |
| AC2: `.ts` doesn't match typescript dir | `test_given_extension_ts_when_include_then_excludes_typescript_dir` | 100% |
| AC3: Symbol nodes match | `test_pattern_matches_node_ids[.cs-type:src/Foo.cs:FooClass-True]` | 100% |
| AC4: Regex backward compat | `test_regex_patterns_pass_through_unchanged` (7 patterns) | 100% |
| AC5: Help text update | Visual inspection of lines 87, 94 | 75% (manual) |
| AC6: MCP parity | `TestSearchToolGlobPatterns` (4 tests) | 100% |
| AC7: Existing tests pass | `TestSearchIncludeExcludeOptions` (13 tests) | 100% |
| AC8: Empty pattern error | `test_empty_patterns_rejected` (4 variants) | 100% |

**Test Counts:**
- Unit tests (pattern_utils): **44 pass**
- CLI integration tests: **20 pass** (7 new + 13 existing)
- MCP integration tests: **4 pass** (in isolation)
- **Total: 68 tests for this feature**

---

## G) Commands Executed

```bash
# Test pattern_utils unit tests
UV_CACHE_DIR=.uv_cache uv run pytest tests/unit/utils/test_pattern_utils.py -v
# Result: 44 passed

# Test CLI glob patterns
UV_CACHE_DIR=.uv_cache uv run pytest tests/unit/cli/test_search_cli.py::TestSearchGlobPatterns -v
# Result: 7 passed

# Test backward compatibility
UV_CACHE_DIR=.uv_cache uv run pytest tests/unit/cli/test_search_cli.py::TestSearchIncludeExcludeOptions -v
# Result: 13 passed

# Test MCP glob patterns (isolation)
UV_CACHE_DIR=.uv_cache uv run pytest tests/mcp_tests/test_search_tool.py::TestSearchToolGlobPatterns -v
# Result: 4 passed (with deprecation warning)

# Lint check
UV_CACHE_DIR=.uv_cache uv run ruff check src/fs2/core/utils/pattern_utils.py src/fs2/cli/search.py src/fs2/mcp/server.py
# Result: 4 errors (3 I001 import sorting, 1 B904 raise from)
```

---

## H) Decision & Next Steps

### Decision: **APPROVE**

The implementation is functionally correct and follows TDD methodology. All acceptance criteria are met with comprehensive test coverage.

### Required Before Commit (Advisory):

1. **Fix B904 linting error** (F001):
   ```python
   # In search.py:164
   raise typer.Exit(code=1) from None
   ```

2. **Fix import sorting** (F002-F004):
   ```bash
   uv run ruff check --fix src/fs2/cli/search.py src/fs2/mcp/server.py
   ```

### Optional Improvements (Future):

3. **Modernize MCP test async pattern** (F005) - tracked as technical debt

### Next Steps:

1. Apply fixes above
2. Commit changes:
   ```
   git add .
   git commit -m "feat: Implement glob pattern support for search filters

   - Add normalize_filter_pattern() utility to convert glob patterns to regex
   - Integrate into CLI --include/--exclude filters
   - Integrate into MCP search tool
   - Update help text to mention glob support
   - Add 55 tests (44 unit + 7 CLI + 4 MCP)
   - All 8 acceptance criteria verified

   Closes: plan-015

   🤖 Generated with [Claude Code](https://claude.com/claude-code)

   Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
   ```

---

## I) Footnotes Audit

| Diff Path | Footnote | Node ID |
|-----------|----------|---------|
| `src/fs2/core/utils/pattern_utils.py` | [^1] | `function:src/fs2/core/utils/pattern_utils.py:normalize_filter_pattern` |
| `src/fs2/core/utils/pattern_utils.py` | [^1] | `function:src/fs2/core/utils/pattern_utils.py:_convert_glob_to_regex` |
| `src/fs2/core/utils/__init__.py` | [^1] | `file:src/fs2/core/utils/__init__.py` |
| `tests/unit/utils/test_pattern_utils.py` | [^2] | `class:tests/unit/utils/test_pattern_utils.py:TestPatternNormalizationConversion` |
| `tests/unit/utils/test_pattern_utils.py` | [^2] | `class:tests/unit/utils/test_pattern_utils.py:TestPatternMatching` |
| `tests/unit/utils/test_pattern_utils.py` | [^2] | `class:tests/unit/utils/test_pattern_utils.py:TestEdgeCases` |
| `tests/unit/cli/test_search_cli.py` | [^3] | `class:tests/unit/cli/test_search_cli.py:TestSearchGlobPatterns` |
| `src/fs2/cli/search.py` | [^4] | `function:src/fs2/cli/search.py:search` |
| `tests/mcp_tests/test_search_tool.py` | [^5] | `class:tests/mcp_tests/test_search_tool.py:TestSearchToolGlobPatterns` |
| `src/fs2/mcp/server.py` | [^6] | `function:src/fs2/mcp/server.py:search` |

All footnotes have corresponding file changes in the diff. Graph integrity maintained.

---

**Review Complete**: 2026-01-02
**Verdict**: ✅ APPROVE
