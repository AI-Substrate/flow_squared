"""Unit tests for StorageStage.

Purpose: Verifies StorageStage wraps GraphStore and persists nodes/edges.
Quality Contribution: Ensures graph persistence works correctly in pipeline.

Per Phase 5 Tasks:
- T009: Tests for StorageStage edge creation from node.parent_node_id
- T010: Tests for StorageStage persistence with FakeGraphStore

Per Alignment Brief:
- StorageStage validates graph_store not None
- Uses node.parent_node_id for edges (set by ASTParser during traversal)
- Calls add_node, add_edge, save
- Catches GraphStoreError, appends to context.errors
"""

from pathlib import Path

import pytest

from fs2.config.objects import ScanConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.models.code_node import CodeNode
from fs2.core.repos.graph_store_fake import FakeGraphStore
from fs2.core.services.pipeline_context import PipelineContext


class TestStorageStageProtocol:
    """Tests for StorageStage protocol compliance."""

    def test_given_storage_stage_when_checked_then_implements_pipeline_stage(self):
        """
        Purpose: Verifies StorageStage implements PipelineStage protocol.
        Quality Contribution: Ensures stage can be used in pipeline.
        Acceptance Criteria: isinstance check passes.
        """
        from fs2.core.services.stages.storage_stage import StorageStage
        from fs2.core.services.pipeline_stage import PipelineStage

        stage = StorageStage()
        assert isinstance(stage, PipelineStage)

    def test_given_storage_stage_when_name_accessed_then_returns_storage(self):
        """
        Purpose: Verifies stage name is 'storage'.
        Quality Contribution: Enables logging and metrics identification.
        Acceptance Criteria: name property returns 'storage'.
        """
        from fs2.core.services.stages.storage_stage import StorageStage

        stage = StorageStage()
        assert stage.name == "storage"


class TestStorageStageValidation:
    """Tests for StorageStage precondition validation."""

    def test_given_context_without_graph_store_when_processing_then_raises_value_error(
        self,
    ):
        """
        Purpose: Verifies stage validates graph_store presence.
        Quality Contribution: Provides clear error for misconfiguration.
        Acceptance Criteria: ValueError raised with descriptive message.
        """
        from fs2.core.services.stages.storage_stage import StorageStage

        stage = StorageStage()
        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.nodes = [
            CodeNode.create_file(
                file_path="test.py",
                language="python",
                ts_kind="module",
                start_byte=0,
                end_byte=100,
                start_line=1,
                end_line=10,
                content="# test",
            )
        ]
        # graph_store is None by default

        with pytest.raises(ValueError) as exc_info:
            stage.process(ctx)

        assert "graph_store" in str(exc_info.value).lower()


class TestStorageStageNodePersistence:
    """Tests for StorageStage node persistence."""

    def test_given_nodes_when_processing_then_adds_all_nodes_to_store(self):
        """
        Purpose: Verifies all nodes are added to graph store.
        Quality Contribution: Ensures complete graph population.
        Acceptance Criteria: add_node called for each node.
        """
        from fs2.core.services.stages.storage_stage import StorageStage

        config_service = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config_service)

        file_node = CodeNode.create_file(
            file_path="test.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# test",
        )
        class_node = CodeNode.create_type(
            file_path="test.py",
            language="python",
            ts_kind="class_definition",
            name="MyClass",
            qualified_name="MyClass",
            start_line=1,
            end_line=5,
            start_column=0,
            end_column=10,
            start_byte=0,
            end_byte=50,
            content="class MyClass: pass",
            signature="class MyClass:",
            parent_node_id="file:test.py",
        )

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.graph_store = store
        ctx.nodes = [file_node, class_node]

        stage = StorageStage()
        stage.process(ctx)

        add_node_calls = [c for c in store.call_history if c["method"] == "add_node"]
        assert len(add_node_calls) == 2

    def test_given_nodes_when_processing_then_nodes_in_store(self):
        """
        Purpose: Verifies nodes are actually stored.
        Quality Contribution: Ensures graph is populated correctly.
        Acceptance Criteria: Nodes retrievable from store.
        """
        from fs2.core.services.stages.storage_stage import StorageStage

        config_service = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config_service)

        file_node = CodeNode.create_file(
            file_path="test.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# test",
        )

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.graph_store = store
        ctx.nodes = [file_node]

        stage = StorageStage()
        stage.process(ctx)

        stored = store.get_node("file:test.py")
        assert stored is not None
        assert stored.node_id == "file:test.py"


