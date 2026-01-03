"""Unit tests for ParsingStage.

Purpose: Verifies ParsingStage wraps ASTParser and populates context.nodes.
Quality Contribution: Ensures AST parsing works correctly in pipeline.

Per Phase 5 Tasks:
- T007: Tests for ParsingStage with FakeASTParser

Per Alignment Brief:
- ParsingStage validates ast_parser not None
- Iterates scan_results, calls ast_parser.parse() per file
- Catches ASTParserError per file, appends to context.errors, continues
"""

from pathlib import Path

import pytest

from fs2.config.objects import ScanConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters.ast_parser_fake import FakeASTParser
from fs2.core.models.code_node import CodeNode
from fs2.core.models.scan_result import ScanResult
from fs2.core.services.pipeline_context import PipelineContext


class TestParsingStageProtocol:
    """Tests for ParsingStage protocol compliance."""

    def test_given_parsing_stage_when_checked_then_implements_pipeline_stage(self):
        """
        Purpose: Verifies ParsingStage implements PipelineStage protocol.
        Quality Contribution: Ensures stage can be used in pipeline.
        Acceptance Criteria: isinstance check passes.
        """
        from fs2.core.services.pipeline_stage import PipelineStage
        from fs2.core.services.stages.parsing_stage import ParsingStage

        stage = ParsingStage()
        assert isinstance(stage, PipelineStage)

    def test_given_parsing_stage_when_name_accessed_then_returns_parsing(self):
        """
        Purpose: Verifies stage name is 'parsing'.
        Quality Contribution: Enables logging and metrics identification.
        Acceptance Criteria: name property returns 'parsing'.
        """
        from fs2.core.services.stages.parsing_stage import ParsingStage

        stage = ParsingStage()
        assert stage.name == "parsing"


class TestParsingStageValidation:
    """Tests for ParsingStage precondition validation."""

    def test_given_context_without_ast_parser_when_processing_then_raises_value_error(
        self,
    ):
        """
        Purpose: Verifies stage validates ast_parser presence.
        Quality Contribution: Provides clear error for misconfiguration.
        Acceptance Criteria: ValueError raised with descriptive message.
        """
        from fs2.core.services.stages.parsing_stage import ParsingStage

        stage = ParsingStage()
        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.scan_results = [ScanResult(path=Path("test.py"), size_bytes=100)]
        # ast_parser is None by default

        with pytest.raises(ValueError) as exc_info:
            stage.process(ctx)

        assert "ast_parser" in str(exc_info.value).lower()


class TestParsingStageHappyPath:
    """Tests for ParsingStage normal operation."""

    def test_given_scan_results_when_processing_then_calls_parse_for_each(self):
        """
        Purpose: Verifies stage calls ast_parser.parse() for each file.
        Quality Contribution: Ensures all files are parsed.
        Acceptance Criteria: parse() called once per scan_result.
        """
        from fs2.core.services.stages.parsing_stage import ParsingStage

        config_service = FakeConfigurationService(ScanConfig())
        parser = FakeASTParser(config_service)

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.ast_parser = parser
        ctx.scan_results = [
            ScanResult(path=Path("a.py"), size_bytes=100),
            ScanResult(path=Path("b.py"), size_bytes=200),
        ]

        stage = ParsingStage()
        stage.process(ctx)

        parse_calls = [c for c in parser.call_history if c["method"] == "parse"]
        assert len(parse_calls) == 2

    def test_given_parser_returns_nodes_when_processing_then_populates_nodes(self):
        """
        Purpose: Verifies stage populates context.nodes.
        Quality Contribution: Ensures downstream stages have input.
        Acceptance Criteria: context.nodes contains parsed nodes.
        """
        from fs2.core.services.stages.parsing_stage import ParsingStage

        config_service = FakeConfigurationService(ScanConfig())
        parser = FakeASTParser(config_service)

        # Configure parser results
        file_node = CodeNode.create_file(
            file_path="src/main.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# main",
        )
        parser.set_results(Path("src/main.py"), [file_node])

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.ast_parser = parser
        ctx.scan_results = [ScanResult(path=Path("src/main.py"), size_bytes=100)]

        stage = ParsingStage()
        result_ctx = stage.process(ctx)

        assert len(result_ctx.nodes) == 1
        assert result_ctx.nodes[0].node_id == "file:src/main.py"

    def test_given_multiple_files_when_processing_then_accumulates_all_nodes(self):
        """
        Purpose: Verifies nodes from all files are accumulated.
        Quality Contribution: Ensures complete code graph.
        Acceptance Criteria: All nodes from all files in context.nodes.
        """
        from fs2.core.services.stages.parsing_stage import ParsingStage

        config_service = FakeConfigurationService(ScanConfig())
        parser = FakeASTParser(config_service)

        # Configure parser results for two files
        file1 = CodeNode.create_file(
            file_path="a.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=50,
            start_line=1,
            end_line=5,
            content="# a",
        )
        file2 = CodeNode.create_file(
            file_path="b.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=60,
            start_line=1,
            end_line=6,
            content="# b",
        )
        parser.set_results(Path("a.py"), [file1])
        parser.set_results(Path("b.py"), [file2])

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.ast_parser = parser
        ctx.scan_results = [
            ScanResult(path=Path("a.py"), size_bytes=50),
            ScanResult(path=Path("b.py"), size_bytes=60),
        ]

        stage = ParsingStage()
        result_ctx = stage.process(ctx)

        assert len(result_ctx.nodes) == 2

    def test_given_parser_when_processing_then_returns_context(self):
        """
        Purpose: Verifies stage returns the context.
        Quality Contribution: Enables pipeline chaining.
        Acceptance Criteria: process() returns the context.
        """
        from fs2.core.services.stages.parsing_stage import ParsingStage

        config_service = FakeConfigurationService(ScanConfig())
        parser = FakeASTParser(config_service)

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.ast_parser = parser
        ctx.scan_results = []

        stage = ParsingStage()
        result = stage.process(ctx)

        assert result is ctx


