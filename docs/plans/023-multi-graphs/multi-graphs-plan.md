# Multi-Graph Support Implementation Plan

**Plan Version**: 1.0.0
**Created**: 2026-01-13
**Spec**: [./multi-graphs-spec.md](./multi-graphs-spec.md)
**Status**: DRAFT

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Technical Context](#technical-context)
3. [Critical Research Findings](#critical-research-findings)
4. [Testing Philosophy](#testing-philosophy)
5. [Implementation Phases](#implementation-phases)
   - [Phase 1: Configuration Model](#phase-1-configuration-model)
   - [Phase 2: GraphService Implementation](#phase-2-graphservice-implementation)
   - [Phase 3: MCP Integration](#phase-3-mcp-integration)
   - [Phase 4: CLI Integration](#phase-4-cli-integration)
   - [Phase 5: Documentation](#phase-5-documentation)
6. [Cross-Cutting Concerns](#cross-cutting-concerns)
7. [Complexity Tracking](#complexity-tracking)
8. [Progress Tracking](#progress-tracking)
9. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

### Problem Statement
fs2 currently supports only a single graph file (`.fs2/graph.pickle`), limiting agents to exploring one codebase at a time. Coding agents need access to multiple codebases simultaneously—their local project graph plus external reference graphs—for richer context during development.

### Solution Approach
- Add `OtherGraphsConfig` to YAML configuration for defining named external graphs
- Create `GraphService` with thread-safe caching and staleness detection
- Extend MCP tools with `graph_name` parameter for graph selection
- Add `list_graphs` MCP tool for discovering available graphs
- Add `--graph-name` CLI option (mutually exclusive with `--graph-file`)

### Expected Outcomes
- Agents can query multiple codebases within a single session
- Graphs are cached with automatic staleness detection (mtime/size)
- Reserved name "default" refers to local project graph
- Backward compatible: existing commands work unchanged

### Success Metrics
- All 11 acceptance criteria from spec pass
- No performance regression for single-graph usage
- Thread-safe under concurrent MCP access

---

## Technical Context

### Current System State
- Single graph via `GraphConfig.graph_path` (default: `.fs2/graph.pickle`)
- MCP uses lazy singletons (`get_graph_store()`) with RLock thread safety
- CLI commands create fresh config/store/service per invocation (stateless)
- Config composition via deep merge (user config + project config)

### Integration Requirements
- Must integrate with existing `ConfigurationService` typed registry pattern
- Must preserve `GraphStore` ABC interface for services
- MCP tools must remain backward compatible (graph_name defaults to None)
- CLI validation for mutual exclusivity of `--graph-file` and `--graph-name`

### Constraints and Limitations
- No remote graph fetching (source_url is informational only)
- Scan functionality remains hidden from MCP
- No cross-graph queries (each query targets one graph)
- Relative paths resolve from CWD at service execution time

### Assumptions
- Users pre-scan external repositories before adding to config
- Graph files are trusted (RestrictedUnpickler boundary)
- Most users have 1-5 additional graphs (not hundreds)
- MCP server CWD is predictable (typically project root)

---

## Critical Research Findings

### Synthesis Summary

Research conducted via 2 specialized subagents (Implementation Strategist + Risk Planner) building on 70+ findings from initial research dossier. Findings are renumbered by impact.

---

### 01: Config List Concatenation Requires Custom Merge Logic
**Impact**: Critical
**Sources**: I1-07, R1-02
**Problem**: `deep_merge()` treats lists as scalars; project config would replace user config's graph list
**Solution**: Implement custom merge for `other_graphs.graphs` that concatenates lists and deduplicates by name
**Action Required**: Create `merge_other_graphs_configs()` called after standard deep merge
**Affects Phases**: Phase 1

---

### 02: MCP Singleton Must Become GraphService Cache
**Impact**: Critical
**Sources**: I1-02, I1-03, R1-01
**Problem**: Current `get_graph_store()` returns single NetworkXGraphStore; multi-graph needs cache
**Solution**: Create `get_graph_service()` singleton managing dict of cached graphs; keep `get_graph_store()` for backward compat delegating to `service.get_graph(name=None)`
**Action Required**:
```python
# New: GraphService with RLock, cache dict
def get_graph_service() -> GraphService:
    ...
# Keep: Delegates to service for default graph
def get_graph_store() -> GraphStore:
    return get_graph_service().get_graph(name=None)
```
**Affects Phases**: Phase 2, Phase 3

---

### 03: Thread Safety Requires RLock (Not Lock) for Reentrant Acquisition
**Impact**: Critical
**Sources**: R1-01, I1-02
**Problem**: `get_graph_service()` may call `get_config()` internally; simple Lock would deadlock
**Solution**: Use `threading.RLock()` for graph cache; fine-grained locking for cache mutations only
**Action Required**: GraphService uses RLock; pre-check staleness outside critical section
**Affects Phases**: Phase 2

---

### 04: Reserved Name "default" Must Be Enforced
**Impact**: High
**Sources**: I1-04, R1-04
**Problem**: User could configure a graph named "default", causing ambiguity
**Solution**: Add Pydantic validator rejecting `name == "default"` in OtherGraph
**Action Required**:
```python
@field_validator('name')
def validate_not_reserved(cls, v):
    if v == "default":
        raise ValueError("'default' is reserved for the local graph")
    return v
```
**Affects Phases**: Phase 1

---

### 05: Mutual Exclusivity of --graph-name and --graph-file
**Impact**: High
**Sources**: I1-04, R1-05
**Problem**: Both options accepted simultaneously; undefined behavior
**Solution**: Validate in `main()` callback; raise `typer.BadParameter` if both provided
**Action Required**: Add check before composition roots
**Affects Phases**: Phase 4

---

### 06: 6+ Command Composition Roots Need Consistent Changes
**Impact**: High
**Sources**: I1-03, R1-03
**Problem**: Each CLI command has own composition root; inconsistent graph_name handling
**Solution**: Extract `resolve_graph_from_context()` utility; centralize in main callback
**Action Required**: Create utility function; update all commands to use it
**Affects Phases**: Phase 4

---

### 07: Existing Services Require No Signature Changes
**Impact**: High (positive)
**Sources**: I1-06
**Problem**: None - this is good news
**Solution**: TreeService, SearchService, GetNodeService already depend on GraphStore ABC
**Action Required**: Only composition roots change; service signatures stay same
**Affects Phases**: Phase 3, Phase 4

---

### 08: list_graphs Must Check Existence Without Loading
**Impact**: High
**Sources**: I1-08, R1-10
**Problem**: list_graphs should be fast; shouldn't load entire pickle
**Solution**: Use `Path.exists()` for availability; return `available: false` for missing files
**Action Required**: GraphInfo dataclass with `available: bool` field
**Affects Phases**: Phase 3

---

### 09: Path Resolution Must Handle Absolute, Tilde, and Relative
**Impact**: Medium
**Sources**: I1-05, R1-08
**Problem**: Relative paths resolved from CWD; MCP server CWD may differ
**Solution**: Normalize at service access time; document CWD behavior
**Action Required**: `_resolve_path()` uses `expanduser().resolve()`
**Affects Phases**: Phase 2

---

### 10: Pickle Version Mismatch Should Warn, Not Fail
**Impact**: Medium
**Sources**: R1-07
**Problem**: External graph from different fs2 version may have different CodeNode structure
**Solution**: Compare metadata.format_version; log warning if different, continue loading
**Action Required**: Add version check in `GraphService.get_graph()`
**Affects Phases**: Phase 2

---

### 11: NetworkXGraphStore Tests Must Remain Unchanged
**Impact**: Medium
**Sources**: R1-06
**Problem**: 37+ tests directly use NetworkXGraphStore; caching is separate layer
**Solution**: Keep storage tests as-is; add new GraphService tests for caching
**Action Required**: Create separate test file for GraphService
**Affects Phases**: Phase 2

---

### 12: Backward Compatibility Must Be Verified
**Impact**: Medium
**Sources**: R1-09
**Problem**: Existing commands without --graph-name must work unchanged
**Solution**: Add integration tests running all commands without --graph-name
**Action Required**: Test class `TestBackwardCompatibility`
**Affects Phases**: Phase 4

---

## Testing Philosophy

### Testing Approach
**Selected Approach**: Full TDD
**Rationale**: Thread-safe caching and multi-component integration require comprehensive test coverage
**Focus Areas**:
- GraphService thread safety under concurrent access
- Config list concatenation (user + project configs)
- Staleness detection (mtime/size changes)
- MCP tool graph_name parameter routing
- Path resolution (absolute, tilde, relative)

### Test-Driven Development
- Write tests FIRST (RED)
- Implement minimal code (GREEN)
- Refactor for quality (REFACTOR)

### Mock Usage
**Policy**: Targeted mocks only
- May reuse existing fakes: `FakeGraphStore`, `FakeConfigurationService`
- New mocks/fakes require human review before implementation
- Prefer real fixtures (`tests/fixtures/fixture_graph.pkl`) where practical

### Test Documentation
Every test must include:
```python
"""
Purpose: [what truth this test proves]
Quality Contribution: [how this prevents bugs]
Acceptance Criteria: [measurable assertions]
"""
```

---

## Implementation Phases

### Phase 1: Configuration Model

**Objective**: Add OtherGraph and OtherGraphsConfig to enable multi-graph configuration via YAML.

**Deliverables**:
- `OtherGraph` Pydantic model with name, path, description, source_url
- `OtherGraphsConfig` model with `__config_path__ = "other_graphs"`
- Custom list concatenation merge for user + project configs
- Validator rejecting reserved name "default"

**Dependencies**: None (foundational phase)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Deep merge breaks lists | High | High | Custom merge function for other_graphs |
| Reserved name collision | Medium | Medium | Pydantic validator enforcement |

### Tasks (TDD Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 1.1 | [ ] | Write tests for OtherGraph model | 2 | Tests cover: name validation, path types, optional fields, reserved name rejection | - | /workspaces/flow_squared/tests/unit/config/test_other_graphs_config.py |
| 1.2 | [ ] | Write tests for OtherGraphsConfig model | 2 | Tests cover: empty list default, multiple graphs, config_path attribute | - | Same file |
| 1.3 | [ ] | Write tests for config list concatenation | 2 | Tests: user(2) + project(2) = 4 graphs; duplicate names deduplicated | - | Same file |
| 1.4 | [ ] | Implement OtherGraph model | 2 | All tests from 1.1 pass | - | /workspaces/flow_squared/src/fs2/config/objects.py |
| 1.5 | [ ] | Implement OtherGraphsConfig model | 2 | All tests from 1.2 pass; registered in YAML_CONFIG_TYPES | - | Same file |
| 1.6 | [ ] | Implement custom merge for other_graphs | 3 | All tests from 1.3 pass | - | /workspaces/flow_squared/src/fs2/config/loaders.py or service.py |
| 1.7 | [ ] | Integration test: load config with other_graphs | 2 | Config loads from YAML, graphs accessible | - | Test with tmp_path fixture |

### Test Examples (Write First!)

```python
import pytest
from pydantic import ValidationError
from fs2.config.objects import OtherGraph, OtherGraphsConfig

class TestOtherGraph:
    """Tests for OtherGraph configuration model."""

    def test_valid_graph_config(self):
        """
        Purpose: Proves basic OtherGraph instantiation works
        Quality Contribution: Validates config schema
        Acceptance Criteria: All fields populated correctly
        """
        graph = OtherGraph(
            name="shared-lib",
            path="~/projects/shared/.fs2/graph.pickle",
            description="Shared utilities",
            source_url="https://github.com/org/shared"
        )
        assert graph.name == "shared-lib"
        assert graph.path == "~/projects/shared/.fs2/graph.pickle"

    def test_reserved_name_default_rejected(self):
        """
        Purpose: Ensures 'default' cannot be used as graph name
        Quality Contribution: Prevents ambiguity with local graph
        Acceptance Criteria: ValidationError raised
        """
        with pytest.raises(ValidationError, match="reserved"):
            OtherGraph(name="default", path="/some/path")

    def test_optional_fields(self):
        """
        Purpose: Proves description and source_url are optional
        Quality Contribution: Validates minimal config works
        Acceptance Criteria: Graph created with only name and path
        """
        graph = OtherGraph(name="minimal", path="/path/to/graph.pickle")
        assert graph.description is None
        assert graph.source_url is None


class TestOtherGraphsConfig:
    """Tests for OtherGraphsConfig container model."""

    def test_empty_graphs_list_by_default(self):
        """
        Purpose: Proves default state is empty list
        Quality Contribution: Backward compatibility
        Acceptance Criteria: Empty list, not None
        """
        config = OtherGraphsConfig()
        assert config.graphs == []

    def test_config_path_attribute(self):
        """
        Purpose: Verifies YAML loading path
        Quality Contribution: Ensures auto-loading works
        Acceptance Criteria: __config_path__ = "other_graphs"
        """
        assert OtherGraphsConfig.__config_path__ == "other_graphs"
```

### Non-Happy-Path Coverage
- [ ] Empty name string rejected
- [ ] Empty path string rejected
- [ ] Invalid characters in name handled
- [ ] Duplicate graph names in same config rejected

### Acceptance Criteria
- [ ] All tests passing (7+ tests)
- [ ] OtherGraphsConfig registered in YAML_CONFIG_TYPES
- [ ] Config loads successfully from YAML
- [ ] List concatenation preserves all graphs from both sources
- [ ] Test coverage > 90% for new code

---

### Phase 2: GraphService Implementation

**Objective**: Create thread-safe GraphService with caching and staleness detection for multi-graph management.

**Deliverables**:
- `GraphService` class with `get_graph(name)` and `list_graphs()` methods
- Thread-safe cache with RLock
- Staleness detection via mtime/size comparison
- Path resolution (absolute, tilde, relative)
- GraphInfo dataclass for list_graphs return type

**Dependencies**: Phase 1 must be complete

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Thread safety race conditions | Medium | High | RLock, fine-grained locking, concurrent tests |
| Cache staleness false positives | Low | Medium | Use both mtime AND size for comparison |

### Tasks (TDD Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 2.0 | [x] | Add _source_dir field to OtherGraph | 3 | Tests for source_dir tracking; field added; merge sets value | - | Prerequisite for DYK-02 |
| 2.1 | [x] | Write tests for GraphService.get_graph() | 3 | Tests: default graph, named graph, missing graph error, cache hit, cache miss | - | /workspaces/flow_squared/tests/unit/services/test_graph_service.py |
| 2.2 | [x] | Write tests for staleness detection | 2 | Tests: unchanged file = cache hit, modified mtime = reload, modified size = reload | - | Same file |
| 2.3 | [x] | Write tests for path resolution | 2 | Tests: absolute path, tilde expansion, relative path resolution | - | Same file |
| 2.4 | [x] | Write tests for list_graphs() | 2 | Tests: default + configured graphs, availability status, missing files | - | Same file |
| 2.5 | [x] | Write concurrent access tests | 3 | 5+ threads calling get_graph() simultaneously without race conditions | - | Same file |
| 2.6 | [x] | Implement GraphInfo dataclass | 1 | Dataclass with name, path, description, source_url, available fields | - | /workspaces/flow_squared/src/fs2/core/services/graph_service.py |
| 2.7 | [x] | Implement GraphService._resolve_path() | 2 | Path resolution handles all three cases | - | Same file |
| 2.8 | [x] | Implement GraphService.get_graph() | 3 | All tests from 2.1, 2.2, 2.3, 2.5 pass | - | Same file |
| 2.9 | [x] | Implement GraphService.list_graphs() | 2 | All tests from 2.4 pass | - | Same file |
| 2.10 | [x] | Add version mismatch warning | 1 | Log warning if graph format_version differs from current | - | Same file |
| 2.11 | [x] | Integration test with real config loading | 2 | End-to-end YAML→Service test passes | - | Validates DYK-04 |

### Test Examples (Write First!)

```python
import pytest
import threading
import time
from pathlib import Path
from fs2.core.services.graph_service import GraphService, GraphInfo
from fs2.config.service import FakeConfigurationService
from fs2.config.objects import GraphConfig, OtherGraphsConfig, OtherGraph

class TestGraphServiceGetGraph:
    """Tests for GraphService.get_graph() method."""

    def test_get_default_graph(self, tmp_path, fixture_graph_path):
        """
        Purpose: Proves None/default returns local project graph
        Quality Contribution: Backward compatibility
        Acceptance Criteria: Returns graph from GraphConfig.graph_path
        """
        config = FakeConfigurationService()
        config.set(GraphConfig(graph_path=str(fixture_graph_path)))
        service = GraphService(config)

        store = service.get_graph(name=None)
        assert store is not None
        # Also test explicit "default" name
        store2 = service.get_graph(name="default")
        assert store2 is store  # Same cached instance

    def test_get_named_graph(self, tmp_path, create_test_graph):
        """
        Purpose: Proves named graph lookup works
        Quality Contribution: Core multi-graph functionality
        Acceptance Criteria: Returns correct graph by name
        """
        graph_path = create_test_graph(tmp_path / "external.pickle")
        config = FakeConfigurationService()
        config.set(OtherGraphsConfig(graphs=[
            OtherGraph(name="external", path=str(graph_path))
        ]))
        service = GraphService(config)

        store = service.get_graph(name="external")
        assert store is not None

    def test_cache_hit_same_instance(self, fixture_graph_path):
        """
        Purpose: Proves caching returns same instance
        Quality Contribution: Performance validation
        Acceptance Criteria: Two calls return identical object
        """
        config = FakeConfigurationService()
        config.set(GraphConfig(graph_path=str(fixture_graph_path)))
        service = GraphService(config)

        store1 = service.get_graph(name=None)
        store2 = service.get_graph(name=None)
        assert store1 is store2


class TestGraphServiceStaleness:
    """Tests for cache staleness detection."""

    def test_modified_file_triggers_reload(self, tmp_path, create_test_graph):
        """
        Purpose: Proves file modification invalidates cache
        Quality Contribution: Ensures fresh data after updates
        Acceptance Criteria: Modified file triggers reload
        """
        graph_path = create_test_graph(tmp_path / "graph.pickle")
        config = FakeConfigurationService()
        config.set(GraphConfig(graph_path=str(graph_path)))
        service = GraphService(config)

        store1 = service.get_graph()

        # Modify file (touch to change mtime)
        time.sleep(0.1)  # Ensure mtime differs
        graph_path.touch()

        store2 = service.get_graph()
        assert store1 is not store2  # Different instance after reload


class TestGraphServiceConcurrency:
    """Tests for thread-safe concurrent access."""

    def test_concurrent_access_no_race(self, fixture_graph_path):
        """
        Purpose: Proves thread safety under concurrent load
        Quality Contribution: Prevents race conditions in MCP
        Acceptance Criteria: 10 threads access without errors
        """
        config = FakeConfigurationService()
        config.set(GraphConfig(graph_path=str(fixture_graph_path)))
        service = GraphService(config)

        results = []
        errors = []

        def worker():
            try:
                store = service.get_graph()
                results.append(store)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
        # All should be same cached instance
        assert all(r is results[0] for r in results)
```

### Non-Happy-Path Coverage
- [ ] Unknown graph name raises clear error
- [ ] Missing file raises FileNotFoundError with helpful message
- [ ] Corrupted pickle handled gracefully
- [ ] Version mismatch logged as warning

### Acceptance Criteria
- [ ] All tests passing (15+ tests)
- [ ] Thread-safe under 10 concurrent threads
- [ ] Staleness detection works correctly
- [ ] Path resolution handles all three cases
- [ ] list_graphs returns availability status

---

### Phase 3: MCP Integration

**Objective**: Integrate GraphService with MCP server; add list_graphs tool and graph_name parameter to existing tools.

**Deliverables**:
- `get_graph_service()` lazy singleton in dependencies.py
- `list_graphs` MCP tool
- `graph_name` parameter added to tree, search, get_node tools
- Backward compatible: existing calls without graph_name work

**Dependencies**: Phase 2 must be complete

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking existing MCP integrations | Low | High | Default graph_name=None preserves behavior |
| Singleton lifecycle issues | Medium | Medium | Follow existing RLock pattern |

### Tasks (TDD Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 3.1 | [x] | Write tests for get_graph_service() | 2 | Tests: singleton behavior, thread safety, returns GraphService | [📋](tasks/phase-3-mcp-integration/execution.log.md#task-t001) | Complete |
| 3.2 | [x] | Write tests for list_graphs MCP tool | 2 | Tests: returns all graphs, availability status, count field | [📋](tasks/phase-3-mcp-integration/execution.log.md#task-t002) | Complete |
| 3.3 | [x] | Write tests for tree with graph_name | 2 | Tests: default graph, named graph, unknown graph error | [📋](tasks/phase-3-mcp-integration/execution.log.md#task-t003) | Complete [^7] |
| 3.4 | [x] | Write tests for search with graph_name | 2 | Tests: default graph, named graph, results from correct graph | [📋](tasks/phase-3-mcp-integration/execution.log.md#task-t004) | Complete [^8] |
| 3.5 | [x] | Write tests for get_node with graph_name | 2 | Tests: default graph, named graph, node from correct graph | [📋](tasks/phase-3-mcp-integration/execution.log.md#task-t005) | Complete [^9] |
| 3.6 | [x] | Implement get_graph_service() singleton | 2 | Tests from 3.1 pass | [📋](tasks/phase-3-mcp-integration/execution.log.md#task-t006) | Complete |
| 3.7 | [x] | Update get_graph_store() to delegate | 1 | Backward compatible; uses get_graph_service().get_graph(None) | [📋](tasks/phase-3-mcp-integration/execution.log.md#task-t007) | Complete |
| 3.8 | [x] | Implement list_graphs MCP tool | 2 | Tests from 3.2 pass; FastMCP registration | [📋](tasks/phase-3-mcp-integration/execution.log.md#task-t008) | Complete |
| 3.9 | [x] | Add graph_name to tree tool | 2 | Tests from 3.3 pass | [📋](tasks/phase-3-mcp-integration/execution.log.md#task-t009) | Complete [^7] |
| 3.10 | [x] | Add graph_name to search tool | 2 | Tests from 3.4 pass | [📋](tasks/phase-3-mcp-integration/execution.log.md#task-t010) | Complete [^8] |
| 3.11 | [x] | Add graph_name to get_node tool | 2 | Tests from 3.5 pass | [📋](tasks/phase-3-mcp-integration/execution.log.md#task-t011) | Complete [^9] |

### Test Examples (Write First!)

```python
import pytest
from fs2.mcp.server import list_graphs, tree, search, get_node
from fs2.mcp.dependencies import get_graph_service, get_graph_store

class TestListGraphsTool:
    """Tests for list_graphs MCP tool."""

    def test_returns_default_graph(self, mcp_test_config):
        """
        Purpose: Proves default graph always appears
        Quality Contribution: Core discovery functionality
        Acceptance Criteria: 'default' graph in results
        """
        result = list_graphs()
        assert "graphs" in result
        assert "count" in result
        default = next((g for g in result["graphs"] if g["name"] == "default"), None)
        assert default is not None

    def test_returns_configured_graphs(self, mcp_test_config_with_other_graphs):
        """
        Purpose: Proves configured graphs appear in list
        Quality Contribution: Multi-graph discovery
        Acceptance Criteria: All configured graphs listed
        """
        result = list_graphs()
        names = [g["name"] for g in result["graphs"]]
        assert "default" in names
        assert "external-lib" in names

    def test_unavailable_graph_shows_available_false(self, mcp_test_config_missing_graph):
        """
        Purpose: Proves missing files don't cause errors
        Quality Contribution: Graceful degradation
        Acceptance Criteria: available=false for missing file
        """
        result = list_graphs()
        missing = next((g for g in result["graphs"] if g["name"] == "missing"), None)
        assert missing is not None
        assert missing["available"] == False


class TestTreeWithGraphName:
    """Tests for tree tool with graph_name parameter."""

    def test_default_graph_when_none(self, mcp_test_config):
        """
        Purpose: Proves backward compatibility
        Quality Contribution: Existing integrations work
        Acceptance Criteria: Returns results from default graph
        """
        result = tree(pattern=".", graph_name=None)
        assert "count" in result
        assert result["count"] > 0

    def test_named_graph_returns_different_content(self, mcp_test_config_with_other_graphs):
        """
        Purpose: Proves graph switching works
        Quality Contribution: Core multi-graph functionality
        Acceptance Criteria: Different graph returns different content
        """
        default_result = tree(pattern=".", graph_name=None)
        other_result = tree(pattern=".", graph_name="external-lib")
        # Results should differ (different codebases)
        assert default_result["count"] != other_result["count"]
```

### Non-Happy-Path Coverage
- [ ] Unknown graph_name raises clear error
- [ ] Missing graph file handled gracefully
- [ ] Concurrent MCP calls thread-safe

### Acceptance Criteria
- [ ] All tests passing (15+ tests)
- [ ] list_graphs returns all configured graphs
- [ ] tree/search/get_node accept graph_name parameter
- [ ] Backward compatible: None/omitted = default graph
- [ ] FastMCP tool registration correct

---

### Phase 4: CLI Integration

**Objective**: Add --graph-name global option to CLI with mutual exclusivity validation.

**Deliverables**:
- `graph_name` field in CLIContext dataclass
- `--graph-name` option in main() callback
- Mutual exclusivity validation with --graph-file
- Graph resolution utility function
- Updated composition roots in all CLI commands

**Dependencies**: Phase 2 must be complete (GraphService available)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Inconsistent behavior across commands | Medium | Medium | Extract shared resolution utility |
| Breaking existing --graph-file usage | Low | High | Preserve existing behavior when only --graph-file used |

### Tasks (TDD Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 4.1 | [x] | Write tests for CLIContext with graph_name | 1 | Tests: field exists, defaults to None | [📋](tasks/phase-4-cli-integration/execution.log.md#task-41) | Completed [^11] |
| 4.2 | [x] | Write tests for mutual exclusivity | 2 | Tests: both options = error, either alone = ok, neither = ok | [📋](tasks/phase-4-cli-integration/execution.log.md#task-42) | Completed [^11] |
| 4.3 | [x] | Write tests for resolve_graph_from_context() | 2 | Tests: --graph-name resolves to path, --graph-file resolves to path | [📋](tasks/phase-4-cli-integration/execution.log.md#task-43) | Completed [^11] |
| 4.4 | [x] | Write integration tests for CLI commands | 2 | Tests: tree, search, get-node with --graph-name | [📋](tasks/phase-4-cli-integration/execution.log.md#task-44) | Completed [^11] |
| 4.5 | [x] | Write backward compatibility tests | 2 | Tests: all commands work without --graph-name | [📋](tasks/phase-4-cli-integration/execution.log.md#task-45) | Completed [^11] |
| 4.6 | [x] | Update CLIContext dataclass | 1 | Add graph_name field | [📋](tasks/phase-4-cli-integration/execution.log.md#task-46) | Completed [^11] |
| 4.7 | [x] | Add --graph-name to main() callback | 2 | Option registered with help text | [📋](tasks/phase-4-cli-integration/execution.log.md#task-47) | Completed [^11] |
| 4.8 | [x] | Implement mutual exclusivity validation | 2 | Tests from 4.2 pass | [📋](tasks/phase-4-cli-integration/execution.log.md#task-48) | Completed [^11] |
| 4.9 | [x] | Implement resolve_graph_from_context() | 2 | Tests from 4.3 pass | [📋](tasks/phase-4-cli-integration/execution.log.md#task-49) | Completed [^11] |
| 4.10 | [x] | Update tree command composition root | 2 | Uses resolved graph path | [📋](tasks/phase-4-cli-integration/execution.log.md#task-410) | Completed [^11] |
| 4.11 | [x] | Update search command composition root | 2 | Uses resolved graph path | [📋](tasks/phase-4-cli-integration/execution.log.md#task-411) | Completed [^11] |
| 4.12 | [x] | Update get-node command composition root | 2 | Uses resolved graph path | [📋](tasks/phase-4-cli-integration/execution.log.md#task-412) | Completed [^11] |

### Test Examples (Write First!)

```python
import pytest
from typer.testing import CliRunner
from fs2.cli.main import app, CLIContext

runner = CliRunner()

class TestCLIContextGraphName:
    """Tests for CLIContext graph_name field."""

    def test_graph_name_field_exists(self):
        """
        Purpose: Proves CLIContext has graph_name
        Quality Contribution: Verifies dataclass update
        Acceptance Criteria: Field accessible, defaults to None
        """
        ctx = CLIContext()
        assert hasattr(ctx, 'graph_name')
        assert ctx.graph_name is None


class TestMutualExclusivity:
    """Tests for --graph-name and --graph-file mutual exclusivity."""

    def test_both_options_raises_error(self):
        """
        Purpose: Proves mutual exclusivity enforced
        Quality Contribution: Clear user feedback
        Acceptance Criteria: Error message when both provided
        """
        result = runner.invoke(app, [
            "--graph-file", "/tmp/graph.pickle",
            "--graph-name", "external",
            "tree"
        ])
        assert result.exit_code != 0
        assert "Cannot use both" in result.output

    def test_only_graph_file_works(self, tmp_graph_file):
        """
        Purpose: Proves --graph-file alone works
        Quality Contribution: Backward compatibility
        Acceptance Criteria: Command succeeds
        """
        result = runner.invoke(app, [
            "--graph-file", str(tmp_graph_file),
            "tree"
        ])
        assert result.exit_code == 0

    def test_only_graph_name_works(self, configured_other_graph):
        """
        Purpose: Proves --graph-name alone works
        Quality Contribution: New functionality
        Acceptance Criteria: Command succeeds
        """
        result = runner.invoke(app, [
            "--graph-name", "external",
            "tree"
        ])
        assert result.exit_code == 0


class TestBackwardCompatibility:
    """Tests ensuring existing CLI usage unchanged."""

    def test_tree_without_graph_options(self, project_with_default_graph):
        """
        Purpose: Proves existing usage works
        Quality Contribution: No breaking changes
        Acceptance Criteria: Command succeeds with default graph
        """
        result = runner.invoke(app, ["tree"])
        assert result.exit_code == 0
```

### Non-Happy-Path Coverage
- [ ] Unknown graph name raises clear error
- [ ] Missing configured graph file handled
- [ ] Empty graph name string rejected

### Acceptance Criteria
- [ ] All tests passing (15+ tests)
- [ ] --graph-name works with tree, search, get-node
- [ ] Mutual exclusivity enforced with clear error
- [ ] Backward compatible: existing commands unchanged
- [ ] Help text documents the option

---

### Phase 5: Documentation

**Objective**: Document multi-graph feature for users and agents following hybrid approach.

**Deliverables**:
- Updated README.md with multi-graph mention
- New docs/how/user/multi-graphs.md guide
- Registry entry for MCP docs_list/docs_get access
- Build script inclusion

**Dependencies**: All implementation phases complete

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Documentation drift | Medium | Low | Include doc updates in acceptance criteria |

### Discovery & Placement Decision

**Existing docs/how/user/ structure**:
```
docs/how/user/
├── AGENTS.md
├── cli.md
├── configuration-guide.md
├── configuration.md
├── mcp-server-guide.md
├── registry.yaml
├── scanning.md
└── wormhole-mcp-guide.md
```

**Decision**: Create new `docs/how/user/multi-graphs.md` (complements existing configuration-guide.md)

**File strategy**: Single comprehensive guide covering config + MCP + CLI usage

### Tasks (Lightweight Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 5.1 | [ ] | Survey existing docs for integration points | 1 | List files that need cross-references | - | configuration-guide.md, mcp-server-guide.md, cli.md |
| 5.2 | [ ] | Update README.md features section | 1 | Brief mention of multi-graph capability | - | /workspaces/flow_squared/README.md |
| 5.3 | [ ] | Create docs/how/user/multi-graphs.md | 2 | Complete guide with examples | - | /workspaces/flow_squared/docs/how/user/multi-graphs.md |
| 5.4 | [ ] | Add registry entry | 1 | Entry in registry.yaml for MCP discovery | - | /workspaces/flow_squared/docs/how/user/registry.yaml |
| 5.5 | [ ] | Update configuration-guide.md with cross-reference | 1 | Link to multi-graphs.md | - | /workspaces/flow_squared/docs/how/user/configuration-guide.md |
| 5.6 | [ ] | Run doc-build and verify | 1 | `just doc-build` succeeds, doc accessible via MCP | - | Build and test |

### Content Outline

**README.md addition**:
```markdown
### Multi-Graph Support
Query multiple codebases from a single fs2 instance. Configure external graphs in `other_graphs` section and access via `--graph-name` CLI option or MCP `graph_name` parameter.
```

**docs/how/user/multi-graphs.md**:
1. **Overview**: What and why
2. **Configuration**: YAML schema, examples
3. **CLI Usage**: --graph-name option, mutual exclusivity
4. **MCP Usage**: list_graphs tool, graph_name parameter
5. **Path Resolution**: Absolute, tilde, relative
6. **Troubleshooting**: Common issues

**registry.yaml entry**:
```yaml
- id: multi-graphs
  title: "Multi-Graph Configuration Guide"
  summary: "Configure and use multiple code graphs..."
  category: how-to
  tags:
    - config
    - graphs
    - mcp
  path: multi-graphs.md
```

### Acceptance Criteria
- [ ] README.md updated
- [ ] multi-graphs.md complete and accurate
- [ ] Registry entry added
- [ ] doc-build succeeds
- [ ] MCP docs_get(id="multi-graphs") returns content

---

## Cross-Cutting Concerns

### Security Considerations
- Graph files loaded via RestrictedUnpickler (existing security boundary)
- External graphs should be from trusted sources
- No new attack surface introduced

### Observability
- Log warning on graph format version mismatch
- Log info on graph cache hit/miss (debug level)
- Error messages include configured path for troubleshooting

### Documentation
- Primary: docs/how/user/multi-graphs.md
- Secondary: README.md features section
- MCP delivery via registry.yaml

---

## Complexity Tracking

| Component | CS | Label | Breakdown (S,I,D,N,F,T) | Justification | Mitigation |
|-----------|-----|-------|------------------------|---------------|------------|
| GraphService caching | 3 | Medium | S=1,I=0,D=1,N=0,F=1,T=2 | Thread safety critical | RLock, concurrent tests |
| Config list merge | 2 | Small | S=1,I=0,D=1,N=1,F=0,T=1 | Custom merge logic | Dedicated tests |
| CLI composition roots | 2 | Small | S=2,I=0,D=0,N=0,F=0,T=1 | 6 files need changes | Extract shared utility |

---

## Progress Tracking

### Phase Completion Checklist
- [x] Phase 1: Configuration Model - COMPLETE (2026-01-13)
- [x] Phase 2: GraphService Implementation - COMPLETE (2026-01-13)
- [x] Phase 3: MCP Integration - COMPLETE (2026-01-14)
- [x] Phase 4: CLI Integration - COMPLETE (100%)
- [ ] Phase 5: Documentation - PENDING

### STOP Rule
**IMPORTANT**: This plan must be complete before creating tasks. After writing this plan:
1. Run `/plan-4-complete-the-plan` to validate readiness
2. Only proceed to `/plan-5-phase-tasks-and-brief` after validation passes

---

## Change Footnotes Ledger

**NOTE**: This section is populated during implementation by plan-6a-update-progress.

**Footnote Numbering Authority**: plan-6a-update-progress is the **single source of truth** for footnote numbering across the entire plan.

### Phase 1: Configuration Model (2026-01-13)

[^1]: Phase 1 T001-T007 - OtherGraph and OtherGraphsConfig models
  - `type:src/fs2/config/objects.py:OtherGraph`
  - `type:src/fs2/config/objects.py:OtherGraphsConfig`
  - `callable:src/fs2/config/service.py:_concatenate_and_dedupe`
  - `callable:src/fs2/config/service.py:_extract_and_remove_list`

[^2]: Phase 1 T007 - Integration tests for config loading
  - `file:tests/unit/config/test_other_graphs_config.py`

### Phase 2: GraphService Implementation (2026-01-13)

[^3]: Phase 2 T000 - Add _source_dir field to OtherGraph
  - `type:src/fs2/config/objects.py:OtherGraph` (added _source_dir PrivateAttr)
  - `callable:src/fs2/config/service.py:FS2ConfigurationService._concatenate_and_dedupe` (updated for source tracking)
  - `callable:src/fs2/config/service.py:FS2ConfigurationService._create_other_graphs_config` (new method)

[^4]: Phase 2 T006 - GraphInfo dataclass and exception hierarchy
  - `type:src/fs2/core/services/graph_service.py:GraphServiceError`
  - `type:src/fs2/core/services/graph_service.py:UnknownGraphError`
  - `type:src/fs2/core/services/graph_service.py:GraphFileNotFoundError`
  - `type:src/fs2/core/services/graph_service.py:GraphInfo`

[^5]: Phase 2 T007-T009 - GraphService core implementation
  - `type:src/fs2/core/services/graph_service.py:GraphService`
  - `callable:src/fs2/core/services/graph_service.py:GraphService._resolve_path`
  - `callable:src/fs2/core/services/graph_service.py:GraphService.get_graph`
  - `callable:src/fs2/core/services/graph_service.py:GraphService.list_graphs`
  - `callable:src/fs2/core/services/graph_service.py:GraphService._is_stale`
  - `callable:src/fs2/core/services/graph_service.py:GraphService._load_graph`

[^6]: Phase 2 T001-T005, T011 - GraphService test suite
  - `file:tests/unit/services/test_graph_service.py` (20 tests)

### Phase 3: MCP Integration (2026-01-14)

[^7]: Phase 3 T003+T009 - tree with graph_name parameter
  - `function:src/fs2/mcp/server.py:tree` - Added graph_name parameter
  - `class:tests/mcp_tests/test_tree_tool.py:TestTreeWithGraphName` - 4 tests

[^8]: Phase 3 T004+T010 - search with graph_name parameter
  - `function:src/fs2/mcp/server.py:search` - Added graph_name parameter
  - `class:tests/mcp_tests/test_search_tool.py:TestSearchWithGraphName` - 4 tests

[^9]: Phase 3 T005+T011 - get_node with graph_name parameter
  - `function:src/fs2/mcp/server.py:get_node` - Added graph_name parameter
  - `class:tests/mcp_tests/test_get_node_tool.py:TestGetNodeWithGraphName` - 5 tests

[^10]: Phase 3 T015 - E2E cache invalidation validation
  - `file:tests/mcp_tests/test_cache_invalidation.py` - 3 E2E tests
  - `method:src/fs2/core/services/tree_service.py:TreeService._ensure_loaded` - Fixed to skip reload if store has content

### Phase 4: CLI Integration

[^11]: Phase 4: CLI Integration completion
  - `file:src/fs2/cli/main.py` - Added --graph-name option, mutual exclusivity validation
  - `function:src/fs2/cli/utils.py:resolve_graph_from_context` - Graph resolution utility
  - `file:src/fs2/cli/tree.py` - Updated composition root
  - `file:src/fs2/cli/search.py` - Updated composition root
  - `file:src/fs2/cli/get_node.py` - Updated composition root
  - `file:src/fs2/core/dependencies.py` - Shared DI container (created)
  - `file:tests/unit/cli/test_main.py` - Unit tests (created)
  - `file:tests/integration/test_cli_multi_graph.py` - Integration tests (created)