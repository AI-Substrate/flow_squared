"""Unit tests for PipelineContext dataclass.

Purpose: Verifies PipelineContext mutable dataclass carries all pipeline state.
Quality Contribution: Ensures context flows correctly through pipeline stages.

Per Phase 5 Tasks:
- T001: Tests for PipelineContext fields, defaults, factories

Per Alignment Brief:
- PipelineContext is MUTABLE (unlike frozen domain models)
- Carries config, adapters, results, errors through stages
"""

from pathlib import Path

from fs2.config.objects import ScanConfig
from fs2.config.service import FakeConfigurationService


# Import will fail initially (RED phase)
class TestPipelineContextFields:
    """Tests for PipelineContext field definitions and defaults."""

    def test_given_pipeline_context_when_created_with_config_then_stores_config(self):
        """
        Purpose: Verifies PipelineContext stores ScanConfig.
        Quality Contribution: Ensures config flows through pipeline.
        Acceptance Criteria: scan_config accessible after creation.
        """
        from fs2.core.services.pipeline_context import PipelineContext

        config = ScanConfig(scan_paths=["./src"])
        ctx = PipelineContext(scan_config=config)

        assert ctx.scan_config == config
        assert ctx.scan_config.scan_paths == ["./src"]

    def test_given_pipeline_context_when_created_then_has_default_graph_path(self):
        """
        Purpose: Verifies default graph_path is .fs2/graph.pickle.
        Quality Contribution: Ensures consistent default storage location.
        Acceptance Criteria: graph_path defaults to .fs2/graph.pickle.
        """
        from fs2.core.services.pipeline_context import PipelineContext

        ctx = PipelineContext(scan_config=ScanConfig())

        assert ctx.graph_path == Path(".fs2/graph.pickle")

    def test_given_pipeline_context_when_created_then_has_empty_scan_results(self):
        """
        Purpose: Verifies scan_results defaults to empty list.
        Quality Contribution: Prevents NoneType errors in stages.
        Acceptance Criteria: scan_results is empty list by default.
        """
        from fs2.core.services.pipeline_context import PipelineContext

        ctx = PipelineContext(scan_config=ScanConfig())

        assert ctx.scan_results == []
        assert isinstance(ctx.scan_results, list)

    def test_given_pipeline_context_when_created_then_has_empty_nodes(self):
        """
        Purpose: Verifies nodes defaults to empty list.
        Quality Contribution: Prevents NoneType errors in stages.
        Acceptance Criteria: nodes is empty list by default.
        """
        from fs2.core.services.pipeline_context import PipelineContext

        ctx = PipelineContext(scan_config=ScanConfig())

        assert ctx.nodes == []
        assert isinstance(ctx.nodes, list)

    def test_given_pipeline_context_when_created_then_has_empty_errors(self):
        """
        Purpose: Verifies errors defaults to empty list.
        Quality Contribution: Enables error collection pattern.
        Acceptance Criteria: errors is empty list by default.
        """
        from fs2.core.services.pipeline_context import PipelineContext

        ctx = PipelineContext(scan_config=ScanConfig())

        assert ctx.errors == []
        assert isinstance(ctx.errors, list)

    def test_given_pipeline_context_when_created_then_has_empty_metrics(self):
        """
        Purpose: Verifies metrics defaults to empty dict.
        Quality Contribution: Enables per-stage metrics collection.
        Acceptance Criteria: metrics is empty dict by default.
        """
        from fs2.core.services.pipeline_context import PipelineContext

        ctx = PipelineContext(scan_config=ScanConfig())

        assert ctx.metrics == {}
        assert isinstance(ctx.metrics, dict)

    def test_given_pipeline_context_when_created_then_adapters_are_none(self):
        """
        Purpose: Verifies adapters default to None.
        Quality Contribution: Pipeline sets adapters before running stages.
        Acceptance Criteria: file_scanner, ast_parser, graph_store are None.
        """
        from fs2.core.services.pipeline_context import PipelineContext

        ctx = PipelineContext(scan_config=ScanConfig())

        assert ctx.file_scanner is None
        assert ctx.ast_parser is None
        assert ctx.graph_store is None