class TestParsingStageErrorHandling:
    """Tests for ParsingStage per-file error handling."""

    def test_given_parser_error_for_one_file_when_processing_then_continues_others(
        self,
    ):
        """
        Purpose: Verifies ASTParserError for one file doesn't stop others.
        Quality Contribution: Pipeline is resilient to partial failures.
        Acceptance Criteria: Other files still parsed, error collected.
        """
        from fs2.core.services.stages.parsing_stage import ParsingStage

        config_service = FakeConfigurationService(ScanConfig())
        parser = FakeASTParser(config_service)

        # Set up: good.py succeeds, bad.py fails
        good_node = CodeNode.create_file(
            file_path="good.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=50,
            start_line=1,
            end_line=5,
            content="# good",
        )
        parser.set_results(Path("good.py"), [good_node])
        parser.simulate_error_for.add(Path("bad.py"))

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.ast_parser = parser
        ctx.scan_results = [
            ScanResult(path=Path("bad.py"), size_bytes=100),
            ScanResult(path=Path("good.py"), size_bytes=50),
        ]

        stage = ParsingStage()
        result_ctx = stage.process(ctx)

        # good.py parsed successfully
        assert len(result_ctx.nodes) == 1
        assert result_ctx.nodes[0].node_id == "file:good.py"

        # Error collected for bad.py
        assert len(result_ctx.errors) == 1
        assert "bad.py" in result_ctx.errors[0]

    def test_given_all_files_fail_when_processing_then_collects_all_errors(self):
        """
        Purpose: Verifies all errors are collected.
        Quality Contribution: Complete error reporting.
        Acceptance Criteria: All errors in context.errors.
        """
        from fs2.core.services.stages.parsing_stage import ParsingStage

        config_service = FakeConfigurationService(ScanConfig())
        parser = FakeASTParser(config_service)
        parser.simulate_error_for.add(Path("a.py"))
        parser.simulate_error_for.add(Path("b.py"))

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.ast_parser = parser
        ctx.scan_results = [
            ScanResult(path=Path("a.py"), size_bytes=100),
            ScanResult(path=Path("b.py"), size_bytes=100),
        ]

        stage = ParsingStage()
        result_ctx = stage.process(ctx)

        assert len(result_ctx.errors) == 2
        assert result_ctx.nodes == []


class TestParsingStageMetrics:
    """Tests for ParsingStage metrics recording."""

    def test_given_successful_parsing_when_processing_then_records_node_count(self):
        """
        Purpose: Verifies stage records node count in metrics.
        Quality Contribution: Enables pipeline observability.
        Acceptance Criteria: metrics['parsing_nodes'] set.
        """
        from fs2.core.services.stages.parsing_stage import ParsingStage

        config_service = FakeConfigurationService(ScanConfig())
        parser = FakeASTParser(config_service)

        # Set up nodes
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
        parser.set_results(Path("test.py"), [file_node, class_node])

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.ast_parser = parser
        ctx.scan_results = [ScanResult(path=Path("test.py"), size_bytes=100)]

        stage = ParsingStage()
        result_ctx = stage.process(ctx)

        assert "parsing_nodes" in result_ctx.metrics
        assert result_ctx.metrics["parsing_nodes"] == 2

    def test_given_parsing_errors_when_processing_then_records_error_count(self):
        """
        Purpose: Verifies stage records error count in metrics.
        Quality Contribution: Enables error tracking.
        Acceptance Criteria: metrics['parsing_errors'] set.
        """
        from fs2.core.services.stages.parsing_stage import ParsingStage

        config_service = FakeConfigurationService(ScanConfig())
        parser = FakeASTParser(config_service)
        parser.simulate_error_for.add(Path("bad.py"))

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.ast_parser = parser
        ctx.scan_results = [ScanResult(path=Path("bad.py"), size_bytes=100)]

        stage = ParsingStage()
        result_ctx = stage.process(ctx)

        assert "parsing_errors" in result_ctx.metrics
        assert result_ctx.metrics["parsing_errors"] == 1
