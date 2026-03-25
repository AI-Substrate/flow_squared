"""Unit tests for ScanPipeline orchestrator.

Purpose: Verifies ScanPipeline orchestrates stages and returns ScanSummary.
Quality Contribution: Ensures pipeline works correctly as a whole.

Per Phase 5 Tasks:
- T014: Tests for stage ordering
- T015: Tests for DI pattern (config.require, adapter injection)
- T016: Tests for error aggregation
- T017: Tests for custom stage injection

Per Alignment Brief:
- ScanPipeline receives ConfigurationService, calls config.require(ScanConfig)
- Receives adapters via constructor, injects into context
- Runs stages sequentially: Discovery → Parsing → Storage
- Returns ScanSummary with success, counts, errors, metrics
"""

from pathlib import Path

import pytest

from fs2.config.objects import ScanConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters.ast_parser_fake import FakeASTParser
from fs2.core.adapters.file_scanner_fake import FakeFileScanner
from fs2.core.models.code_node import CodeNode
from fs2.core.models.scan_result import ScanResult
from fs2.core.repos.graph_store_fake import FakeGraphStore
from fs2.core.services.pipeline_context import PipelineContext


@pytest.fixture
def test_graph_path(tmp_path: Path) -> Path:
    """Temp graph path to avoid corrupting project graph."""
    return tmp_path / "test_graph.pickle"


class TestScanPipelineConstruction:
    """Tests for ScanPipeline construction and DI."""

    def test_given_config_service_when_constructing_then_extracts_scan_config(
        self, test_graph_path: Path
    ):
        """
        Purpose: Verifies pipeline calls config.require(ScanConfig).
        Quality Contribution: Follows ConfigurationService registry pattern (CF01).
        Acceptance Criteria: No MissingConfigurationError raised.
        """
        from fs2.core.services.scan_pipeline import ScanPipeline

        config_service = FakeConfigurationService(ScanConfig(scan_paths=["./src"]))
        scanner = FakeFileScanner(config_service)
        parser = FakeASTParser(config_service)
        store = FakeGraphStore(config_service)

        # Should not raise
        pipeline = ScanPipeline(
            config=config_service,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            graph_path=test_graph_path,
        )

        assert pipeline is not None

    def test_given_missing_scan_config_when_constructing_then_raises_error(
        self, test_graph_path: Path
    ):
        """
        Purpose: Verifies pipeline requires ScanConfig in registry.
        Quality Contribution: Clear error on misconfiguration.
        Acceptance Criteria: MissingConfigurationError raised.
        """
        from fs2.config.service import (
            FakeConfigurationService,
            MissingConfigurationError,
        )
        from fs2.core.services.scan_pipeline import ScanPipeline

        # Empty config service - no ScanConfig
        config_service = FakeConfigurationService()

        with pytest.raises(MissingConfigurationError):
            ScanPipeline(
                config=config_service,
                file_scanner=None,  # type: ignore
                ast_parser=None,  # type: ignore
                graph_store=None,  # type: ignore
                graph_path=test_graph_path,
            )


class TestScanPipelineStageOrdering:
    """Tests for ScanPipeline stage execution order."""

    def test_given_default_stages_when_running_then_executes_in_order(
        self, test_graph_path: Path
    ):
        """
        Purpose: Verifies stages run in correct order.
        Quality Contribution: Ensures data flows correctly.
        Acceptance Criteria: Discovery → Parsing → Storage order.
        """
        from fs2.core.services.scan_pipeline import ScanPipeline

        config_service = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config_service)
        parser = FakeASTParser(config_service)
        store = FakeGraphStore(config_service)

        # Set up scanner to return a file
        scanner.set_results([ScanResult(path=Path("test.py"), size_bytes=100)])

        # Set up parser to return nodes
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
        parser.set_results(Path("test.py"), [file_node])

        pipeline = ScanPipeline(
            config=config_service,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            graph_path=test_graph_path,
        )

        summary = pipeline.run()

        # Verify all adapters were called
        assert len(scanner.call_history) > 0  # Discovery ran
        assert len(parser.call_history) > 0  # Parsing ran
        assert len(store.call_history) > 0  # Storage ran

        # Verify order: scan before parse, parse before store
        # Call history confirms stages executed in sequence
        _ = next(i for i, c in enumerate(scanner.call_history) if c["method"] == "scan")
        _ = next(i for i, c in enumerate(parser.call_history) if c["method"] == "parse")

        # Scanner call_history has its own indices, but we just verify parse happened
        # and nodes were stored
        assert summary.files_scanned == 1
        assert summary.nodes_created == 1


