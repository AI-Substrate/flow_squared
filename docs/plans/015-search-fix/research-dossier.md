# Research Report: Search CLI Include/Exclude Pattern UX Issue

**Generated**: 2026-01-02T00:00:00Z
**Research Query**: "Why does `fs2 search --include '*.gs'` fail with regex error?"
**Mode**: Plan-Associated
**Location**: docs/plans/015-search-fix/research-dossier.md
**FlowSpace**: Available (fs2 MCP dogfooding)
**Findings**: 12 total

## Executive Summary

### What's Happening
The `fs2 search` command's `--include` and `--exclude` options expect **regex patterns**, but users naturally provide **glob patterns** (like `*.py` or `.gd`). This causes two failure modes:
1. **Hard failure**: Glob patterns with `*` at start are invalid regex → crashes
2. **Silent failure**: Patterns like `.gd` match incorrectly (`.` = any char in regex)

### Business Impact
- Users cannot filter search results by file extension without knowing regex
- Error messages don't guide users toward the correct syntax
- Violates principle of least surprise (glob patterns work everywhere else)

### Key Insights
1. `--include "*.gs"` fails because `*` at position 0 is invalid regex
2. `--include ".gd"` silently matches wrong files (e.g., CSS files in `gdUnit4/`)
3. Fix is straightforward: auto-detect glob patterns and convert via `fnmatch.translate()`
4. Conversion should happen in CLI layer, keeping `QuerySpec` pure

### Quick Stats
- **Components Affected**: 2 files (CLI, QuerySpec)
- **Test Coverage**: Good - invalid regex test exists, but no glob conversion tests
- **Complexity**: Low - well-isolated change
- **Risk**: Low - additive behavior, backward compatible

## Problem Analysis

### Failure Mode 1: Invalid Regex Error

**User command**:
```bash
fs2 search "navigation curve" --include "*.gs"
```

**Error**:
```
ValueError: Invalid regex in include pattern '*.gs': nothing to repeat at position 0
```

**Root cause**: In regex, `*` is a quantifier meaning "zero or more of the preceding element". At position 0, there's nothing to repeat.

| Syntax | Glob meaning | Regex meaning |
|--------|--------------|---------------|
| `*` | Match any characters | Zero or more of preceding |
| `.` | Literal dot | Any single character |
| `?` | Any single character | Zero or one of preceding |

### Failure Mode 2: Silent Wrong Matches

**User command**:
```bash
fs2 search "navigation curve" --include ".gd"
```

**Expected**: Only `.gd` files (GDScript)
**Actual**: Matched `breadcrumb.css` and other files

**Root cause**: `.gd` as regex means "any character followed by 'gd'". The path `godot/godot-app/addons/gdUnit4/...` contains `gdUnit4` which has `gd` preceded by a character.

**Correct regex would be**: `\.gd$` (escaped dot, literal "gd", end of string)

## How It Currently Works

### Entry Points

| Entry Point | Type | Location | Purpose |
|------------|------|----------|---------|
| `fs2 search` | CLI Command | `src/fs2/cli/search.py:46` | Search with filters |
| `mcp__flowspace__query` | MCP Tool | MCP server | Programmatic search |

### Core Execution Flow

1. **CLI Parsing** (`search.py:82-95`)
   - `--include` and `--exclude` parsed as `list[str]`
   - No transformation applied
   - Passed directly to QuerySpec

2. **QuerySpec Construction** (`search.py:189`)
   ```python
   spec = QuerySpec(
       pattern=pattern,
       mode=search_mode,
       limit=10000,
       ...
       include=include_patterns,  # Raw user input
       exclude=exclude_patterns,
   )
   ```

3. **Validation** (`query_spec.py:102-116`)
   ```python
   if self.include:
       for p in self.include:
           try:
               re.compile(p)
           except re.error as e:
               raise ValueError(f"Invalid regex in include pattern '{p}': {e}")
   ```

4. **Filter Application** (in SearchService)
   - Patterns applied via `re.search()` against `node_id`
   - Matches anywhere in string (not anchored)

### Data Flow

```
User Input: "*.gs"
     │
     ▼
CLI Layer (no transformation)
     │
     ▼
QuerySpec.__post_init__()
     │
     ▼
re.compile("*.gs") → FAILS
     │
     ▼
ValueError raised
```

## Architecture & Design

### Component Map

```
src/fs2/
├── cli/
│   └── search.py          # CLI command definition
│       └── search()       # Typer command handler
│
└── core/
    └── models/
        └── search/
            └── query_spec.py  # QuerySpec frozen dataclass
                └── __post_init__()  # Regex validation
```

### Current Design Decisions

1. **QuerySpec expects regex** - Documented in docstring:
   ```python
   include: Tuple of regex patterns - keep only node_ids matching ANY pattern.
   ```

2. **Validation happens at construction** - `__post_init__` validates all patterns compile

3. **No pattern transformation** - User input passed through unchanged

### Help Text Analysis

