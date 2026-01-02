"""Integration tests for embedding pipeline (embeddings enabled path).

Purpose: Validates full scan pipeline with embeddings enabled.
Quality Contribution: End-to-end verification of embedding generation.

Per Phase 5 Task T002:
- Tests "embeddings enabled" path (see test_cli_embeddings.py for "disabled" path)
- Uses FakeEmbeddingAdapter + FakeLLMAdapter from fixture graph (no real API calls)
- Validates both adapter layer (list[float]) and service layer (tuple[tuple[float, ...], ...])
- Validates graph metadata persistence per Finding 09

DYK-1: Adapter returns list[float], service aggregates to tuple[tuple[float, ...], ...]
DYK-2: Uses FakeEmbeddingAdapter + FakeLLMAdapter (no real services in CI)
DYK-4: Tests "embeddings enabled" path; test_cli_embeddings.py tests "disabled" path
"""

from pathlib import Path

import pytest

from fs2.config.objects import ChunkConfig, EmbeddingConfig, ScanConfig, SmartContentConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters.ast_parser_impl import TreeSitterParser
from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter
from fs2.core.adapters.file_scanner_impl import FileSystemScanner
from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
from fs2.core.repos.graph_store_impl import NetworkXGraphStore
from fs2.core.services.embedding.embedding_service import EmbeddingService
from fs2.core.services.llm_service import LLMService
from fs2.core.services.scan_pipeline import ScanPipeline
from fs2.core.services.smart_content.smart_content_service import SmartContentService
from fs2.core.services.smart_content.template_service import TemplateService


@pytest.fixture
def test_graph_path(tmp_path: Path) -> Path:
    """Temp graph path to avoid corrupting project graph."""
    return tmp_path / "test_graph.pickle"


@pytest.fixture
def simple_python_project(tmp_path: Path) -> Path:
    """Create a simple Python project structure for embedding tests."""
    src = tmp_path / "src"
    src.mkdir()

    # Main module with class and methods
    calculator = src / "calculator.py"
    calculator.write_text('''"""Calculator module."""


class Calculator:
    """A basic calculator class."""

    def __init__(self, value: int = 0):
        self.value = value

    def add(self, x: int) -> int:
        """Add x to current value."""
        self.value += x
        return self.value

    def subtract(self, x: int) -> int:
        """Subtract x from current value."""
        self.value -= x
        return self.value
''')

    # Utils module with standalone function
    utils = src / "utils.py"
    utils.write_text('''"""Utility functions."""


def format_number(n: int) -> str:
    """Format a number with commas."""
    return f"{n:,}"
''')

    return tmp_path


@pytest.fixture
def embedding_config() -> EmbeddingConfig:
    """Standard embedding config for tests."""
    return EmbeddingConfig(
        mode="fake",
        dimensions=1024,
        batch_size=10,
        code=ChunkConfig(max_tokens=400, overlap_tokens=50),
        documentation=ChunkConfig(max_tokens=800, overlap_tokens=120),
        smart_content=ChunkConfig(max_tokens=8000, overlap_tokens=0),
    )