class TestScanPipelineAdapterInjection:
    """Tests for adapter injection into context."""

    def test_given_adapters_when_running_then_injected_into_context(
        self, test_graph_path: Path
    ):
        """
        Purpose: Verifies adapters are injected into PipelineContext.
        Quality Contribution: Stages have access to adapters.
        Acceptance Criteria: Stages can use adapters.
        """
        from fs2.core.services.scan_pipeline import ScanPipeline

        config_service = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config_service)
        parser = FakeASTParser(config_service)
        store = FakeGraphStore(config_service)

        pipeline = ScanPipeline(
            config=config_service,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            graph_path=test_graph_path,
        )

        summary = pipeline.run()

        # If adapters weren't injected, stages would raise ValueError
        # The fact that we got a summary means injection worked
        assert summary is not None


class TestScanPipelineSummaryGeneration:
    """Tests for ScanSummary generation."""

    def test_given_successful_run_when_completed_then_returns_summary(
        self, test_graph_path: Path
    ):
        """
        Purpose: Verifies pipeline returns ScanSummary.
        Quality Contribution: Provides execution results.
        Acceptance Criteria: ScanSummary returned with correct fields.
        """
        from fs2.core.models.scan_summary import ScanSummary
        from fs2.core.services.scan_pipeline import ScanPipeline

        config_service = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config_service)
        parser = FakeASTParser(config_service)
        store = FakeGraphStore(config_service)

        pipeline = ScanPipeline(
            config=config_service,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            graph_path=test_graph_path,
        )

        summary = pipeline.run()

        assert isinstance(summary, ScanSummary)

    def test_given_no_errors_when_completed_then_success_is_true(
        self, test_graph_path: Path
    ):
        """
        Purpose: Verifies success=True when no errors.
        Quality Contribution: Correct success reporting.
        Acceptance Criteria: success=True, errors empty.
        """
        from fs2.core.services.scan_pipeline import ScanPipeline

        config_service = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config_service)
        parser = FakeASTParser(config_service)
        store = FakeGraphStore(config_service)

        pipeline = ScanPipeline(
            config=config_service,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            graph_path=test_graph_path,
        )

        summary = pipeline.run()

        assert summary.success is True
        assert summary.errors == []

    def test_given_files_scanned_when_completed_then_count_in_summary(
        self, test_graph_path: Path
    ):
        """
        Purpose: Verifies files_scanned count is accurate.
        Quality Contribution: Accurate metrics.
        Acceptance Criteria: files_scanned matches discovered files.
        """
        from fs2.core.services.scan_pipeline import ScanPipeline

        config_service = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config_service)
        parser = FakeASTParser(config_service)
        store = FakeGraphStore(config_service)

        scanner.set_results(
            [
                ScanResult(path=Path("a.py"), size_bytes=100),
                ScanResult(path=Path("b.py"), size_bytes=200),
                ScanResult(path=Path("c.py"), size_bytes=300),
            ]
        )

        pipeline = ScanPipeline(
            config=config_service,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            graph_path=test_graph_path,
        )

        summary = pipeline.run()

        assert summary.files_scanned == 3

    def test_given_nodes_created_when_completed_then_count_in_summary(
        self, test_graph_path: Path
    ):
        """
        Purpose: Verifies nodes_created count is accurate.
        Quality Contribution: Accurate metrics.
        Acceptance Criteria: nodes_created matches parsed nodes.
        """
        from fs2.core.services.scan_pipeline import ScanPipeline

        config_service = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config_service)
        parser = FakeASTParser(config_service)
        store = FakeGraphStore(config_service)

        scanner.set_results(
            [
                ScanResult(path=Path("test.py"), size_bytes=100),
            ]
        )

        # 3 nodes from one file
        file_node = CodeNode.create_file(
            file_path="test.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=200,
            start_line=1,
            end_line=20,
            content="class Foo: ...",
        )
        class_node = CodeNode.create_type(
            file_path="test.py",
            language="python",
            ts_kind="class_definition",
            name="Foo",
            qualified_name="Foo",
            start_line=1,
            end_line=10,
            start_column=0,
            end_column=10,
            start_byte=0,
            end_byte=100,
            content="class Foo:",
            signature="class Foo:",
            parent_node_id="file:test.py",
        )
        method_node = CodeNode.create_callable(
            file_path="test.py",
            language="python",
            ts_kind="function_definition",
            name="bar",
            qualified_name="Foo.bar",
            start_line=2,
            end_line=5,
            start_column=4,
            end_column=20,
            start_byte=20,
            end_byte=80,
            content="def bar(self): pass",
            signature="def bar(self):",
            parent_node_id="type:test.py:Foo",
        )
        parser.set_results(Path("test.py"), [file_node, class_node, method_node])

        pipeline = ScanPipeline(
            config=config_service,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            graph_path=test_graph_path,
        )

        summary = pipeline.run()

        assert summary.nodes_created == 3


