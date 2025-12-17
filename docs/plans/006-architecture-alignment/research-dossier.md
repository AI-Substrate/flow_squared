# Research Report: CLI Architecture Refactoring - Service Layer Extraction

**Generated**: 2025-12-17T00:00:00Z
**Research Query**: "Refactor CLI commands (get-node, scan, tree) to follow Clean Architecture - extract business logic into services"
**Mode**: Plan-Associated
**Location**: docs/plans/006-architecture-alignment/research-dossier.md
**FlowSpace**: Available
**Findings**: 45+

## Executive Summary

### What It Does
The CLI layer currently contains significant business logic that violates Clean Architecture principles. Commands like `tree`, `get-node`, and `scan` directly instantiate adapters/repos, perform data transformation, and handle presentation - instead of delegating to a service layer.

### Business Purpose
Refactoring CLI commands to use services will:
1. Enable unit testing of business logic without CLI/Rich/Typer dependencies
2. Enforce SRP: CLI handles arg parsing + presentation only; services handle logic
3. Enable code reuse: services can be used from other interfaces (API, SDK, tests)
4. Align with documented architecture: `CLI → Services → {Adapters, Repos}`

### Key Insights
1. **tree.py is the worst offender**: 372 lines with `_filter_nodes()`, `_build_root_bucket()`, `_display_tree()`, `_add_node_to_tree()` - all business logic
2. **get_node.py has config coupling**: Directly loads configs and interacts with GraphStore
3. **scan.py is the best example**: Already delegates to ScanPipeline service, but still has display logic
4. **Pattern exists**: `SampleService` and `ScanPipeline` demonstrate correct DI pattern

### Quick Stats
- **CLI Files Requiring Refactoring**: 4 (init.py, scan.py, tree.py, get_node.py)
- **Business Logic Lines in CLI**: ~350+ lines
- **Existing Service Examples**: 2 (ScanPipeline, SampleService)
- **Complexity**: Medium (CS-3) - established patterns exist, mechanical refactoring

## How It Currently Works

### Entry Points

| Entry Point | Type | Location | Purpose | Violation Level |
|------------|------|----------|---------|-----------------|
| `scan()` | CLI Command | src/fs2/cli/scan.py:28-104 | Scan codebase | Low - uses ScanPipeline |
| `tree()` | CLI Command | src/fs2/cli/tree.py:41-158 | Display code tree | **HIGH** - all logic in CLI |
| `get_node()` | CLI Command | src/fs2/cli/get_node.py:28-109 | Get node by ID | **MEDIUM** - direct repo access |
| `init()` | CLI Command | src/fs2/cli/init.py:34-72 | Initialize config | Low - simple template |

### Core Execution Flow

#### Current scan.py Flow (Good Example)
```
1. CLI parses args (--verbose, --no-progress, --progress)
2. CLI creates ConfigurationService
3. CLI creates adapters (FileSystemScanner, TreeSitterParser, NetworkXGraphStore)
4. CLI creates ScanPipeline(config, adapters) ← CORRECT DI
5. CLI calls pipeline.run() → ScanSummary ← CORRECT delegation
6. CLI displays summary ← PRESENTATION LAYER
```

**What's Right**: Business logic is in `ScanPipeline`
**What's Wrong**: Display logic (`_display_summary()`) could be cleaner

#### Current tree.py Flow (Bad Example)
```
1. CLI parses args (pattern, --detail, --depth, --verbose)
2. CLI creates ConfigurationService
3. CLI creates NetworkXGraphStore directly ← VIOLATION
4. CLI calls graph_store.get_all_nodes() ← VIOLATION
5. CLI calls _filter_nodes(nodes, pattern) ← BUSINESS LOGIC IN CLI
6. CLI calls _build_root_bucket(matched, store) ← BUSINESS LOGIC IN CLI
7. CLI calls _display_tree(roots, store, ...) ← MIXED LOGIC/PRESENTATION
```

**What's Wrong**:
- `_filter_nodes()` (lines 161-186): Pattern matching logic
- `_build_root_bucket()` (lines 189-247): Tree structure algorithm
- `_add_node_to_tree()` (lines 318-371): Recursive tree building
- All 210+ lines of business logic embedded in CLI

