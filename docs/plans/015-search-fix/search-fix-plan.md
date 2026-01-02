# Glob Pattern Support for Search Filters - Implementation Plan

**Mode**: Simple
**Plan Version**: 1.1.0
**Created**: 2026-01-02
**Updated**: 2026-01-02 (added test infrastructure research findings R09-R10)
**Spec**: [./search-fix-spec.md](./search-fix-spec.md)
**Status**: READY

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Critical Research Findings](#critical-research-findings)
3. [Implementation](#implementation)
4. [Change Footnotes Ledger](#change-footnotes-ledger)

## Executive Summary

**Problem**: Users expect glob patterns like `*.py` and `.gd` in `--include`/`--exclude` filters, but fs2 search treats them as regex, causing crashes (`*.py` is invalid regex) or silent wrong matches (`.gd` matches any char + "gd").

**Solution**: Add `normalize_filter_pattern()` utility that auto-detects glob patterns and converts them to regex, applied before QuerySpec construction in both CLI and MCP layers.

**Expected Outcome**: `fs2 search "test" --include "*.py"` works intuitively, while existing regex patterns continue working unchanged.

## Critical Research Findings (Concise)

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | **Backward compatibility**: Proposed algorithm would break `Calculator.*` regex patterns by wrongly detecting `*` as glob | Validate regex FIRST, only try glob if regex fails |
| 02 | Critical | **Node ID format**: Extensions appear before `:` in symbol nodes (`type:foo.cs:Bar`), not at end | Use `(?:$|:)` anchor, not simple `$` |
| 03 | High | **CLI/MCP parity**: Both entry points share QuerySpec but need independent pattern conversion | Add conversion in both `search.py` and `server.py` |
| 04 | High | **Architecture**: QuerySpec must stay pure (regex-only); conversion in presentation layer | Create `core/utils/pattern_utils.py` |
| 05 | High | **Test fixtures exist**: `scanned_fixtures_graph` has 9 file types (.py, .cs, .md, .ts, .tsx, .js, .go, .rs, .tf) from ast_samples | Use `scanned_fixtures_graph` for glob tests, extend `TestSearchIncludeExcludeOptions` |
| 06 | Medium | **fnmatch format dependency**: `fnmatch.translate()` returns `(?s:...)\Z` format | Use regex extraction with explicit format check |
| 07 | Medium | **Empty pattern handling**: Empty strings compile as valid regex but are semantically wrong | Add validation layer in normalize function |
| 08 | Low | **Extension edge cases**: `.py-old` won't match `^\.\w+$` pattern | Accept limitation, document behavior |
| 09 | High | **Existing tests**: `TestSearchIncludeExcludeOptions` (lines 597-933) has 13 tests covering regex patterns; no glob tests exist | Add `TestSearchGlobPatterns` class or extend existing |
| 10 | Medium | **Fixture comparison**: `scanned_project` has .py only; `scanned_fixtures_graph` has 9 file types for testing glob patterns | Use `scanned_fixtures_graph` for integration tests |

**Algorithm Fix (from R1-01, refined by DYK-001)**:
```python
def normalize_filter_pattern(pattern: str) -> str:
    # CRITICAL: Detect OBVIOUS glob patterns FIRST (DYK Insight #1)
    # These are unambiguous glob intent, even if technically valid regex

    # 1. Extension pattern (.py, .cs) - always convert
    if re.match(r"^\.\w+$", pattern):
        return re.escape(pattern) + r"(?:$|:)"

    # 2. Starts with * (*.py) - always convert (invalid regex anyway)
    if pattern.startswith("*"):
        return _convert_glob_to_regex(pattern)

    # 3. Ends with * but NOT .* (test_*) - likely glob intent
    if pattern.endswith("*") and not pattern.endswith(".*"):
        return _convert_glob_to_regex(pattern)

    # 4. Contains ? after word char (file?.py) - likely glob
    if re.search(r"\w\?", pattern):
        return _convert_glob_to_regex(pattern)

    # 5. All else - try as regex (Calculator.*, src/, ^class:)
    try:
        re.compile(pattern)
        return pattern
    except re.error as e:
        raise ValueError(f"Invalid pattern '{pattern}': {e}")
```

## Implementation (Single Phase)

**Objective**: Enable glob pattern support for `--include`/`--exclude` filters in both CLI and MCP, with full backward compatibility.

**Testing Approach**: Full TDD - Write tests first, use `scanned_fixtures_graph` fixture (has .py, .cs, .md, .ts, .tsx, .js, .go, .rs, .tf)
**Mock Usage**: Avoid mocks - use fixtures and fakes per codebase convention

### Test Infrastructure Summary

| Fixture | Purpose | File Types |
|---------|---------|------------|
| `scanned_project` | Temp project w/ 3 Python files | .py only |
| `scanned_fixtures_graph` | Real graph from `tests/fixtures/ast_samples/` | 7 .py, 3 .md, 3 .cs, 2 .ts, 2 .go, 2 .rs, 2 .tf, 1 .tsx, 1 .js |
| `fixture_graph.pkl` | Pre-built graph with embeddings | (for semantic tests) |

**Existing Tests** (`TestSearchIncludeExcludeOptions`, lines 597-933 in `test_search_cli.py`):
- 13 tests covering help text, basic filtering, OR logic, include-before-exclude, meta fields, regex support, invalid regex errors
- All use text/regex patterns (e.g., `"samples/"`, `"Calculator"`)
- **No glob pattern tests exist** - this is what we're adding

**Recommended Approach**:
1. Use `scanned_fixtures_graph` fixture (has multiple file types for testing `*.py`, `*.cs`, `*.md`)
2. Add new `TestSearchGlobPatterns` class in `test_search_cli.py`
3. Test both CLI integration and the pattern utility unit tests

### Tasks

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Notes |
|--------|-----|------|----|------|--------------|------------------|------------|-------|
| [ ] | T001 | Create utils module structure | 1 | Setup | -- | `/workspaces/flow_squared/src/fs2/core/utils/__init__.py`, `/workspaces/flow_squared/src/fs2/core/utils/pattern_utils.py` | Module imports without error | mkdir + touch |
| [ ] | T002 | Write unit tests for `normalize_filter_pattern()` | 2 | Test | T001 | `/workspaces/flow_squared/tests/unit/utils/test_pattern_utils.py` | Tests exist, all fail initially (RED) | TDD: tests first |
| [ ] | T003 | Implement `normalize_filter_pattern()` with safe algorithm | 2 | Core | T002 | `/workspaces/flow_squared/src/fs2/core/utils/pattern_utils.py` | All T002 tests pass (GREEN) | Regex-first algorithm per R1-01 |
| [ ] | T004 | Write CLI integration tests for glob patterns | 2 | Test | T003 | `/workspaces/flow_squared/tests/unit/cli/test_search_cli.py` | New tests in `TestSearchGlobPatterns` class | Use `scanned_fixtures_graph` fixture for .py/.cs/.md tests |
| [ ] | T005 | Integrate pattern conversion into CLI search | 2 | Core | T003 | `/workspaces/flow_squared/src/fs2/cli/search.py` | T004 tests pass, existing tests still pass | Lines 152-155 + import |
| [ ] | T006 | Update CLI help text | 1 | Core | T005 | `/workspaces/flow_squared/src/fs2/cli/search.py` | Help shows "glob like *.py or regex" | Line 86-87 |
| [ ] | T007 | Write MCP integration tests for glob patterns | 2 | Test | T003 | `/workspaces/flow_squared/tests/mcp_tests/test_search_tool.py` | New tests for glob in MCP search | May need fixture adjustment |
| [ ] | T008 | Integrate pattern conversion into MCP search | 2 | Core | T003,T007 | `/workspaces/flow_squared/src/fs2/mcp/server.py` | T007 tests pass | DYK-004: Lines 593-594 + import |
| [ ] | T009 | Update MCP search docstring | 1 | Core | T008 | `/workspaces/flow_squared/src/fs2/mcp/server.py` | Docstring mentions glob support | DYK-004: Lines 544-545 "(regex patterns)" → "(glob or regex)" |
| [ ] | T010 | Write backward compatibility tests | 2 | Test | T005,T008 | `/workspaces/flow_squared/tests/unit/cli/test_search_cli.py` | Existing regex patterns pass through unchanged | Verify all 13 existing tests in `TestSearchIncludeExcludeOptions` still pass |
| [ ] | T011 | Run full test suite | 1 | Validation | T010 | -- | `pytest tests/unit/cli/test_search_cli.py tests/mcp_tests/` passes | Final validation |
| [ ] | T012 | Manual end-to-end validation | 1 | Validation | T011 | `/workspaces/flow_squared/scratch/graph.pickle` | All baseline tests pass (see Manual Testing section) | Use scratch graph |

### Task Details

#### T002: Unit Tests for Pattern Normalization

```python
# tests/unit/utils/test_pattern_utils.py
import pytest
import re
from fs2.core.utils.pattern_utils import normalize_filter_pattern

@pytest.mark.unit
class TestPatternNormalizationConversion:
    """Test glob→regex conversion with backward compatibility."""

    @pytest.mark.parametrize("input_pattern,expected", [
        # Glob patterns - converted with anchor
        ("*.py", r".*\.py(?:$|:)"),
        ("*.gd", r".*\.gd(?:$|:)"),
        ("*.cs", r".*\.cs(?:$|:)"),
        # Trailing glob (DYK-002: ends with * but not .*)
        ("test_*", r"test_.*(?:$|:)"),
        ("src/*", r"src/.*(?:$|:)"),
        # Question mark glob (DYK-005: ? wildcard)
        ("file?.py", r"file.\.py(?:$|:)"),
        ("test_?.cs", r"test_..\.cs(?:$|:)"),
        # Extension patterns - escaped and anchored
        (".py", r"\.py(?:$|:)"),
        (".gd", r"\.gd(?:$|:)"),
    ])
    def test_glob_patterns_converted(self, input_pattern, expected):
        result = normalize_filter_pattern(input_pattern)
        assert result == expected

    @pytest.mark.parametrize("pattern", [
        "Calculator.*",  # Valid regex with .*
        ".*test.*",      # Match anything with test
        "src/",          # Simple substring
        "^class:",       # Anchored regex
        r"\.py$",        # Explicit end anchor
    ])
    def test_regex_patterns_pass_through_unchanged(self, pattern):
        """CRITICAL: Existing regex patterns must not be converted."""
        result = normalize_filter_pattern(pattern)
        assert result == pattern

    @pytest.mark.parametrize("pattern", ["", " ", "\t", "  \t  "])
    def test_empty_patterns_rejected(self, pattern):
        with pytest.raises(ValueError, match="empty"):
            normalize_filter_pattern(pattern)

    def test_fnmatch_format_assumption(self):
        """Verify fnmatch output format hasn't changed (DYK-003).

        If this test fails after a Python upgrade, the _convert_glob_to_regex
        function needs to be updated to handle the new format.
        """
        import fnmatch
        result = fnmatch.translate("*.py")
        assert result == r"(?s:.*\.py)\Z", f"fnmatch format changed! Got: {result}"


@pytest.mark.unit
class TestPatternMatching:
    """Verify converted patterns match expected node_ids."""

    @pytest.mark.parametrize("pattern,node_id,should_match", [
        # File nodes (extension at end)
        (".cs", "file:src/Foo.cs", True),
        (".cs", "file:src/Foo.css", False),
        # Symbol nodes (extension before :)
        (".cs", "type:src/Foo.cs:FooClass", True),
        (".py", "callable:src/test.py:TestClass.method", True),
        # Glob patterns
        ("*.gd", "file:scripts/player.gd", True),
        ("*.gd", "callable:scripts/player.gd:Player.move", True),
    ])
    def test_pattern_matches_node_ids(self, pattern, node_id, should_match):
        regex = normalize_filter_pattern(pattern)
        match = re.search(regex, node_id)
        assert bool(match) == should_match
```

#### T003: Pattern Normalization Implementation

```python
# src/fs2/core/utils/pattern_utils.py
"""Pattern normalization utilities for glob/regex filter support."""

import fnmatch
import re


def normalize_filter_pattern(pattern: str) -> str:
    """Convert glob patterns to regex for node_id matching.

    Uses GLOB-DETECTION-FIRST algorithm (DYK Insight #1):
    1. Extension patterns (.py, .cs) - always convert (unambiguous glob intent)
    2. Starts with * (*.py) - always convert (invalid regex anyway)
    3. Ends with * but not .* (test_*) - convert (likely glob intent)
    4. Contains ? after word char - convert (likely glob intent)
    5. All else - try as regex (Calculator.*, src/, ^class:)

    Node ID format assumption:
        file:path/to/file.ext
        category:path/to/file.ext:Symbol

    The anchor (?:$|:) matches at end of string OR before colon.

    Args:
        pattern: User-provided filter pattern (glob or regex)

    Returns:
        Regex pattern suitable for re.search()

    Raises:
        ValueError: If pattern is empty/whitespace or invalid
    """
    # Validate non-empty
    if not pattern or not pattern.strip():
        raise ValueError(
            "Filter pattern cannot be empty or whitespace-only. "
            "Provide a pattern like '*.py' or 'src/'"
        )

    # CRITICAL: Detect OBVIOUS glob patterns FIRST (DYK Insight #1)
    # These are unambiguous glob intent, even if technically valid regex

    # 1. Extension pattern (.py, .cs) - always convert
    if re.match(r"^\.\w+$", pattern):
        return re.escape(pattern) + r"(?:$|:)"

    # 2. Starts with * (*.py) - always convert (invalid regex anyway)
    if pattern.startswith("*"):
        return _convert_glob_to_regex(pattern)

    # 3. Ends with * but NOT .* (test_*) - likely glob intent
    if pattern.endswith("*") and not pattern.endswith(".*"):
        return _convert_glob_to_regex(pattern)

    # 4. Contains ? after word char (file?.py) - likely glob
    if re.search(r"\w\?", pattern):
        return _convert_glob_to_regex(pattern)

    # 5. All else - try as regex (Calculator.*, src/, ^class:)
    try:
        re.compile(pattern)
        return pattern
    except re.error as e:
        raise ValueError(f"Invalid pattern '{pattern}': {e}")


def _convert_glob_to_regex(pattern: str) -> str:
    """Convert glob pattern to regex with node_id anchor.

    Uses fnmatch.translate() and adds (?:$|:) anchor to handle
    both file nodes (ext at end) and symbol nodes (ext before :).
    """
    translated = fnmatch.translate(pattern)

    # fnmatch.translate returns (?s:CORE)\Z - extract core pattern
    # Use regex for safer extraction in case format changes
    match = re.match(r"^\(\?s:(.*)\)\\Z$", translated)
    if match:
        core = match.group(1)
    else:
        # Format changed - fall back to string manipulation with warning
        core = translated.replace(r"\Z", "").lstrip("(?s:").rstrip(")")

    # Add anchor for node_id format: matches at end OR before colon
    return core + r"(?:$|:)"
```

#### T005: CLI Integration

```python
# In src/fs2/cli/search.py - add import at top
from fs2.core.utils.pattern_utils import normalize_filter_pattern

# Replace lines 152-155 with:
# Convert glob patterns to regex, then to tuples for QuerySpec
if include:
    include_patterns = tuple(normalize_filter_pattern(p) for p in include)
else:
    include_patterns = None

if exclude:
    exclude_patterns = tuple(normalize_filter_pattern(p) for p in exclude)
else:
    exclude_patterns = None
```

#### T006: Help Text Update

```python
# In src/fs2/cli/search.py line 86, change:
# OLD: help="Keep only results matching pattern (text/regex). Repeatable for OR logic."
# NEW:
help="Filter by pattern (glob like *.py or regex). Repeatable for OR logic."
```

### Acceptance Criteria

- [ ] AC1: `fs2 search "test" --include "*.py"` returns only `.py` files (no crash)
- [ ] AC2: `fs2 search "test" --include ".gd"` matches only `.gd` files, not `gdUnit4`
- [ ] AC3: `fs2 search "test" --include ".cs"` matches `type:foo.cs:Bar` (symbol nodes)
- [ ] AC4: `fs2 search "test" --include "Calculator.*"` still works (regex backward compat)
- [ ] AC5: `fs2 search --help` shows "glob like *.py or regex"
- [ ] AC6: MCP `query` tool with `include=["*.py"]` works identically to CLI
- [ ] AC7: All existing tests in `TestSearchIncludeExcludeOptions` still pass
- [ ] AC8: Empty pattern `--include ""` raises clear error

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Pattern misclassification breaks existing regex users | Low | High | Regex-first algorithm (R1-01); backward compat tests (T010) |
| Node ID format changes break anchor | Low | Medium | Document assumption; integration tests verify format |
| fnmatch output format changes | Very Low | Medium | Regex extraction with fallback; version test |

## Manual Testing (T012)

**Graph File**: `/workspaces/flow_squared/scratch/graph.pickle` (33 MB, 498 nodes)
**NOT FOR CI**: This is manual validation only - do not add to automated tests.

### Baseline (Current Broken Behavior)

| Command | Current Result | Issue |
|---------|----------------|-------|
| `--include "*.gd"` | `ValueError: nothing to repeat` | Glob `*` invalid as regex |
| `--include ".gd"` | Matches `GdUnit4CSharpApi.cs` | `.` = any char in regex |
| `--include ".cs"` | Matches `.css` files too | `cs` substring in `css` |

### Expected Results After Fix

| Command | Expected Count | Validation |
|---------|----------------|------------|
| `--include "*.cs"` | 416+ nodes | All `.cs` files, zero `.css` |
| `--include "*.md"` | 50+ nodes | All markdown files |
| `--include "*.css"` | 2 nodes | Only `styles.css`, `breadcrumb.css` |
| `--include "*.gd"` | 0 nodes | No GDScript in graph (negative test) |

### Validation Commands

```bash
# After implementation, run these:
cd /workspaces/flow_squared

# Test 1: C# files (should get 416+, no .css)
fs2 --graph-file ./scratch/graph.pickle search "." --include "*.cs" --limit 500

# Test 2: Markdown files (should get 50+)
fs2 --graph-file ./scratch/graph.pickle search "." --include "*.md" --limit 100

# Test 3: CSS files (should get exactly 2)
fs2 --graph-file ./scratch/graph.pickle search "." --include "*.css" --limit 10

# Test 4: GDScript (should get 0 - negative test)
fs2 --graph-file ./scratch/graph.pickle search "." --include "*.gd" --limit 10

# Test 5: Symbol nodes with extension before colon
fs2 --graph-file ./scratch/graph.pickle search "." --include ".cs" --limit 10
# Should match: type:...ThreadSafetyTests.cs:ThreadSafetyTests...

# Test 6: Exclude pattern
fs2 --graph-file ./scratch/graph.pickle search "." --include "*.cs" --exclude "*Tests*" --limit 50
```

### Critical Node IDs for Anchor Validation

Symbol nodes where extension appears BEFORE `:` (tests `(?:$|:)` anchor):
```
type:godot/godot-app/Dig.Tests/ThreadSafetyTests.cs:ThreadSafetyTests...
type:godot/godot-app/Dig.Tests/LavaPhysicsTests.cs:LavaPhysicsTests...
type:godot/godot-app/scripts/substrate/LiquidSimulator.cs:LiquidSimulator...
```

File nodes where extension is at END (tests `$` anchor):
```
file:godot/godot-app/Dig.Tests/ActiveCellTests.cs
file:docs/how/godot/tdd.md
```

## Change Footnotes Ledger

[^1]: [To be added during implementation via plan-6a]
[^2]: [To be added during implementation via plan-6a]
[^3]: [To be added during implementation via plan-6a]

---

**Next steps:**
- **Ready to implement**: `/plan-6-implement-phase --plan "docs/plans/015-search-fix/search-fix-plan.md"`
- **Optional validation**: `/plan-4-complete-the-plan` (recommended to verify task completeness)