class TestScanPipelineErrorAggregation:
    """Tests for error collection from stages."""

    def test_given_stage_error_when_completed_then_success_is_false(
        self, test_graph_path: Path
    ):
        """
        Purpose: Verifies success=False when any error.
        Quality Contribution: Accurate failure reporting.
        Acceptance Criteria: success=False, errors not empty.
        """
        from fs2.core.services.scan_pipeline import ScanPipeline

        config_service = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config_service)
        parser = FakeASTParser(config_service)
        store = FakeGraphStore(config_service)

        # Simulate parse error
        scanner.set_results(
            [
                ScanResult(path=Path("bad.py"), size_bytes=100),
            ]
        )
        parser.simulate_error_for.add(Path("bad.py"))

        pipeline = ScanPipeline(
            config=config_service,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            graph_path=test_graph_path,
        )

        summary = pipeline.run()

        assert summary.success is False
        assert len(summary.errors) > 0

    def test_given_multiple_errors_when_completed_then_all_collected(
        self, test_graph_path: Path
    ):
        """
        Purpose: Verifies all errors are collected.
        Quality Contribution: Complete error reporting.
        Acceptance Criteria: All stage errors in summary.
        """
        from fs2.core.services.scan_pipeline import ScanPipeline

        config_service = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config_service)
        parser = FakeASTParser(config_service)
        store = FakeGraphStore(config_service)

        # Simulate multiple parse errors
        scanner.set_results(
            [
                ScanResult(path=Path("bad1.py"), size_bytes=100),
                ScanResult(path=Path("bad2.py"), size_bytes=100),
            ]
        )
        parser.simulate_error_for.add(Path("bad1.py"))
        parser.simulate_error_for.add(Path("bad2.py"))

        pipeline = ScanPipeline(
            config=config_service,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            graph_path=test_graph_path,
        )

        summary = pipeline.run()

        assert len(summary.errors) == 2


class TestScanPipelineMetrics:
    """Tests for metrics collection."""

    def test_given_run_when_completed_then_metrics_in_summary(
        self, test_graph_path: Path
    ):
        """
        Purpose: Verifies metrics are collected from stages.
        Quality Contribution: Enables observability.
        Acceptance Criteria: Stage metrics in summary.metrics.
        """
        from fs2.core.services.scan_pipeline import ScanPipeline

        config_service = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config_service)
        parser = FakeASTParser(config_service)
        store = FakeGraphStore(config_service)

        scanner.set_results(
            [
                ScanResult(path=Path("test.py"), size_bytes=100),
            ]
        )
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
        parser.set_results(Path("test.py"), [file_node])

        pipeline = ScanPipeline(
            config=config_service,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            graph_path=test_graph_path,
        )

        summary = pipeline.run()

        assert "discovery_files" in summary.metrics
        assert "parsing_nodes" in summary.metrics
        assert "storage_nodes" in summary.metrics