#### Current get_node.py Flow (Medium Violation)
```
1. CLI parses args (node_id, --file)
2. CLI creates ConfigurationService
3. CLI gets TreeConfig directly ← OK but could be in service
4. CLI checks graph_path.exists() ← SHOULD BE SERVICE RESPONSIBILITY
5. CLI creates NetworkXGraphStore ← DIRECT INSTANTIATION
6. CLI calls store.load() / store.get_node() ← DIRECT REPO ACCESS
7. CLI serializes to JSON ← COULD BE SERVICE METHOD
8. CLI writes to stdout/file ← PRESENTATION
```

### Data Flow

```
Current (Broken):
┌─────────────┐    ┌────────────────┐
│    CLI      │───→│  Repos/Adapters│
│ (all logic) │    │  (direct use)  │
└─────────────┘    └────────────────┘

Should Be:
┌─────────────┐    ┌──────────────┐    ┌────────────────┐
│    CLI      │───→│   Services   │───→│  Repos/Adapters│
│ (args+view) │    │  (business)  │    │  (data access) │
└─────────────┘    └──────────────┘    └────────────────┘
```

## Architecture & Design

### Component Map

#### Current CLI Structure
```
src/fs2/cli/
├── __init__.py
├── main.py          # Typer app registration
├── init.py          # 72 lines - mostly OK (simple template)
├── scan.py          # 176 lines - uses ScanPipeline, has display logic
├── tree.py          # 372 lines - ALL business logic in CLI ❌
└── get_node.py      # 110 lines - direct repo access ❌
```

#### Proposed Service Structure
```
src/fs2/core/services/
├── __init__.py
├── tree_service.py      # NEW: TreeService
├── get_node_service.py  # NEW: GetNodeService
├── init_service.py      # NEW: InitService (optional)
├── scan_pipeline.py     # EXISTS: Good pattern to follow
└── sample_service.py    # EXISTS: Reference implementation
```

### Design Patterns Identified

#### 1. ConfigurationService Registry Pattern (Correct)
**Location**: `src/fs2/core/services/sample_service.py:94-111`
```python
class SampleService:
    def __init__(
        self,
        config: "ConfigurationService",  # Registry, NOT specific config
        adapter: SampleAdapter,           # ABC, not implementation
    ):
        # Service gets its own config internally
        self._service_config = config.require(SampleServiceConfig)
        self._adapter = adapter
```

**Why This Matters**: Composition root passes registry; service decides what config it needs.

#### 2. ABC-Based Dependency Injection (Correct)
**Location**: `src/fs2/core/services/scan_pipeline.py:55-87`
```python
def __init__(
    self,
    config: "ConfigurationService",
    file_scanner: "FileScanner",    # ABC
    ast_parser: "ASTParser",        # ABC
    graph_store: "GraphStore",      # ABC
    stages: list[PipelineStage] | None = None,
):
```

**Why This Matters**: Services depend on interfaces, not implementations.

#### 3. Domain Result Types (Correct)
**Location**: `src/fs2/core/models/scan_summary.py`
```python
@dataclass(frozen=True)
class ScanSummary:
    success: bool
    files_scanned: int
    nodes_created: int
    errors: list[str]
    metrics: dict[str, Any]
```

**Why This Matters**: Services return domain types, not raw data.

#### 4. Anti-Pattern: Business Logic in CLI (VIOLATION)
**Location**: `src/fs2/cli/tree.py:161-186`
```python
def _filter_nodes(nodes: list[CodeNode], pattern: str) -> list[CodeNode]:
    """Filter nodes by pattern using unified node_id matching.

    Matching priority:
    1. Exact match on node_id → short-circuit
    2. Glob pattern → fnmatch on node_id
    3. Substring match → partial match on node_id
    """
    # ... 25 lines of matching logic
```

**Why This Is Wrong**: This is pure business logic with no CLI concerns - belongs in a service.

## Dependencies & Integration

### What CLI Currently Depends On (Direct - Should Be Indirect via Services)