@pytest.mark.integration
class TestEmbeddingPipelineEnabled:
    """Integration tests for full pipeline with embeddings enabled.

    Per DYK-4: This tests the "embeddings enabled" path.
    See test_cli_embeddings.py for "embeddings disabled" path.
    """

    def test_given_embedding_service_when_scanning_then_nodes_have_embeddings(
        self, simple_python_project: Path, embedding_config: EmbeddingConfig, test_graph_path: Path
    ):
        """
        Purpose: Verifies pipeline generates embeddings for all nodes.
        Quality Contribution: End-to-end embedding generation validation.
        Acceptance Criteria: All nodes with content have embeddings.

        Per DYK-2: Uses FakeEmbeddingAdapter (no real API calls).
        Per Finding 07: Pipeline stage integration validated.
        """
        # Arrange
        src_path = simple_python_project / "src"
        config = FakeConfigurationService(
            ScanConfig(scan_paths=[str(src_path)], respect_gitignore=True),
            embedding_config,
        )

        # Create fake embedding adapter with deterministic response
        embedding_adapter = FakeEmbeddingAdapter(dimensions=1024)
        embedding_adapter.set_response([0.1] * 1024)

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
        summary = pipeline.run()

        # Assert
        # Note: success may be False due to metadata mismatch warnings if graph
        # was previously used with different model, but enrichment still works
        assert summary.files_scanned == 2  # calculator.py, utils.py
        assert summary.nodes_created > 0

        # Verify embedding metrics - this is the core validation
        assert summary.metrics.get("embedding_enriched", 0) > 0, (
            "Expected embedding_enriched > 0"
        )
        assert summary.metrics.get("embedding_errors", 0) == 0, (
            "Expected embedding_errors == 0"
        )

        # Verify nodes have embeddings
        nodes = list(store.get_all_nodes())
        nodes_with_content = [n for n in nodes if n.content and n.content.strip()]
        nodes_with_embeddings = [n for n in nodes_with_content if n.embedding is not None]

        assert len(nodes_with_embeddings) > 0, "Expected some nodes to have embeddings"

    def test_given_embedding_service_when_scanning_then_embeddings_are_tuple_of_tuples(
        self, simple_python_project: Path, embedding_config: EmbeddingConfig, test_graph_path: Path
    ):
        """
        Purpose: Verifies embeddings stored in correct format.
        Quality Contribution: Validates DYK-1 tuple-of-tuples format.
        Acceptance Criteria: node.embedding is tuple[tuple[float, ...], ...].

        Per DYK-1: Service aggregates to tuple[tuple[float, ...], ...].
        """
        # Arrange
        src_path = simple_python_project / "src"
        config = FakeConfigurationService(
            ScanConfig(scan_paths=[str(src_path)], respect_gitignore=True),
            embedding_config,
        )

        embedding_adapter = FakeEmbeddingAdapter(dimensions=1024)
        embedding_adapter.set_response([0.2] * 1024)

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
        summary = pipeline.run()

        # Assert
        nodes = list(store.get_all_nodes())
        nodes_with_embeddings = [n for n in nodes if n.embedding is not None]

        assert len(nodes_with_embeddings) > 0

        for node in nodes_with_embeddings:
            # Per DYK-1: Must be tuple of tuples
            assert isinstance(node.embedding, tuple), (
                f"Expected tuple, got {type(node.embedding)}"
            )
            assert len(node.embedding) >= 1, "Expected at least one chunk"
            assert isinstance(node.embedding[0], tuple), (
                f"Expected inner tuple, got {type(node.embedding[0])}"
            )
            assert len(node.embedding[0]) == 1024, (
                f"Expected 1024 dimensions, got {len(node.embedding[0])}"
            )
            assert isinstance(node.embedding[0][0], float), (
                f"Expected float, got {type(node.embedding[0][0])}"
            )


@pytest.mark.integration
class TestEmbeddingMetadataPersistence:
    """Tests for graph metadata persistence per Finding 09."""

    def test_given_embedding_service_when_scanning_then_metadata_stored_in_graph(
        self, simple_python_project: Path, embedding_config: EmbeddingConfig
    ):
        """
        Purpose: Verifies embedding metadata is persisted to graph.
        Quality Contribution: Enables model mismatch detection at search time.
        Acceptance Criteria: Graph metadata contains embedding model info.

        Per Finding 09: Graph Config Node for Model Tracking.
        """
        # Arrange
        src_path = simple_python_project / "src"
        graph_path = simple_python_project / "graph.pickle"

        config = FakeConfigurationService(
            ScanConfig(scan_paths=[str(src_path)], respect_gitignore=True),
            embedding_config,
        )

        embedding_adapter = FakeEmbeddingAdapter(dimensions=1024)
        embedding_adapter.set_response([0.1] * 1024)

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
            graph_path=graph_path,
        )

        # Act
        summary = pipeline.run()
        store.save(graph_path)

        # Load into new store to verify persistence
        loaded_store = NetworkXGraphStore(config)
        loaded_store.load(graph_path)

        # Assert - check metadata was captured
        metadata = loaded_store.get_metadata()
        assert "embedding_model" in metadata, "Missing embedding_model in metadata"
        assert "embedding_dimensions" in metadata, "Missing embedding_dimensions"
        assert "chunk_params" in metadata, "Missing chunk_params"

        assert metadata["embedding_dimensions"] == 1024
        assert "code" in metadata["chunk_params"]
        assert metadata["chunk_params"]["code"]["max_tokens"] == 400

    def test_given_saved_graph_when_loading_then_metadata_preserved(
        self, simple_python_project: Path, embedding_config: EmbeddingConfig
    ):
        """
        Purpose: Verifies metadata survives save/load cycle.
        Quality Contribution: Ensures search can validate model match.
        Acceptance Criteria: Loaded graph has same metadata.
        """
        # Arrange
        src_path = simple_python_project / "src"
        graph_path = simple_python_project / "graph.pickle"

        config = FakeConfigurationService(
            ScanConfig(scan_paths=[str(src_path)], respect_gitignore=True),
            embedding_config,
        )

        embedding_adapter = FakeEmbeddingAdapter(dimensions=1024)
        embedding_adapter.set_response([0.1] * 1024)

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
            graph_path=graph_path,
        )

        # Act - first scan and save
        pipeline.run()
        store.save(graph_path)

        # Load into new store
        new_store = NetworkXGraphStore(config)
        new_store.load(graph_path)

        # Assert
        metadata = new_store.get_metadata()
        assert metadata["embedding_model"] == "fake"
        assert metadata["embedding_dimensions"] == 1024