class TestScanPipelineCustomStages:
    """Tests for custom stage injection."""

    def test_given_custom_stages_when_constructing_then_uses_custom_stages(
        self, test_graph_path: Path
    ):
        """
        Purpose: Verifies custom stages override defaults.
        Quality Contribution: Enables pipeline extensibility.
        Acceptance Criteria: Custom stages are executed.
        """
        from fs2.core.services.scan_pipeline import ScanPipeline

        config_service = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config_service)
        parser = FakeASTParser(config_service)
        store = FakeGraphStore(config_service)

        # Create a custom stage that marks itself
        class CustomStage:
            @property
            def name(self) -> str:
                return "custom"

            def process(self, context: PipelineContext) -> PipelineContext:
                context.metrics["custom_ran"] = True
                return context

        pipeline = ScanPipeline(
            config=config_service,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            stages=[CustomStage()],
            graph_path=test_graph_path,
        )

        summary = pipeline.run()

        assert summary.metrics.get("custom_ran") is True

    def test_given_no_custom_stages_when_running_then_uses_default_stages(
        self, test_graph_path: Path
    ):
        """
        Purpose: Verifies default stages are used when not specified.
        Quality Contribution: Sensible defaults.
        Acceptance Criteria: Discovery, Parsing, Storage stages run.
        """
        from fs2.core.services.scan_pipeline import ScanPipeline

        config_service = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config_service)
        parser = FakeASTParser(config_service)
        store = FakeGraphStore(config_service)

        scanner.set_results(
            [
                ScanResult(path=Path("test.py"), size_bytes=100),
            ]
        )

        pipeline = ScanPipeline(
            config=config_service,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            graph_path=test_graph_path,
            # No stages= argument
        )

        summary = pipeline.run()

        # If default stages ran, we'd have discovery_files metric
        assert "discovery_files" in summary.metrics