| CLI Command | Direct Dependency | Should Be |
|-------------|-------------------|-----------|
| tree.py | NetworkXGraphStore | TreeService |
| tree.py | GraphStore ABC | TreeService |
| get_node.py | NetworkXGraphStore | GetNodeService |
| get_node.py | GraphStore ABC | GetNodeService |
| scan.py | ScanPipeline | Already correct |

### What Services Will Depend On

| New Service | Dependencies (ABCs) | Config Type |
|-------------|---------------------|-------------|
| TreeService | GraphStore | TreeConfig |
| GetNodeService | GraphStore | TreeConfig |
| InitService | None (file ops only) | None |

## Quality & Testing

### Current Test Coverage Analysis

#### CLI Tests (tests/unit/cli/)
```
test_scan_cli.py     - 614 lines - Tests via CliRunner (integration-style)
test_tree_cli.py     - Similar pattern
test_get_node_cli.py - 344 lines - Tests via CliRunner
```

**Problem**: These tests require complex fixtures (`scanned_project`, `config_only_project`) that do real file I/O and scanning. They're testing business logic through the CLI interface.

#### Service Tests (tests/unit/services/)
```
test_scan_pipeline.py - 508 lines - Tests with FakeConfigurationService + fake adapters
```

**Solution**: Same pattern for new services. Pure unit tests with fakes.

### Testing Concerns

1. **Slow Tests**: CLI tests are slow because they create real files and run real scans
2. **Flaky Tests**: File system operations can be flaky
3. **Hard to Test Edge Cases**: Must set up complex file structures
4. **No Isolation**: Can't test tree filtering logic without file I/O

### Proposed Testing Strategy

| Layer | Test Type | Dependencies | Speed |
|-------|-----------|--------------|-------|
| TreeService | Unit | FakeGraphStore | Fast (<1ms) |
| GetNodeService | Unit | FakeGraphStore | Fast (<1ms) |
| CLI (tree.py) | Integration | Real services, mocked output | Medium |
| CLI (get_node.py) | Integration | Real services, mocked output | Medium |

## Modification Considerations

### Safe to Modify

1. **tree.py**: Can be refactored to use TreeService
   - Low risk: clear function boundaries
   - Well tested via CLI tests (can verify behavior preserved)

2. **get_node.py**: Can be refactored to use GetNodeService
   - Low risk: simple logic
   - Well tested

### Modify with Caution

1. **scan.py**: Already uses ScanPipeline correctly
   - Only change: extract `_display_summary()` to presenter class?
   - Risk: might break working pattern

2. **conftest.py fixtures**: Will need updating
   - Risk: many tests depend on these
   - Mitigation: keep old fixtures, add new service-focused ones

### Extension Points

1. **New services can be added following ScanPipeline pattern**
2. **Existing fake adapters (FakeGraphStore, FakeFileScanner) can be reused**

## Critical Discoveries

### Finding IA-01: tree.py Contains 210+ Lines of Business Logic
**Impact**: Critical
**What**: The `_filter_nodes()`, `_build_root_bucket()`, and `_add_node_to_tree()` functions are pure algorithms with no CLI concerns.
**Why It Matters**: Impossible to unit test tree filtering/building logic in isolation.
**Required Action**: Extract to `TreeService` with methods like:
- `filter_nodes(pattern: str) -> list[CodeNode]`
- `build_tree(matched: list[CodeNode]) -> TreeNode`

### Finding IA-02: get_node.py Directly Instantiates Repositories
**Impact**: High
**What**: Line 74: `graph_store: GraphStore = NetworkXGraphStore(config)`
**Why It Matters**: CLI is doing composition AND business logic.
**Required Action**: Create `GetNodeService` that receives `GraphStore` via DI.

### Finding DC-01: Constitution Doesn't Explicitly Prohibit CLI Business Logic
**Impact**: Medium
**What**: Constitution P1 says "CLI → Services → {Adapters, Repos}" but doesn't enforce it.
**Why It Matters**: Future implementations might repeat this mistake.
**Required Action**: Add explicit rule: "CLI layer MUST NOT contain business logic. All non-trivial operations MUST be delegated to services."

### Finding QT-01: CLI Tests Are Integration Tests Disguised as Unit Tests
**Impact**: High
**What**: `tests/unit/cli/*.py` files use `CliRunner` and real file fixtures.
**Why It Matters**: Slow, flaky, hard to maintain.
**Required Action**:
1. Rename to `tests/integration/cli/` OR
2. Add true unit tests for new services

