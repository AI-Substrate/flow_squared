"""Unit tests for RelationshipExtractionStage.

Purpose: Verifies RelationshipExtractionStage extracts cross-file relationships
         and populates context.relationships with CodeEdge instances.

Quality Contribution: Ensures relationship extraction integrates correctly
                      with pipeline and produces expected CodeEdge outputs.

Per Phase 8 Tasks:
- T002: Write failing tests for RelationshipExtractionStage (TDD RED)
- T003: Implementation to make these tests pass (TDD GREEN)

Per Alignment Brief:
- Stage position: After ParsingStage, before SmartContentStage
- Orchestrates: NodeIdDetector, RawFilenameDetector, LspAdapter (optional)
- Populates: context.relationships with list[CodeEdge]
- Graceful degradation: Logs WARNING when lsp_adapter=None (DYK-4)
- Deduplication: Reuses TextReferenceExtractor._deduplicate_edges() (DYK-5)

Test Naming: Given-When-Then format
"""

import logging

from fs2.config.objects import ScanConfig
from fs2.core.models.code_node import CodeNode
from fs2.core.services.pipeline_context import PipelineContext


class TestRelationshipExtractionStageProtocol:
    """Tests for RelationshipExtractionStage protocol compliance."""

    def test_given_stage_when_checked_then_implements_pipeline_stage(self):
        """
        Purpose: Verifies RelationshipExtractionStage implements PipelineStage protocol.
        Quality Contribution: Ensures stage can be used in pipeline.
        Acceptance Criteria: isinstance check passes.
        """
        from fs2.core.services.pipeline_stage import PipelineStage
        from fs2.core.services.stages.relationship_extraction_stage import (
            RelationshipExtractionStage,
        )

        stage = RelationshipExtractionStage()
        assert isinstance(stage, PipelineStage)

    def test_given_stage_when_name_accessed_then_returns_relationship_extraction(self):
        """
        Purpose: Verifies stage name is 'relationship_extraction'.
        Quality Contribution: Enables logging and metrics identification.
        Acceptance Criteria: name property returns 'relationship_extraction'.
        """
        from fs2.core.services.stages.relationship_extraction_stage import (
            RelationshipExtractionStage,
        )

        stage = RelationshipExtractionStage()
        assert stage.name == "relationship_extraction"


class TestRelationshipExtractionStageGracefulDegradation:
    """Tests for graceful degradation when LSP is unavailable (DYK-4)."""

    def test_given_no_lsp_adapter_when_processing_then_logs_warning(self, caplog):
        """
        Purpose: Verifies stage logs WARNING when lsp_adapter=None (DYK-4).
        Quality Contribution: User visibility when LSP extraction is skipped.
        Acceptance Criteria: WARNING logged with "LSP" in message.
        """
        from fs2.core.services.stages.relationship_extraction_stage import (
            RelationshipExtractionStage,
        )

        # Create stage without LSP adapter
        stage = RelationshipExtractionStage(lsp_adapter=None)

        # Create minimal context with a node
        ctx = _create_context_with_node()

        with caplog.at_level(logging.WARNING):
            stage.process(ctx)

        # Should log warning about LSP being disabled
        assert any("lsp" in record.message.lower() for record in caplog.records)

    def test_given_no_lsp_adapter_when_processing_then_still_extracts_text_refs(self):
        """
        Purpose: Verifies text extraction works even when LSP is disabled.
        Quality Contribution: Scan completes without LSP servers (AC15).
        Acceptance Criteria: NodeId/filename edges still detected.
        """
        from fs2.core.services.stages.relationship_extraction_stage import (
            RelationshipExtractionStage,
        )

        stage = RelationshipExtractionStage(lsp_adapter=None)

        # Create node with explicit node_id reference in content
        # Include target node for validation
        ctx = _create_context_with_node(
            content="See `file:src/auth.py` for details",
            target_files=["src/auth.py"],
        )

        result = stage.process(ctx)

        # Should still populate relationships from text extractors
        assert result.relationships is not None
        assert len(result.relationships) > 0

    def test_given_no_lsp_adapter_when_processing_then_scan_completes(self):
        """
        Purpose: Verifies scan completes successfully without LSP (AC16).
        Quality Contribution: No crash when LSP servers unavailable.
        Acceptance Criteria: No errors appended to context.errors.
        """
        from fs2.core.services.stages.relationship_extraction_stage import (
            RelationshipExtractionStage,
        )

        stage = RelationshipExtractionStage(lsp_adapter=None)
        ctx = _create_context_with_node()

        result = stage.process(ctx)

        # No errors from missing LSP
        assert len(result.errors) == 0


