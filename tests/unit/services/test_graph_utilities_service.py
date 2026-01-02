"""Tests for GraphUtilitiesService.

Purpose: Verify extension summary computation from graph store.

Uses FakeGraphStore (no mocks per constitution P4).
TDD: Tests written before implementation.
"""

import pytest

from fs2.config.objects import GraphConfig, ScanConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.models.code_node import CodeNode
from fs2.core.models.extension_summary import ExtensionSummary
from fs2.core.repos.graph_store_fake import FakeGraphStore
from fs2.core.services.graph_utilities_service import GraphUtilitiesService


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


def make_class_node(file_path: str, name: str) -> CodeNode:
    """Create a class CodeNode for tests."""
    file_node_id = f"file:{file_path}"
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
        parent_node_id=file_node_id,
    )


def make_method_node(file_path: str, class_name: str, method_name: str) -> CodeNode:
    """Create a method CodeNode for tests."""
    class_node_id = f"class:{file_path}:{class_name}"
    return CodeNode.create_callable(
        file_path=file_path,
        language="python",
        ts_kind="function_definition",
        name=method_name,
        qualified_name=f"{class_name}.{method_name}",
        start_line=2,
        end_line=4,
        start_column=4,
        end_column=0,
        start_byte=0,
        end_byte=50,
        content=f"def {method_name}(self): pass",
        signature=f"def {method_name}(self):",
        parent_node_id=class_node_id,
    )


class TestExtractFilePath:
    """Tests for extract_file_path static method."""

    def test_given_file_node_id_when_extract_then_returns_path(self):
        """Verify extraction from file:path format."""
        node_id = "file:src/main.py"
        result = GraphUtilitiesService.extract_file_path(node_id)
        assert result == "src/main.py"

    def test_given_class_node_id_when_extract_then_returns_path(self):
        """Verify extraction from class:path:name format."""
        node_id = "class:src/models/user.py:User"
        result = GraphUtilitiesService.extract_file_path(node_id)
        assert result == "src/models/user.py"

    def test_given_callable_node_id_when_extract_then_returns_path(self):
        """Verify extraction from callable:path:qualified_name format."""
        node_id = "callable:src/calc.py:Calculator.add"
        result = GraphUtilitiesService.extract_file_path(node_id)
        assert result == "src/calc.py"

    def test_given_nested_path_when_extract_then_returns_full_path(self):
        """Verify nested paths are preserved."""
        node_id = "callable:src/core/services/stages/parsing_stage.py:ParsingStage.process"
        result = GraphUtilitiesService.extract_file_path(node_id)
        assert result == "src/core/services/stages/parsing_stage.py"

    def test_given_root_file_when_extract_then_returns_filename(self):
        """Verify root-level files work."""
        node_id = "file:README.md"
        result = GraphUtilitiesService.extract_file_path(node_id)
        assert result == "README.md"

    def test_given_invalid_format_when_extract_then_raises_value_error(self):
        """Verify invalid node_id raises ValueError."""
        with pytest.raises(ValueError, match="Invalid node_id format"):
            GraphUtilitiesService.extract_file_path("invalid_no_colon")


