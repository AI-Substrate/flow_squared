"""Unit tests for embedding graph metadata persistence and validation.

Purpose: Verifies embedding metadata is persisted with the graph and
validated against current embedding configuration.
Quality Contribution: Prevents embedding/model mismatch across scans.
"""

from dataclasses import replace

from fs2.config.objects import ScanConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.models.code_node import CodeNode
from fs2.core.repos.graph_store_fake import FakeGraphStore
from fs2.core.repos.graph_store_impl import NetworkXGraphStore
from fs2.core.services.pipeline_context import PipelineContext


class FakeEmbeddingService:
    """Async fake embedding service with static metadata."""

    def __init__(self, metadata: dict):
        self._metadata = metadata

    def get_metadata(self) -> dict:
        return self._metadata

    async def process_batch(self, nodes, progress_callback=None, courtesy_save=None):
        updated = {}
        for node in nodes:
            updated[node.node_id] = replace(
                node,
                embedding=((0.1, 0.2),),
                embedding_hash=node.content_hash,
            )
        return {
            "processed": len(nodes),
            "skipped": 0,
            "errors": [],
            "total": len(nodes),
            "results": updated,
        }


def _make_node(file_path: str = "a.py", content: str = "# test") -> CodeNode:
    return CodeNode.create_file(
        file_path=file_path,
        language="python",
        ts_kind="module",
        start_byte=0,
        end_byte=len(content),
        start_line=1,
        end_line=content.count("\n") + 1,
        content=content,
    )


class TestGraphMetadataPersistence:
    """Tests for embedding metadata persistence in graph store."""

    def test_given_embedding_metadata_when_saved_then_loaded_metadata_includes_fields(
        self, tmp_path
    ):
        """
        Purpose: Verifies embedding metadata is persisted with graph data.
        Quality Contribution: Enables model validation on subsequent scans.
        Acceptance Criteria: embedding_model, embedding_dimensions, chunk_params present.
        """
        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        metadata = {
            "embedding_model": "text-embedding-3-small",
            "embedding_dimensions": 1024,
            "chunk_params": {
                "code": {"max_tokens": 400, "overlap_tokens": 50},
                "documentation": {"max_tokens": 800, "overlap_tokens": 120},
                "smart_content": {"max_tokens": 8000, "overlap_tokens": 0},
            },
        }

        store.set_metadata(metadata)
        store.add_node(_make_node())
        path = tmp_path / "graph.pickle"
        store.save(path)

        store2 = NetworkXGraphStore(config)
        store2.load(path)

        loaded = store2.get_metadata()

        assert loaded["embedding_model"] == "text-embedding-3-small"
        assert loaded["embedding_dimensions"] == 1024
        assert loaded["chunk_params"]["code"]["max_tokens"] == 400


class TestGraphMetadataValidation:
    """Tests for embedding metadata mismatch detection."""

    def test_given_mismatched_metadata_when_embedding_stage_runs_then_records_error(
        self,
    ):
        """
        Purpose: Verifies mismatch between prior graph and current config is detected.
        Quality Contribution: Prevents silently mixing embeddings from different models.
        Acceptance Criteria: context.errors includes mismatch message.
        """
        from fs2.core.services.stages.embedding_stage import EmbeddingStage

        config = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config)
        store.set_metadata(
            {
                "embedding_model": "old-model",
                "embedding_dimensions": 1024,
                "chunk_params": {"code": {"max_tokens": 400, "overlap_tokens": 50}},
            }
        )

        current_metadata = {
            "embedding_model": "new-model",
            "embedding_dimensions": 1024,
            "chunk_params": {"code": {"max_tokens": 400, "overlap_tokens": 50}},
        }

        context = PipelineContext(scan_config=ScanConfig())
        context.graph_store = store
        context.nodes = [_make_node()]
        context.embedding_service = FakeEmbeddingService(current_metadata)

        stage = EmbeddingStage()
        result = stage.process(context)

        assert any("Embedding metadata mismatch" in error for error in result.errors)
