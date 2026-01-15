"""Tests for GraphService.

Phase 2: GraphService Implementation - Multi-Graph Support
Per spec AC2, AC3, AC5, AC6: Graph retrieval, caching, error handling
Per DYK-01: Double-checked locking for thread safety
Per DYK-02: Path resolution from config source directory
Per DYK-03: Distinct error types for unknown vs missing file

TDD Approach: Tests written FIRST (RED), implementation follows (GREEN).
"""

import pickle
from pathlib import Path

import networkx as nx
import pytest

from fs2.config.objects import GraphConfig, OtherGraph, OtherGraphsConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.models.code_node import CodeNode

# =============================================================================
# Test Fixtures and Helpers
# =============================================================================


def create_test_graph_file(path: Path) -> None:
    """Create a minimal valid graph pickle file for tests.

    Per NetworkXGraphStore.save(): File format is (metadata_dict, networkx.DiGraph)
    """
    graph = nx.DiGraph()

    # Build metadata as NetworkXGraphStore expects
    metadata = {
        "format_version": "1.0",
        "created_at": "2026-01-13T00:00:00+00:00",
        "node_count": 0,
        "edge_count": 0,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump((metadata, graph), f, protocol=pickle.HIGHEST_PROTOCOL)


def create_graph_with_nodes(path: Path, nodes: list[CodeNode]) -> None:
    """Create a graph pickle file with specified nodes.

    Per NetworkXGraphStore.save(): File format is (metadata_dict, networkx.DiGraph)
    """
    graph = nx.DiGraph()

    for node in nodes:
        graph.add_node(node.node_id, data=node)

    metadata = {
        "format_version": "1.0",
        "created_at": "2026-01-13T00:00:00+00:00",
        "node_count": len(nodes),
        "edge_count": 0,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump((metadata, graph), f, protocol=pickle.HIGHEST_PROTOCOL)


def make_code_node(file_path: str = "test.py", name: str = "test") -> CodeNode:
    """Create a CodeNode for tests."""
    return CodeNode.create_file(
        file_path=file_path,
        language="python",
        ts_kind="module",
        start_byte=0,
        end_byte=100,
        start_line=1,
        end_line=10,
        content="# test content",
    )


@pytest.fixture
def tmp_graph_dir(tmp_path):
    """Create a temporary directory with default graph file."""
    graph_path = tmp_path / ".fs2" / "graph.pickle"
    create_test_graph_file(graph_path)
    return tmp_path


# =============================================================================
# T001: Tests for GraphService.get_graph()
# =============================================================================


@pytest.mark.unit
class TestGraphServiceGetGraph:
    """T001: Tests for GraphService.get_graph() method.

    Per spec AC2: Service returns GraphStore for named graph
    Per spec AC3: Default graph uses existing GraphConfig.graph_path
    Per spec AC5: Unknown graph raises UnknownGraphError
    Per DYK-03: Missing file raises GraphFileNotFoundError
    """

    def test_get_default_graph_returns_graph_store(self, tmp_path):
        """
        Purpose: get_graph("default") returns GraphStore for local project graph.
        Quality Contribution: Core functionality for default graph access.
        Acceptance Criteria: Returns GraphStore instance, graph is loaded.

        Task: T001
        Per: AC3 - Default graph uses existing GraphConfig.graph_path
        """
        from fs2.core.services.graph_service import GraphService

        # Setup: Create default graph file
        default_graph_path = tmp_path / ".fs2" / "graph.pickle"
        create_test_graph_file(default_graph_path)

        # Create config with default graph path
        config = FakeConfigurationService(
            GraphConfig(graph_path=str(default_graph_path)),
            OtherGraphsConfig(graphs=[]),
        )

        service = GraphService(config=config)
        store = service.get_graph("default")

        assert store is not None
        # Verify it's usable (has get_all_nodes method)
        assert hasattr(store, "get_all_nodes")

    def test_get_named_graph_returns_graph_store(self, tmp_path):
        """
        Purpose: get_graph("name") returns GraphStore for configured named graph.
        Quality Contribution: Core functionality for multi-graph access.
        Acceptance Criteria: Returns GraphStore for named graph from config.

        Task: T001
        Per: AC2 - Service returns GraphStore for named graph
        """
        from fs2.core.services.graph_service import GraphService

        # Setup: Create named graph file
        named_graph_path = tmp_path / "other-project" / ".fs2" / "graph.pickle"
        create_test_graph_file(named_graph_path)

        # Setup: Create default graph file
        default_graph_path = tmp_path / ".fs2" / "graph.pickle"
        create_test_graph_file(default_graph_path)

        # Create config with named graph
        other_graph = OtherGraph(name="other-lib", path=str(named_graph_path))
        config = FakeConfigurationService(
            GraphConfig(graph_path=str(default_graph_path)),
            OtherGraphsConfig(graphs=[other_graph]),
        )

        service = GraphService(config=config)
        store = service.get_graph("other-lib")

        assert store is not None
        assert hasattr(store, "get_all_nodes")

    def test_get_graph_unknown_name_raises_error(self, tmp_path):
        """
        Purpose: get_graph("nonexistent") raises UnknownGraphError.
        Quality Contribution: Clear error for unknown graph names.
        Acceptance Criteria: UnknownGraphError raised with helpful message.

        Task: T001
        Per: AC5 - Unknown graph raises UnknownGraphError
        Per: DYK-03 - Distinct error for unknown vs missing file
        """
        from fs2.core.services.graph_service import (
            GraphService,
            UnknownGraphError,
        )

        # Setup: Create default graph file
        default_graph_path = tmp_path / ".fs2" / "graph.pickle"
        create_test_graph_file(default_graph_path)

        config = FakeConfigurationService(
            GraphConfig(graph_path=str(default_graph_path)),
            OtherGraphsConfig(graphs=[]),
        )

        service = GraphService(config=config)

        with pytest.raises(UnknownGraphError) as exc_info:
            service.get_graph("nonexistent")

        # Error message should include unknown name
        assert "nonexistent" in str(exc_info.value)
        # Error message should list available graphs
        assert "default" in str(exc_info.value)

    def test_get_graph_missing_file_raises_error(self, tmp_path):
        """
        Purpose: get_graph() for configured graph with missing file raises GraphFileNotFoundError.
        Quality Contribution: Clear error distinguishing config vs file issues.
        Acceptance Criteria: GraphFileNotFoundError raised with path and guidance.

        Task: T001
        Per: DYK-03 - Distinct error for unknown vs missing file
        """
        from fs2.core.services.graph_service import (
            GraphFileNotFoundError,
            GraphService,
        )

        # Setup: Create default graph file but NOT the named graph file
        default_graph_path = tmp_path / ".fs2" / "graph.pickle"
        create_test_graph_file(default_graph_path)

        # Configure a graph that doesn't exist
        missing_path = tmp_path / "missing" / "graph.pickle"
        other_graph = OtherGraph(name="missing-lib", path=str(missing_path))
        config = FakeConfigurationService(
            GraphConfig(graph_path=str(default_graph_path)),
            OtherGraphsConfig(graphs=[other_graph]),
        )

        service = GraphService(config=config)

        with pytest.raises(GraphFileNotFoundError) as exc_info:
            service.get_graph("missing-lib")

        # Error message should include path
        assert str(missing_path) in str(exc_info.value) or "missing" in str(
            exc_info.value
        )
        # Error message should suggest running scan
        assert "scan" in str(exc_info.value).lower()

    def test_get_default_graph_missing_file_raises_error(self, tmp_path):
        """
        Purpose: get_graph("default") with missing file raises GraphFileNotFoundError.
        Quality Contribution: Consistent error handling for default graph.
        Acceptance Criteria: GraphFileNotFoundError raised (not generic error).

        Task: T001
        Per: DYK-03 - Distinct error for missing file
        """
        from fs2.core.services.graph_service import (
            GraphFileNotFoundError,
            GraphService,
        )

        # Configure default graph that doesn't exist
        missing_path = tmp_path / ".fs2" / "graph.pickle"
        config = FakeConfigurationService(
            GraphConfig(graph_path=str(missing_path)),
            OtherGraphsConfig(graphs=[]),
        )

        service = GraphService(config=config)

        with pytest.raises(GraphFileNotFoundError):
            service.get_graph("default")

    def test_get_graph_caches_store(self, tmp_path):
        """
        Purpose: Repeated calls to get_graph() return cached store.
        Quality Contribution: Performance optimization via caching.
        Acceptance Criteria: Same GraphStore instance returned on repeated calls.

        Task: T001
        Per: AC4 - Service caches loaded graphs
        """
        from fs2.core.services.graph_service import GraphService

        # Setup: Create default graph file
        default_graph_path = tmp_path / ".fs2" / "graph.pickle"
        create_test_graph_file(default_graph_path)

        config = FakeConfigurationService(
            GraphConfig(graph_path=str(default_graph_path)),
            OtherGraphsConfig(graphs=[]),
        )

        service = GraphService(config=config)

        store1 = service.get_graph("default")
        store2 = service.get_graph("default")

        # Should be the exact same instance (cached)
        assert store1 is store2

    def test_unknown_graph_error_lists_available_graphs(self, tmp_path):
        """
        Purpose: UnknownGraphError includes list of available graph names.
        Quality Contribution: Actionable error messages for users.
        Acceptance Criteria: Error message lists all configured graphs.

        Task: T001
        Per: AC5, DYK-03 - Helpful error messages
        """
        from fs2.core.services.graph_service import (
            GraphService,
            UnknownGraphError,
        )

        # Setup: Create graph files
        default_graph_path = tmp_path / ".fs2" / "graph.pickle"
        create_test_graph_file(default_graph_path)

        lib1_path = tmp_path / "lib1" / "graph.pickle"
        create_test_graph_file(lib1_path)

        lib2_path = tmp_path / "lib2" / "graph.pickle"
        create_test_graph_file(lib2_path)

        config = FakeConfigurationService(
            GraphConfig(graph_path=str(default_graph_path)),
            OtherGraphsConfig(
                graphs=[
                    OtherGraph(name="lib1", path=str(lib1_path)),
                    OtherGraph(name="lib2", path=str(lib2_path)),
                ]
            ),
        )

        service = GraphService(config=config)

        with pytest.raises(UnknownGraphError) as exc_info:
            service.get_graph("typo-lib")

        error_msg = str(exc_info.value)
        assert "default" in error_msg
        assert "lib1" in error_msg
        assert "lib2" in error_msg


# =============================================================================
# T002: Tests for staleness detection - in separate class
# =============================================================================


@pytest.mark.unit
class TestGraphServiceStaleness:
    """T002: Tests for staleness detection.

    Per AC4: Service detects stale graphs and reloads when file changes.
    Staleness is detected via mtime + size comparison.
    """

    def test_unchanged_file_returns_cached_store(self, tmp_path):
        """
        Purpose: File unchanged since load returns cached store.
        Quality Contribution: Performance - avoid unnecessary reloads.
        Acceptance Criteria: Same store returned, no reload occurs.

        Task: T002
        Per: AC4 - Cache hit when file unchanged
        """
        from fs2.core.services.graph_service import GraphService

        # Setup
        default_graph_path = tmp_path / ".fs2" / "graph.pickle"
        create_test_graph_file(default_graph_path)

        config = FakeConfigurationService(
            GraphConfig(graph_path=str(default_graph_path)),
            OtherGraphsConfig(graphs=[]),
        )

        service = GraphService(config=config)

        # First access - loads graph
        store1 = service.get_graph("default")

        # Second access - should use cache (file unchanged)
        store2 = service.get_graph("default")

        assert store1 is store2

    def test_modified_mtime_triggers_reload(self, tmp_path):
        """
        Purpose: Modified mtime triggers graph reload.
        Quality Contribution: Detect file changes and refresh data.
        Acceptance Criteria: Different store instance after file modification.

        Task: T002
        Per: AC4 - Reload when mtime changes
        """
        import os
        import time

        from fs2.core.services.graph_service import GraphService

        # Setup
        default_graph_path = tmp_path / ".fs2" / "graph.pickle"
        create_test_graph_file(default_graph_path)

        config = FakeConfigurationService(
            GraphConfig(graph_path=str(default_graph_path)),
            OtherGraphsConfig(graphs=[]),
        )

        service = GraphService(config=config)

        # First access
        store1 = service.get_graph("default")

        # Modify the file (touch to update mtime)
        time.sleep(0.01)  # Ensure different mtime
        create_test_graph_file(default_graph_path)
        # Touch file to ensure mtime updates
        os.utime(default_graph_path, None)

        # Second access - should reload due to mtime change
        store2 = service.get_graph("default")

        # Should be a different instance (reloaded)
        assert store1 is not store2

    def test_modified_size_triggers_reload(self, tmp_path):
        """
        Purpose: Modified file size triggers graph reload.
        Quality Contribution: Detect content changes via size.
        Acceptance Criteria: Different store instance after size change.

        Task: T002
        Per: AC4 - Reload when size changes
        """
        from fs2.core.services.graph_service import GraphService

        # Setup - create initial graph
        default_graph_path = tmp_path / ".fs2" / "graph.pickle"
        create_test_graph_file(default_graph_path)

        config = FakeConfigurationService(
            GraphConfig(graph_path=str(default_graph_path)),
            OtherGraphsConfig(graphs=[]),
        )

        service = GraphService(config=config)

        # First access
        store1 = service.get_graph("default")
        original_size = default_graph_path.stat().st_size

        # Create larger graph (different size)
        nodes = [make_code_node(f"file{i}.py") for i in range(10)]
        create_graph_with_nodes(default_graph_path, nodes)

        # Verify size actually changed
        new_size = default_graph_path.stat().st_size
        assert new_size != original_size, "Test setup error: file size didn't change"

        # Second access - should reload due to size change
        store2 = service.get_graph("default")

        # Should be a different instance (reloaded)
        assert store1 is not store2


# =============================================================================
# T003: Tests for path resolution - in separate class
# =============================================================================


@pytest.mark.unit
class TestGraphServicePathResolution:
    """T003: Tests for path resolution.

    Per Critical Finding 09: Support absolute, tilde, and relative paths.
    Per DYK-02: Relative paths resolve from config source directory.
    """

    def test_absolute_path_used_directly(self, tmp_path):
        """
        Purpose: Absolute paths are used as-is.
        Quality Contribution: Validates absolute path handling.
        Acceptance Criteria: Graph loaded from absolute path.

        Task: T003
        Per: Critical Finding 09 - Absolute path support
        """
        from fs2.core.services.graph_service import GraphService

        # Setup - use absolute path
        abs_path = tmp_path / "absolute" / "graph.pickle"
        create_test_graph_file(abs_path)

        # Default graph for fallback
        default_path = tmp_path / ".fs2" / "graph.pickle"
        create_test_graph_file(default_path)

        other_graph = OtherGraph(name="abs-lib", path=str(abs_path))
        config = FakeConfigurationService(
            GraphConfig(graph_path=str(default_path)),
            OtherGraphsConfig(graphs=[other_graph]),
        )

        service = GraphService(config=config)
        store = service.get_graph("abs-lib")

        assert store is not None

    def test_tilde_path_expanded(self, tmp_path, monkeypatch):
        """
        Purpose: Tilde (~) paths are expanded to home directory.
        Quality Contribution: User convenience for home-relative paths.
        Acceptance Criteria: Graph loaded from expanded tilde path.

        Task: T003
        Per: Critical Finding 09 - Tilde expansion
        """
        from fs2.core.services.graph_service import GraphService

        # Setup - create graph in fake home directory
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()
        graph_in_home = fake_home / "projects" / "lib" / "graph.pickle"
        create_test_graph_file(graph_in_home)

        # Monkeypatch home directory
        monkeypatch.setenv("HOME", str(fake_home))

        # Default graph
        default_path = tmp_path / ".fs2" / "graph.pickle"
        create_test_graph_file(default_path)

        other_graph = OtherGraph(name="home-lib", path="~/projects/lib/graph.pickle")
        config = FakeConfigurationService(
            GraphConfig(graph_path=str(default_path)),
            OtherGraphsConfig(graphs=[other_graph]),
        )

        service = GraphService(config=config)
        store = service.get_graph("home-lib")

        assert store is not None

    def test_relative_path_resolved_from_config_source(self, tmp_path):
        """
        Purpose: Relative paths resolve from config file's source directory.
        Quality Contribution: Core DYK-02 functionality.
        Acceptance Criteria: Graph loaded relative to config source, not CWD.

        Task: T003
        Per: DYK-02 - Path resolution from config source directory
        """
        from fs2.core.services.graph_service import GraphService

        # Setup directory structure:
        # tmp_path/
        #   user_config/           <- user config source dir
        #     sibling-project/
        #       .fs2/
        #         graph.pickle     <- relative path "../sibling-project/.fs2/graph.pickle"
        #   .fs2/
        #     graph.pickle         <- default graph

        user_config_dir = tmp_path / "user_config"
        user_config_dir.mkdir()

        sibling_project_graph = (
            user_config_dir / "sibling-project" / ".fs2" / "graph.pickle"
        )
        create_test_graph_file(sibling_project_graph)

        default_path = tmp_path / ".fs2" / "graph.pickle"
        create_test_graph_file(default_path)

        # Create OtherGraph with relative path and _source_dir set
        other_graph = OtherGraph(
            name="sibling", path="./sibling-project/.fs2/graph.pickle"
        )
        # Set _source_dir as would happen during config merge
        other_graph._source_dir = user_config_dir

        config = FakeConfigurationService(
            GraphConfig(graph_path=str(default_path)),
            OtherGraphsConfig(graphs=[other_graph]),
        )

        service = GraphService(config=config)
        store = service.get_graph("sibling")

        assert store is not None


# =============================================================================
# T004: Tests for list_graphs() - in separate class
# =============================================================================


@pytest.mark.unit
class TestGraphServiceListGraphs:
    """T004: Tests for list_graphs() method.

    Per AC6: Service lists available graphs with metadata.
    Per Critical Finding 08: Include availability status.
    """

    def test_list_graphs_includes_default(self, tmp_path):
        """
        Purpose: list_graphs() always includes "default" graph.
        Quality Contribution: Default graph always available.
        Acceptance Criteria: "default" in returned list.

        Task: T004
        Per: AC6 - List includes default graph
        """
        from fs2.core.services.graph_service import GraphService

        default_path = tmp_path / ".fs2" / "graph.pickle"
        create_test_graph_file(default_path)

        config = FakeConfigurationService(
            GraphConfig(graph_path=str(default_path)),
            OtherGraphsConfig(graphs=[]),
        )

        service = GraphService(config=config)
        graphs = service.list_graphs()

        graph_names = [g.name for g in graphs]
        assert "default" in graph_names

    def test_list_graphs_includes_configured_graphs(self, tmp_path):
        """
        Purpose: list_graphs() includes all configured graphs.
        Quality Contribution: Visibility into available graphs.
        Acceptance Criteria: All configured graphs in returned list.

        Task: T004
        Per: AC6 - List includes configured graphs
        """
        from fs2.core.services.graph_service import GraphService

        # Setup graph files
        default_path = tmp_path / ".fs2" / "graph.pickle"
        create_test_graph_file(default_path)

        lib1_path = tmp_path / "lib1" / "graph.pickle"
        create_test_graph_file(lib1_path)

        lib2_path = tmp_path / "lib2" / "graph.pickle"
        create_test_graph_file(lib2_path)

        config = FakeConfigurationService(
            GraphConfig(graph_path=str(default_path)),
            OtherGraphsConfig(
                graphs=[
                    OtherGraph(name="lib1", path=str(lib1_path)),
                    OtherGraph(name="lib2", path=str(lib2_path)),
                ]
            ),
        )

        service = GraphService(config=config)
        graphs = service.list_graphs()

        graph_names = [g.name for g in graphs]
        assert "default" in graph_names
        assert "lib1" in graph_names
        assert "lib2" in graph_names

    def test_list_graphs_shows_availability(self, tmp_path):
        """
        Purpose: list_graphs() shows availability status for each graph.
        Quality Contribution: User knows which graphs can be accessed.
        Acceptance Criteria: Each GraphInfo has available field.

        Task: T004
        Per: Critical Finding 08 - Availability status
        """
        from fs2.core.services.graph_service import GraphService

        # Setup: default exists, lib1 exists, lib2 missing
        default_path = tmp_path / ".fs2" / "graph.pickle"
        create_test_graph_file(default_path)

        lib1_path = tmp_path / "lib1" / "graph.pickle"
        create_test_graph_file(lib1_path)

        # lib2 path doesn't exist
        lib2_path = tmp_path / "lib2" / "graph.pickle"

        config = FakeConfigurationService(
            GraphConfig(graph_path=str(default_path)),
            OtherGraphsConfig(
                graphs=[
                    OtherGraph(name="lib1", path=str(lib1_path)),
                    OtherGraph(name="lib2", path=str(lib2_path)),
                ]
            ),
        )

        service = GraphService(config=config)
        graphs = service.list_graphs()

        # Find each graph
        default_info = next(g for g in graphs if g.name == "default")
        lib1_info = next(g for g in graphs if g.name == "lib1")
        lib2_info = next(g for g in graphs if g.name == "lib2")

        assert default_info.available is True
        assert lib1_info.available is True
        assert lib2_info.available is False


# =============================================================================
# T005: Tests for concurrent access - in separate class
# =============================================================================


@pytest.mark.unit
class TestGraphServiceConcurrency:
    """T005: Tests for concurrent access.

    Per Critical Finding 03: Thread-safe concurrent access.
    Per DYK-01: Double-checked locking to prevent double-load.
    """

    def test_concurrent_get_graph_no_race_condition(self, tmp_path):
        """
        Purpose: Concurrent calls to get_graph() don't cause race conditions.
        Quality Contribution: Thread safety validation.
        Acceptance Criteria: All threads get valid stores, no exceptions.

        Task: T005
        Per: Critical Finding 03 - Thread safety
        """
        import threading

        from fs2.core.services.graph_service import GraphService

        default_path = tmp_path / ".fs2" / "graph.pickle"
        create_test_graph_file(default_path)

        config = FakeConfigurationService(
            GraphConfig(graph_path=str(default_path)),
            OtherGraphsConfig(graphs=[]),
        )

        service = GraphService(config=config)

        results = []
        errors = []

        def worker():
            try:
                store = service.get_graph("default")
                results.append(store)
            except Exception as e:
                errors.append(e)

        # Launch multiple threads
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should succeed
        assert len(errors) == 0
        assert len(results) == 10

        # All should get the same cached instance
        assert all(r is results[0] for r in results)

    def test_concurrent_get_graph_single_load(self, tmp_path):
        """
        Purpose: Concurrent calls result in single graph load (not multiple).
        Quality Contribution: Validates double-checked locking pattern.
        Acceptance Criteria: Graph loaded exactly once despite concurrent calls.

        Task: T005
        Per: DYK-01 - Double-checked locking prevents double-load
        """
        import threading

        from fs2.core.services.graph_service import GraphService

        default_path = tmp_path / ".fs2" / "graph.pickle"
        create_test_graph_file(default_path)

        config = FakeConfigurationService(
            GraphConfig(graph_path=str(default_path)),
            OtherGraphsConfig(graphs=[]),
        )

        service = GraphService(config=config)

        # Use barrier to ensure all threads start at same time
        barrier = threading.Barrier(10)
        results = []

        def worker():
            barrier.wait()  # All threads start together
            store = service.get_graph("default")
            results.append(store)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should get the exact same instance
        assert len(results) == 10
        assert all(r is results[0] for r in results)


# =============================================================================
# T011: Integration test with real config loading
# =============================================================================


@pytest.mark.unit
class TestGraphServiceIntegration:
    """T011: Integration test with real FS2ConfigurationService.

    Per DYK-04: Validates _source_dir flows through correctly from
    YAML config → FS2ConfigurationService → GraphService.
    """

    def test_yaml_config_to_graph_service_path_resolution(
        self, tmp_path, monkeypatch, clean_config_env
    ):
        """
        Purpose: End-to-end test of path resolution through real config loading.
        Quality Contribution: Validates full integration stack.
        Acceptance Criteria: Graph loaded via relative path resolved from config source.

        Task: T011
        Per: DYK-04 - Integration layer validation
        """
        from fs2.config.service import FS2ConfigurationService
        from fs2.core.services.graph_service import GraphService

        # Directory structure:
        # tmp_path/
        #   user_config/                    <- user config directory
        #     config.yaml                   <- user config file
        #     sibling-project/
        #       .fs2/
        #         graph.pickle              <- graph to load via relative path
        #   .fs2/
        #     config.yaml                   <- project config file
        #     graph.pickle                  <- default graph

        # Setup user config directory with a sibling project
        user_config_dir = tmp_path / "user_config"
        user_config_dir.mkdir()

        # Create sibling project graph (relative to user config)
        sibling_graph_path = (
            user_config_dir / "sibling-project" / ".fs2" / "graph.pickle"
        )
        create_test_graph_file(sibling_graph_path)

        # Create user config with relative path to sibling
        user_config_file = user_config_dir / "config.yaml"
        user_config_file.write_text(
            """scan:
  scan_paths:
    - "."
other_graphs:
  graphs:
    - name: "sibling"
      path: "./sibling-project/.fs2/graph.pickle"
      description: "Sibling project"
"""
        )

        # Setup project directory
        project_dir = tmp_path
        project_config_dir = project_dir / ".fs2"
        project_config_dir.mkdir()

        # Create default graph
        default_graph_path = project_config_dir / "graph.pickle"
        create_test_graph_file(default_graph_path)

        # Create minimal project config
        project_config_file = project_config_dir / "config.yaml"
        project_config_file.write_text(
            """scan:
  scan_paths:
    - "."
graph:
  graph_path: ".fs2/graph.pickle"
"""
        )

        # Set CWD and user config dir
        monkeypatch.chdir(project_dir)
        monkeypatch.setattr(
            "fs2.config.service.get_user_config_dir", lambda: user_config_dir
        )

        # Load config using real FS2ConfigurationService
        config_service = FS2ConfigurationService()

        # Create GraphService
        graph_service = GraphService(config=config_service)

        # Should successfully load the sibling graph via relative path
        # The relative path should resolve from user_config_dir, not CWD
        store = graph_service.get_graph("sibling")

        assert store is not None
        # Verify the graph is usable
        assert hasattr(store, "get_all_nodes")

    def test_yaml_config_list_graphs_shows_both_sources(
        self, tmp_path, monkeypatch, clean_config_env
    ):
        """
        Purpose: list_graphs() shows graphs from both user and project config.
        Quality Contribution: Validates config merge and list functionality.
        Acceptance Criteria: Both user and project graphs listed with correct availability.

        Task: T011
        Per: DYK-04 - Integration layer validation
        """
        from fs2.config.service import FS2ConfigurationService
        from fs2.core.services.graph_service import GraphService

        # Setup user config with one graph
        user_config_dir = tmp_path / "user_config"
        user_config_dir.mkdir()

        user_graph_path = user_config_dir / "user-lib" / "graph.pickle"
        create_test_graph_file(user_graph_path)

        user_config_file = user_config_dir / "config.yaml"
        user_config_file.write_text(
            """scan:
  scan_paths:
    - "."
other_graphs:
  graphs:
    - name: "user-lib"
      path: "./user-lib/graph.pickle"
"""
        )

        # Setup project config with another graph
        project_dir = tmp_path
        project_config_dir = project_dir / ".fs2"
        project_config_dir.mkdir()

        default_graph_path = project_config_dir / "graph.pickle"
        create_test_graph_file(default_graph_path)

        project_lib_path = project_dir / "project-lib" / "graph.pickle"
        create_test_graph_file(project_lib_path)

        project_config_file = project_config_dir / "config.yaml"
        project_config_file.write_text(
            f"""scan:
  scan_paths:
    - "."
graph:
  graph_path: ".fs2/graph.pickle"
other_graphs:
  graphs:
    - name: "project-lib"
      path: "{project_lib_path}"
"""
        )

        monkeypatch.chdir(project_dir)
        monkeypatch.setattr(
            "fs2.config.service.get_user_config_dir", lambda: user_config_dir
        )

        config_service = FS2ConfigurationService()
        graph_service = GraphService(config=config_service)

        graphs = graph_service.list_graphs()
        graph_names = [g.name for g in graphs]

        # Should have default + user-lib + project-lib
        assert "default" in graph_names
        assert "user-lib" in graph_names
        assert "project-lib" in graph_names

        # All should be available since we created the files
        for g in graphs:
            assert g.available is True, f"Graph {g.name} should be available"