### Finding PS-01: SampleService and ScanPipeline Provide Correct Patterns
**Impact**: Positive
**What**: These services demonstrate:
- ConfigurationService registry injection
- ABC-based adapter dependencies
- Domain return types (ProcessResult, ScanSummary)
**Why It Matters**: Pattern exists; just needs to be replicated.

## Supporting Documentation

### Related Documentation
- `docs/how/adding-services-adapters.md` - Guide for new services
- `docs/rules-idioms-architecture/constitution.md` - Architectural rules
- `docs/rules-idioms-architecture/architecture.md` - Layer descriptions

### Key Code Comments
From `sample_service.py:28-35`:
```python
# CRITICAL: The composition root passes ConfigurationService (the registry),
# NOT specific config types. Extracting SampleServiceConfig beforehand would
# be CONCEPT LEAKAGE - the composition root shouldn't know what configs
# SampleService needs internally. That's SampleService's business.
```

## Recommendations

### If Refactoring This System

1. **Start with GetNodeService** (simplest)
   - Create `src/fs2/core/services/get_node_service.py`
   - Move logic from `get_node.py`
   - Add unit tests with `FakeGraphStore`
   - Update CLI to use service

2. **Then TreeService** (most complex)
   - Create `src/fs2/core/services/tree_service.py`
   - Extract `_filter_nodes()`, `_build_root_bucket()`
   - Create domain model `TreeNode` for output
   - Add comprehensive unit tests
   - Update CLI to use service

3. **Update Constitution** (prevent future violations)
   - Add explicit CLI scope rule
   - Add code review checklist item

### Proposed Service Interfaces

#### GetNodeService
```python
class GetNodeService:
    def __init__(self, config: ConfigurationService, graph_store: GraphStore):
        self._config = config.require(TreeConfig)
        self._graph_store = graph_store

    def get_node(self, node_id: str) -> GetNodeResult:
        """Return GetNodeResult with node or error."""

    def get_node_json(self, node_id: str) -> str:
        """Return node as JSON string."""
```

#### TreeService
```python
class TreeService:
    def __init__(self, config: ConfigurationService, graph_store: GraphStore):
        self._config = config.require(TreeConfig)
        self._graph_store = graph_store

    def filter_nodes(self, pattern: str = ".") -> list[CodeNode]:
        """Filter nodes by pattern (exact, glob, substring)."""

    def build_tree_structure(
        self,
        matched: list[CodeNode],
        max_depth: int = 0
    ) -> TreeResult:
        """Build tree structure from matched nodes."""
```

## External Research Opportunities

No external research is required for this refactoring task. All necessary patterns exist in the codebase:
- `ScanPipeline` demonstrates service composition
- `SampleService` demonstrates DI pattern
- `FakeGraphStore` demonstrates test fakes

The refactoring is mechanical: extract functions → wrap in class → add DI → update CLI → add tests.

## Appendix: File Inventory

### Core Files Requiring Change

| File | Purpose | Lines | Change Type |
|------|---------|-------|-------------|
| src/fs2/cli/tree.py | Tree command | 372 | Heavy refactor |
| src/fs2/cli/get_node.py | Get node command | 110 | Medium refactor |
| src/fs2/cli/scan.py | Scan command | 176 | Minor cleanup |

### New Files to Create

| File | Purpose |
|------|---------|
| src/fs2/core/services/tree_service.py | Tree business logic |
| src/fs2/core/services/get_node_service.py | Get node business logic |
| tests/unit/services/test_tree_service.py | Tree service tests |
| tests/unit/services/test_get_node_service.py | Get node service tests |

### Files to Update

| File | Change |
|------|--------|
| docs/rules-idioms-architecture/constitution.md | Add CLI scope rule |
| tests/conftest.py | Add service-focused fixtures |

## Next Steps

**Ready for specification phase**: Run `/plan-1b-specify "CLI Architecture Alignment - Extract Services"`

---

**Research Complete**: 2025-12-17
**Report Location**: /workspaces/flow_squared/docs/plans/006-architecture-alignment/research-dossier.md
