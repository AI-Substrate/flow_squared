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


def make_folder_node(folder_path: str) -> CodeNode:
    """Create a synthetic folder CodeNode for tests.

    Per DD1, DD5: Folders use category="folder", start_line=0, end_line=0,
    and node_id is the path with trailing slash.
    """
    # Ensure trailing slash for consistency
    path = folder_path if folder_path.endswith("/") else folder_path + "/"
    # Extract folder name from path (last component before trailing slash)
    name = (
        path.rstrip("/").split("/")[-1] if "/" in path.rstrip("/") else path.rstrip("/")
    )

    return CodeNode(
        node_id=path,
        category="folder",
        ts_kind="folder",
        name=name,
        qualified_name=name,
        start_line=0,
        end_line=0,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=0,
        content="",
        content_hash="",
        signature=None,
        language="",
        is_named=True,
        field_name=None,
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

    def test_given_config_and_store_when_created_then_service_exists(self, graph_setup):
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

    def test_given_glob_pattern_when_build_tree_then_filters_nodes(self, graph_setup):
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

    def test_given_no_matches_when_build_tree_then_returns_empty(self, graph_setup):
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

    def test_given_max_depth_when_build_tree_then_limits_expansion(self, graph_setup):
        """
        Purpose: Verifies depth limiting works.
        Quality Contribution: Performance control.

        Task: T008

        Depth semantics (count of levels shown):
        - max_depth=0: unlimited (show all levels)
        - max_depth=1: root only (1 level)
        - max_depth=2: root + children (2 levels)
        - max_depth=3: root + children + grandchildren (3 levels)
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
        store.add_edge(
            "type:src/calc.py:Calculator", "callable:src/calc.py:Calculator.add"
        )

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree(pattern="file:src/calc.py", max_depth=2)

        # max_depth=2: root (file) + children (class), but grandchildren (method) hidden
        assert len(result) == 1
        assert len(result[0].children) == 1  # Calculator class visible
        assert result[0].children[0].children == ()  # Method hidden (depth limited)
        assert result[0].children[0].hidden_children_count == 1  # Method count shown

    def test_given_zero_depth_when_build_tree_then_unlimited(self, graph_setup):
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
        store.add_edge(
            "type:src/calc.py:Calculator", "callable:src/calc.py:Calculator.add"
        )

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree(pattern="file:src/calc.py", max_depth=0)

        # Should have children (class) and grandchildren (method)
        assert len(result) == 1
        assert len(result[0].children) == 1  # Calculator class
        assert len(result[0].children[0].children) == 1  # add method

    def test_given_depth_one_when_build_tree_then_root_only(self, graph_setup):
        """
        Purpose: Verifies max_depth=1 shows root only (no children expanded).
        Quality Contribution: Enables agent overview without context explosion.

        Task: T008

        This is the key use case: agents need to see just file names first,
        then drill down with filters. depth=1 must mean "root only".
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
        store.add_edge(
            "type:src/calc.py:Calculator", "callable:src/calc.py:Calculator.add"
        )

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree(pattern="file:src/calc.py", max_depth=1)

        # max_depth=1: root only, children hidden with count
        assert len(result) == 1
        assert result[0].children == ()  # No children expanded
        assert result[0].hidden_children_count == 1  # Calculator class is hidden


@pytest.mark.unit
class TestTreeServiceTreeNode:
    """T008: Tests for TreeNode structure."""

    def test_given_nodes_when_build_tree_then_returns_tree_nodes(self, graph_setup):
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

    def test_given_missing_graph_when_build_tree_then_raises_not_found(self, tmp_path):
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


@pytest.mark.unit
class TestInputModeDetection:
    """T002: Tests for input mode detection (folder/node_id/pattern).

    Per P9: Business logic for input mode detection is in TreeService.
    Detection order: `:` (node_id) → `/` (folder) → otherwise (pattern).
    """

    def test_given_folder_pattern_with_trailing_slash_when_detect_mode_then_returns_folder(
        self,
    ):
        """
        Purpose: Verifies folder patterns (containing `/`) are detected.
        Quality Contribution: Core folder navigation mode detection.

        Task: T002
        """
        from fs2.core.services.tree_service import TreeService

        # Trailing slash indicates folder mode
        assert TreeService._detect_input_mode("src/") == "folder"
        assert TreeService._detect_input_mode("src/fs2/") == "folder"
        assert TreeService._detect_input_mode("src/fs2/cli/") == "folder"
        assert TreeService._detect_input_mode("tests/unit/") == "folder"

    def test_given_folder_pattern_without_trailing_slash_when_detect_mode_then_returns_folder(
        self,
    ):
        """
        Purpose: Verifies folder patterns with internal `/` but no trailing slash are folder mode.
        Quality Contribution: Handle `src/fs2` as folder mode (contains `/`).

        Task: T002
        """
        from fs2.core.services.tree_service import TreeService

        # Internal slash but no trailing - still folder mode per spec
        assert TreeService._detect_input_mode("src/fs2") == "folder"
        assert TreeService._detect_input_mode("tests/unit") == "folder"

    def test_given_node_id_with_colon_when_detect_mode_then_returns_node_id(self):
        """
        Purpose: Verifies node_id patterns (containing `:`) are detected.
        Quality Contribution: Enables drill-down via node_id.

        Task: T002

        CRITICAL: Detection order is `:` first, then `/`.
        This ensures `file:src/main.py` is detected as node_id, not folder.
        """
        from fs2.core.services.tree_service import TreeService

        # Node IDs have colon prefix
        assert TreeService._detect_input_mode("file:src/main.py") == "node_id"
        assert (
            TreeService._detect_input_mode("type:src/calc.py:Calculator") == "node_id"
        )
        assert (
            TreeService._detect_input_mode("callable:src/calc.py:Calculator.add")
            == "node_id"
        )

    def test_given_node_id_with_both_colon_and_slash_when_detect_mode_then_returns_node_id(
        self,
    ):
        """
        Purpose: Verifies colon is checked BEFORE slash (critical for node_ids).
        Quality Contribution: Prevents misclassification of node_ids containing `/`.

        Task: T002

        This is the key test for the detection order bug identified in didyouknow session.
        """
        from fs2.core.services.tree_service import TreeService

        # These contain BOTH `:` and `/` - must be node_id, not folder
        assert TreeService._detect_input_mode("file:src/fs2/main.py") == "node_id"
        assert (
            TreeService._detect_input_mode("callable:src/fs2/cli/tree.py:_display_tree")
            == "node_id"
        )

    def test_given_simple_pattern_when_detect_mode_then_returns_pattern(self):
        """
        Purpose: Verifies patterns without `:` or `/` return pattern mode.
        Quality Contribution: Maintains existing pattern matching behavior.

        Task: T002
        """
        from fs2.core.services.tree_service import TreeService

        # No `:` or `/` - pattern mode
        assert TreeService._detect_input_mode("Calculator") == "pattern"
        assert TreeService._detect_input_mode("test_") == "pattern"
        assert TreeService._detect_input_mode("*calc*") == "pattern"
        assert TreeService._detect_input_mode(".") == "pattern"
        assert TreeService._detect_input_mode("README") == "pattern"

    def test_given_dot_pattern_when_detect_mode_then_returns_pattern(self):
        """
        Purpose: Verifies the special `.` (all nodes) pattern returns pattern mode.
        Quality Contribution: Ensures backward compatibility with existing usage.

        Task: T002
        """
        from fs2.core.services.tree_service import TreeService

        assert TreeService._detect_input_mode(".") == "pattern"

    def test_given_glob_pattern_when_detect_mode_then_returns_pattern(self):
        """
        Purpose: Verifies glob patterns without `/` return pattern mode.
        Quality Contribution: Glob patterns work as before.

        Task: T002
        """
        from fs2.core.services.tree_service import TreeService

        # Globs without `/` are pattern mode
        assert TreeService._detect_input_mode("*.py") == "pattern"
        assert TreeService._detect_input_mode("test_*") == "pattern"
        assert TreeService._detect_input_mode("*Service*") == "pattern"


@pytest.mark.unit
class TestFolderHierarchyComputation:
    """T004/T005: Tests for folder hierarchy computation from file paths.

    Per P9: Business logic for folder hierarchy is in TreeService.
    Folders are virtual (computed from file paths), not persisted in graph.

    Per DD1, DD5: Folders use synthetic CodeNode with:
    - category="folder"
    - start_line=0, end_line=0
    - node_id is path with trailing slash (e.g., "src/fs2/cli/")
    - name is the folder name (e.g., "cli")

    Per DD2: Tests are strengthened BEFORE implementation to follow TDD.
    Per DD4: Folders appear first, then files (both sorted alphabetically).
    """

    def test_given_files_in_one_folder_when_depth_one_then_returns_folder_node(
        self, graph_setup
    ):
        """
        Purpose: Verifies single folder is returned as synthetic folder node.
        Quality Contribution: Basic folder grouping works with correct node structure.

        Task: T005 (strengthened from T004)
        """
        config, store, _ = graph_setup
        file1 = make_file_node("src/main.py")
        file2 = make_file_node("src/utils.py")
        store.set_nodes([file1, file2])

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree(pattern=".", max_depth=1)

        # Per DD1: Should have synthetic folder node
        assert len(result) == 1, (
            f"Expected 1 folder, got {len(result)}: {[tn.node.node_id for tn in result]}"
        )

        folder = result[0]
        # Per DD1: category="folder"
        assert folder.node.category == "folder", (
            f"Expected folder category, got {folder.node.category}"
        )
        # Per DD5: node_id is path with trailing slash
        assert folder.node.node_id == "src/", (
            f"Expected node_id 'src/', got {folder.node.node_id}"
        )
        # name is just the folder name
        assert folder.node.name == "src", f"Expected name 'src', got {folder.node.name}"
        # Per DD1: synthetic nodes have start_line=0, end_line=0
        assert folder.node.start_line == 0
        assert folder.node.end_line == 0
        # At depth=1, folder children are hidden, count shows items inside
        assert folder.hidden_children_count == 2, (
            f"Expected 2 hidden files, got {folder.hidden_children_count}"
        )

    def test_given_files_in_multiple_top_level_folders_when_depth_one_then_returns_all_folders(
        self, graph_setup
    ):
        """
        Purpose: Verifies multiple top-level folders are detected.
        Quality Contribution: Core folder enumeration works.

        Task: T005 (strengthened from T004)
        """
        config, store, _ = graph_setup
        file1 = make_file_node("src/main.py")
        file2 = make_file_node("tests/test_main.py")
        file3 = make_file_node("docs/readme.md")
        store.set_nodes([file1, file2, file3])

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree(pattern=".", max_depth=1)

        # Should have 3 folder nodes
        assert len(result) == 3, (
            f"Expected 3 folders, got {len(result)}: {[tn.node.node_id for tn in result]}"
        )

        # All should be folders
        for folder in result:
            assert folder.node.category == "folder", (
                f"Expected folder, got {folder.node.category}"
            )

        # Per DD4: Folders sorted alphabetically
        node_ids = [tn.node.node_id for tn in result]
        assert node_ids == ["docs/", "src/", "tests/"], (
            f"Expected alphabetical order, got {node_ids}"
        )

    def test_given_nested_folders_when_depth_one_then_returns_only_top_level_folder(
        self, graph_setup
    ):
        """
        Purpose: Verifies nested folder structure is flattened at depth=1.
        Quality Contribution: Hierarchical navigation respects depth limiting.

        Task: T005 (strengthened from T004)
        """
        config, store, _ = graph_setup
        file1 = make_file_node("src/fs2/cli/tree.py")
        file2 = make_file_node("src/fs2/core/service.py")
        file3 = make_file_node("src/fs2/__init__.py")
        store.set_nodes([file1, file2, file3])

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree(pattern=".", max_depth=1)

        # At depth=1, only see top-level "src/" folder
        assert len(result) == 1, f"Expected 1 top-level folder, got {len(result)}"
        assert result[0].node.node_id == "src/"
        # All 3 files are nested inside src/
        assert result[0].hidden_children_count == 3, (
            f"Expected 3 hidden items, got {result[0].hidden_children_count}"
        )

    def test_given_root_level_files_when_depth_one_then_includes_both_folders_and_files(
        self, graph_setup
    ):
        """
        Purpose: Verifies root-level files appear alongside folders (AC8).
        Quality Contribution: Ensures progressive disclosure handles mixed content.

        Task: T005 (strengthened from T004)
        """
        config, store, _ = graph_setup
        root_file = make_file_node("pyproject.toml")
        folder_file = make_file_node("src/main.py")
        store.set_nodes([root_file, folder_file])

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree(pattern=".", max_depth=1)

        # Per DD4: folders first, then files (both alphabetically)
        assert len(result) == 2, f"Expected 2 items, got {len(result)}"

        # First item should be src/ folder
        assert result[0].node.category == "folder"
        assert result[0].node.node_id == "src/"

        # Second item should be root file
        assert result[1].node.category == "file"
        assert result[1].node.node_id == "file:pyproject.toml"

    def test_given_nested_structure_when_depth_two_then_shows_immediate_children(
        self, graph_setup
    ):
        """
        Purpose: Verifies depth=2 shows folders + immediate children.
        Quality Contribution: Drill-down pattern works.

        Task: T005 (strengthened from T004)
        """
        config, store, _ = graph_setup
        file1 = make_file_node("src/fs2/cli/tree.py")
        file2 = make_file_node("src/fs2/core/service.py")
        store.set_nodes([file1, file2])

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree(pattern=".", max_depth=2)

        # At depth=2: src/ (depth 1) -> fs2/ (depth 2)
        assert len(result) == 1, "Expected 1 top-level folder"
        src_folder = result[0]
        assert src_folder.node.node_id == "src/"

        # src/ should have fs2/ as child
        assert len(src_folder.children) == 1, "Expected 1 child of src/"
        fs2_folder = src_folder.children[0]
        assert fs2_folder.node.node_id == "src/fs2/"
        assert fs2_folder.node.category == "folder"

        # At depth 2, fs2/'s children (cli/, core/) are hidden
        assert fs2_folder.hidden_children_count == 2, (
            "Expected 2 hidden children (cli/, core/)"
        )

    def test_given_folder_with_file_and_subfolder_when_depth_two_then_shows_mixed_children(
        self, graph_setup
    ):
        """
        Purpose: Verifies depth=2 shows mix of files and subfolders.
        Quality Contribution: Validates DD4 (folders first, then files).

        Task: T005 (new test for comprehensive coverage)
        """
        config, store, _ = graph_setup
        file1 = make_file_node("src/__init__.py")  # Direct file in src/
        file2 = make_file_node("src/cli/main.py")  # File in subfolder
        store.set_nodes([file1, file2])

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree(pattern=".", max_depth=2)

        # At depth=2: src/ contains cli/ (folder) and __init__.py (file)
        assert len(result) == 1
        src_folder = result[0]
        assert src_folder.node.node_id == "src/"

        # Per DD4: folders first, then files
        assert len(src_folder.children) == 2, (
            "Expected cli/ folder and __init__.py file"
        )
        assert src_folder.children[0].node.category == "folder"
        assert src_folder.children[0].node.node_id == "src/cli/"
        assert src_folder.children[1].node.category == "file"
        assert src_folder.children[1].node.node_id == "file:src/__init__.py"


@pytest.mark.unit
class TestFolderFiltering:
    """T006: Tests for folder filtering (path prefix mode).

    When pattern contains `/`, files are filtered by path prefix.
    """

    def test_given_folder_pattern_when_build_tree_then_filters_by_prefix(
        self, graph_setup
    ):
        """
        Purpose: Verifies folder patterns filter files by path prefix.
        Quality Contribution: Core folder navigation works.

        Task: T006
        """
        config, store, _ = graph_setup
        file1 = make_file_node("src/fs2/main.py")
        file2 = make_file_node("src/fs2/utils.py")
        file3 = make_file_node("tests/test_main.py")
        store.set_nodes([file1, file2, file3])

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree(pattern="src/fs2/", max_depth=0)

        # Should only include files under src/fs2/
        node_ids = [tn.node.node_id for tn in result]
        assert "file:src/fs2/main.py" in node_ids
        assert "file:src/fs2/utils.py" in node_ids
        assert "file:tests/test_main.py" not in node_ids

    def test_given_folder_pattern_without_trailing_slash_when_build_tree_then_filters_by_prefix(
        self, graph_setup
    ):
        """
        Purpose: Verifies folder patterns work without trailing slash.
        Quality Contribution: Flexible folder navigation.

        Task: T006
        """
        config, store, _ = graph_setup
        file1 = make_file_node("src/fs2/main.py")
        file2 = make_file_node("tests/test_main.py")
        store.set_nodes([file1, file2])

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree(pattern="src/fs2", max_depth=0)

        # Should include files under src/fs2
        node_ids = [tn.node.node_id for tn in result]
        assert "file:src/fs2/main.py" in node_ids
        assert "file:tests/test_main.py" not in node_ids

    def test_given_nested_folder_pattern_when_build_tree_then_filters_deeply_nested(
        self, graph_setup
    ):
        """
        Purpose: Verifies deeply nested folder patterns work.
        Quality Contribution: Full path drill-down works.

        Task: T006
        """
        config, store, _ = graph_setup
        file1 = make_file_node("src/fs2/cli/tree.py")
        file2 = make_file_node("src/fs2/core/service.py")
        file3 = make_file_node("src/fs2/__init__.py")
        store.set_nodes([file1, file2, file3])

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree(pattern="src/fs2/cli/", max_depth=0)

        # Should only include files under src/fs2/cli/
        node_ids = [tn.node.node_id for tn in result]
        assert "file:src/fs2/cli/tree.py" in node_ids
        assert "file:src/fs2/core/service.py" not in node_ids
        assert "file:src/fs2/__init__.py" not in node_ids

    def test_given_nonexistent_folder_when_build_tree_then_returns_empty(
        self, graph_setup
    ):
        """
        Purpose: Verifies nonexistent folder patterns return empty result.
        Quality Contribution: Handles empty folder case gracefully.

        Task: T006

        Note: The "Folder not found" message will be handled at CLI layer.
        TreeService just returns empty list.
        """
        config, store, _ = graph_setup
        file1 = make_file_node("src/main.py")
        store.set_nodes([file1])

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree(pattern="nonexistent/", max_depth=0)

        # Should return empty list for nonexistent folder
        assert result == []

    def test_given_folder_pattern_when_build_tree_then_includes_nested_files(
        self, graph_setup
    ):
        """
        Purpose: Verifies folder patterns include all nested files.
        Quality Contribution: Recursive folder contents work.

        Task: T006
        """
        config, store, _ = graph_setup
        file1 = make_file_node("src/fs2/__init__.py")
        file2 = make_file_node("src/fs2/cli/tree.py")
        file3 = make_file_node("src/fs2/core/services/tree_service.py")
        store.set_nodes([file1, file2, file3])

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree(pattern="src/fs2/", max_depth=0)

        # Should include ALL files under src/fs2/ at any depth
        node_ids = [tn.node.node_id for tn in result]
        assert "file:src/fs2/__init__.py" in node_ids
        assert "file:src/fs2/cli/tree.py" in node_ids
        assert "file:src/fs2/core/services/tree_service.py" in node_ids


@pytest.mark.unit
class TestTreeServiceCrossFileFiltering:
    """Tests for TreeService cross-file edge filtering (Phase 1: T008)."""

    def test_get_children_excludes_cross_file_edges(self, graph_setup):
        """
        Purpose: Proves TreeService tree excludes cross-file reference edges.
        Acceptance Criteria: Tree shows only same-file containment children.

        Task: T008
        """
        config, store, _ = graph_setup

        # File A with class A containing method A
        file_a = make_file_node("src/a.py")
        class_a = make_class_node("src/a.py", "ClassA", file_a.node_id)
        method_a = make_method_node("src/a.py", "ClassA", "method_a", class_a.node_id)

        # File B with class B
        file_b = make_file_node("src/b.py")
        class_b = make_class_node("src/b.py", "ClassB", file_b.node_id)

        store.set_nodes([file_a, class_a, method_a, file_b, class_b])

        # Containment edges
        store.add_edge(file_a.node_id, class_a.node_id)
        store.add_edge(class_a.node_id, method_a.node_id)
        store.add_edge(file_b.node_id, class_b.node_id)

        # Cross-file reference: class_b references class_a
        store.add_edge(class_b.node_id, class_a.node_id, edge_type="references")

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree(pattern="file:src/b.py", max_depth=0)

        # Navigate into src/b.py → ClassB
        assert len(result) == 1  # Just file_b
        file_b_tree = result[0]
        assert file_b_tree.node.node_id == file_b.node_id

        # ClassB should NOT show ClassA as a child (that's a cross-file reference)
        class_b_children = file_b_tree.children
        assert len(class_b_children) == 1  # Only ClassB
        class_b_tree = class_b_children[0]
        assert class_b_tree.node.name == "ClassB"

        # ClassB's children should be empty (no cross-file nodes)
        assert len(class_b_tree.children) == 0

    def test_tree_unchanged_when_no_cross_file_edges(self, graph_setup):
        """
        Purpose: Proves tree output unchanged when only containment edges exist.
        Acceptance Criteria: Backward compatible — same output as before.

        Task: T008
        """
        config, store, _ = graph_setup

        file_a = make_file_node("src/a.py")
        class_a = make_class_node("src/a.py", "ClassA", file_a.node_id)
        method_a = make_method_node("src/a.py", "ClassA", "method_a", class_a.node_id)

        store.set_nodes([file_a, class_a, method_a])
        store.add_edge(file_a.node_id, class_a.node_id)
        store.add_edge(class_a.node_id, method_a.node_id)

        service = TreeService(config=config, graph_store=store)
        result = service.build_tree(pattern="file:src/a.py", max_depth=0)

        # Normal containment tree should be intact
        assert len(result) == 1
        file_tree = result[0]
        assert len(file_tree.children) == 1
        class_tree = file_tree.children[0]
        assert class_tree.node.name == "ClassA"
        assert len(class_tree.children) == 1
        assert class_tree.children[0].node.name == "method_a"
