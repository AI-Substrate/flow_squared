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

import pytest

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

    def test_given_pipeline_context_when_appending_scan_results_then_modifies_list(self):
        """
        Purpose: Verifies scan_results is mutable.
        Quality Contribution: Stages can append results.
        Acceptance Criteria: append() modifies scan_results in place.
        """
        from fs2.core.services.pipeline_context import PipelineContext
        from fs2.core.models.scan_result import ScanResult

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
        from fs2.core.services.pipeline_context import PipelineContext
        from fs2.core.models.code_node import CodeNode

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
        from fs2.core.services.pipeline_context import PipelineContext
        from fs2.core.adapters.file_scanner_fake import FakeFileScanner

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
        from fs2.core.services.pipeline_context import PipelineContext
        from fs2.core.adapters.ast_parser_fake import FakeASTParser

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
        from fs2.core.services.pipeline_context import PipelineContext
        from fs2.core.repos.graph_store_fake import FakeGraphStore

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