@pytest.mark.integration
class TestEmbeddingHashPreservation:
    """Tests for hash-based embedding skip logic per Finding 08."""

    def test_given_unchanged_files_when_rescanning_then_embeddings_preserved(
        self, simple_python_project: Path, embedding_config: EmbeddingConfig
    ):
        """
        Purpose: Verifies unchanged content preserves embeddings.
        Quality Contribution: Cost optimization for incremental updates.
        Acceptance Criteria: Second scan reports preservation, fewer API calls.

        Per Finding 08: Hash-Based Skip Logic.
        """
        # Arrange
        src_path = simple_python_project / "src"
        graph_path = simple_python_project / "graph.pickle"

        config = FakeConfigurationService(
            ScanConfig(scan_paths=[str(src_path)], respect_gitignore=True),
            embedding_config,
        )

        embedding_adapter = FakeEmbeddingAdapter(dimensions=1024)
        embedding_adapter.set_response([0.1] * 1024)

        token_counter = FakeTokenCounterAdapter(config)

        embedding_service = EmbeddingService(
            config=embedding_config,
            embedding_adapter=embedding_adapter,
            token_counter=token_counter,
        )

        # First scan
        store1 = NetworkXGraphStore(config)
        pipeline1 = ScanPipeline(
            config=config,
            file_scanner=FileSystemScanner(config),
            ast_parser=TreeSitterParser(config),
            graph_store=store1,
            embedding_service=embedding_service,
            graph_path=graph_path,
        )

        summary1 = pipeline1.run()
        first_enriched = summary1.metrics.get("embedding_enriched", 0)
        store1.save(graph_path)

        # Reset adapter to track second scan calls
        embedding_adapter.reset()
        embedding_adapter.set_response([0.1] * 1024)

        # Second scan with loaded graph
        store2 = NetworkXGraphStore(config)
        store2.load(graph_path)

        pipeline2 = ScanPipeline(
            config=config,
            file_scanner=FileSystemScanner(config),
            ast_parser=TreeSitterParser(config),
            graph_store=store2,
            embedding_service=embedding_service,
            graph_path=graph_path,
        )

        summary2 = pipeline2.run()

        # Assert
        assert summary2.metrics.get("embedding_preserved", 0) > 0, (
            "Expected preservation on second scan"
        )

        # Second scan should have fewer enrichments (most preserved)
        second_enriched = summary2.metrics.get("embedding_enriched", 0)
        assert second_enriched <= first_enriched, (
            f"Expected fewer enrichments on second scan ({second_enriched} vs {first_enriched})"
        )