Current help text (`search.py:86`):
```python
help="Keep only results matching pattern (text/regex). Repeatable for OR logic."
```

**Problem**: "text/regex" is ambiguous. Users interpret "text" as simple matching (like grep) which often uses glob-like patterns.

## Dependencies & Integration

### What This Affects

| Consumer | Impact | Breaking Change Risk |
|----------|--------|---------------------|
| CLI users | Primary beneficiary | None (additive) |
| MCP tools | Should also convert | None (additive) |
| Tests | Need new test cases | None |

### External Dependencies

| Dependency | Purpose | Notes |
|------------|---------|-------|
| `fnmatch` | Glob to regex conversion | Python stdlib, no new dep |
| `re` | Pattern validation | Already used |

## Quality & Testing

### Current Test Coverage

**Existing tests** (`test_search_cli.py`):
- `test_given_include_flag_when_search_then_shows_in_help` - Help registered
- `test_given_include_flag_when_search_then_keeps_only_matching` - Basic filtering
- `test_given_regex_include_when_search_then_pattern_matches` - Regex works
- `test_given_invalid_regex_when_search_then_error` - Invalid regex fails

**Missing tests**:
- Glob pattern conversion
- Extension patterns (`.py`, `.gd`)
- Mixed glob/regex handling

### Test Gap Analysis

| Scenario | Current Coverage | Needed |
|----------|-----------------|--------|
| Valid regex | Yes | - |
| Invalid regex | Yes | - |
| Glob `*.ext` | No | Add |
| Extension `.ext` | No | Add |
| Glob with `?` | No | Add |

## Proposed Solution

### Approach: Auto-detect and Convert Glob Patterns

**Location**: CLI layer (`src/fs2/cli/search.py`) - transform before QuerySpec

**Why CLI layer**:
1. Keeps QuerySpec pure (always receives regex)
2. Can also be used by MCP tools
3. Transformation logic isolated and testable

### Implementation

```python
# New utility function (could be in fs2/core/utils/pattern_utils.py)
import fnmatch
import re

def normalize_filter_pattern(pattern: str) -> str:
    """Convert glob patterns to regex for node_id matching.

    Node ID formats (extension is NOT always at end):
    - file:path/to/file.ext           ← extension at end
    - type:path/to/file.ext:ClassName ← extension before ':'
    - callable:path/to/file.ext:Class.method ← extension before ':'

    Detection heuristics:
    - Starts with '*' → definitely glob (invalid regex)
    - Matches r'^\\.\\w+$' (e.g., '.gd', '.py') → extension filter
    - Contains '*' or '?' → likely glob

    Args:
        pattern: User-provided filter pattern

    Returns:
        Regex pattern suitable for re.search()
    """
    # Pattern starting with * is definitely glob (would fail as regex)
    if pattern.startswith('*'):
        translated = fnmatch.translate(pattern)
        # fnmatch.translate returns (?s:...)\Z, extract the core pattern
        core = translated.replace(r'\Z', '').lstrip('(?s:').rstrip(')')
        # Match at end of string OR before colon (symbol separator)
        return core + r'(?:$|:)'

    # Pattern like ".gd", ".py", ".cs" - simple extension filter
    if re.match(r'^\.\w+$', pattern):
        # Escape the dot, match at end OR before colon
        # This handles both:
        #   file:path/to/file.cs        ← .cs at end
        #   type:path/to/file.cs:Class  ← .cs before :
        return re.escape(pattern) + r'(?:$|:)'

    # Contains glob metacharacters
    if '*' in pattern or '?' in pattern:
        translated = fnmatch.translate(pattern)
        core = translated.replace(r'\Z', '').lstrip('(?s:').rstrip(')')
        return core + r'(?:$|:)'

    # Assume it's already valid regex
    return pattern
```

### Conversion Examples

| User Input | Detected As | Converted To | Matches |
|------------|-------------|--------------|---------|
| `*.cs` | glob | `.*\.cs(?:$|:)` | `file:foo.cs` AND `type:foo.cs:Bar` |
| `.cs` | extension | `\.cs(?:$|:)` | Same - works for files and symbols |
| `.gd` | extension | `\.gd(?:$|:)` | GDScript files and their symbols |
| `.py` | extension | `\.py(?:$|:)` | Python files and their symbols |
| `test_*` | glob | `test_.*(?:$|:)` | Nodes starting with test_ |
| `src/` | regex | `src/` | Paths containing src/ (unchanged) |
| `.*\.py$` | regex | `.*\.py$` | Unchanged (explicit regex) |

**Key insight**: Node IDs have format `category:path:symbol`, so extension `.cs` appears BEFORE the `:symbol` part, not at end of string. The pattern `(?:$|:)` handles both file nodes (end of string) and symbol nodes (before colon).

### Integration Points

**CLI (`search.py`)**:
```python
# Before creating QuerySpec
if include:
    include_patterns = tuple(normalize_filter_pattern(p) for p in include)
else:
    include_patterns = None

if exclude:
    exclude_patterns = tuple(normalize_filter_pattern(p) for p in exclude)
else:
    exclude_patterns = None
```

