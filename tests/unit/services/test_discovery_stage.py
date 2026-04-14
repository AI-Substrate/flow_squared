"""Unit tests for DiscoveryStage.

Purpose: Verifies DiscoveryStage wraps FileScanner and populates context.scan_results.
Quality Contribution: Ensures file discovery works correctly in pipeline.

Per Phase 5 Tasks:
- T005: Tests for DiscoveryStage with FakeFileScanner

Per Alignment Brief:
- DiscoveryStage validates file_scanner not None
- Catches FileScannerError, appends to context.errors
"""

from pathlib import Path

import pytest

from fs2.config.objects import ScanConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters.file_scanner_fake import FakeFileScanner
from fs2.core.models.scan_result import ScanResult
from fs2.core.services.pipeline_context import PipelineContext


class TestDiscoveryStageProtocol:
    """Tests for DiscoveryStage protocol compliance."""

    def test_given_discovery_stage_when_checked_then_implements_pipeline_stage(self):
        """
        Purpose: Verifies DiscoveryStage implements PipelineStage protocol.
        Quality Contribution: Ensures stage can be used in pipeline.
        Acceptance Criteria: isinstance check passes.
        """
        from fs2.core.services.pipeline_stage import PipelineStage
        from fs2.core.services.stages.discovery_stage import DiscoveryStage

        stage = DiscoveryStage()
        assert isinstance(stage, PipelineStage)

    def test_given_discovery_stage_when_name_accessed_then_returns_discovery(self):
        """
        Purpose: Verifies stage name is 'discovery'.
        Quality Contribution: Enables logging and metrics identification.
        Acceptance Criteria: name property returns 'discovery'.
        """
        from fs2.core.services.stages.discovery_stage import DiscoveryStage

        stage = DiscoveryStage()
        assert stage.name == "discovery"


class TestDiscoveryStageValidation:
    """Tests for DiscoveryStage precondition validation."""

    def test_given_context_without_file_scanner_when_processing_then_raises_value_error(
        self,
    ):
        """
        Purpose: Verifies stage validates file_scanner presence.
        Quality Contribution: Provides clear error for misconfiguration.
        Acceptance Criteria: ValueError raised with descriptive message.
        """
        from fs2.core.services.stages.discovery_stage import DiscoveryStage

        stage = DiscoveryStage()
        ctx = PipelineContext(scan_config=ScanConfig())
        # file_scanner is None by default

        with pytest.raises(ValueError) as exc_info:
            stage.process(ctx)

        assert "file_scanner" in str(exc_info.value).lower()


class TestDiscoveryStageHappyPath:
    """Tests for DiscoveryStage normal operation."""

    def test_given_file_scanner_when_processing_then_calls_scan(self):
        """
        Purpose: Verifies stage calls file_scanner.scan().
        Quality Contribution: Ensures adapter is invoked.
        Acceptance Criteria: scan() recorded in call history.
        """
        from fs2.core.services.stages.discovery_stage import DiscoveryStage

        config_service = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config_service)

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.file_scanner = scanner

        stage = DiscoveryStage()
        stage.process(ctx)

        assert len(scanner.call_history) > 0
        assert scanner.call_history[0]["method"] == "scan"

    def test_given_file_scanner_returns_results_when_processing_then_populates_scan_results(
        self,
    ):
        """
        Purpose: Verifies stage populates context.scan_results.
        Quality Contribution: Ensures downstream stages have input.
        Acceptance Criteria: context.scan_results contains scanner output.
        """
        from fs2.core.services.stages.discovery_stage import DiscoveryStage

        config_service = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config_service)
        scanner.set_results(
            [
                ScanResult(path=Path("src/main.py"), size_bytes=1000),
                ScanResult(path=Path("src/utils.py"), size_bytes=500),
            ]
        )

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.file_scanner = scanner

        stage = DiscoveryStage()
        result_ctx = stage.process(ctx)

        assert len(result_ctx.scan_results) == 2
        assert result_ctx.scan_results[0].path == Path("src/main.py")
        assert result_ctx.scan_results[1].path == Path("src/utils.py")

    def test_given_file_scanner_when_processing_then_returns_context(self):
        """
        Purpose: Verifies stage returns the context.
        Quality Contribution: Enables pipeline chaining.
        Acceptance Criteria: process() returns the context.
        """
        from fs2.core.services.stages.discovery_stage import DiscoveryStage

        config_service = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config_service)

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.file_scanner = scanner

        stage = DiscoveryStage()
        result = stage.process(ctx)

        assert result is ctx


class TestDiscoveryStageErrorHandling:
    """Tests for DiscoveryStage error handling."""

    def test_given_scanner_raises_error_when_processing_then_appends_to_errors(self):
        """
        Purpose: Verifies FileScannerError is caught and collected.
        Quality Contribution: Pipeline continues despite scanner errors.
        Acceptance Criteria: Error message in context.errors, no exception raised.
        """
        from fs2.core.adapters.exceptions import FileScannerError
        from fs2.core.adapters.file_scanner import FileScanner
        from fs2.core.services.stages.discovery_stage import DiscoveryStage

        # Create a scanner that raises on scan()
        class FailingScanner(FileScanner):
            def scan(self):
                raise FileScannerError("Permission denied on /etc")

            def should_ignore(self, path):
                return False

            @property
            def missing_paths(self):
                return []

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.file_scanner = FailingScanner()

        stage = DiscoveryStage()
        result_ctx = stage.process(ctx)

        assert len(result_ctx.errors) == 1
        assert "Permission denied" in result_ctx.errors[0]
        assert result_ctx.scan_results == []  # Empty due to error


class TestDiscoveryStageMetrics:
    """Tests for DiscoveryStage metrics recording."""

    def test_given_successful_scan_when_processing_then_records_file_count(self):
        """
        Purpose: Verifies stage records file count in metrics.
        Quality Contribution: Enables pipeline observability.
        Acceptance Criteria: metrics['discovery_files'] set.
        """
        from fs2.core.services.stages.discovery_stage import DiscoveryStage

        config_service = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config_service)
        scanner.set_results(
            [
                ScanResult(path=Path("a.py"), size_bytes=100),
                ScanResult(path=Path("b.py"), size_bytes=200),
                ScanResult(path=Path("c.py"), size_bytes=300),
            ]
        )

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.file_scanner = scanner

        stage = DiscoveryStage()
        result_ctx = stage.process(ctx)

        assert "discovery_files" in result_ctx.metrics
        assert result_ctx.metrics["discovery_files"] == 3
