"""Tests for GetNodeService.

T002: Unit tests for GetNodeService.
Purpose: Verify GetNodeService retrieves nodes correctly with lazy loading.

Uses FakeGraphStore (no mocks per constitution P4).
"""

import pytest

from fs2.config.objects import GraphConfig, ScanConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters.exceptions import GraphNotFoundError, GraphStoreError
from fs2.core.models.code_node import CodeNode
from fs2.core.repos.graph_store_fake import FakeGraphStore
from fs2.core.services.get_node_service import GetNodeService


def make_code_node(
    node_id: str,
    category: str = "file",
    name: str = "test",
) -> CodeNode:
    """Helper to create CodeNode for tests using factory methods."""
    # Extract file path from node_id (format: category:file_path:qualified_name)
    parts = node_id.split(":")
    file_path = parts[1] if len(parts) >= 2 else "test.py"

    if category == "file":
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
    elif category == "callable":
        return CodeNode.create_callable(
            file_path=file_path,
            language="python",
            ts_kind="function_definition",
            name=name,
            qualified_name=name,
            start_line=1,
            end_line=10,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=100,
            content="def test(): pass",
            signature="def test():",
        )
    else:
        # Generic - use file factory with dataclasses.replace() override
        # (CodeNode is frozen; keep factory as source of truth for new fields).
        import dataclasses

        node = CodeNode.create_file(
            file_path=file_path,
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# test content",
        )
        return dataclasses.replace(
            node,
            node_id=node_id,
            category=category,
            name=name,
            qualified_name=name,
            signature=None,
        )


@pytest.mark.unit
class TestGetNodeServiceInit:
    """T002: Tests for GetNodeService initialization."""

    def test_given_config_and_store_when_created_then_service_exists(
        self, tmp_path
    ):
        """
        Purpose: Verifies service can be created with DI pattern.
        Quality Contribution: Ensures proper dependency injection.

        Task: T002
        """
        # Arrange
        config = FakeConfigurationService(
            ScanConfig(),
            GraphConfig(graph_path=str(tmp_path / "graph.pickle")),
        )
        store = FakeGraphStore(config)

        # Act
        service = GetNodeService(config=config, graph_store=store)

        # Assert
        assert service is not None
        assert service._loaded is False

    def test_given_missing_graph_config_when_created_then_raises(self):
        """
        Purpose: Verifies service requires GraphConfig.
        Quality Contribution: Catches missing config early.

        Task: T002
        """
        from fs2.config.exceptions import MissingConfigurationError

        # Arrange - only ScanConfig, no GraphConfig
        config = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config)

        # Act & Assert
        with pytest.raises(MissingConfigurationError):
            GetNodeService(config=config, graph_store=store)


@pytest.mark.unit
class TestGetNodeServiceLazyLoading:
    """T002: Tests for lazy loading behavior."""

    def test_given_new_service_when_get_node_called_then_loads_graph(
        self, tmp_path
    ):
        """
        Purpose: Verifies lazy loading triggers on first access.
        Quality Contribution: Ensures graph loaded before access.

        Task: T002
        """
        # Arrange
        graph_path = tmp_path / "graph.pickle"
        graph_path.touch()  # Create empty file (FakeGraphStore doesn't read it)

        config = FakeConfigurationService(
            ScanConfig(),
            GraphConfig(graph_path=str(graph_path)),
        )
        store = FakeGraphStore(config)
        service = GetNodeService(config=config, graph_store=store)

        # Act
        service.get_node("file:test.py")

        # Assert - load was called
        load_calls = [c for c in store.call_history if c["method"] == "load"]
        assert len(load_calls) == 1
        assert load_calls[0]["args"][0] == graph_path

    def test_given_already_loaded_when_get_node_called_then_no_reload(
        self, tmp_path
    ):
        """
        Purpose: Verifies graph is not re-loaded on subsequent calls.
        Quality Contribution: Prevents redundant I/O.

        Task: T002
        """
        # Arrange
        graph_path = tmp_path / "graph.pickle"
        graph_path.touch()

        config = FakeConfigurationService(
            ScanConfig(),
            GraphConfig(graph_path=str(graph_path)),
        )
        store = FakeGraphStore(config)
        service = GetNodeService(config=config, graph_store=store)

        # Act - call twice
        service.get_node("file:test1.py")
        service.get_node("file:test2.py")

        # Assert - load called only once
        load_calls = [c for c in store.call_history if c["method"] == "load"]
        assert len(load_calls) == 1


