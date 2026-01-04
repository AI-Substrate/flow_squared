"""End-to-end embedding validation test.

Purpose: Phase 5 T007 - Validate full scan with embeddings on fixture samples.
Quality Contribution: Proves embedding pipeline works E2E with all file types.

Per DYK-2: Uses FakeEmbeddingAdapter + FakeLLMAdapter (no real services).
Scans tests/fixtures/samples/ and verifies all nodes have embeddings.
"""

from pathlib import Path

import pytest

from fs2.config.objects import (
    ChunkConfig,
    EmbeddingConfig,
    ScanConfig,
    SmartContentConfig,
)
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters.ast_parser_impl import TreeSitterParser
from fs2.core.adapters.file_scanner_impl import FileSystemScanner
from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
from fs2.core.repos.graph_store_impl import NetworkXGraphStore
from fs2.core.services.embedding.embedding_service import EmbeddingService
from fs2.core.services.llm_service import LLMService
from fs2.core.services.scan_pipeline import ScanPipeline
from fs2.core.services.smart_content.smart_content_service import SmartContentService
from fs2.core.services.smart_content.template_service import TemplateService


@pytest.fixture
def samples_path() -> Path:
    """Path to fixture samples directory."""
    return Path(__file__).parent.parent / "fixtures" / "samples"


@pytest.fixture
def test_graph_path(tmp_path: Path) -> Path:
    """Temp graph path to avoid corrupting project graph."""
    return tmp_path / "test_graph.pickle"


@pytest.fixture
def embedding_config() -> EmbeddingConfig:
    """Standard embedding config."""
    return EmbeddingConfig(
        mode="fake",
        dimensions=1024,
        batch_size=50,
        code=ChunkConfig(max_tokens=400, overlap_tokens=50),
        documentation=ChunkConfig(max_tokens=800, overlap_tokens=120),
        smart_content=ChunkConfig(max_tokens=8000, overlap_tokens=0),
    )


