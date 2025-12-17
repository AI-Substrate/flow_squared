"""Tests for TreeService.

T008: Unit tests for TreeService.
Purpose: Verify TreeService builds trees correctly with filtering and depth limits.

Uses FakeGraphStore (no mocks per constitution P4).
"""

import pytest

from fs2.config.objects import GraphConfig, ScanConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters.exceptions import GraphNotFoundError, GraphStoreError
from fs2.core.models.code_node import CodeNode
from fs2.core.models.tree_node import TreeNode
from fs2.core.repos.graph_store_fake import FakeGraphStore
from fs2.core.services.tree_service import TreeService


def make_file_node(file_path: str) -> CodeNode:
    """Create a file CodeNode for tests."""
    return CodeNode.create_file(
        file_path=file_path,
        language="python",
        ts_kind="module",
        start_byte=0,
        end_byte=100,
        start_line=1,
        end_line=10,
        content="# file content",
    )


def make_class_node(
    file_path: str, name: str, parent_node_id: str | None = None
) -> CodeNode:
    """Create a class CodeNode for tests."""
    return CodeNode.create_type(
        file_path=file_path,
        language="python",
        ts_kind="class_definition",
        name=name,
        qualified_name=name,
        start_line=1,
        end_line=10,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=100,
        content=f"class {name}: pass",
        signature=f"class {name}:",
        parent_node_id=parent_node_id,
    )


def make_method_node(
    file_path: str,
    class_name: str,
    method_name: str,
    parent_node_id: str | None = None,
    start_line: int = 2,
) -> CodeNode:
    """Create a method CodeNode for tests."""
    qualified_name = f"{class_name}.{method_name}"
    return CodeNode.create_callable(
        file_path=file_path,
        language="python",
        ts_kind="function_definition",
        name=method_name,
        qualified_name=qualified_name,
        start_line=start_line,
        end_line=start_line + 2,
        start_column=4,
        end_column=0,
        start_byte=0,
        end_byte=50,
        content=f"def {method_name}(self): pass",
        signature=f"def {method_name}(self):",
        parent_node_id=parent_node_id,
    )


@pytest.fixture
def graph_setup(tmp_path):
    """Create config and graph store for tests."""
    graph_path = tmp_path / "graph.pickle"
    graph_path.touch()  # FakeGraphStore doesn't read, just needs to exist

    config = FakeConfigurationService(
        ScanConfig(),
        GraphConfig(graph_path=str(graph_path)),
    )
    store = FakeGraphStore(config)

    return config, store, graph_path


@pytest.mark.unit
class TestTreeServiceInit:
    """T008: Tests for TreeService initialization."""

    def test_given_config_and_store_when_created_then_service_exists(
        self, graph_setup
    ):
        """
        Purpose: Verifies service can be created with DI pattern.
        Quality Contribution: Ensures proper dependency injection.

        Task: T008
        """
        config, store, _ = graph_setup

        service = TreeService(config=config, graph_store=store)

        assert service is not None
        assert service._loaded is False


@pytest.mark.unit
class TestTreeServiceLazyLoading:
    """T008: Tests for lazy loading behavior."""

    def test_given_new_service_when_build_tree_called_then_loads_graph(
        self, graph_setup
    ):
        """
        Purpose: Verifies lazy loading triggers on first access.
        Quality Contribution: Ensures graph loaded before access.

        Task: T008
        """
        config, store, graph_path = graph_setup
        service = TreeService(config=config, graph_store=store)

        service.build_tree()

        load_calls = [c for c in store.call_history if c["method"] == "load"]
        assert len(load_calls) == 1


@pytest.mark.unit
class TestTreeServiceFiltering:
    """T008: Tests for pattern filtering."""

    def test_given_dot_pattern_when_build_tree_then_returns_all_nodes(
        self, graph_setup
    ):
        """
        Purpose: Verifies "." pattern returns all nodes.
        Quality Contribution: Default behavior works.

        Task: T008
        """
        config, store, _ = graph_setup
        file1 = make_file_node("src/main.py")
        file2 = make_file_node("src/utils.py")
        store.set_nodes([file1, file2])

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree(pattern=".")

        assert len(result) == 2

    def test_given_exact_match_when_build_tree_then_returns_single_node(
        self, graph_setup
    ):
        """
        Purpose: Verifies exact node_id match.
        Quality Contribution: Precise filtering works.

        Task: T008
        """
        config, store, _ = graph_setup
        file1 = make_file_node("src/main.py")
        file2 = make_file_node("src/utils.py")
        store.set_nodes([file1, file2])

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree(pattern="file:src/main.py")

        assert len(result) == 1
        assert result[0].node.node_id == "file:src/main.py"

    def test_given_substring_pattern_when_build_tree_then_filters_nodes(
        self, graph_setup
    ):
        """
        Purpose: Verifies substring matching.
        Quality Contribution: Flexible pattern matching.

        Task: T008
        """
        config, store, _ = graph_setup
        file1 = make_file_node("src/calculator.py")
        file2 = make_file_node("src/utils.py")
        store.set_nodes([file1, file2])

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree(pattern="calculator")

        assert len(result) == 1
        assert "calculator" in result[0].node.node_id

    def test_given_glob_pattern_when_build_tree_then_filters_nodes(
        self, graph_setup
    ):
        """
        Purpose: Verifies glob pattern matching.
        Quality Contribution: Advanced pattern support.

        Task: T008
        """
        config, store, _ = graph_setup
        file1 = make_file_node("src/calculator.py")
        file2 = make_file_node("tests/test_calc.py")
        file3 = make_file_node("src/utils.py")
        store.set_nodes([file1, file2, file3])

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree(pattern="*calc*")

        assert len(result) == 2

    def test_given_no_matches_when_build_tree_then_returns_empty(
        self, graph_setup
    ):
        """
        Purpose: Verifies empty result for no matches.
        Quality Contribution: Correct handling of no matches.

        Task: T008
        """
        config, store, _ = graph_setup
        file1 = make_file_node("src/main.py")
        store.set_nodes([file1])

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree(pattern="nonexistent")

        assert result == []


