# CLI Architecture Alignment Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2025-12-17
**Completed**: 2025-12-17
**Spec**: [cli-architecture-alignment-spec.md](./cli-architecture-alignment-spec.md)
**Research**: [research-dossier.md](./research-dossier.md)
**Status**: COMPLETE ✅

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Critical Research Findings](#critical-research-findings)
3. [Implementation](#implementation)
4. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

**Problem**: CLI commands (`tree.py`, `get_node.py`) contain 210+ lines of business logic that violate Clean Architecture principle P1: "CLI → Services → {Adapters, Repos}". This makes the logic untestable without file I/O.

**Solution**: Extract business logic into dedicated service classes (`TreeService`, `GetNodeService`) following the established `ScanPipeline` and `SampleService` patterns. CLI commands become thin wrappers: parse args, call service, render output.

**Expected Outcome**: Services are unit-testable with `FakeGraphStore`, CLI behavior unchanged, constitution updated to prevent future violations.

---

## Critical Research Findings

Per `research-dossier.md`, the following findings inform implementation:

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | tree.py contains 210+ lines of business logic (`_filter_nodes`, `_build_root_bucket`, `_add_node_to_tree`) | Extract all to TreeService |
| 02 | Critical | get_node.py directly instantiates NetworkXGraphStore and calls repo methods | Create GetNodeService with GraphStore DI |
| 03 | High | ScanPipeline pattern shows correct DI: `config: ConfigurationService`, `graph_store: GraphStore` | Follow this pattern exactly |
| 04 | High | SampleService shows config extraction: `self._config = config.require(ConfigType)` | Use internal config extraction |
| 05 | High | FakeGraphStore exists and can be used for service unit tests | Use for all service tests |
| 06 | High | Constitution P1 doesn't explicitly prohibit CLI business logic | Add explicit rule to constitution |
| 06a | **Critical** | Services MUST NOT store copies of graph data (nodes, edges, subgraphs) - memory management | Pass GraphStore refs only; access via ABC methods |
| 06b | High | TreeConfig naming is semantically wrong - GetNodeService shouldn't use "Tree" config | Rename TreeConfig → GraphConfig (T000) |
| 06c | High | TreeService with granular API forces CLI to orchestrate multiple calls | Add high-level `build_tree()` method; internal methods become private |
| 06d | Medium | GraphNotFoundError exception doesn't exist - services need specific error for missing graph | Add to adapters/exceptions.py (T000a) |
| 07 | Medium | CLI tests are integration tests using real fixtures | Keep existing tests; add service unit tests |
| 08 | Medium | tree.py has CATEGORY_ICONS dict (presentation) mixed with filtering logic | Keep icons in CLI; move filtering to service |
| 09 | Medium | get_node.py handles graph_path.exists() check | Move existence check to service |
| 10 | Medium | Services should raise domain exceptions (GraphStoreError) | CLI catches and renders errors |
| 11 | Low | scan.py already uses ScanPipeline correctly | No changes needed |
| 12 | Low | init.py is simple template writing | No changes needed |

---

## Implementation

**Objective**: Extract business logic from CLI commands into services, update CLI to use services, add service tests, update constitution.

**Testing Approach**: Lightweight
**Mock Usage**: Avoid mocks entirely (use FakeGraphStore per constitution P4)

### Tasks

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Notes |
|--------|-----|------|----|------|--------------|------------------|------------|-------|
| [x] | T000 | Rename TreeConfig → GraphConfig | 2 | Refactor | -- | /workspaces/flow_squared/src/fs2/config/objects.py, /workspaces/flow_squared/tests/unit/config/test_graph_config.py | Class renamed, `__config_path__="graph"`, all imports updated, tests pass | [^1] [^13] [log](execution.log.md#t000) |
| [x] | T000a | Add GraphNotFoundError exception | 1 | Core | -- | /workspaces/flow_squared/src/fs2/core/adapters/exceptions.py | `GraphNotFoundError(AdapterError)` exists with path attribute | [^2] [log](execution.log.md#t000a) |
| [x] | T001 | Create GetNodeService ABC and implementation | 2 | Core | T000,T000a | /workspaces/flow_squared/src/fs2/core/services/get_node_service.py | Service class exists with `get_node(node_id: str) -> CodeNode \| None` method | [^3] [log](execution.log.md#t001) |
| [x] | T002 | Add GetNodeService unit tests | 2 | Test | T001 | /workspaces/flow_squared/tests/unit/services/test_get_node_service.py | Tests pass using FakeGraphStore; covers found/not-found/error cases | [^4] [log](execution.log.md#t002) |
| [x] | T003 | Refactor get_node.py to use GetNodeService | 2 | Refactor | T001,T002 | /workspaces/flow_squared/src/fs2/cli/get_node.py | CLI only has arg parsing + JSON output; all logic in service | [^5] [log](execution.log.md#t003) |
| [x] | T004 | Verify get-node CLI tests still pass | 1 | Verify | T003 | /workspaces/flow_squared/tests/unit/cli/test_get_node_cli.py | `pytest tests/unit/cli/test_get_node_cli.py -v` passes | [log](execution.log.md#t004) |
| [x] | T005 | Create TreeService with internal methods | 2 | Core | T000,T000a | /workspaces/flow_squared/src/fs2/core/services/tree_service.py | Service has `_filter_nodes`, `_build_root_bucket`, `_get_children` private methods | [^6] [^12] [log](execution.log.md#t005-t006) |
| [x] | T006 | Add high-level build_tree() method | 2 | Core | T005 | /workspaces/flow_squared/src/fs2/core/services/tree_service.py | Service has `build_tree(pattern, max_depth) -> list[TreeNode]` public method | [^6] [log](execution.log.md#t005-t006) |
| [x] | T007 | Create TreeNode result dataclass | 1 | Core | T005 | /workspaces/flow_squared/src/fs2/core/models/tree_node.py | Frozen dataclass for tree rendering: `node: CodeNode, children: list[TreeNode]` | [^7] [log](execution.log.md#t007) |
| [x] | T008 | Add TreeService unit tests | 2 | Test | T007 | /workspaces/flow_squared/tests/unit/services/test_tree_service.py | Tests pass using FakeGraphStore; covers filtering, bucketing, children | [^8] [log](execution.log.md#t008) |
| [x] | T009 | Refactor tree.py to use TreeService | 3 | Refactor | T008 | /workspaces/flow_squared/src/fs2/cli/tree.py | CLI only has arg parsing + Rich tree rendering; business logic in service | [^9] [log](execution.log.md#t009) |
| [x] | T010 | Verify tree CLI tests still pass | 1 | Verify | T009 | /workspaces/flow_squared/tests/unit/cli/test_tree_cli.py | `pytest tests/unit/cli/test_tree_cli.py -v` passes | [log](execution.log.md#t010) |
| [x] | T011 | Update services and models __init__.py exports | 1 | Setup | T001,T005,T007 | /workspaces/flow_squared/src/fs2/core/services/__init__.py, /workspaces/flow_squared/src/fs2/core/models/__init__.py | TreeService, GetNodeService, TreeNode exported | [^10] [log](execution.log.md#t011) |
| [x] | T012 | Add CLI scope rule to constitution | 1 | Doc | T010 | /workspaces/flow_squared/docs/rules-idioms-architecture/constitution.md | New principle P9 added: "CLI layer MUST NOT contain business logic" | [^11] [log](execution.log.md#t012) |
| [x] | T013 | Run full test suite and lint | 1 | Verify | T012 | -- | `just fft` passes (fix, format, test) | [log](execution.log.md#t013) |

### Task Details

**T000a: Add GraphNotFoundError Exception**
```python
# src/fs2/core/adapters/exceptions.py
class GraphNotFoundError(AdapterError):
    """Graph file does not exist.

    Raised when a service attempts to load a graph that hasn't been created yet.

    Common causes:
    - User hasn't run `fs2 scan` yet
    - Graph path is misconfigured
    - Graph file was deleted

    Recovery:
    - Run `fs2 scan` to create the graph
    - Check graph_path in configuration
    """

    def __init__(self, path: Path, message: str | None = None):
        self.path = path
        super().__init__(
            message or f"Graph not found at {path}. Run 'fs2 scan' first."
        )
```

**T000: Rename TreeConfig → GraphConfig**
```python
# src/fs2/config/objects.py
# BEFORE:
class TreeConfig(BaseModel):
    __config_path__: ClassVar[str] = "tree"
    graph_path: str = ".fs2/graph.pickle"

# AFTER:
class GraphConfig(BaseModel):
    """Configuration for graph access.

    Used by any service that needs to load/access the code graph.
    Path: graph (e.g., FS2_GRAPH__GRAPH_PATH)
    """
    __config_path__: ClassVar[str] = "graph"
    graph_path: str = ".fs2/graph.pickle"
```
**Files to update:**
- `src/fs2/config/objects.py` - Rename class, update docstring, change __config_path__
- `src/fs2/cli/tree.py` - Update import and usage
- `src/fs2/cli/get_node.py` - Update import and usage
- `tests/conftest.py` - Update import and usage
- `tests/unit/config/test_tree_config.py` → `test_graph_config.py` - Rename file, update all references
- `YAML_CONFIG_TYPES` registration in objects.py

**T001: Create GetNodeService**
```python
# src/fs2/core/services/get_node_service.py
class GetNodeService:
    """Service for retrieving nodes from the code graph.

    CRITICAL: This service MUST NOT store copies of graph data.
    All access goes through GraphStore ABC. See rules.md R3.5.
    """
    def __init__(
        self,
        config: "ConfigurationService",
        graph_store: "GraphStore",
    ):
        self._config = config.require(GraphConfig)
        self._graph_store = graph_store
        self._loaded = False  # Lazy loading flag

    def _ensure_loaded(self) -> None:
        """Lazy load graph on first access."""
        if self._loaded:
            return
        graph_path = Path(self._config.graph_path)
        if not graph_path.exists():
            raise GraphNotFoundError(graph_path)
        self._graph_store.load(graph_path)
        self._loaded = True

    def get_node(self, node_id: str) -> CodeNode | None:
        """Retrieve node by ID. Auto-loads graph on first call."""
        self._ensure_loaded()
        return self._graph_store.get_node(node_id)
```

**T007: TreeNode Result Dataclass**
```python
# src/fs2/core/models/tree_node.py
from dataclasses import dataclass
from fs2.core.models.code_node import CodeNode

@dataclass(frozen=True)
class TreeNode:
    """A node in the tree structure for rendering.

    Recursive structure: each TreeNode contains its CodeNode data
    and a list of child TreeNodes.
    """
    node: CodeNode
    children: tuple["TreeNode", ...]  # Tuple for immutability
```

**T005-T006: TreeService Structure**
```python
# src/fs2/core/services/tree_service.py
class TreeService:
    """Service for tree operations on the code graph.

    CRITICAL: This service MUST NOT store copies of graph data.
    All access goes through GraphStore ABC. See rules.md R3.5.

    Usage (CLI becomes truly dumb):
        service = TreeService(config, graph_store)
        tree_nodes = service.build_tree(pattern=".", max_depth=2)
        for tree_node in tree_nodes:
            render(tree_node)  # CLI handles Rich rendering
    """
    def __init__(
        self,
        config: "ConfigurationService",
        graph_store: "GraphStore",
    ):
        self._config = config.require(GraphConfig)
        self._graph_store = graph_store
        self._loaded = False  # Lazy loading flag

    def _ensure_loaded(self) -> None:
        """Lazy load graph on first access."""
        if self._loaded:
            return
        graph_path = Path(self._config.graph_path)
        if not graph_path.exists():
            raise GraphNotFoundError(graph_path)
        self._graph_store.load(graph_path)
        self._loaded = True

    # === PUBLIC API (CLI uses this) ===

    def build_tree(
        self,
        pattern: str = ".",
        max_depth: int = 0
    ) -> list[TreeNode]:
        """Build complete tree structure for rendering.

        This is the main entry point - CLI calls this single method.
        Orchestrates filtering, root bucketing, and child expansion.

        Args:
            pattern: Filter pattern (exact, glob, or substring)
            max_depth: How deep to expand children (0 = unlimited)

        Returns:
            List of root TreeNodes with children populated
        """
        self._ensure_loaded()
        matched = self._filter_nodes(pattern)
        roots = self._build_root_bucket(matched)
        return [self._build_tree_node(root, max_depth, 0) for root in roots]

    # === PRIVATE METHODS (internal orchestration) ===

    def _filter_nodes(self, pattern: str) -> list[CodeNode]:
        """Filter nodes by pattern (exact, glob, substring)."""
        # Moved from tree.py:_filter_nodes()

    def _build_root_bucket(self, matched: list[CodeNode]) -> list[CodeNode]:
        """Build root nodes removing children when ancestor matched."""
        # Moved from tree.py:_build_root_bucket()

    def _build_tree_node(
        self,
        node: CodeNode,
        max_depth: int,
        current_depth: int
    ) -> TreeNode:
        """Recursively build TreeNode with children."""
        # Moved from tree.py:_add_node_to_tree()
        # Returns TreeNode instead of mutating Rich Tree
```

### Acceptance Criteria

- [x] AC1: TreeService exists and is unit testable with FakeGraphStore
- [x] AC1a: TreeService has single public `build_tree(pattern, max_depth)` method
- [x] AC1b: TreeNode frozen dataclass exists for tree structure
- [x] AC2: TreeService implements all logic from `_filter_nodes`, `_build_root_bucket` as private methods
- [x] AC3: GetNodeService exists and is unit testable with FakeGraphStore
- [x] AC4: GetNodeService implements graph loading and node retrieval logic
- [x] AC4a: GraphNotFoundError exception exists and is raised when graph file missing
- [x] AC5: All existing CLI tests pass (behavior preserved) - 60 CLI tests pass
- [x] AC6: Services follow DI pattern (ConfigurationService registry + GraphStore ABC)
- [x] AC6a: TreeConfig renamed to GraphConfig with `__config_path__="graph"`
- [x] AC7: No mocks used in service tests (FakeGraphStore only)
- [x] AC8: Constitution updated with CLI scope rule (P9)
- [x] AC9: Services do NOT store copies of graph data (per rules.md R3.5)
- [x] AC10: 561 tests pass, lint clean for new files

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| CLI behavior regression | Medium | High | Run CLI tests after T003, T009, T010 |
| Incomplete logic extraction | Low | Medium | Compare line counts; tree.py should shrink by 200+ lines |
| Service pattern deviation | Low | Medium | Code review against ScanPipeline |

---

## Change Footnotes Ledger

**Implementation completed**: 2025-12-17

[^1]: T000 - Renamed TreeConfig → GraphConfig
  - `class:src/fs2/config/objects.py:GraphConfig` - Renamed from TreeConfig, `__config_path__="graph"`
  - `file:src/fs2/cli/tree.py` - Updated import
  - `file:src/fs2/cli/get_node.py` - Updated import
  - `file:tests/conftest.py` - Updated imports and YAML fixtures
  - `file:tests/unit/config/test_graph_config.py` - New test file (renamed from test_tree_config.py)
  - `file:tests/unit/cli/test_tree_cli.py` - Updated YAML fixtures (tree: → graph:)
  - `file:.fs2/config.yaml` - Updated section name

[^2]: T000a - Added GraphNotFoundError exception
  - `class:src/fs2/core/adapters/exceptions.py:GraphNotFoundError` - New exception with path attribute

[^3]: T001 - Created GetNodeService
  - `class:src/fs2/core/services/get_node_service.py:GetNodeService` - Service class with DI
  - `method:src/fs2/core/services/get_node_service.py:GetNodeService.__init__` - DI constructor
  - `method:src/fs2/core/services/get_node_service.py:GetNodeService._ensure_loaded` - Lazy loading
  - `method:src/fs2/core/services/get_node_service.py:GetNodeService.get_node` - Node retrieval

[^4]: T002 - Added GetNodeService unit tests
  - `file:tests/unit/services/test_get_node_service.py` - 8 test cases with FakeGraphStore

[^5]: T003 - Refactored get_node.py
  - `function:src/fs2/cli/get_node.py:get_node` - Refactored to use GetNodeService

[^6]: T005-T006 - Created TreeService
  - `class:src/fs2/core/services/tree_service.py:TreeService` - Service class with DI
  - `method:src/fs2/core/services/tree_service.py:TreeService.__init__` - DI constructor
  - `method:src/fs2/core/services/tree_service.py:TreeService._ensure_loaded` - Lazy loading
  - `method:src/fs2/core/services/tree_service.py:TreeService.build_tree` - High-level API
  - `method:src/fs2/core/services/tree_service.py:TreeService._filter_nodes` - Private method
  - `method:src/fs2/core/services/tree_service.py:TreeService._build_root_bucket` - Private method
  - `method:src/fs2/core/services/tree_service.py:TreeService._build_tree_node` - Private method

[^7]: T007 - Created TreeNode dataclass
  - `class:src/fs2/core/models/tree_node.py:TreeNode` - Frozen dataclass with hidden_children_count

[^8]: T008 - Added TreeService unit tests
  - `file:tests/unit/services/test_tree_service.py` - 13 test cases with FakeGraphStore

[^9]: T009 - Refactored tree.py
  - `function:src/fs2/cli/tree.py:tree` - Refactored to use TreeService
  - `function:src/fs2/cli/tree.py:_display_tree` - Rich rendering only
  - `function:src/fs2/cli/tree.py:_add_tree_node_to_rich_tree` - Rich rendering helper

[^10]: T011 - Updated __init__.py exports
  - `file:src/fs2/core/services/__init__.py` - Added GetNodeService, TreeService exports
  - `file:src/fs2/core/models/__init__.py` - Added TreeNode export

[^11]: T012 - Added CLI scope rule to constitution
  - `file:docs/rules-idioms-architecture/constitution.md` - Added P9: CLI Layer Scope, updated code review checklist

[^12]: T005 - Added R3.5 Graph Data Access rule
  - `file:docs/rules-idioms-architecture/rules.md` - Added R3.5 memory management rule for graph data access

[^13]: T000 - Updated FS2Settings to allow extra fields
  - `file:src/fs2/config/models.py` - Added `extra="ignore"` to SettingsConfigDict to allow YAML sections

---

## Critical Insights Discussion

**Session**: 2025-12-17
**Context**: CLI Architecture Alignment Implementation Plan v1.0
**Analyst**: AI Clarity Agent
**Reviewer**: Development Team
**Format**: Water Cooler Conversation (5 Critical Insights)

### Insight 1: Two-Step Service Initialization Creates Error Risk

**Did you know**: The proposed GetNodeService design required a two-step initialization (create → load_graph) that could lead to runtime errors if callers forget the second step.

**Implications**:
- Inconsistent with ScanPipeline pattern (which does everything in run())
- Easy to misuse in future code
- Tests need to remember the setup step

**Options Considered**:
- Option A: Lazy Loading - auto-load on first access
- Option B: Load in Constructor - always ready after creation
- Option C: Stateless Single Method - load fresh each call
- Option D: Keep Two-Step - explicit but error-prone

**AI Recommendation**: Option A (Lazy Loading)
- Reasoning: Impossible to misuse, clean API, still testable

**Discussion Summary**: User agreed with lazy loading approach.

**Decision**: Implement lazy loading with `_ensure_loaded()` pattern

**Action Items**: None - plan updated

**Affects**: T001 (GetNodeService), T005-T006 (TreeService)

---

### Insight 2: TreeConfig Naming Creates Conceptual Confusion

**Did you know**: Both GetNodeService and TreeService use TreeConfig, even though GetNodeService has nothing to do with "trees" - TreeConfig just contains graph_path.

**Implications**:
- Future developers will be confused
- Name doesn't communicate what it provides (graph location)
- Semantic coupling between unrelated concepts

**Options Considered**:
- Option A: Rename to GraphConfig - clean but touches many files
- Option B: Create separate GraphConfig - potential duplication
- Option C: Leave as-is with documentation - technical debt
- Option D: Use existing ScanConfig - creates wrong dependency

**AI Recommendation**: Option C initially (defer to keep scope tight)

**Discussion Summary**: User chose Option A - fix it now during this refactor.

**Decision**: Rename TreeConfig → GraphConfig with `__config_path__="graph"`

**Action Items**:
- [x] Added T000 task for rename
- [x] Updated all code examples to use GraphConfig

**Affects**: T000 (new task), T001, T005, config files, test files

---

### Insight 3: CLI Tests Will Test Less After Refactor

**Did you know**: After extracting business logic to services, CLI tests will test a thinner slice (arg parsing + rendering) while business logic moves to service tests.

**Implications**:
- CLI tests become integration tests
- Some redundant coverage between CLI and service tests
- Two test files cover different aspects of same flow

**Options Considered**:
- Option A: Keep as-is - safe, validates full stack
- Option B: Slim down CLI tests - DRY but risky
- Option C: Convert to true integration tests - complex
- Option D: Separate test directories - organizational only

**AI Recommendation**: Option A (Keep as-is)
- Reasoning: Regression safety during refactor, scope discipline

**Discussion Summary**: User agreed - keep CLI tests as safety net.

**Decision**: Keep existing CLI tests unchanged; they verify behavior preservation

**Action Items**: None - this is already the plan

**Affects**: T004, T010 (verification tasks)

---

### Insight 4: TreeService API Requires CLI to Orchestrate Multiple Calls

**Did you know**: With the original plan, CLI would need to call 3 separate TreeService methods in sequence (filter_nodes → build_root_bucket → get_children), keeping orchestration logic in CLI.

**Implications**:
- CLI still contains algorithm flow knowledge
- Hard to reuse from other interfaces (API would need same orchestration)
- Not truly "dumb" CLI

**Options Considered**:
- Option A: Keep granular API - flexible but CLI orchestrates
- Option B: Add high-level build_tree() - single call, encapsulates algorithm
- Option C: Return rich result object - single call, large return type
- Option D: Generator/iterator - memory efficient but complex

**AI Recommendation**: Option B (High-level build_tree() method)
- Reasoning: CLI becomes truly dumb, encapsulates algorithm, reusable

**Discussion Summary**: User agreed - convenience is great, make it easy to use.

**Decision**: Add `build_tree(pattern, max_depth) -> list[TreeNode]` as single public method

**Action Items**:
- [x] Updated T005-T007 task structure
- [x] Added TreeNode dataclass (T007)
- [x] Updated code examples with new API

**Affects**: T005, T006, T007, T008, T009

---

### Insight 5: GraphNotFoundError Needs to Be Created

**Did you know**: The plan references GraphNotFoundError for missing graph files, but this exception doesn't exist in the codebase yet.

**Implications**:
- Services need specific error for missing graph (vs corrupted graph)
- CLI needs to catch and render user-friendly message
- Exception should include path for debugging

**Options Considered**:
- Option A: Add to existing exceptions.py - centralized location
- Option B: Create service exceptions module - clean separation
- Option C: Subclass of GraphStoreError - unified handling
- Option D: Use FileNotFoundError - no new code but less semantic

**AI Recommendation**: Option C (Subclass of GraphStoreError)
- Reasoning: Unified error handling, specific when needed

**Discussion Summary**: User requested verification that it doesn't exist first, then chose Option A.

**Decision**: Add GraphNotFoundError to adapters/exceptions.py

**Action Items**:
- [x] Verified exception doesn't exist (via subagent search)
- [x] Added T000a task for creating exception
- [x] Updated dependencies for T001, T005

**Affects**: T000a (new task), T001, T005, exception handling in CLI

---

## Session Summary

**Insights Surfaced**: 5 critical insights identified and discussed
**Decisions Made**: 5 decisions reached through collaborative discussion
**Action Items Created**: 0 remaining (all applied immediately)
**Areas Updated**:
- Plan tasks: T000, T000a, T001, T005, T006, T007, T011 modified
- Findings table: 4 new findings added (06a-06d)
- Acceptance criteria: 5 new ACs added
- Task details: Complete code examples updated
- Rules docs: R3.5 added to rules.md, code review checklist updated

**Shared Understanding Achieved**: ✓

**Confidence Level**: High - All key risks identified and mitigated through improved design

**Next Steps**:
Proceed to implementation with `/plan-6-implement-phase`

---

**Next steps:**
- **Ready to implement**: `/plan-6-implement-phase --plan "docs/plans/006-architecture-alignment/cli-architecture-alignment-plan.md"`
- **Optional validation**: `/plan-4-complete-the-plan` (recommended for CS-3 overall complexity)
- **Optional task expansion**: `/plan-5-phase-tasks-and-brief` (if you want a separate dossier)