**MCP tool** (if applicable):
```python
# Same conversion in MCP query handler
```

**Help text update**:
```python
help="Filter by pattern (glob like *.py or regex). Repeatable for OR logic."
```

## Modification Considerations

### Safe to Modify
- CLI layer pattern handling - isolated, no downstream dependencies
- Help text - documentation only

### Modify with Caution
- QuerySpec validation - keep pure (regex only), don't add glob detection here

### Extension Points
- Could add `--glob` and `--regex` explicit flags in future
- Could make conversion configurable via settings

## Critical Discoveries

### Discovery 1: Two Distinct Failure Modes
**Impact**: Critical
**Finding**: Users experience either hard crash (invalid regex) or silent wrong results (regex matches too broadly)

### Discovery 2: Help Text is Misleading
**Impact**: High
**Finding**: "text/regex" doesn't communicate that regex syntax is required

### Discovery 3: fnmatch.translate() Handles Conversion
**Impact**: Medium (positive)
**Finding**: Python stdlib provides reliable glob→regex conversion

### Discovery 4: Node ID Format Requires Special Anchoring
**Impact**: Critical
**Finding**: Node IDs have format `category:path/file.ext:SymbolName`, so file extensions appear BEFORE the colon separator, not at end of string. Simple `$` anchoring fails for symbol nodes.

**Example**:
```
type:godot/godot-app/Dig.Tests/CompletionTokenTests.cs:CompletionTokenTests.CompletionToken_SetAfterSimulateType_Lava
                                                    ^^
                                                    .cs is HERE, not at end
```

**Solution**: Use `(?:$|:)` anchor pattern to match extension at end of string OR before colon.

## Recommendations

### If Implementing This Fix

1. **Create pattern utility module** - `fs2/core/utils/pattern_utils.py`
2. **Add normalize_filter_pattern()** - With detection heuristics
3. **Update CLI to use it** - Transform before QuerySpec
4. **Update help text** - Mention glob support
5. **Add tests** - For all conversion scenarios

### Backward Compatibility

- Existing regex patterns continue to work unchanged
- No breaking changes for current users
- Purely additive improvement

### Test Strategy

```python
class TestPatternNormalization:
    """Test glob to regex conversion for node_id matching."""

    @pytest.mark.parametrize("input_pattern,expected", [
        # Glob patterns - converted with (?:$|:) anchor
        ("*.py", r".*\.py(?:$|:)"),
        ("*.gd", r".*\.gd(?:$|:)"),
        ("*.cs", r".*\.cs(?:$|:)"),
        ("test_*", r"test_.*(?:$|:)"),
        # Extension patterns - escaped and anchored
        (".py", r"\.py(?:$|:)"),
        (".gd", r"\.gd(?:$|:)"),
        (".cs", r"\.cs(?:$|:)"),
        # Plain text/regex - unchanged
        ("src/", "src/"),
        ("Calculator", "Calculator"),
        (r".*\.py$", r".*\.py$"),  # Already regex
    ])
    def test_glob_conversion(self, input_pattern, expected):
        result = normalize_filter_pattern(input_pattern)
        assert result == expected

    @pytest.mark.parametrize("pattern,node_id,should_match", [
        # Extension pattern matches both file and symbol nodes
        (".cs", "file:src/Foo.cs", True),
        (".cs", "type:src/Foo.cs:FooClass", True),
        (".cs", "callable:src/Foo.cs:FooClass.Method", True),
        (".cs", "file:src/Foo.css", False),  # .css != .cs
        # Glob pattern
        ("*.gd", "file:scripts/player.gd", True),
        ("*.gd", "callable:scripts/player.gd:Player.move", True),
        ("*.gd", "file:scripts/player.gds", False),  # .gds != .gd
    ])
    def test_pattern_matching(self, pattern, node_id, should_match):
        regex = normalize_filter_pattern(pattern)
        match = re.search(regex, node_id)
        assert bool(match) == should_match
```

## File Inventory

### Core Files

| File | Purpose | Lines | Modification Needed |
|------|---------|-------|---------------------|
| `src/fs2/cli/search.py` | CLI command | 270 | Add pattern conversion |
| `src/fs2/core/models/search/query_spec.py` | Query model | 117 | None (keep pure) |

### New Files

| File | Purpose |
|------|---------|
| `src/fs2/core/utils/pattern_utils.py` | Pattern conversion utility |
| `tests/unit/utils/test_pattern_utils.py` | Conversion tests |

### Test Files

| File | Changes Needed |
|------|----------------|
| `tests/unit/cli/test_search_cli.py` | Add glob pattern tests |

## Next Steps

1. **Create spec**: Run `/plan-1b-specify "Add glob pattern support to search --include/--exclude"`
2. **Implement**: Create utility, update CLI, add tests
3. **Update docs**: Help text and any user-facing documentation

---

**Research Complete**: 2026-01-02
**Report Location**: /workspaces/flow_squared/docs/plans/015-search-fix/research-dossier.md
