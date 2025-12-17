# fs2 tree Command Implementation Plan

**Plan Version**: 1.0.0
**Created**: 2025-12-17
**Spec**: [./tree-command-spec.md](./tree-command-spec.md)
**Status**: READY

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Technical Context](#technical-context)
3. [Critical Research Findings](#critical-research-findings)
4. [Testing Philosophy](#testing-philosophy)
5. [Implementation Phases](#implementation-phases)
   - [Phase 1: Core Tree Command with Path Filtering](#phase-1-core-tree-command-with-path-filtering)
   - [Phase 2: Detail Levels and Depth Limiting](#phase-2-detail-levels-and-depth-limiting)
   - [Phase 3: File-Type-Specific Handling and Polish](#phase-3-file-type-specific-handling-and-polish)
6. [Cross-Cutting Concerns](#cross-cutting-concerns)
7. [Complexity Tracking](#complexity-tracking)
8. [Progress Tracking](#progress-tracking)
9. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

**Problem Statement**: Users need to quickly visualize and navigate code structure without reading source files. Currently, there's no way to explore the scanned code graph hierarchy, understand file→class→method relationships, or get FlowSpace-compatible node IDs for downstream tool usage.

**Solution Approach**:
- Create new `fs2 tree` CLI command using Rich Tree API for hierarchical display
- Leverage existing GraphStore ABC and NetworkXGraphStore for graph traversal
- Implement two-pass pattern matching (glob detection with path prefix fallback)
- Follow established CLI patterns from `scan.py` and `init.py`

**Expected Outcomes**:
- Visual tree representation of code structure from persisted graph
- Path/glob filtering with `--detail min|max` and `--depth N` options
- FlowSpace-compatible node IDs displayed in `--detail max` mode
- Scan freshness indicator in summary line

**Success Metrics**:
- All 16 acceptance criteria (AC1-AC16) verified via tests
- Exit codes follow 0/1/2 convention
- Performance: <200ms for graphs with <1000 nodes

---

## Technical Context

### Current System State

The fs2 codebase has complete infrastructure for this feature:
- **GraphStore ABC** (`src/fs2/core/repos/graph_store.py`): Provides `get_all_nodes()`, `get_children()`, `get_parent()`, `load()`
- **NetworkXGraphStore** (`src/fs2/core/repos/graph_store_impl.py`): Production implementation with pickle persistence
- **CodeNode model** (`src/fs2/core/models/code_node.py`): 23-field frozen dataclass with hierarchy support
- **CLI framework** (`src/fs2/cli/`): Typer app with `scan` and `init` commands registered

### Integration Requirements

| Component | Interface | Usage |
|-----------|-----------|-------|
| GraphStore ABC | `get_all_nodes()`, `get_children()`, `load()` | Read graph data |
| ConfigurationService | `require(ScanConfig)` | Get graph file path |
| Rich Console | `Console()`, `Tree()` | Terminal output and tree rendering |
| Typer | `@app.command()`, `Annotated[]` | CLI argument parsing |

### Constraints and Limitations

1. **Graph must be pre-loaded**: Tree shows persisted graph state, not live files
2. **Data files (YAML/JSON/TOML)**: Tree-sitter only creates file-level nodes (no internal structure)
3. **Memory**: Full graph load required for tree traversal (get_all_nodes())
4. **No interactive mode**: Output is static text, not TUI browser

### Assumptions

1. Graph file exists at `.fs2/graph.pickle` (created by `fs2 scan`)
2. Rich library available for tree rendering
3. CodeNode `language` field accurately identifies file type for icon selection
4. Users understand glob pattern syntax

---

## Critical Research Findings

### Deduplication Log

| Final # | Source Discoveries | Merge Reason |
|---------|-------------------|--------------|
| 01 | S4-01, S1-05 | Both cover GraphStore ABC injection pattern |
| 05 | S3-01, S3-05 | Both require GraphStore metadata extension |
| 09 | S1-04, S4-08 | Both cover exit codes and error translation |

### 🚨 Critical Discovery 01: GraphStore ABC Pattern with DI

**Impact**: Critical
**Sources**: [S4-01, S1-05]
**Problem**: Tree command must decide between using GraphStore ABC interface or NetworkXGraphStore directly
**Root Cause**: Clean Architecture requires composition root creates impls, but logic operates on ABCs
**Solution**: CLI creates NetworkXGraphStore (impl) but passes via GraphStore ABC parameter
**Example**:
```python
# CORRECT - CLI is composition root
def tree(verbose: bool = False) -> None:
    config = FS2ConfigurationService()
    graph_store = NetworkXGraphStore(config)  # Creates impl
    _display_tree(graph_store)  # Passes as ABC

def _display_tree(store: GraphStore) -> None:  # Type hint uses ABC
    nodes = store.get_all_nodes()
```
**Action Required**: Import GraphStore ABC for type hints; create NetworkXGraphStore in CLI body
**Affects Phases**: Phase 1

---

### 🚨 Critical Discovery 02: ConfigurationService No Concept Leakage

**Impact**: Critical
**Sources**: [S4-02]
**Problem**: Tree command must NOT extract ScanConfig at CLI boundary
**Root Cause**: Constitution P3 forbids composition root from calling config.require()
**Solution**: GraphStore internally calls config.require(ScanConfig); CLI only passes registry
**Example**:
```python
# FORBIDDEN - Concept leakage
scan_cfg = config.require(ScanConfig)  # NO!

# CORRECT - Pass registry only
graph_store = NetworkXGraphStore(config)  # Config passed to impl
```
**Action Required**: Never call `config.require(ScanConfig)` in CLI; pass ConfigurationService
**Affects Phases**: Phase 1

---

### 🚨 Critical Discovery 03: Need TreeConfig for graph_path

**Impact**: Critical
**Sources**: [S4-03]
**Problem**: ScanConfig has no graph_path field; tree needs to know where pickle is stored
**Root Cause**: ScanConfig stores scan directories, not output paths
**Solution**: Create TreeConfig in config/objects.py with graph_path field
**Example**:
```python
class TreeConfig(BaseModel):
    __config_path__: ClassVar[str] = "tree"
    graph_path: str = ".fs2/graph.pickle"
```
**Action Required**: Add TreeConfig to config/objects.py; register in YAML_CONFIG_TYPES
**Affects Phases**: Phase 1

---

### 🚨 Critical Discovery 04: Command Registration Pattern

**Impact**: Critical
**Sources**: [S1-01]
**Problem**: Tree command must be registered consistently with existing commands
**Root Cause**: Commands use `app.command(name="X")(func)` pattern, not decorators
**Solution**: Follow exact pattern from scan.py
**Example**:
```python
# In main.py
from fs2.cli.tree import tree
app.command(name="tree")(tree)
```
**Action Required**: Create tree.py; add import and registration to main.py
**Affects Phases**: Phase 1

---

### 🚨 Critical Discovery 05: GraphStore Needs get_metadata() Extension

**Impact**: Critical
**Sources**: [S3-01, S3-05]
**Problem**: AC9 requires scan freshness ("scanned 2h ago"); AC16 requires node count warning (>10K)
**Root Cause**: GraphStore has no method to access loaded metadata (created_at, node_count)
**Solution**: Extend GraphStore ABC with `get_metadata() -> dict` method
**Example**:
```python
@abstractmethod
def get_metadata(self) -> dict[str, Any]:
    """Return loaded graph metadata: format_version, created_at, node_count, edge_count."""
    ...
```
**Action Required**: Add abstract method to GraphStore ABC; implement in NetworkXGraphStore
**Affects Phases**: Phase 1, Phase 3

---

### Discovery 06: Pattern Matching Semantics

**Impact**: High
**Sources**: [S3-02]
**Problem**: Spec defines path filtering (AC2) vs glob filtering (AC3) but not how to distinguish them
**Root Cause**: Single PATTERN argument; no explicit flag for glob vs path
**Solution**: Two-pass detection: check for glob characters (`*?[]`); if found use glob, else path prefix
**Example**:
```python
import fnmatch
def is_glob_pattern(pattern: str) -> bool:
    return any(c in pattern for c in '*?[]')

if is_glob_pattern(pattern):
    matches = [n for n in nodes if fnmatch.fnmatch(n.node_id, pattern)]
else:
    matches = [n for n in nodes if pattern in n.node_id]
```
**Action Required**: Implement two-pass pattern detection in tree command
**Affects Phases**: Phase 1

---

### Discovery 07: Typer Options Pattern with Annotated

**Impact**: High
**Sources**: [S1-02]
**Problem**: CLI options must follow established pattern for consistency
**Root Cause**: Typer requires Annotated type hints for proper documentation
**Solution**: Use `Annotated[type, typer.Option(...)]` pattern
**Example**:
```python
def tree(
    pattern: Annotated[str, typer.Argument(default=".")] = ".",
    detail: Annotated[str, typer.Option("--detail", help="min or max")] = "min",
    depth: Annotated[int, typer.Option("--depth", "-d")] = 0,
) -> None:
```
**Action Required**: Define all options using Annotated pattern
**Affects Phases**: Phase 1, Phase 2

---

### Discovery 08: Rich Console and Tree API

**Impact**: High
**Sources**: [S1-03, S1-06]
**Problem**: Tree rendering requires consistent output and proper hierarchy display
**Root Cause**: Rich provides Tree class for hierarchical display
**Solution**: Use module-level Console instance; Rich Tree for hierarchy
**Example**:
```python
from rich.console import Console
from rich.tree import Tree

console = Console()

def _display_tree(nodes: list[CodeNode]) -> None:
    tree = Tree(label="📁 src/")
    file_node = tree.add("📄 calculator.py [1-50]")
    file_node.add("📦 Calculator [15-45]")
    console.print(tree)
```
**Action Required**: Import Rich Tree; build tree recursively from CodeNode hierarchy
**Affects Phases**: Phase 1

---

### Discovery 09: Exit Code Convention and Error Translation

**Impact**: High
**Sources**: [S1-04, S4-08, S1-08]
**Problem**: Exit codes must be consistent; errors must be user-friendly
**Root Cause**: Scripts depend on exit codes; users need actionable messages
**Solution**: 0=success, 1=user error, 2=system error; catch GraphStoreError at boundary
**Example**:
```python
try:
    graph_store.load(graph_path)
except GraphStoreError as e:
    console.print(f"[red]Error:[/red] {e}")
    raise typer.Exit(code=1) from None
```
**Action Required**: Implement structured error handling with exit codes
**Affects Phases**: Phase 1

---

### Discovery 10: Node ID Parsing for Windows Paths

**Impact**: High
**Sources**: [S2-03]
**Problem**: Node ID format `category:path:qualified_name` breaks on Windows paths with colons
**Root Cause**: `C:\path` contains colon that conflicts with separator
**Solution**: Use `rfind()` based parsing from right side
**Example**:
```python
def parse_node_id(node_id: str) -> tuple[str, str, str]:
    last_colon = node_id.rfind(":")
    second_colon = node_id.rfind(":", 0, last_colon)
    category = node_id[:second_colon]
    # ... handle edge cases
```
**Action Required**: Implement robust node_id parsing if needed for filtering
**Affects Phases**: Phase 1

---

### Discovery 11: Depth Limit Indicator Format

**Impact**: Medium
**Sources**: [S3-03]
**Problem**: AC6 requires "indicator for hidden children" but doesn't define format
**Root Cause**: Spec has no example output for `--depth N`
**Solution**: Show inline count: `[N children hidden by depth limit]`
**Example**:
```
📄 calculator.py [1-50]
├── 📦 Calculator [15-45]
│   └── [3 children hidden by depth limit]
```
**Action Required**: Implement depth tracking and hidden child counter
**Affects Phases**: Phase 2

---

### Discovery 12: NetworkX Edge Direction - Use get_children()

**Impact**: Medium
**Sources**: [S2-02]
**Problem**: Graph edges are parent→child direction; must not use parent_node_id directly
**Root Cause**: Dual source of truth between parent_node_id field and graph edges
**Solution**: Always use `get_children()` for tree traversal, not parent_node_id
**Example**:
```python
# CORRECT
children = graph_store.get_children(node_id)

# AVOID - may be inconsistent
children_by_field = [n for n in all_nodes if n.parent_node_id == node_id]
```
**Action Required**: Use GraphStore API methods exclusively for traversal
**Affects Phases**: Phase 1

---

### Discovery 13: Icon Conventions from Spec

**Impact**: Medium
**Sources**: [S1-07]
**Problem**: Tree must use consistent icons for node categories
**Root Cause**: Spec defines exact icons; must follow for consistency
**Solution**: Map category to icon per spec
**Example**:
```python
CATEGORY_ICONS = {
    "directory": "📁",  # Virtual grouping
    "file": "📄",
    "type": "📦",
    "callable": "ƒ",
    "section": "📝",
    "block": "🏗️",
}
```
**Action Required**: Define icon mapping constant
**Affects Phases**: Phase 1

---

### Discovery 14: File Type Detection by Extension

**Impact**: Medium
**Sources**: [S3-06]
**Problem**: `language` field may be unreliable for file type detection
**Root Cause**: Tree-sitter grammar names vary; extension is stable
**Solution**: Use file extension as primary, language as fallback
**Example**:
```python
def get_file_type(node: CodeNode) -> str:
    ext = Path(node.name or "").suffix.lower()
    if ext in {".yaml", ".yml", ".json", ".toml"}:
        return "datafile"
    return node.language or "unknown"
```
**Action Required**: Implement extension-based file type detection
**Affects Phases**: Phase 3

---

### Discovery 15: Wide Tree Performance

**Impact**: Medium
**Sources**: [S2-01]
**Problem**: Rendering degrades with many siblings (1000 siblings = 83ms)
**Root Cause**: Rich Tree iterates each sibling for rendering
**Solution**: Consider grouping/pagination for very wide trees (future optimization)
**Example**: For now, accept performance for typical codebases (<100 siblings)
**Action Required**: Monitor performance; defer optimization
**Affects Phases**: Future

---

### Discovery 16: Empty Graph Edge Case

**Impact**: Medium
**Sources**: [S3-04]
**Problem**: AC8 handles pattern mismatch but not empty graph (0 nodes total)
**Root Cause**: Spec doesn't cover graph is empty case
**Solution**: Treat as valid state; show "Found 0 nodes in 0 files"
**Example**:
```
✓ Found 0 nodes in 0 files (scanned 5m ago)
```
**Action Required**: Handle empty graph case in display logic
**Affects Phases**: Phase 1

---

### Discovery 17: Signature Missing Handling

**Impact**: Medium
**Sources**: [S3-07]
**Problem**: Spec shows signature for all callables in max detail but some nodes lack signature
**Root Cause**: Anonymous functions, file nodes don't have signatures
**Solution**: Show qualified_name as fallback when signature unavailable
**Example**:
```python
sig_display = node.signature or f"({node.qualified_name})"
```
**Action Required**: Handle missing signature gracefully
**Affects Phases**: Phase 2

---

### Discovery 18: Loading Spinner and TTY Detection

**Impact**: Low
**Sources**: [S3-08]
**Problem**: AC15 requires loading spinner for >200ms loads
**Root Cause**: Need spinner library choice and TTY detection
**Solution**: Use Rich Status spinner; auto-detect TTY
**Example**:
```python
from rich.status import Status
if node_count > 5000 and sys.stdout.isatty():
    with Status("[bold green]Loading graph...", console=console):
        store.load(path)
```
**Action Required**: Implement conditional spinner with TTY detection
**Affects Phases**: Phase 3

---

### Discovery 19: Verbose Logging Pattern

**Impact**: Low
**Sources**: [S4-07]
**Problem**: Verbose mode needs proper logging setup
**Root Cause**: CLI layer should not import logger directly
**Solution**: Setup RichHandler on --verbose flag
**Example**:
```python
def _setup_verbose_logging() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_path=False)],
    )
```
**Action Required**: Implement verbose logging setup
**Affects Phases**: Phase 2

---

## Testing Philosophy

### Testing Approach

**Selected Approach**: Full TDD (per Clarifications Session 2025-12-17)
**Rationale**: Core CLI command with user-facing output requires comprehensive test coverage to ensure correct behavior across all acceptance criteria.

**Focus Areas**:
- CLI invocation and exit codes (AC7, AC8, AC13)
- Output format verification (AC1, AC4, AC5, AC9)
- Pattern matching (AC2, AC3)
- Error handling (AC7, AC13)
- File-type-specific display (AC10, AC11, AC12)

**Excluded**:
- Performance benchmarking (deferred to optimization phase)
- Visual appearance testing (manual verification sufficient)

### Test-Driven Development

Per Constitution P7 (Tests as Executable Documentation):
- Write tests FIRST (RED)
- Implement minimal code (GREEN)
- Refactor for quality (REFACTOR)

### Test Documentation

Every test MUST include:
```python
"""
Purpose: [what truth this test proves]
Quality Contribution: [how this prevents bugs]
Acceptance Criteria: [measurable assertions]
"""
```

### Mock Usage

**Policy**: Avoid mocks entirely (per Clarifications Session 2025-12-17 and Constitution P4)
- Per Constitution P4 (Fakes over Mocks), use `FakeGraphStore` ABC implementation for unit tests
- Use real `NetworkXGraphStore` for integration tests
- Monkeypatch allowed for file system and environment variables only

---

## Implementation Phases

### Phase 1: Core Tree Command with Path Filtering

**Objective**: Create functional `fs2 tree` command with basic display and path filtering.

**Deliverables**:
- `src/fs2/cli/tree.py` with tree command function
- GraphStore ABC extension with `get_metadata()` method
- TreeConfig in config/objects.py
- Unit tests for CLI invocation, exit codes, basic output
- Integration tests with real graph

**Dependencies**: None (foundational phase)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| GraphStore ABC change breaks compatibility | Low | High | Add method with default impl in abstract |
| Pattern matching edge cases | Medium | Medium | Start with simple prefix; expand in Phase 2 |

### Tasks (TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 1.1 | [x] | Write tests for TreeConfig creation and validation | 1 | Tests verify TreeConfig loads from YAML and env vars | [^6] | tests/unit/config/test_tree_config.py |
| 1.2 | [x] | Create TreeConfig in config/objects.py | 1 | TreeConfig with graph_path field; registered in YAML_CONFIG_TYPES | [^6] | Per Discovery 03 |
| 1.3 | [x] | Write tests for GraphStore.get_metadata() | 2 | Tests cover: metadata after load, error if not loaded, all fields present | [^6] | tests/unit/repos/test_graph_store.py |
| 1.4 | [x] | Extend GraphStore ABC with get_metadata() | 1 | Abstract method added; FakeGraphStore and NetworkXGraphStore implement | [^6] | Per Discovery 05 |
| 1.5 | [x] | Write tests for tree CLI registration and --help | 1 | Tests verify command exists, --help shows options | [^6] | tests/unit/cli/test_tree_cli.py |
| 1.6 | [x] | Create tree.py skeleton with Typer options | 2 | tree command registered; accepts pattern, --detail, --depth, --verbose | [^6] | Per Discovery 04, 07 |
| 1.7 | [x] | Write tests for missing graph error (AC7) | 2 | Tests verify exit code 1 and error message | [^6] | |
| 1.8 | [x] | Implement graph loading with error handling | 2 | Loads graph; exits 1 if missing; exits 2 if corrupted | [^6] | Per Discovery 09 |
| 1.9 | [x] | Write tests for basic tree display (AC1) | 2 | Tests verify Rich Tree output format | [^6] | |
| 1.10 | [x] | Implement basic tree traversal and display | 3 | Displays all files with hierarchy using Rich Tree | [^6] | Per Discovery 08, 12, 13 |
| 1.11 | [x] | Write tests for path filtering (AC2) | 2 | Tests verify prefix matching filters correctly | [^6] | |
| 1.12 | [x] | Implement path prefix filtering | 2 | Filters nodes by path prefix | [^6] | Per Discovery 06 |
| 1.13 | [x] | Write tests for glob pattern filtering (AC3) | 2 | Tests verify glob patterns work | [^6] | |
| 1.14 | [x] | Implement glob pattern detection and filtering | 2 | Detects globs; applies fnmatch filtering | [^6] | Per Discovery 06 |
| 1.15 | [x] | Write tests for empty results (AC8) | 1 | Tests verify message and exit code 0 | [^6] | Per Discovery 16 |
| 1.16 | [x] | Implement empty results handling | 1 | Shows "No nodes match pattern" message | [^6] | |
| 1.17 | [x] | Write integration tests with real graph | 2 | End-to-end test with fixture project | [^6] | |
| 1.18 | [x] | Refactor and clean up Phase 1 code | 2 | Lint passes; test coverage >80% | [^6] | |

### Test Examples (Write First!)

```python
# tests/unit/cli/test_tree_cli.py
class TestTreeCommandRegistration:
    def test_given_cli_app_when_inspected_then_tree_command_registered(self):
        """
        Purpose: Verifies tree command is registered on app.
        Quality Contribution: Ensures command is discoverable.
        Acceptance Criteria: 'tree' in registered commands.
        """
        from fs2.cli.main import app

        command_names = [cmd.name for cmd in app.registered_commands]
        assert "tree" in command_names

class TestTreeMissingGraph:
    def test_given_no_graph_when_tree_invoked_then_exit_one(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies AC7 - missing graph exits 1.
        Quality Contribution: Ensures user error is reported correctly.
        Acceptance Criteria: Exit code 1, error message shown.
        """
        from fs2.cli.main import app

        # Create config but no graph
        (tmp_path / ".fs2").mkdir()
        (tmp_path / ".fs2" / "config.yaml").write_text("scan:\n  scan_paths: [.]")
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["tree"])

        assert result.exit_code == 1
        assert "no graph found" in result.stdout.lower()
```

### Non-Happy-Path Coverage
- [ ] Missing graph file → exit 1
- [ ] Corrupted graph file → exit 2
- [ ] Missing config → exit 1
- [ ] Empty pattern results → exit 0 with message

### Acceptance Criteria
- [x] AC1: Basic tree display works
- [x] AC2: Path filtering works
- [x] AC3: Glob pattern filtering works
- [x] AC7: Missing graph shows error, exit 1
- [x] AC8: Empty results handled correctly
- [x] AC13: Exit codes follow 0/1/2 convention
- [x] AC14: --help shows usage

### Phase 1 Validation Commands

```bash
# Run all Phase 1 tests
pytest tests/unit/config/test_tree_config.py tests/unit/repos/test_graph_store.py tests/unit/cli/test_tree_cli.py -v

# Run specific test classes
pytest tests/unit/cli/test_tree_cli.py::TestTreeCommandRegistration -v
pytest tests/unit/cli/test_tree_cli.py::TestTreeMissingGraph -v

# Run integration tests with fixture project
pytest tests/integration/test_tree_cli_integration.py -v

# Lint and format check
ruff check src/fs2/cli/tree.py src/fs2/config/objects.py
ruff format --check src/fs2/cli/tree.py src/fs2/config/objects.py

# Coverage verification (>80% target)
pytest tests/unit/cli/test_tree_cli.py tests/unit/config/test_tree_config.py --cov=src/fs2/cli/tree --cov=src/fs2/config/objects --cov-report=term-missing --cov-fail-under=80

# Create test fixture (scanned project)
# Fixture is created automatically via conftest.py::scanned_project fixture
# Manual creation: cd tests/fixtures/sample_project && fs2 scan
```

---

### Phase 2: Detail Levels and Depth Limiting

**Objective**: Implement `--detail min|max` and `--depth N` options with all associated UI refinements.

**Deliverables**:
- `--detail min` (default): icon, name, type, line range
- `--detail max`: adds node ID, signature
- `--depth N`: limits tree depth with hidden child indicator
- Summary line with node/file counts
- Verbose mode with debug logging

**Dependencies**: Phase 1 complete

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Deep nesting performance | Low | Medium | Default depth unlimited; --depth provides escape hatch |
| Signature missing for some nodes | Medium | Low | Fallback to qualified_name |

### Tasks (TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 2.1 | [x] | Write tests for --detail min output (AC4) | 2 | Tests verify icon, name, line range format | [^7] | TestDetailMin: 3 tests |
| 2.2 | [x] | Implement --detail min formatting | 2 | Output matches spec format exactly | [^7] | Verified existing impl |
| 2.3 | [x] | Write tests for --detail max output (AC5) | 2 | Tests verify node ID and signature display | [^7] | TestDetailMax: 4 tests |
| 2.4 | [x] | Implement --detail max formatting | 2 | Shows node IDs; handles missing signatures | [^7] | Verified existing impl |
| 2.5 | [x] | Write tests for --depth limiting (AC6) | 2 | Tests verify depth cutoff and indicator | [^7] | TestDepthLimiting: 5 tests |
| 2.6 | [x] | Implement --depth limiting with indicator | 2 | Stops at depth; shows hidden child count | [^7] | Verified existing impl |
| 2.7 | [x] | Write tests for summary line (AC9 counts) | 2 | Tests verify format with counts: "Found N nodes in M files" | [^7] | TestSummaryLine: 5 tests |
| 2.8 | [x] | Implement summary line with counts | 1 | Shows "Found N nodes in M files" without freshness | [^7] | Verified existing impl |
| 2.9 | [x] | Write tests for --verbose flag | 1 | Tests verify debug output appears | [^7] | Already tested in Phase 1 |
| 2.10 | [x] | Implement verbose logging setup | 1 | RichHandler configured on --verbose | [^7] | Existing impl sufficient |
| 2.11 | [x] | Refactor and validate Phase 2 | 2 | All tests pass; lint clean | [^7] | 67 tests, lint clean |

### Test Examples (Write First!)

```python
class TestDetailMin:
    def test_given_detail_min_when_tree_then_shows_basic_format(self, scanned_project, monkeypatch):
        """
        Purpose: Verifies AC4 - min detail shows essential info.
        Quality Contribution: Ensures default output is clean.
        Acceptance Criteria: Icon, name, line range present; no node IDs.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        result = runner.invoke(app, ["tree", "--detail", "min"])

        assert result.exit_code == 0
        assert "📄" in result.stdout  # File icon
        assert "[" in result.stdout and "]" in result.stdout  # Line range
        assert "node:" not in result.stdout  # No node IDs in min

class TestDepthLimiting:
    def test_given_depth_two_when_tree_then_hides_deep_children(self, scanned_project, monkeypatch):
        """
        Purpose: Verifies AC6 - depth limiting works.
        Quality Contribution: Prevents overwhelming output.
        Acceptance Criteria: Depth honored; hidden indicator shown.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        result = runner.invoke(app, ["tree", "--depth", "2"])

        assert result.exit_code == 0
        assert "hidden" in result.stdout.lower()  # Indicator present
```

### Acceptance Criteria
- [x] AC4: --detail min shows icon, name, type, line range
- [x] AC5: --detail max shows node ID and signature
- [x] AC6: --depth N limits depth with indicator
- [x] AC9 (partial): Summary line shows node/file counts ("Found N nodes in M files")
  - Note: Freshness timestamp "(scanned Xh ago)" is delivered in Phase 3

### Phase 2 Validation Commands

```bash
# Run all Phase 2 tests
pytest tests/unit/cli/test_tree_cli.py::TestDetailMin tests/unit/cli/test_tree_cli.py::TestDetailMax tests/unit/cli/test_tree_cli.py::TestDepthLimiting tests/unit/cli/test_tree_cli.py::TestSummaryLine tests/unit/cli/test_tree_cli.py::TestVerboseFlag -v

# Run specific detail level tests
pytest tests/unit/cli/test_tree_cli.py -k "detail" -v

# Run depth limiting tests
pytest tests/unit/cli/test_tree_cli.py -k "depth" -v

# Lint and format check
ruff check src/fs2/cli/tree.py
ruff format --check src/fs2/cli/tree.py

# Full test suite (Phase 1 + Phase 2)
pytest tests/unit/cli/test_tree_cli.py -v

# Coverage verification
pytest tests/unit/cli/test_tree_cli.py --cov=src/fs2/cli/tree --cov-report=term-missing --cov-fail-under=80
```

---

### Phase 3: File-Type-Specific Handling and Polish

**Objective**: Add file-type-specific display, loading feedback, freshness indicator, and final polish.

**Deliverables**:
- Dockerfile tree display (AC10)
- Markdown heading display (AC11)
- Data file handling (AC12)
- Loading spinner for >200ms (AC15)
- Large graph warning (AC16)
- Scan freshness in summary (AC9)

**Dependencies**: Phase 2 complete

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| TTY detection edge cases | Low | Low | Use sys.stdout.isatty() |
| Spinner timing variance | Low | Low | Heuristic: >5K nodes shows spinner |

### Tasks (TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 3.1 | [ ] | Write tests for Dockerfile display (AC10) | 2 | Tests verify instruction blocks shown | - | |
| 3.2 | [ ] | Implement Dockerfile-specific formatting | 2 | Shows FROM, RUN, COPY with 🏗️ icon | - | |
| 3.3 | [ ] | Write tests for Markdown heading display (AC11) | 2 | Tests verify heading hierarchy | - | |
| 3.4 | [ ] | Implement Markdown heading formatting | 2 | Shows headings with 📝 icon | - | |
| 3.5 | [ ] | Write tests for data file display (AC12) | 2 | Tests verify YAML/JSON show file-only | - | Per Discovery 14 |
| 3.6 | [ ] | Implement data file detection and display | 2 | Uses extension detection; shows file node only | - | |
| 3.7 | [ ] | Write tests for loading spinner (AC15) | 1 | Tests verify spinner shown for slow loads | - | Per Discovery 18 |
| 3.8 | [ ] | Implement loading spinner with TTY detection | 2 | Rich Status spinner for >5K nodes in TTY | - | |
| 3.9 | [ ] | Write tests for large graph warning (AC16) | 1 | Tests verify warning for >10K nodes | - | Uses get_metadata() |
| 3.10 | [ ] | Implement large graph warning | 1 | Shows warning before loading | - | |
| 3.11 | [ ] | Write tests for scan freshness (AC9 complete) | 2 | Tests verify "scanned Xh ago" format in summary line | - | Completes AC9: Phase 2 added counts, this adds freshness |
| 3.12 | [ ] | Implement freshness calculation from metadata | 2 | Uses get_metadata()['created_at']; displays relative time | - | Appends freshness to Phase 2's summary line |
| 3.13 | [ ] | Final integration tests and polish | 2 | Full end-to-end coverage; all 16 ACs verified | - | |
| 3.14 | [ ] | Documentation update (README mention) | 1 | README contains 2-3 usage examples, tree in TOC | - | /workspaces/flow_squared/README.md |

### Test Examples (Write First!)

```python
class TestDockerfileDisplay:
    def test_given_dockerfile_when_tree_then_shows_instructions(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies AC10 - Dockerfile shows instructions.
        Quality Contribution: Ensures special file types handled correctly.
        Acceptance Criteria: FROM, RUN displayed with block icon.
        """
        # Create project with Dockerfile, scan, then tree
        ...

        assert "🏗️" in result.stdout  # Block icon
        assert "FROM" in result.stdout

class TestScanFreshness:
    def test_given_old_graph_when_tree_then_shows_time_ago(self, scanned_project, monkeypatch):
        """
        Purpose: Verifies AC9 - freshness shown in summary.
        Quality Contribution: Users know data currency.
        Acceptance Criteria: "scanned Xh ago" present.
        """
        result = runner.invoke(app, ["tree"])

        assert result.exit_code == 0
        assert "scanned" in result.stdout.lower()
        assert ("ago" in result.stdout.lower() or
                "m ago" in result.stdout or
                "h ago" in result.stdout)
```

### Acceptance Criteria
- [ ] AC9: Summary includes scan freshness
- [ ] AC10: Dockerfile shows instructions correctly
- [ ] AC11: Markdown shows heading hierarchy
- [ ] AC12: Data files show file-level only
- [ ] AC15: Loading spinner for slow loads
- [ ] AC16: Warning for large graphs

### Phase 3 Validation Commands

```bash
# Run all Phase 3 tests
pytest tests/unit/cli/test_tree_cli.py::TestDockerfileDisplay tests/unit/cli/test_tree_cli.py::TestMarkdownDisplay tests/unit/cli/test_tree_cli.py::TestDataFileDisplay tests/unit/cli/test_tree_cli.py::TestLoadingSpinner tests/unit/cli/test_tree_cli.py::TestLargeGraphWarning tests/unit/cli/test_tree_cli.py::TestScanFreshness -v

# Run file-type-specific tests
pytest tests/unit/cli/test_tree_cli.py -k "Dockerfile or Markdown or DataFile" -v

# Run loading/performance tests
pytest tests/unit/cli/test_tree_cli.py -k "Loading or LargeGraph or Spinner" -v

# Run freshness tests
pytest tests/unit/cli/test_tree_cli.py -k "Freshness" -v

# Integration test with large graph fixture (>10K nodes)
pytest tests/integration/test_tree_large_graph.py -v

# Create large graph fixture for AC16 testing
python -c "
from pathlib import Path
from fs2.core.repos import NetworkXGraphStore
from fs2.config.service import FS2ConfigurationService
from fs2.core.models import CodeNode

# Generate 10001 nodes to trigger warning
config = FS2ConfigurationService()
store = NetworkXGraphStore(config)
for i in range(10001):
    node = CodeNode.create_file(f'src/file_{i}.py', 'python', 'module', 0, 100, 1, 10, f'# file {i}')
    store.add_node(node)
store.save(Path('.fs2/large_graph.pickle'))
print('Created large graph with 10001 nodes')
"

# Full test suite (all phases)
pytest tests/unit/cli/test_tree_cli.py tests/integration/test_tree_cli_integration.py -v

# Lint and format check
ruff check src/fs2/cli/tree.py
ruff format --check src/fs2/cli/tree.py

# Final coverage verification (>80% target)
pytest tests/unit/cli/test_tree_cli.py --cov=src/fs2/cli/tree --cov-report=term-missing --cov-fail-under=80

# README documentation check (manual verification)
# Ensure README.md contains tree command examples
grep -A 5 "fs2 tree" README.md
```

---

## Cross-Cutting Concerns

### Security Considerations

| Concern | Mitigation |
|---------|------------|
| Graph pickle loading | Already uses RestrictedUnpickler (S2 finding) |
| Path traversal in patterns | Filter operates on node_id, not filesystem |
| No user input to shell | Patterns used only for string matching |

### Observability

| Aspect | Implementation |
|--------|----------------|
| Logging | RichHandler on --verbose; DEBUG level |
| Metrics | Summary line provides node/file counts |
| Error tracking | Exit codes; actionable error messages |

### Documentation

**Location**: README.md only (per Clarifications Session 2025-12-17)
**Rationale**: The `fs2 tree` command is self-documenting via `--help` output (AC14). README provides quick-start command examples.

| Location | Content | Status |
|----------|---------|--------|
| README.md | Brief mention with 1-2 usage examples | Phase 3 |
| --help | Command usage and examples | Phase 1 |
| Spec | Already complete | Done |

**Target Audience**: fs2 users exploring codebases
**Maintenance**: Update README when new major features added to tree command

---

## Complexity Tracking

| Component | CS | Label | Breakdown (S,I,D,N,F,T) | Justification | Mitigation |
|-----------|-----|-------|------------------------|---------------|------------|
| GraphStore.get_metadata() extension | 2 | Small | S=1,I=0,D=0,N=0,F=0,T=1 | One method added to ABC | Minimal; backward compatible |
| TreeConfig creation | 1 | Trivial | S=1,I=0,D=0,N=0,F=0,T=0 | Copy ScanConfig pattern | None needed |
| Pattern matching (glob vs prefix) | 2 | Small | S=1,I=0,D=0,N=1,F=0,T=0 | Some edge cases | Test coverage |
| Rich Tree rendering | 2 | Small | S=1,I=0,D=0,N=0,F=0,T=1 | Well-documented API | None needed |

**Overall Feature CS**: 2 (Small) - Well-understood requirements, existing patterns to follow

---

## Progress Tracking

### Phase Completion Checklist

- [x] Phase 1: Core Tree Command with Path Filtering - COMPLETE
- [x] Phase 2: Detail Levels and Depth Limiting - COMPLETE
- [~] Phase 3: File-Type-Specific Handling and Polish - SKIPPED [^8]

### STOP Rule

**IMPORTANT**: This plan must be complete before creating tasks. After writing this plan:
1. Run `/plan-4-complete-the-plan` to validate readiness
2. Only proceed to `/plan-5-phase-tasks-and-brief` after validation passes

---

## Change Footnotes Ledger

[^1]: [To be added during implementation via plan-6a]
[^2]: [To be added during implementation via plan-6a]
[^3]: [To be added during implementation via plan-6a]
[^4]: [To be added during implementation via plan-6a]
[^5]: [To be added during implementation via plan-6a]
[^6]: Phase 1 Implementation Complete (2025-12-17)
  - `class:src/fs2/config/objects.py:TreeConfig`
  - `method:src/fs2/core/repos/graph_store.py:GraphStore.get_metadata`
  - `method:src/fs2/core/repos/graph_store_impl.py:NetworkXGraphStore.get_metadata`
  - `method:src/fs2/core/repos/graph_store_fake.py:FakeGraphStore.get_metadata`
  - `file:src/fs2/cli/tree.py`
  - `file:src/fs2/cli/main.py` (tree command registration)
  - `file:tests/unit/config/test_tree_config.py`
  - `file:tests/unit/cli/test_tree_cli.py`
  - `file:tests/unit/repos/test_graph_store.py` (get_metadata tests)
  - `file:tests/integration/test_tree_cli_integration.py`
  - `file:tests/conftest.py` (scanned_fixtures_graph fixture)
  - `section:docs/rules-idioms-architecture/rules.md:R9` (CLI standards per Insight #2)
[^7]: Phase 2 Implementation Complete (2025-12-17)
  - `file:tests/unit/cli/test_tree_cli.py` (17 new tests added)
  - Test classes: TestDetailMin, TestDetailMax, TestDepthLimiting, TestSummaryLine
  - Total tests: 67 passing (39 tree CLI + 7 TreeConfig + 16 GraphStore + 5 integration)
  - No code changes to tree.py - Phase 1 impl verified correct per /didyouknow session
[^8]: Phase 3 Skipped (2025-12-17)
  - User decision to skip file-type-specific handling and polish features
  - Deferred ACs: AC9 (freshness), AC10 (Dockerfile), AC11 (Markdown), AC12 (data files), AC15 (spinner), AC16 (warning)
  - Core tree functionality (Phase 1 + Phase 2) is complete and usable
  - Phase 3 tasks.md dossier created at `docs/plans/004-tree-command/tasks/phase-3-file-type-specific-handling-and-polish/tasks.md` for future reference

---

## Appendix A: Deviation Ledger

| Principle Violated | Why Needed | Simpler Alternative Rejected | Risk Mitigation |
|-------------------|------------|------------------------------|-----------------|
| None | N/A | N/A | N/A |

*No constitution or architecture deviations required for this implementation.*

---

## Appendix B: ADR Ledger

| ADR | Status | Affects Phases | Notes |
|-----|--------|----------------|-------|
| None | N/A | N/A | No ADRs reference this feature |

*No ADRs found in docs/adr/ for tree command. ADR may be created if significant design decisions arise during implementation.*

---

## References

- [tree-command-spec.md](./tree-command-spec.md) - Feature specification
- [constitution.md](/workspaces/flow_squared/docs/rules-idioms-architecture/constitution.md) - Project principles
- [architecture.md](/workspaces/flow_squared/docs/rules-idioms-architecture/architecture.md) - Layer boundaries
- [rules.md](/workspaces/flow_squared/docs/rules-idioms-architecture/rules.md) - Normative rules including R9 CLI Standards