class TestGraphUtilitiesServiceExtensionSummary:
    """Tests for get_extension_summary method."""

    def test_given_graph_with_nodes_when_get_extension_summary_then_returns_counts(
        self,
    ):
        """Verify extension counting from graph store."""
        # Arrange
        config = FakeConfigurationService(
            GraphConfig(graph_path=".fs2/graph.pickle"),
            ScanConfig(),
        )
        graph_store = FakeGraphStore(config)

        # Add nodes to fake graph store
        # Two Python nodes (1 file, 1 class) + 1 TypeScript node
        graph_store.add_node(make_file_node("src/main.py"))
        graph_store.add_node(make_class_node("src/main.py", "Calculator"))
        graph_store.add_node(make_file_node("src/utils.ts"))

        service = GraphUtilitiesService(config=config, graph_store=graph_store)

        # Act
        result = service.get_extension_summary()

        # Assert
        assert isinstance(result, ExtensionSummary)
        assert result.files_by_ext == {".py": 1, ".ts": 1}
        assert result.nodes_by_ext == {".py": 2, ".ts": 1}

    def test_given_multiple_files_same_ext_when_get_extension_summary_then_counts_unique_files(
        self,
    ):
        """Verify unique file counting per extension."""
        # Arrange
        config = FakeConfigurationService(
            GraphConfig(graph_path=".fs2/graph.pickle"),
            ScanConfig(),
        )
        graph_store = FakeGraphStore(config)

        # Add 2 classes from same file, 1 from another
        graph_store.add_node(make_file_node("src/main.py"))
        graph_store.add_node(make_class_node("src/main.py", "ClassA"))
        graph_store.add_node(make_class_node("src/main.py", "ClassB"))
        graph_store.add_node(make_file_node("src/util.py"))
        graph_store.add_node(make_class_node("src/util.py", "Helper"))

        service = GraphUtilitiesService(config=config, graph_store=graph_store)

        # Act
        result = service.get_extension_summary()

        # Assert
        # 2 unique .py files, 5 total nodes (2 files + 3 classes)
        assert result.files_by_ext == {".py": 2}
        assert result.nodes_by_ext == {".py": 5}
        assert result.total_files == 2
        assert result.total_nodes == 5

    def test_given_file_without_extension_when_get_extension_summary_then_uses_no_ext(
        self,
    ):
        """Verify files without extension are counted as '(no ext)'."""
        # Arrange
        config = FakeConfigurationService(
            GraphConfig(graph_path=".fs2/graph.pickle"),
            ScanConfig(),
        )
        graph_store = FakeGraphStore(config)

        # Add file without extension
        graph_store.add_node(make_file_node("Makefile"))
        graph_store.add_node(make_file_node("README"))
        graph_store.add_node(make_file_node("src/main.py"))

        service = GraphUtilitiesService(config=config, graph_store=graph_store)

        # Act
        result = service.get_extension_summary()

        # Assert
        assert result.files_by_ext == {"(no ext)": 2, ".py": 1}
        assert result.nodes_by_ext == {"(no ext)": 2, ".py": 1}

    def test_given_empty_graph_when_get_extension_summary_then_returns_empty(self):
        """Verify empty graph returns empty dicts."""
        # Arrange
        config = FakeConfigurationService(
            GraphConfig(graph_path=".fs2/graph.pickle"),
            ScanConfig(),
        )
        graph_store = FakeGraphStore(config)
        # No nodes added

        service = GraphUtilitiesService(config=config, graph_store=graph_store)

        # Act
        result = service.get_extension_summary()

        # Assert
        assert result.files_by_ext == {}
        assert result.nodes_by_ext == {}
        assert result.total_files == 0
        assert result.total_nodes == 0

    def test_given_mixed_extensions_when_get_extension_summary_then_normalizes_to_lowercase(
        self,
    ):
        """Verify extension normalization to lowercase."""
        # Arrange
        config = FakeConfigurationService(
            GraphConfig(graph_path=".fs2/graph.pickle"),
            ScanConfig(),
        )
        graph_store = FakeGraphStore(config)

        # Add files with mixed case extensions
        graph_store.add_node(make_file_node("src/Main.PY"))
        graph_store.add_node(make_file_node("src/utils.py"))
        graph_store.add_node(make_file_node("README.MD"))

        service = GraphUtilitiesService(config=config, graph_store=graph_store)

        # Act
        result = service.get_extension_summary()

        # Assert - all lowercase
        assert result.files_by_ext == {".py": 2, ".md": 1}

    def test_service_loads_graph_lazily_on_first_call(self):
        """Verify graph is loaded on first method call, not at construction."""
        # Arrange
        config = FakeConfigurationService(
            GraphConfig(graph_path=".fs2/graph.pickle"),
            ScanConfig(),
        )
        graph_store = FakeGraphStore(config)
        graph_store.add_node(make_file_node("src/main.py"))

        service = GraphUtilitiesService(config=config, graph_store=graph_store)

        # Assert - load not called yet
        load_calls = [c for c in graph_store.call_history if c["method"] == "load"]
        assert len(load_calls) == 0

        # Act
        service.get_extension_summary()

        # Assert - now load was called
        load_calls = [c for c in graph_store.call_history if c["method"] == "load"]
        assert len(load_calls) == 1