class TestStorageStageEdgeCreation:
    """Tests for StorageStage edge creation from parent_node_id."""

    def test_given_node_with_parent_id_when_processing_then_creates_edge(self):
        """
        Purpose: Verifies edges created from node.parent_node_id.
        Quality Contribution: Ensures hierarchy is persisted.
        Acceptance Criteria: add_edge called with parent → child.
        """
        from fs2.core.services.stages.storage_stage import StorageStage

        config_service = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config_service)

        file_node = CodeNode.create_file(
            file_path="calc.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=200,
            start_line=1,
            end_line=20,
            content="class Calculator: pass",
        )
        class_node = CodeNode.create_type(
            file_path="calc.py",
            language="python",
            ts_kind="class_definition",
            name="Calculator",
            qualified_name="Calculator",
            start_line=1,
            end_line=10,
            start_column=0,
            end_column=10,
            start_byte=0,
            end_byte=100,
            content="class Calculator:",
            signature="class Calculator:",
            parent_node_id="file:calc.py",  # Points to file node
        )

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.graph_store = store
        ctx.nodes = [file_node, class_node]

        stage = StorageStage()
        stage.process(ctx)

        add_edge_calls = [c for c in store.call_history if c["method"] == "add_edge"]
        assert len(add_edge_calls) == 1
        # Edge from file → class
        assert add_edge_calls[0]["args"] == ("file:calc.py", "type:calc.py:Calculator")

    def test_given_node_without_parent_id_when_processing_then_no_edge_created(self):
        """
        Purpose: Verifies file nodes (no parent) don't create edges.
        Quality Contribution: Prevents invalid edge creation.
        Acceptance Criteria: No add_edge call for file nodes.
        """
        from fs2.core.services.stages.storage_stage import StorageStage

        config_service = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config_service)

        file_node = CodeNode.create_file(
            file_path="test.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# test",
        )
        # File nodes have parent_node_id=None

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.graph_store = store
        ctx.nodes = [file_node]

        stage = StorageStage()
        stage.process(ctx)

        add_edge_calls = [c for c in store.call_history if c["method"] == "add_edge"]
        assert len(add_edge_calls) == 0

    def test_given_nested_hierarchy_when_processing_then_creates_all_edges(self):
        """
        Purpose: Verifies multi-level hierarchy creates all edges.
        Quality Contribution: Ensures file → class → method edges.
        Acceptance Criteria: Edge for each parent-child relationship.
        """
        from fs2.core.services.stages.storage_stage import StorageStage

        config_service = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config_service)

        file_node = CodeNode.create_file(
            file_path="calc.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=300,
            start_line=1,
            end_line=30,
            content="class Calculator: ...",
        )
        class_node = CodeNode.create_type(
            file_path="calc.py",
            language="python",
            ts_kind="class_definition",
            name="Calculator",
            qualified_name="Calculator",
            start_line=1,
            end_line=20,
            start_column=0,
            end_column=10,
            start_byte=0,
            end_byte=200,
            content="class Calculator:",
            signature="class Calculator:",
            parent_node_id="file:calc.py",
        )
        method_node = CodeNode.create_callable(
            file_path="calc.py",
            language="python",
            ts_kind="function_definition",
            name="add",
            qualified_name="Calculator.add",
            start_line=2,
            end_line=5,
            start_column=4,
            end_column=20,
            start_byte=20,
            end_byte=100,
            content="def add(self): pass",
            signature="def add(self):",
            parent_node_id="type:calc.py:Calculator",  # Points to class
        )

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.graph_store = store
        ctx.nodes = [file_node, class_node, method_node]

        stage = StorageStage()
        stage.process(ctx)

        add_edge_calls = [c for c in store.call_history if c["method"] == "add_edge"]
        assert len(add_edge_calls) == 2

        # Verify specific edges
        edges = [(c["args"][0], c["args"][1]) for c in add_edge_calls]
        assert ("file:calc.py", "type:calc.py:Calculator") in edges
        assert ("type:calc.py:Calculator", "callable:calc.py:Calculator.add") in edges