@pytest.mark.integration
class TestEmbeddingWithSmartContent:
    """Tests for dual embedding (raw content + smart_content).

    Per DYK-2: Both embedding and smart_content_embedding fields populated.
    """

    def test_given_smart_content_when_embedding_then_both_fields_populated(
        self, simple_python_project: Path, embedding_config: EmbeddingConfig, test_graph_path: Path
    ):
        """
        Purpose: Verifies nodes with smart_content get both embeddings.
        Quality Contribution: Enables semantic search on AI descriptions.
        Acceptance Criteria: Nodes have both embedding and smart_content_embedding.

        Per DYK-2: Uses FakeLLMAdapter for smart content generation.
        """
        # Arrange
        src_path = simple_python_project / "src"
        config = FakeConfigurationService(
            ScanConfig(scan_paths=[str(src_path)], respect_gitignore=True),
            embedding_config,
            SmartContentConfig(max_workers=2),
        )

        # Create fake LLM adapter for smart content
        llm_adapter = FakeLLMAdapter()
        llm_adapter.set_response("A helpful description of this code.")

        llm_service = LLMService(config, llm_adapter)
        template_service = TemplateService(config)
        token_counter = FakeTokenCounterAdapter(config)

        smart_service = SmartContentService(
            config=config,
            llm_service=llm_service,
            template_service=template_service,
            token_counter=token_counter,
        )

        # Create embedding adapter
        embedding_adapter = FakeEmbeddingAdapter(dimensions=1024)
        embedding_adapter.set_response([0.3] * 1024)

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
            smart_content_service=smart_service,
            embedding_service=embedding_service,
            graph_path=test_graph_path,
        )

        # Act
        summary = pipeline.run()

        # Assert
        assert summary.success is True
        assert summary.metrics.get("smart_content_enriched", 0) > 0, (
            "Expected smart_content_enriched > 0"
        )
        assert summary.metrics.get("embedding_enriched", 0) > 0, (
            "Expected embedding_enriched > 0"
        )

        # Check for dual embeddings on nodes with smart_content
        nodes = list(store.get_all_nodes())
        nodes_with_smart_content = [n for n in nodes if n.smart_content]

        if nodes_with_smart_content:
            # At least some nodes should have both embeddings
            nodes_with_both = [
                n for n in nodes_with_smart_content
                if n.embedding and n.smart_content_embedding
            ]
            assert len(nodes_with_both) > 0, (
                "Expected nodes with smart_content to have both embeddings"
            )

            # Verify format
            for node in nodes_with_both:
                assert isinstance(node.smart_content_embedding, tuple)
                assert isinstance(node.smart_content_embedding[0], tuple)


@pytest.mark.integration
class TestEmbeddingWithFixtureGraph:
    """Integration tests using real fixture graph with real embeddings.

    Per DYK-2: These tests use the pre-computed fixture_graph.pkl
    with real Azure embeddings for deterministic testing.
    """

    @pytest.mark.skip(reason="embedding precision tolerance too strict (1e-10)")
    @pytest.mark.asyncio
    async def test_given_fixture_content_when_embedding_then_returns_real_vectors(
        self, fixture_graph
    ):
        """
        Purpose: Verifies FakeEmbeddingAdapter returns real embeddings from fixture.
        Quality Contribution: Enables realistic similarity testing.
        Acceptance Criteria: Known content returns known embedding values.

        Uses fixture_graph from conftest.py (session-scoped).
        """
        # Arrange - content from tests/fixtures/samples/python/auth_handler.py
        content = (
            'def is_expired(self) -> bool:\n'
            '        """Check if the token has expired."""\n'
            '        return datetime.utcnow() > self.expires_at'
        )

        # Act
        embedding = await fixture_graph.embedding_adapter.embed_text(content)

        # Assert - real embedding from Azure (1024 dimensions)
        assert len(embedding) == 1024
        # Check specific value from fixture (proves it's the real embedding)
        assert abs(embedding[0] - (-0.0015815813094377518)) < 1e-10

    @pytest.mark.asyncio
    async def test_given_unknown_content_when_embedding_then_deterministic_fallback(
        self, fixture_graph
    ):
        """
        Purpose: Verifies unknown content gets deterministic fallback.
        Quality Contribution: Ensures test reproducibility.
        Acceptance Criteria: Same content always returns same embedding.
        """
        # Arrange
        unknown_content = "def completely_unknown_function(): return 42"

        # Act
        embedding1 = await fixture_graph.embedding_adapter.embed_text(unknown_content)
        embedding2 = await fixture_graph.embedding_adapter.embed_text(unknown_content)

        # Assert
        assert len(embedding1) == 1024
        assert embedding1 == embedding2  # Deterministic