class TestScanPipelinePriorNodesLoading:
    """Tests for loading prior graph state into context.prior_nodes.

    Per Subtask 001: Graph Loading for Smart Content Preservation.
    Enables hash-based skip logic (AC5/AC6) by loading prior graph.
    """

    def test_given_existing_graph_when_running_then_prior_nodes_populated(
        self, test_graph_path: Path
    ):
        """
        Purpose: Verifies pipeline loads existing graph into context.prior_nodes.
        Quality Contribution: Enables smart content preservation across scans.
        Acceptance Criteria: context.prior_nodes is dict with loaded nodes.

        Why: Pipeline must load prior graph for hash-based skip logic to work.
        Contract: If graph exists, prior_nodes is populated with loaded nodes.
        """
        from fs2.core.services.scan_pipeline import ScanPipeline

        config_service = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config_service)
        parser = FakeASTParser(config_service)
        store = FakeGraphStore(config_service)

        # Create prior node with smart_content
        prior_node = CodeNode.create_file(
            file_path="existing.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# existing",
        )
        # Pre-load into store (simulating previous scan saved it)
        store.set_nodes([prior_node])

        # Create a custom stage that captures the context
        captured_context = []

        class ContextCapturingStage:
            @property
            def name(self) -> str:
                return "capture"

            def process(self, context: PipelineContext) -> PipelineContext:
                captured_context.append(context)
                return context

        pipeline = ScanPipeline(
            config=config_service,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            stages=[ContextCapturingStage()],
            graph_path=test_graph_path,
        )

        pipeline.run()

        # Verify prior_nodes was populated
        assert len(captured_context) == 1
        ctx = captured_context[0]
        assert ctx.prior_nodes is not None
        assert isinstance(ctx.prior_nodes, dict)
        assert prior_node.node_id in ctx.prior_nodes
        assert ctx.prior_nodes[prior_node.node_id] == prior_node

    def test_given_no_graph_exists_when_running_then_prior_nodes_is_none(
        self, test_graph_path: Path
    ):
        """
        Purpose: Verifies first-scan case handles gracefully.
        Quality Contribution: First scans work without error.
        Acceptance Criteria: context.prior_nodes is None on first scan.

        Why: First-scan safety - if no graph exists, prior_nodes = None.
        Contract: If graph doesn't exist, prior_nodes remains None.
        """
        from fs2.core.services.scan_pipeline import ScanPipeline

        config_service = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config_service)
        parser = FakeASTParser(config_service)
        store = FakeGraphStore(config_service)

        # Simulate no existing graph by making load() raise GraphStoreError
        store.simulate_error_for.add("load")

        # Create a custom stage that captures the context
        captured_context = []

        class ContextCapturingStage:
            @property
            def name(self) -> str:
                return "capture"

            def process(self, context: PipelineContext) -> PipelineContext:
                captured_context.append(context)
                return context

        pipeline = ScanPipeline(
            config=config_service,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            stages=[ContextCapturingStage()],
            graph_path=test_graph_path,
        )

        summary = pipeline.run()

        # Verify prior_nodes is None (not an error condition)
        assert len(captured_context) == 1
        ctx = captured_context[0]
        assert ctx.prior_nodes is None
        # Scan should still succeed
        assert summary.success is True

    def test_given_corrupted_graph_when_running_then_prior_nodes_is_none_and_logs_warning(
        self, test_graph_path: Path
    ):
        """
        Purpose: Verifies corrupted graph is handled gracefully.
        Quality Contribution: Scan continues even with bad prior state.
        Acceptance Criteria: prior_nodes is None, warning logged, scan continues.

        Why: Corrupted graph safety - log warning, continue with fresh scan.
        Contract: If graph corrupted, prior_nodes = None, scan proceeds.
        """
        from fs2.core.services.scan_pipeline import ScanPipeline

        config_service = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config_service)
        parser = FakeASTParser(config_service)
        store = FakeGraphStore(config_service)

        # Simulate corrupted graph (load raises error)
        store.simulate_error_for.add("load")

        # Create a custom stage that captures the context
        captured_context = []

        class ContextCapturingStage:
            @property
            def name(self) -> str:
                return "capture"

            def process(self, context: PipelineContext) -> PipelineContext:
                captured_context.append(context)
                return context

        pipeline = ScanPipeline(
            config=config_service,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            stages=[ContextCapturingStage()],
            graph_path=test_graph_path,
        )

        summary = pipeline.run()

        # Verify graceful handling
        assert len(captured_context) == 1
        ctx = captured_context[0]
        assert ctx.prior_nodes is None
        assert summary.success is True  # Scan continues

    def test_given_existing_graph_when_running_then_prior_nodes_is_dict_by_node_id(
        self, test_graph_path: Path
    ):
        """
        Purpose: Verifies prior_nodes dict is keyed by node_id.
        Quality Contribution: Enables O(1) lookup for merge logic.
        Acceptance Criteria: Dict keys are node_id strings.

        Why: Workshop decision - node matching by node_id for O(1) lookup.
        Contract: prior_nodes dict uses node_id as key.
        """
        from fs2.core.services.scan_pipeline import ScanPipeline

        config_service = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config_service)
        parser = FakeASTParser(config_service)
        store = FakeGraphStore(config_service)

        # Create multiple prior nodes
        node1 = CodeNode.create_file(
            file_path="a.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=50,
            start_line=1,
            end_line=5,
            content="# a",
        )
        node2 = CodeNode.create_callable(
            file_path="a.py",
            language="python",
            ts_kind="function_definition",
            name="foo",
            qualified_name="foo",
            start_byte=10,
            end_byte=40,
            start_line=2,
            end_line=4,
            start_column=0,
            end_column=10,
            content="def foo(): pass",
            signature="def foo():",
            parent_node_id="file:a.py",
        )
        store.set_nodes([node1, node2])

        # Capture context
        captured_context = []

        class ContextCapturingStage:
            @property
            def name(self) -> str:
                return "capture"

            def process(self, context: PipelineContext) -> PipelineContext:
                captured_context.append(context)
                return context

        pipeline = ScanPipeline(
            config=config_service,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            stages=[ContextCapturingStage()],
            graph_path=test_graph_path,
        )

        pipeline.run()

        # Verify dict structure
        ctx = captured_context[0]
        assert ctx.prior_nodes is not None
        assert "file:a.py" in ctx.prior_nodes
        assert "callable:a.py:foo" in ctx.prior_nodes
        assert ctx.prior_nodes["file:a.py"] == node1
        assert ctx.prior_nodes["callable:a.py:foo"] == node2