@pytest.mark.integration
class TestEndToEndEmbeddingValidation:
    """E2E validation of embedding pipeline on fixture samples.

    Per Phase 5 Task T007:
    - Scans tests/fixtures/samples/ with FakeEmbeddingAdapter
    - Verifies all 19+ files have embeddings
    - Validates metadata keys exist
    - No real API calls (DYK-2)
    """

    def test_given_samples_directory_when_scanning_with_embeddings_then_all_files_embedded(
        self,
        samples_path: Path,
        embedding_config: EmbeddingConfig,
        fixture_graph,
        test_graph_path: Path,
    ):
        """
        Purpose: E2E validation of embedding pipeline on real fixture files.
        Quality Contribution: Proves pipeline works with all supported file types.
        Acceptance Criteria:
            - All 19+ sample files scanned
            - All nodes with content have embeddings
            - Graph metadata contains embedding model info
        """
        # Arrange
        config = FakeConfigurationService(
            ScanConfig(scan_paths=[str(samples_path)], respect_gitignore=True),
            embedding_config,
            SmartContentConfig(max_workers=2),
        )

        # Use fixture graph adapters for deterministic embedding
        # This uses real embeddings from fixture_graph.pkl
        embedding_adapter = fixture_graph.embedding_adapter
        llm_adapter = fixture_graph.llm_adapter
        token_counter = FakeTokenCounterAdapter(config)

        embedding_service = EmbeddingService(
            config=embedding_config,
            embedding_adapter=embedding_adapter,
            token_counter=token_counter,
        )

        llm_service = LLMService(config, llm_adapter)
        template_service = TemplateService(config)

        smart_service = SmartContentService(
            config=config,
            llm_service=llm_service,
            template_service=template_service,
            token_counter=token_counter,
        )

        scanner = FileSystemScanner(config)
        parser = TreeSitterParser(config)
        store = NetworkXGraphStore(config)

        pipeline = ScanPipeline(
            config=config,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            smart_content_service=smart_service,
            embedding_service=embedding_service,
            graph_path=test_graph_path,
        )

        # Act
        summary = pipeline.run()

        # Assert - scan completed
        assert summary.files_scanned >= 15, (
            f"Expected at least 15 files, got {summary.files_scanned}"
        )
        assert summary.nodes_created > 0, "Expected nodes to be created"

        # Assert - embedding metrics
        assert summary.metrics.get("embedding_enriched", 0) > 0, (
            "Expected embedding_enriched > 0"
        )
        assert summary.metrics.get("embedding_errors", 0) == 0, (
            f"Expected 0 embedding errors, got {summary.metrics.get('embedding_errors')}"
        )

        # Assert - embedding metadata stored in metrics (EmbeddingStage captures it)
        embedding_metadata = summary.metrics.get("embedding_metadata", {})
        assert "embedding_model" in embedding_metadata, (
            f"Missing embedding_model in embedding_metadata: {embedding_metadata}"
        )
        assert embedding_metadata["embedding_model"] == "fake"
        assert embedding_metadata["embedding_dimensions"] == 1024

        # Assert - nodes have embeddings
        nodes = list(store.get_all_nodes())
        nodes_with_content = [n for n in nodes if n.content and n.content.strip()]
        nodes_with_embeddings = [
            n for n in nodes_with_content if n.embedding is not None
        ]

        embedding_rate = (
            len(nodes_with_embeddings) / len(nodes_with_content)
            if nodes_with_content
            else 0
        )
        assert embedding_rate == 1.0, (
            f"Expected 100% embedding rate, got {embedding_rate:.1%} "
            f"({len(nodes_with_embeddings)}/{len(nodes_with_content)})"
        )

        # Print summary for logging
        print("\n=== E2E Embedding Validation Results ===")
        print(f"Files scanned: {summary.files_scanned}")
        print(f"Nodes created: {summary.nodes_created}")
        print(f"Nodes with content: {len(nodes_with_content)}")
        print(f"Nodes with embeddings: {len(nodes_with_embeddings)}")
        print(f"Embedding rate: {embedding_rate:.1%}")
        print(f"Embedding model: {embedding_metadata['embedding_model']}")
        print(f"Embedding dimensions: {embedding_metadata['embedding_dimensions']}")
        print(
            f"Smart content enriched: {summary.metrics.get('smart_content_enriched', 0)}"
        )
        print(f"Embedding enriched: {summary.metrics.get('embedding_enriched', 0)}")
        print(f"Embedding preserved: {summary.metrics.get('embedding_preserved', 0)}")
        print("========================================\n")

    def test_given_samples_when_scanning_then_embedding_format_correct(
        self,
        samples_path: Path,
        embedding_config: EmbeddingConfig,
        fixture_graph,
        test_graph_path: Path,
    ):
        """
        Purpose: Verify embeddings have correct tuple format.
        Quality Contribution: Validates DYK-1 format requirement.
        """
        # Arrange
        config = FakeConfigurationService(
            ScanConfig(scan_paths=[str(samples_path)], respect_gitignore=True),
            embedding_config,
        )

        embedding_adapter = fixture_graph.embedding_adapter
        token_counter = FakeTokenCounterAdapter(config)

        embedding_service = EmbeddingService(
            config=embedding_config,
            embedding_adapter=embedding_adapter,
            token_counter=token_counter,
        )

        scanner = FileSystemScanner(config)
        parser = TreeSitterParser(config)
        store = NetworkXGraphStore(config)

        pipeline = ScanPipeline(
            config=config,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            embedding_service=embedding_service,
            graph_path=test_graph_path,
        )

        # Act
        pipeline.run()

        # Assert - verify tuple format
        nodes = list(store.get_all_nodes())
        nodes_with_embeddings = [n for n in nodes if n.embedding is not None]

        for node in nodes_with_embeddings[:10]:  # Check first 10
            # Per DYK-1: tuple[tuple[float, ...], ...]
            assert isinstance(node.embedding, tuple), (
                f"Expected tuple, got {type(node.embedding)}"
            )
            assert len(node.embedding) >= 1, "Expected at least one chunk"
            assert isinstance(node.embedding[0], tuple), "Expected inner tuple"
            assert len(node.embedding[0]) == 1024, (
                f"Expected 1024 dims, got {len(node.embedding[0])}"
            )