class TestStorageStagePersistence:
    """Tests for StorageStage save operation."""

    def test_given_nodes_when_processing_then_calls_save(self):
        """
        Purpose: Verifies stage calls graph_store.save().
        Quality Contribution: Ensures graph is persisted to disk.
        Acceptance Criteria: save() called with context.graph_path.
        """
        from fs2.core.services.stages.storage_stage import StorageStage

        config_service = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config_service)

        ctx = PipelineContext(
            scan_config=ScanConfig(),
            graph_path=Path("/tmp/test.pickle"),
        )
        ctx.graph_store = store
        ctx.nodes = []

        stage = StorageStage()
        stage.process(ctx)

        save_calls = [c for c in store.call_history if c["method"] == "save"]
        assert len(save_calls) == 1
        assert save_calls[0]["args"] == (Path("/tmp/test.pickle"),)


class TestStorageStageErrorHandling:
    """Tests for StorageStage error handling."""

    def test_given_save_error_when_processing_then_appends_to_errors(self):
        """
        Purpose: Verifies GraphStoreError on save is caught and collected.
        Quality Contribution: Pipeline reports storage failures.
        Acceptance Criteria: Error message in context.errors.
        """
        from fs2.core.services.stages.storage_stage import StorageStage

        config_service = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config_service)
        store.simulate_error_for.add("save")

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.graph_store = store
        ctx.nodes = []

        stage = StorageStage()
        result_ctx = stage.process(ctx)

        assert len(result_ctx.errors) == 1
        assert "save" in result_ctx.errors[0].lower()


class TestStorageStageMetrics:
    """Tests for StorageStage metrics recording."""

    def test_given_nodes_stored_when_processing_then_records_node_count(self):
        """
        Purpose: Verifies stage records stored node count in metrics.
        Quality Contribution: Enables pipeline observability.
        Acceptance Criteria: metrics['storage_nodes'] set.
        """
        from fs2.core.services.stages.storage_stage import StorageStage

        config_service = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config_service)

        file_node = CodeNode.create_file(
            file_path="test.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# test",
        )

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.graph_store = store
        ctx.nodes = [file_node]

        stage = StorageStage()
        result_ctx = stage.process(ctx)

        assert "storage_nodes" in result_ctx.metrics
        assert result_ctx.metrics["storage_nodes"] == 1

    def test_given_edges_created_when_processing_then_records_edge_count(self):
        """
        Purpose: Verifies stage records edge count in metrics.
        Quality Contribution: Enables hierarchy tracking.
        Acceptance Criteria: metrics['storage_edges'] set.
        """
        from fs2.core.services.stages.storage_stage import StorageStage

        config_service = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config_service)

        file_node = CodeNode.create_file(
            file_path="test.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# test",
        )
        class_node = CodeNode.create_type(
            file_path="test.py",
            language="python",
            ts_kind="class_definition",
            name="Foo",
            qualified_name="Foo",
            start_line=1,
            end_line=5,
            start_column=0,
            end_column=10,
            start_byte=0,
            end_byte=50,
            content="class Foo:",
            signature="class Foo:",
            parent_node_id="file:test.py",
        )

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.graph_store = store
        ctx.nodes = [file_node, class_node]

        stage = StorageStage()
        result_ctx = stage.process(ctx)

        assert "storage_edges" in result_ctx.metrics
        assert result_ctx.metrics["storage_edges"] == 1


class TestStorageStageReturnsContext:
    """Tests for StorageStage return value."""

    def test_given_storage_stage_when_processing_then_returns_context(self):
        """
        Purpose: Verifies stage returns the context.
        Quality Contribution: Enables pipeline chaining.
        Acceptance Criteria: process() returns the context.
        """
        from fs2.core.services.stages.storage_stage import StorageStage

        config_service = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config_service)

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.graph_store = store
        ctx.nodes = []

        stage = StorageStage()
        result = stage.process(ctx)

        assert result is ctx