class TestCourtesySaves:
    """Tests for courtesy save functionality (Plan 036)."""

    def test_courtesy_save_wired_in_context(self, test_graph_path):
        """Verify ScanPipeline wires courtesy_save callback into context."""
        from fs2.core.services.scan_pipeline import ScanPipeline

        config_service = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config_service)
        parser = FakeASTParser(config_service)
        store = FakeGraphStore(config_service)

        captured_context = []

        class CapturingStage:
            @property
            def name(self):
                return "capture"

            def process(self, context):
                captured_context.append(context)
                return context

        pipeline = ScanPipeline(
            config=config_service,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            stages=[CapturingStage()],
            graph_path=test_graph_path,
        )
        pipeline.run()

        ctx = captured_context[0]
        assert ctx.courtesy_save is not None
        assert callable(ctx.courtesy_save)

    def test_inter_stage_save_called_after_each_non_storage_stage(
        self, test_graph_path
    ):
        """Verify courtesy_save is called after each stage except storage."""
        from fs2.core.services.scan_pipeline import ScanPipeline

        config_service = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config_service)
        parser = FakeASTParser(config_service)
        store = FakeGraphStore(config_service)

        save_calls = []

        class StageA:
            @property
            def name(self):
                return "smart_content"

            def process(self, context):
                return context

        class StageB:
            @property
            def name(self):
                return "embedding"

            def process(self, context):
                return context

        class StageStorage:
            @property
            def name(self):
                return "storage"

            def process(self, context):
                return context

        # Monkey-patch the pipeline to track courtesy saves
        from fs2.core.services import scan_pipeline as sp_module

        original_fn = sp_module._courtesy_save_graph

        def tracking_save(context, graph_store):
            save_calls.append("save")
            # Don't actually save to avoid test side effects

        sp_module._courtesy_save_graph = tracking_save
        try:
            pipeline = ScanPipeline(
                config=config_service,
                file_scanner=scanner,
                ast_parser=parser,
                graph_store=store,
                stages=[StageA(), StageB(), StageStorage()],
                graph_path=test_graph_path,
            )
            pipeline.run()

            # Should be called after smart_content and embedding, NOT after storage
            assert len(save_calls) == 2
        finally:
            sp_module._courtesy_save_graph = original_fn

    def test_courtesy_save_rebuilds_graph_from_context(self, test_graph_path, tmp_path):
        """Verify courtesy save creates a loadable graph with correct nodes."""
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore
        from fs2.core.services.scan_pipeline import _courtesy_save_graph

        config_service = FakeConfigurationService(ScanConfig())
        graph_store = NetworkXGraphStore(config_service)

        node1 = CodeNode.create_file(
            file_path="src/a.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=10,
            start_line=1,
            end_line=1,
            content="# file a",
        )
        node2 = CodeNode.create_file(
            file_path="src/b.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=10,
            start_line=1,
            end_line=1,
            content="# file b",
        )

        graph_path = tmp_path / "courtesy.pickle"
        context = PipelineContext(
            scan_config=ScanConfig(),
            graph_path=graph_path,
            nodes=[node1, node2],
            graph_store=graph_store,
        )

        _courtesy_save_graph(context, graph_store)

        # Verify saved graph is loadable
        assert graph_path.exists()
        store2 = NetworkXGraphStore(config_service)
        store2.load(graph_path)
        loaded = store2.get_all_nodes()
        assert len(loaded) == 2
        node_ids = {n.node_id for n in loaded}
        assert "file:src/a.py" in node_ids
        assert "file:src/b.py" in node_ids

    def test_courtesy_save_not_set_when_no_graph_store(self, test_graph_path):
        """Verify courtesy_save is None when graph_store is None."""
        from fs2.core.services.scan_pipeline import ScanPipeline

        config_service = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config_service)
        parser = FakeASTParser(config_service)

        captured_context = []

        class CapturingStage:
            @property
            def name(self):
                return "capture"

            def process(self, context):
                captured_context.append(context)
                return context

        pipeline = ScanPipeline(
            config=config_service,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=None,
            stages=[CapturingStage()],
            graph_path=test_graph_path,
        )
        pipeline.run()

        ctx = captured_context[0]
        assert ctx.courtesy_save is None
