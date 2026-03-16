"""Unit tests for EmbeddingStage.

Purpose: Verifies EmbeddingStage integrates embedding generation in the pipeline.
Quality Contribution: Ensures embeddings are preserved, generated, and measured correctly.

Per Phase 4 Tasks:
- T004: Tests for EmbeddingStage merge + processing behavior
"""

from dataclasses import replace

from fs2.config.objects import ScanConfig
from fs2.core.models.code_node import CodeNode
from fs2.core.services.pipeline_context import PipelineContext


def _make_file_node(
    file_path: str = "test.py",
    content: str = "# test",
    embedding: tuple[tuple[float, ...], ...] | None = None,
    smart_content_embedding: tuple[tuple[float, ...], ...] | None = None,
    embedding_hash: str | None = None,
) -> CodeNode:
    """Helper to create a file CodeNode with optional embedding fields."""
    node = CodeNode.create_file(
        file_path=file_path,
        language="python",
        ts_kind="module",
        start_byte=0,
        end_byte=len(content),
        start_line=1,
        end_line=content.count("\n") + 1,
        content=content,
    )
    if embedding is not None or smart_content_embedding is not None or embedding_hash:
        node = replace(
            node,
            embedding=embedding,
            smart_content_embedding=smart_content_embedding,
            embedding_hash=embedding_hash,
        )
    return node


class FakeEmbeddingService:
    """Async fake embedding service for stage tests."""

    def __init__(self, result: dict):
        self.result = result
        self.calls: list[dict] = []

    def get_metadata(self) -> dict:
        return {
            "embedding_model": "fake-model",
            "embedding_dimensions": 1024,
            "chunk_params": {"code": {"max_tokens": 400, "overlap_tokens": 50}},
        }

    async def process_batch(self, nodes, progress_callback=None, courtesy_save=None):
        self.calls.append(
            {
                "nodes": nodes,
                "progress_callback": progress_callback,
            }
        )
        return self.result


class TestEmbeddingStageMergeLogic:
    """Tests for merging prior embeddings from context.prior_nodes."""

    def test_given_matching_embedding_hash_when_merging_then_copies_embeddings(self):
        """
        Purpose: Verifies merge copies embeddings when embedding_hash matches.
        Quality Contribution: Enables hash-based skip for unchanged nodes.
        Acceptance Criteria: Fresh node gets prior embedding + hash.

        Why: embedding_hash tracks content_hash at embed time.
        Contract: If prior.embedding_hash == node.content_hash, copy embeddings.
        """
        from fs2.core.services.stages.embedding_stage import EmbeddingStage

        fresh_node = _make_file_node(
            file_path="unchanged.py",
            content="# unchanged",
        )

        prior_node = _make_file_node(
            file_path="unchanged.py",
            content="# unchanged",
            embedding=((0.1, 0.2),),
            smart_content_embedding=((0.9, 0.8),),
            embedding_hash=fresh_node.content_hash,
        )

        context = PipelineContext(scan_config=ScanConfig())
        context.nodes = [fresh_node]
        context.prior_nodes = {prior_node.node_id: prior_node}

        stage = EmbeddingStage()
        merged = stage._merge_prior_embeddings(context.nodes, context.prior_nodes)

        assert merged[0].embedding == ((0.1, 0.2),)
        assert merged[0].smart_content_embedding == ((0.9, 0.8),)
        assert merged[0].embedding_hash == fresh_node.content_hash

    def test_given_mismatched_hash_when_merging_then_skips_copy(self):
        """
        Purpose: Verifies merge skips copy when embedding_hash mismatches.
        Quality Contribution: Changed content gets re-embedded.
        Acceptance Criteria: Embedding remains None on fresh node.

        Why: Mismatch indicates embeddings are stale.
        Contract: If hashes differ, do not copy embeddings.
        """
        from fs2.core.services.stages.embedding_stage import EmbeddingStage

        fresh_node = _make_file_node(
            file_path="changed.py",
            content="# new content",
        )

        prior_node = _make_file_node(
            file_path="changed.py",
            content="# old content",
            embedding=((0.1, 0.2),),
            embedding_hash="old_hash",
        )

        context = PipelineContext(scan_config=ScanConfig())
        context.nodes = [fresh_node]
        context.prior_nodes = {prior_node.node_id: prior_node}

        stage = EmbeddingStage()
        merged = stage._merge_prior_embeddings(context.nodes, context.prior_nodes)

        assert merged[0].embedding is None
        assert merged[0].embedding_hash is None


class TestEmbeddingStageProcess:
    """Tests for EmbeddingStage.process() behavior."""

    def test_given_no_service_when_processing_then_skips_gracefully(self):
        """
        Purpose: Verifies stage skips when embedding_service is None.
        Quality Contribution: Enables --no-embeddings workflow.
        Acceptance Criteria: Metrics set to zero and preserved count reported.

        Why: EmbeddingStage should not fail when service is disabled.
        Contract: No service => no enrichment, no errors.
        """
        from fs2.core.services.stages.embedding_stage import EmbeddingStage

        preserved_node = _make_file_node(
            file_path="preserved.py",
            content="# preserved",
            embedding=((0.1, 0.2),),
            embedding_hash="hash",
        )

        context = PipelineContext(scan_config=ScanConfig())
        context.nodes = [preserved_node]
        context.embedding_service = None

        stage = EmbeddingStage()
        result = stage.process(context)

        assert result.metrics["embedding_enriched"] == 0
        assert result.metrics["embedding_preserved"] == 1
        assert result.metrics["embedding_errors"] == 0

    def test_given_service_when_processing_then_overlays_results(self):
        """
        Purpose: Verifies stage runs async process_batch and overlays results.
        Quality Contribution: Ensures embeddings are applied to context nodes.
        Acceptance Criteria: Updated nodes returned and metrics set.

        Why: EmbeddingStage bridges sync pipeline to async service.
        Contract: Results dict replaces matching nodes by node_id.
        """
        from fs2.core.services.stages.embedding_stage import EmbeddingStage

        node = _make_file_node(file_path="a.py", content="# content")
        updated_node = replace(
            node,
            embedding=((0.1, 0.2),),
            embedding_hash=node.content_hash,
        )

        fake_service = FakeEmbeddingService(
            {
                "processed": 1,
                "skipped": 0,
                "errors": [],
                "total": 1,
                "results": {node.node_id: updated_node},
            }
        )

        context = PipelineContext(scan_config=ScanConfig())
        context.nodes = [node]
        context.embedding_service = fake_service
        context.embedding_progress_callback = lambda processed, total, skipped: None

        stage = EmbeddingStage()
        result = stage.process(context)

        assert result.nodes[0].embedding == ((0.1, 0.2),)
        assert result.metrics["embedding_enriched"] == 1
        assert result.metrics["embedding_preserved"] == 0
        assert result.metrics["embedding_errors"] == 0
        assert (
            fake_service.calls[0]["progress_callback"]
            is context.embedding_progress_callback
        )
