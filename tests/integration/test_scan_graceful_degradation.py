"""Integration tests for scan graceful degradation when LSP is unavailable.

Per AC15: Scan completes without LSP servers
Per AC16: WARNING logged when LSP extraction skipped (DYK-4)

These tests verify that fs2 scan works correctly even when:
- LSP servers are not installed
- --no-lsp flag is used
- LSP servers crash or timeout
"""

import logging

from fs2.config.objects import ScanConfig
from fs2.core.services.pipeline_context import PipelineContext
from fs2.core.services.stages.relationship_extraction_stage import (
    RelationshipExtractionStage,
)


class TestGracefulDegradationNoLspAdapter:
    """Tests for graceful degradation when lsp_adapter=None."""

    def test_given_no_lsp_adapter_when_stage_processes_then_warning_logged(
        self, caplog
    ) -> None:
        """Per DYK-4: WARNING logged when LSP is unavailable."""
        stage = RelationshipExtractionStage(lsp_adapter=None)
        ctx = _create_minimal_context()

        with caplog.at_level(logging.WARNING):
            stage.process(ctx)

        # Should log warning about LSP being disabled
        assert any("lsp" in record.message.lower() for record in caplog.records)

    def test_given_no_lsp_adapter_when_stage_processes_then_text_extraction_works(
        self,
    ) -> None:
        """Per AC15: Text-based extraction continues without LSP."""
        stage = RelationshipExtractionStage(lsp_adapter=None)
        ctx = _create_context_with_reference(
            content="See `file:src/app.py` for details",
            target_path="src/app.py",
        )

        result = stage.process(ctx)

        # Text extraction should still work
        assert result.relationships is not None
        assert len(result.relationships) >= 1
        assert any(e.target_node_id == "file:src/app.py" for e in result.relationships)

    def test_given_no_lsp_adapter_when_stage_processes_then_no_errors(self) -> None:
        """Per AC16: No errors appended to context.errors."""
        stage = RelationshipExtractionStage(lsp_adapter=None)
        ctx = _create_minimal_context()

        result = stage.process(ctx)

        # No errors from missing LSP
        assert len(result.errors) == 0

    def test_given_no_lsp_adapter_when_stage_processes_then_metrics_recorded(
        self,
    ) -> None:
        """Metrics are still recorded even without LSP."""
        stage = RelationshipExtractionStage(lsp_adapter=None)
        ctx = _create_minimal_context()

        result = stage.process(ctx)

        assert "relationship_extraction_count" in result.metrics
        assert isinstance(result.metrics["relationship_extraction_count"], int)


class TestGracefulDegradationPipeline:
    """Tests for graceful degradation at the pipeline level.

    Note: These tests use the RelationshipExtractionStage directly
    rather than full pipeline to avoid complex setup. The stage-level
    tests above verify the core graceful degradation behavior.
    """

    def test_given_stage_in_isolation_when_no_lsp_then_returns_context(self) -> None:
        """Stage returns context even without LSP (simulates pipeline behavior)."""
        stage = RelationshipExtractionStage(lsp_adapter=None)
        ctx = _create_context_with_reference(
            content="See `file:src/app.py` for the main entry point",
            target_path="src/app.py",
        )

        result = stage.process(ctx)

        # Stage completes and returns context
        assert result is ctx
        # Relationships extracted from text patterns
        assert result.relationships is not None
        assert len(result.relationships) >= 1

    def test_given_multiple_text_refs_when_no_lsp_then_all_extracted(self) -> None:
        """Multiple text references still work without LSP."""
        from fs2.core.models.code_node import CodeNode

        ctx = PipelineContext(scan_config=ScanConfig())

        # Source with multiple references
        source = CodeNode.create_file(
            file_path="README.md",
            language="markdown",
            ts_kind="document",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=3,
            content="See `file:src/app.py` and `file:src/utils.py` for details",
        )

        # Target nodes
        app = CodeNode.create_file(
            file_path="src/app.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=0,
            start_line=1,
            end_line=1,
            content="",
        )
        utils = CodeNode.create_file(
            file_path="src/utils.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=0,
            start_line=1,
            end_line=1,
            content="",
        )

        ctx.nodes = [source, app, utils]

        stage = RelationshipExtractionStage(lsp_adapter=None)
        result = stage.process(ctx)

        # Both targets should be found
        targets = {e.target_node_id for e in result.relationships}
        assert "file:src/app.py" in targets
        assert "file:src/utils.py" in targets


class TestGracefulDegradationWarningContent:
    """Tests for the content of the warning message."""

    def test_given_no_lsp_when_processing_then_warning_mentions_text_fallback(
        self, caplog
    ) -> None:
        """Warning message explains that text-based extraction still works."""
        stage = RelationshipExtractionStage(lsp_adapter=None)
        ctx = _create_minimal_context()

        with caplog.at_level(logging.WARNING):
            stage.process(ctx)

        # Find the LSP warning
        lsp_warnings = [r for r in caplog.records if "lsp" in r.message.lower()]
        assert len(lsp_warnings) >= 1

        # Warning should mention text-based extraction
        warning_msg = lsp_warnings[0].message.lower()
        assert (
            "text" in warning_msg
            or "pattern" in warning_msg
            or "filename" in warning_msg
        )


# ============ Helper Functions ============


def _create_minimal_context() -> PipelineContext:
    """Create minimal PipelineContext for testing."""
    from fs2.core.models.code_node import CodeNode

    ctx = PipelineContext(scan_config=ScanConfig())
    node = CodeNode.create_file(
        file_path="test.py",
        language="python",
        ts_kind="module",
        start_byte=0,
        end_byte=10,
        start_line=1,
        end_line=1,
        content="# test",
    )
    ctx.nodes = [node]
    return ctx


def _create_context_with_reference(content: str, target_path: str) -> PipelineContext:
    """Create PipelineContext with a node that references another file."""
    from fs2.core.models.code_node import CodeNode

    ctx = PipelineContext(scan_config=ScanConfig())

    # Source node with reference
    source = CodeNode.create_file(
        file_path="README.md",
        language="markdown",
        ts_kind="document",
        start_byte=0,
        end_byte=len(content),
        start_line=1,
        end_line=1,
        content=content,
    )

    # Target node (so validation passes)
    target = CodeNode.create_file(
        file_path=target_path,
        language="python",
        ts_kind="module",
        start_byte=0,
        end_byte=0,
        start_line=1,
        end_line=1,
        content="",
    )

    ctx.nodes = [source, target]
    return ctx
