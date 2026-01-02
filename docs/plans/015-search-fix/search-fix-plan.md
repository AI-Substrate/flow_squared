# Glob Pattern Support for Search Filters - Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-01-02
**Spec**: [./search-fix-spec.md](./search-fix-spec.md)
**Status**: DRAFT

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
| 05 | High | **Test fixtures exist**: `scanned_project` for CLI, real graph for MCP tests | Extend `TestSearchIncludeExcludeOptions` class |
| 06 | Medium | **fnmatch format dependency**: `fnmatch.translate()` returns `(?s:...)\Z` format | Use regex extraction with explicit format check |
| 07 | Medium | **Empty pattern handling**: Empty strings compile as valid regex but are semantically wrong | Add validation layer in normalize function |
| 08 | Low | **Extension edge cases**: `.py-old` won't match `^\.\w+$` pattern | Accept limitation, document behavior |

**Algorithm Fix (from R1-01)**:
```python
def normalize_filter_pattern(pattern: str) -> str:
    # CRITICAL: Check valid regex FIRST for backward compatibility
    try:
        re.compile(pattern)
        return pattern  # Valid regex, pass through unchanged
    except re.error:
        pass  # Not valid regex, try glob detection

    # Only now try glob conversion (pattern failed regex validation)
    # ... glob detection and conversion
```

## Implementation (Single Phase)

**Objective**: Enable glob pattern support for `--include`/`--exclude` filters in both CLI and MCP, with full backward compatibility.

**Testing Approach**: Full TDD - Write tests first, use `scanned_project` fixture
**Mock Usage**: Avoid mocks - use fixtures and fakes per codebase convention

### Tasks

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Notes |
|--------|-----|------|----|------|--------------|------------------|------------|-------|
| [ ] | T001 | Create utils module structure | 1 | Setup | -- | `/workspaces/flow_squared/src/fs2/core/utils/__init__.py`, `/workspaces/flow_squared/src/fs2/core/utils/pattern_utils.py` | Module imports without error | mkdir + touch |
| [ ] | T002 | Write unit tests for `normalize_filter_pattern()` | 2 | Test | T001 | `/workspaces/flow_squared/tests/unit/utils/test_pattern_utils.py` | Tests exist, all fail initially (RED) | TDD: tests first |
| [ ] | T003 | Implement `normalize_filter_pattern()` with safe algorithm | 2 | Core | T002 | `/workspaces/flow_squared/src/fs2/core/utils/pattern_utils.py` | All T002 tests pass (GREEN) | Regex-first algorithm per R1-01 |
| [ ] | T004 | Write CLI integration tests for glob patterns | 2 | Test | T003 | `/workspaces/flow_squared/tests/unit/cli/test_search_cli.py` | New tests in `TestSearchGlobPatterns` class | Extend existing test file |
| [ ] | T005 | Integrate pattern conversion into CLI search | 2 | Core | T003 | `/workspaces/flow_squared/src/fs2/cli/search.py` | T004 tests pass, existing tests still pass | Lines 152-155 + import |
| [ ] | T006 | Update CLI help text | 1 | Core | T005 | `/workspaces/flow_squared/src/fs2/cli/search.py` | Help shows "glob like *.py or regex" | Line 86-87 |
| [ ] | T007 | Write MCP integration tests for glob patterns | 2 | Test | T003 | `/workspaces/flow_squared/tests/mcp_tests/test_search_tool.py` | New tests for glob in MCP search | May need fixture adjustment |
| [ ] | T008 | Integrate pattern conversion into MCP search | 2 | Core | T003,T007 | `/workspaces/flow_squared/src/fs2/mcp/server.py` | T007 tests pass | Lines 592-604 + import |
| [ ] | T009 | Update MCP search docstring | 1 | Core | T008 | `/workspaces/flow_squared/src/fs2/mcp/server.py` | Docstring mentions glob support | Lines 544-545 |
| [ ] | T010 | Write backward compatibility tests | 2 | Test | T005,T008 | `/workspaces/flow_squared/tests/unit/cli/test_search_cli.py` | Existing regex patterns pass through unchanged | Critical for R1-01 |
| [ ] | T011 | Run full test suite | 1 | Validation | T010 | -- | `pytest tests/unit/cli/test_search_cli.py tests/mcp_tests/` passes | Final validation |
| [ ] | T012 | Manual end-to-end validation | 1 | Validation | T011 | -- | `fs2 search "test" --include "*.py"` works in real project | Smoke test |

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
        ("test_*", r"test_.*(?:$|:)"),
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

    Handles three pattern types:
    1. Valid regex patterns - passed through unchanged (backward compatible)
    2. Glob patterns (*.py, test_*) - converted via fnmatch
    3. Extension patterns (.py) - escaped and anchored

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

    # CRITICAL: Check valid regex FIRST for backward compatibility
    # This ensures patterns like "Calculator.*" pass through unchanged
    try:
        re.compile(pattern)
        return pattern  # Valid regex, use as-is
    except re.error:
        pass  # Not valid regex, try glob detection

    # Pattern failed regex validation - try glob conversion

    # Glob starting with * (e.g., *.py)
    if pattern.startswith("*"):
        return _convert_glob_to_regex(pattern)

    # Extension pattern (e.g., .py, .gd)
    if re.match(r"^\.\w+$", pattern):
        return re.escape(pattern) + r"(?:$|:)"

    # Contains glob chars anywhere
    if "*" in pattern or "?" in pattern:
        return _convert_glob_to_regex(pattern)

    # Pattern is invalid as both regex and glob
    raise ValueError(
        f"Pattern '{pattern}' is neither valid regex nor recognizable glob. "
        "Use patterns like '*.py' (glob) or 'src/' (substring) or 'Calculator.*' (regex)"
    )


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

## Change Footnotes Ledger

[^1]: [To be added during implementation via plan-6a]
[^2]: [To be added during implementation via plan-6a]
[^3]: [To be added during implementation via plan-6a]

---

**Next steps:**
- **Ready to implement**: `/plan-6-implement-phase --plan "docs/plans/015-search-fix/search-fix-plan.md"`
- **Optional validation**: `/plan-4-complete-the-plan` (recommended to verify task completeness)