class TestPipelineContextMutability:
    """Tests for PipelineContext mutable behavior."""

    def test_given_pipeline_context_when_appending_scan_results_then_modifies_list(
        self,
    ):
        """
        Purpose: Verifies scan_results is mutable.
        Quality Contribution: Stages can append results.
        Acceptance Criteria: append() modifies scan_results in place.
        """
        from fs2.core.models.scan_result import ScanResult
        from fs2.core.services.pipeline_context import PipelineContext

        ctx = PipelineContext(scan_config=ScanConfig())
        result = ScanResult(path=Path("test.py"), size_bytes=100)

        ctx.scan_results.append(result)

        assert len(ctx.scan_results) == 1
        assert ctx.scan_results[0] == result

    def test_given_pipeline_context_when_appending_nodes_then_modifies_list(self):
        """
        Purpose: Verifies nodes is mutable.
        Quality Contribution: Stages can append nodes.
        Acceptance Criteria: append() modifies nodes in place.
        """
        from fs2.core.models.code_node import CodeNode
        from fs2.core.services.pipeline_context import PipelineContext

        ctx = PipelineContext(scan_config=ScanConfig())
        node = CodeNode.create_file(
            file_path="test.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# test",
        )

        ctx.nodes.append(node)

        assert len(ctx.nodes) == 1
        assert ctx.nodes[0] == node

    def test_given_pipeline_context_when_appending_errors_then_modifies_list(self):
        """
        Purpose: Verifies errors is mutable.
        Quality Contribution: Stages can collect errors without raising.
        Acceptance Criteria: append() modifies errors in place.
        """
        from fs2.core.services.pipeline_context import PipelineContext

        ctx = PipelineContext(scan_config=ScanConfig())

        ctx.errors.append("Failed to parse file.py")

        assert len(ctx.errors) == 1
        assert ctx.errors[0] == "Failed to parse file.py"

    def test_given_pipeline_context_when_setting_metrics_then_modifies_dict(self):
        """
        Purpose: Verifies metrics is mutable.
        Quality Contribution: Stages can record metrics.
        Acceptance Criteria: dict assignment works.
        """
        from fs2.core.services.pipeline_context import PipelineContext

        ctx = PipelineContext(scan_config=ScanConfig())

        ctx.metrics["discovery_time_ms"] = 150.5

        assert ctx.metrics["discovery_time_ms"] == 150.5


class TestPipelineContextAdapterInjection:
    """Tests for injecting adapters into PipelineContext."""

    def test_given_pipeline_context_when_setting_file_scanner_then_stores_adapter(self):
        """
        Purpose: Verifies file_scanner can be set.
        Quality Contribution: Pipeline injects adapters before running.
        Acceptance Criteria: file_scanner accessible after assignment.
        """
        from fs2.core.adapters.file_scanner_fake import FakeFileScanner
        from fs2.core.services.pipeline_context import PipelineContext

        config_service = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config_service)

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.file_scanner = scanner

        assert ctx.file_scanner == scanner

    def test_given_pipeline_context_when_setting_ast_parser_then_stores_adapter(self):
        """
        Purpose: Verifies ast_parser can be set.
        Quality Contribution: Pipeline injects adapters before running.
        Acceptance Criteria: ast_parser accessible after assignment.
        """
        from fs2.core.adapters.ast_parser_fake import FakeASTParser
        from fs2.core.services.pipeline_context import PipelineContext

        config_service = FakeConfigurationService(ScanConfig())
        parser = FakeASTParser(config_service)

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.ast_parser = parser

        assert ctx.ast_parser == parser

    def test_given_pipeline_context_when_setting_graph_store_then_stores_adapter(self):
        """
        Purpose: Verifies graph_store can be set.
        Quality Contribution: Pipeline injects adapters before running.
        Acceptance Criteria: graph_store accessible after assignment.
        """
        from fs2.core.repos.graph_store_fake import FakeGraphStore
        from fs2.core.services.pipeline_context import PipelineContext

        config_service = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config_service)

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.graph_store = store

        assert ctx.graph_store == store


class TestPipelineContextCustomGraphPath:
    """Tests for custom graph_path configuration."""

    def test_given_pipeline_context_when_created_with_custom_path_then_uses_it(self):
        """
        Purpose: Verifies graph_path can be customized.
        Quality Contribution: Enables custom storage locations.
        Acceptance Criteria: Custom path is used when provided.
        """
        from fs2.core.services.pipeline_context import PipelineContext

        custom_path = Path("/tmp/custom.pickle")
        ctx = PipelineContext(scan_config=ScanConfig(), graph_path=custom_path)

        assert ctx.graph_path == custom_path