class TestRelationshipExtractionStageHappyPath:
    """Tests for RelationshipExtractionStage normal operation."""

    def test_given_nodes_when_processing_then_relationships_populated(self):
        """
        Purpose: Verifies stage populates context.relationships.
        Quality Contribution: Core functionality test.
        Acceptance Criteria: context.relationships is not None after processing.
        """
        from fs2.core.services.stages.relationship_extraction_stage import (
            RelationshipExtractionStage,
        )

        stage = RelationshipExtractionStage()
        ctx = _create_context_with_node(content="Reference to `file:src/other.py` here")

        result = stage.process(ctx)

        assert result.relationships is not None
        assert isinstance(result.relationships, list)

    def test_given_empty_nodes_when_processing_then_empty_relationships(self):
        """
        Purpose: Verifies stage handles empty nodes gracefully.
        Quality Contribution: Edge case handling.
        Acceptance Criteria: context.relationships is empty list.
        """
        from fs2.core.services.stages.relationship_extraction_stage import (
            RelationshipExtractionStage,
        )

        stage = RelationshipExtractionStage()
        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.nodes = []

        result = stage.process(ctx)

        assert result.relationships is not None
        assert result.relationships == []

    def test_given_node_with_nodeid_ref_when_processing_then_edge_created(self):
        """
        Purpose: Verifies explicit node_id patterns create edges.
        Quality Contribution: NodeIdDetector integration test.
        Acceptance Criteria: Edge with confidence 1.0 created.
        """
        from fs2.core.services.stages.relationship_extraction_stage import (
            RelationshipExtractionStage,
        )

        stage = RelationshipExtractionStage()
        ctx = _create_context_with_node(
            source_file="file:README.md",
            content="Check `file:src/auth.py` for authentication",
            target_files=["src/auth.py"],
        )

        result = stage.process(ctx)

        assert len(result.relationships) >= 1
        edge = result.relationships[0]
        assert edge.target_node_id == "file:src/auth.py"
        assert edge.confidence == 1.0

    def test_given_node_with_filename_ref_when_processing_then_edge_created(self):
        """
        Purpose: Verifies raw filename patterns create edges.
        Quality Contribution: RawFilenameDetector integration test.
        Acceptance Criteria: Edge with confidence 0.4-0.5 created.
        """
        from fs2.core.services.stages.relationship_extraction_stage import (
            RelationshipExtractionStage,
        )

        stage = RelationshipExtractionStage()
        ctx = _create_context_with_node(
            source_file="file:README.md",
            content="Check auth_handler.py for details",
            target_files=["auth_handler.py"],
        )

        result = stage.process(ctx)

        assert len(result.relationships) >= 1
        # Filename detection has lower confidence
        edge = result.relationships[0]
        assert "auth_handler.py" in edge.target_node_id
        assert 0.4 <= edge.confidence <= 0.5


class TestRelationshipExtractionStageMetrics:
    """Tests for stage metrics recording."""

    def test_given_edges_extracted_when_processing_then_records_count_metric(self):
        """
        Purpose: Verifies stage records relationship_extraction_count metric.
        Quality Contribution: Enables monitoring and debugging.
        Acceptance Criteria: Metric present in context.metrics.
        """
        from fs2.core.services.stages.relationship_extraction_stage import (
            RelationshipExtractionStage,
        )

        stage = RelationshipExtractionStage()
        ctx = _create_context_with_node(
            content="See `file:src/auth.py` for details",
            target_files=["src/auth.py"],
        )

        result = stage.process(ctx)

        assert "relationship_extraction_count" in result.metrics
        assert result.metrics["relationship_extraction_count"] >= 1


class TestRelationshipExtractionStageReturnsContext:
    """Tests for context return behavior."""

    def test_given_stage_when_processing_then_returns_context(self):
        """
        Purpose: Verifies stage returns context for pipeline chaining.
        Quality Contribution: Pipeline integration correctness.
        Acceptance Criteria: Same context object returned.
        """
        from fs2.core.services.stages.relationship_extraction_stage import (
            RelationshipExtractionStage,
        )

        stage = RelationshipExtractionStage()
        ctx = _create_context_with_node()

        result = stage.process(ctx)

        assert result is ctx  # Same object, mutated


# ============ Helper Functions ============


def _create_context_with_node(
    source_file: str = "file:README.md",
    content: str = "Some content",
    target_files: list[str] | None = None,
) -> PipelineContext:
    """Create a minimal PipelineContext with one CodeNode for testing.

    Args:
        source_file: Node ID for the source file.
        content: Content string for the node.
        target_files: Optional list of target file paths to add as nodes.
                      This enables target validation to pass for these files.

    Returns:
        PipelineContext with one node (plus optional target nodes).
    """
    ctx = PipelineContext(scan_config=ScanConfig())
    # Use factory method which handles all required fields
    node = CodeNode.create_file(
        file_path=source_file.replace("file:", "")
        if source_file.startswith("file:")
        else "README.md",
        language="markdown",
        ts_kind="document",
        start_byte=0,
        end_byte=len(content),
        start_line=1,
        end_line=content.count("\n") + 1,
        content=content,
    )
    ctx.nodes = [node]

    # Add target nodes for validation
    if target_files:
        for target_path in target_files:
            target_node = CodeNode.create_file(
                file_path=target_path,
                language="python",
                ts_kind="module",
                start_byte=0,
                end_byte=0,
                start_line=1,
                end_line=1,
                content="",
            )
            ctx.nodes.append(target_node)

    return ctx