@pytest.mark.unit
class TestGetNodeServiceRetrieval:
    """T002: Tests for node retrieval."""

    def test_given_existing_node_when_get_node_called_then_returns_node(
        self, tmp_path
    ):
        """
        Purpose: Verifies node retrieval returns correct node.
        Quality Contribution: Core functionality test.

        Task: T002
        """
        # Arrange
        graph_path = tmp_path / "graph.pickle"
        graph_path.touch()

        config = FakeConfigurationService(
            ScanConfig(),
            GraphConfig(graph_path=str(graph_path)),
        )
        store = FakeGraphStore(config)
        node = make_code_node("file:src/main.py", "file", "main.py")
        store.set_nodes([node])

        service = GetNodeService(config=config, graph_store=store)

        # Act
        result = service.get_node("file:src/main.py")

        # Assert
        assert result is not None
        assert result.node_id == "file:src/main.py"
        assert result.name == "main.py"

    def test_given_nonexistent_node_when_get_node_called_then_returns_none(
        self, tmp_path
    ):
        """
        Purpose: Verifies missing node returns None (not error).
        Quality Contribution: Correct missing node handling.

        Task: T002
        """
        # Arrange
        graph_path = tmp_path / "graph.pickle"
        graph_path.touch()

        config = FakeConfigurationService(
            ScanConfig(),
            GraphConfig(graph_path=str(graph_path)),
        )
        store = FakeGraphStore(config)
        store.set_nodes([])  # Empty graph

        service = GetNodeService(config=config, graph_store=store)

        # Act
        result = service.get_node("file:does_not_exist.py")

        # Assert
        assert result is None


@pytest.mark.unit
class TestGetNodeServiceErrors:
    """T002: Tests for error handling."""

    def test_given_missing_graph_file_when_get_node_called_then_raises_not_found(
        self, tmp_path
    ):
        """
        Purpose: Verifies GraphNotFoundError raised for missing graph.
        Quality Contribution: Clear error for common user issue.

        Task: T002
        """
        # Arrange
        graph_path = tmp_path / "nonexistent.pickle"  # Does not exist

        config = FakeConfigurationService(
            ScanConfig(),
            GraphConfig(graph_path=str(graph_path)),
        )
        store = FakeGraphStore(config)
        service = GetNodeService(config=config, graph_store=store)

        # Act & Assert
        with pytest.raises(GraphNotFoundError) as exc_info:
            service.get_node("file:test.py")

        assert exc_info.value.path == graph_path
        assert "fs2 scan" in str(exc_info.value)

    def test_given_corrupted_graph_when_get_node_called_then_raises_store_error(
        self, tmp_path
    ):
        """
        Purpose: Verifies GraphStoreError raised for corrupted graph.
        Quality Contribution: Correct error propagation.

        Task: T002
        """
        # Arrange
        graph_path = tmp_path / "graph.pickle"
        graph_path.touch()

        config = FakeConfigurationService(
            ScanConfig(),
            GraphConfig(graph_path=str(graph_path)),
        )
        store = FakeGraphStore(config)
        store.simulate_error_for.add("load")  # Simulate corruption

        service = GetNodeService(config=config, graph_store=store)

        # Act & Assert
        with pytest.raises(GraphStoreError):
            service.get_node("file:test.py")