class TestPipelineContextPriorNodes:
    """Tests for prior_nodes field supporting smart content preservation.

    Per Subtask 001: Graph Loading for Smart Content Preservation.
    Enables hash-based skip logic (AC5/AC6) by loading prior graph state.
    """

    def test_given_pipeline_context_when_created_then_prior_nodes_defaults_to_none(
        self,
    ):
        """
        Purpose: Verifies prior_nodes defaults to None (first scan case).
        Quality Contribution: First scans work without prior graph.
        Acceptance Criteria: prior_nodes is None by default.

        Why: First-scan safety - if no graph exists, prior_nodes = None.
        Contract: PipelineContext.prior_nodes defaults to None.
        """
        from fs2.core.services.pipeline_context import PipelineContext

        ctx = PipelineContext(scan_config=ScanConfig())

        assert ctx.prior_nodes is None

    def test_given_pipeline_context_when_setting_prior_nodes_dict_then_stores_it(self):
        """
        Purpose: Verifies prior_nodes accepts dict[str, CodeNode].
        Quality Contribution: Enables O(1) lookup for merge logic.
        Acceptance Criteria: Dict is stored and retrievable.

        Why: Pipeline loads graph and builds dict for fast node lookup.
        Contract: prior_nodes can be set to dict mapping node_id to CodeNode.
        """
        from fs2.core.models.code_node import CodeNode
        from fs2.core.services.pipeline_context import PipelineContext

        node = CodeNode.create_file(
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
        ctx.prior_nodes = {node.node_id: node}

        assert ctx.prior_nodes is not None
        assert node.node_id in ctx.prior_nodes
        assert ctx.prior_nodes[node.node_id] == node

    def test_given_pipeline_context_with_prior_nodes_when_looking_up_then_o1_access(
        self,
    ):
        """
        Purpose: Verifies dict enables O(1) node lookup by node_id.
        Quality Contribution: Efficient merge in SmartContentStage.
        Acceptance Criteria: Can retrieve specific node by node_id.

        Why: Workshop decision - node matching by node_id for O(1) lookup.
        Contract: prior_nodes[node_id] returns CodeNode in O(1).
        """
        from fs2.core.models.code_node import CodeNode
        from fs2.core.services.pipeline_context import PipelineContext

        # Create multiple nodes
        node1 = CodeNode.create_file(
            file_path="a.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# a",
        )
        node2 = CodeNode.create_file(
            file_path="b.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# b",
        )

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.prior_nodes = {
            node1.node_id: node1,
            node2.node_id: node2,
        }

        # Direct lookup - O(1)
        assert ctx.prior_nodes.get("file:a.py") == node1
        assert ctx.prior_nodes.get("file:b.py") == node2
        assert ctx.prior_nodes.get("file:nonexistent.py") is None


class TestPipelineContextEmbeddingFields:
    """Tests for embedding service fields on PipelineContext."""

    def test_given_pipeline_context_when_created_then_embedding_fields_default_none(
        self,
    ):
        """
        Purpose: Verifies embedding fields default to None.
        Quality Contribution: Enables --no-embeddings to skip service.
        Acceptance Criteria: embedding_service and progress callback are None.

        Why: Pipeline should be able to run without embedding service.
        Contract: embedding_service and embedding_progress_callback default to None.
        """
        from fs2.core.services.pipeline_context import PipelineContext

        ctx = PipelineContext(scan_config=ScanConfig())

        assert ctx.embedding_service is None
        assert ctx.embedding_progress_callback is None

    def test_given_pipeline_context_when_setting_embedding_fields_then_stores_values(
        self,
    ):
        """
        Purpose: Verifies embedding fields accept assignments.
        Quality Contribution: Enables ScanPipeline to inject EmbeddingService.
        Acceptance Criteria: assigned service and callback are accessible.

        Why: EmbeddingStage reads from context for service and callbacks.
        Contract: embedding_service and embedding_progress_callback are settable.
        """
        from fs2.core.services.pipeline_context import PipelineContext

        ctx = PipelineContext(scan_config=ScanConfig())

        def callback(processed, total, skipped):
            return None

        service = object()

        ctx.embedding_service = service
        ctx.embedding_progress_callback = callback

        assert ctx.embedding_service is service
        assert ctx.embedding_progress_callback is callback