@pytest.mark.unit
class TestTreeServiceRootBucket:
    """T008: Tests for root bucket algorithm."""

    def test_given_parent_and_child_matched_when_build_tree_then_only_parent_is_root(
        self, graph_setup
    ):
        """
        Purpose: Verifies child is removed when ancestor matches.
        Quality Contribution: Correct tree structure.

        Task: T008
        """
        config, store, _ = graph_setup
        file_node = make_file_node("src/calc.py")
        class_node = make_class_node(
            "src/calc.py", "Calculator", parent_node_id="file:src/calc.py"
        )
        store.set_nodes([file_node, class_node])
        store.add_edge("file:src/calc.py", "type:src/calc.py:Calculator")

        service = TreeService(config=config, graph_store=store)
        # Pattern matches both file and class
        result = service.build_tree(pattern="calc")

        # Only file should be root (class is child of file)
        assert len(result) == 1
        assert result[0].node.category == "file"


@pytest.mark.unit
class TestTreeServiceDepth:
    """T008: Tests for depth limiting."""

    def test_given_max_depth_when_build_tree_then_limits_expansion(
        self, graph_setup
    ):
        """
        Purpose: Verifies depth limiting works.
        Quality Contribution: Performance control.

        Task: T008

        Depth semantics:
        - max_depth=0: unlimited
        - max_depth=1: root at depth 0 gets children, children at depth 1 get no children
        - max_depth=2: root→children→grandchildren, no further
        """
        config, store, _ = graph_setup
        file_node = make_file_node("src/calc.py")
        class_node = make_class_node(
            "src/calc.py", "Calculator", parent_node_id="file:src/calc.py"
        )
        method_node = make_method_node(
            "src/calc.py",
            "Calculator",
            "add",
            parent_node_id="type:src/calc.py:Calculator",
        )
        store.set_nodes([file_node, class_node, method_node])
        store.add_edge("file:src/calc.py", "type:src/calc.py:Calculator")
        store.add_edge("type:src/calc.py:Calculator", "callable:src/calc.py:Calculator.add")

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree(pattern="file:src/calc.py", max_depth=1)

        # max_depth=1: root (file) has children (class), but class has no children (method hidden)
        assert len(result) == 1
        assert len(result[0].children) == 1  # Calculator class
        assert result[0].children[0].children == ()  # No method (depth limited)

    def test_given_zero_depth_when_build_tree_then_unlimited(
        self, graph_setup
    ):
        """
        Purpose: Verifies max_depth=0 is unlimited.
        Quality Contribution: Default behavior correct.

        Task: T008
        """
        config, store, _ = graph_setup
        file_node = make_file_node("src/calc.py")
        class_node = make_class_node(
            "src/calc.py", "Calculator", parent_node_id="file:src/calc.py"
        )
        method_node = make_method_node(
            "src/calc.py",
            "Calculator",
            "add",
            parent_node_id="type:src/calc.py:Calculator",
        )
        store.set_nodes([file_node, class_node, method_node])
        store.add_edge("file:src/calc.py", "type:src/calc.py:Calculator")
        store.add_edge("type:src/calc.py:Calculator", "callable:src/calc.py:Calculator.add")

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree(pattern="file:src/calc.py", max_depth=0)

        # Should have children (class) and grandchildren (method)
        assert len(result) == 1
        assert len(result[0].children) == 1  # Calculator class
        assert len(result[0].children[0].children) == 1  # add method


@pytest.mark.unit
class TestTreeServiceTreeNode:
    """T008: Tests for TreeNode structure."""

    def test_given_nodes_when_build_tree_then_returns_tree_nodes(
        self, graph_setup
    ):
        """
        Purpose: Verifies return type is TreeNode.
        Quality Contribution: Correct return type.

        Task: T008
        """
        config, store, _ = graph_setup
        file_node = make_file_node("src/main.py")
        store.set_nodes([file_node])

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree()

        assert len(result) == 1
        assert isinstance(result[0], TreeNode)
        assert result[0].node == file_node
        assert isinstance(result[0].children, tuple)


@pytest.mark.unit
class TestTreeServiceErrors:
    """T008: Tests for error handling."""

    def test_given_missing_graph_when_build_tree_then_raises_not_found(
        self, tmp_path
    ):
        """
        Purpose: Verifies GraphNotFoundError raised for missing graph.
        Quality Contribution: Clear error for common issue.

        Task: T008
        """
        graph_path = tmp_path / "nonexistent.pickle"  # Does not exist
        config = FakeConfigurationService(
            ScanConfig(),
            GraphConfig(graph_path=str(graph_path)),
        )
        store = FakeGraphStore(config)
        service = TreeService(config=config, graph_store=store)

        with pytest.raises(GraphNotFoundError):
            service.build_tree()

    def test_given_corrupted_graph_when_build_tree_then_raises_store_error(
        self, graph_setup
    ):
        """
        Purpose: Verifies GraphStoreError raised for corrupted graph.
        Quality Contribution: Correct error propagation.

        Task: T008
        """
        config, store, _ = graph_setup
        store.simulate_error_for.add("load")

        service = TreeService(config=config, graph_store=store)

        with pytest.raises(GraphStoreError):
            service.build_tree()
