"""Integration tests for fixture graph with real embeddings.

These tests verify the end-to-end flow:
1. Sample files in tests/fixtures/samples/ are scanned
2. Real embeddings are generated via Azure API
3. Saved to fixture_graph.pkl (committed to repo)
4. FakeEmbeddingAdapter looks up by content hash
5. Returns REAL embeddings for known content

Per subtask 001: Tests use conftest.py fixtures that load the real fixture_graph.pkl.
"""

import pytest


@pytest.mark.integration
class TestFakeEmbeddingAdapterWithRealFixtures:
    """Tests that FakeEmbeddingAdapter returns real embeddings from fixture_graph.pkl."""

    async def test_embed_known_python_content_returns_real_embedding(
        self, fake_embedding_adapter
    ):
        """
        Purpose: Verify FakeEmbeddingAdapter returns real embedding for known content.
        Quality Contribution: Proves fixture graph integration works end-to-end.

        This content exists in tests/fixtures/samples/python/auth_handler.py
        and was embedded with real Azure API during fixture generation.
        """
        # Arrange - exact content from AuthToken.is_expired method
        content = (
            'def is_expired(self) -> bool:\n'
            '        """Check if the token has expired."""\n'
            '        return datetime.utcnow() > self.expires_at'
        )

        # Act
        embedding = await fake_embedding_adapter.embed_text(content)

        # Assert - returns real embedding (1024 dimensions from Azure)
        assert len(embedding) == 1024, (
            f"Expected 1024 dimensions (real Azure embedding), got {len(embedding)}"
        )

        # Verify it's the actual embedding (check first few values)
        # These are the real values from fixture_graph.pkl
        expected_start = (-0.0015815813094377518, 0.023476554080843925)
        assert abs(embedding[0] - expected_start[0]) < 1e-10, (
            f"First embedding value doesn't match. Got {embedding[0]}, "
            f"expected {expected_start[0]}"
        )
        assert abs(embedding[1] - expected_start[1]) < 1e-10, (
            f"Second embedding value doesn't match. Got {embedding[1]}, "
            f"expected {expected_start[1]}"
        )

    async def test_embed_another_known_method_returns_real_embedding(
        self, fake_embedding_adapter
    ):
        """
        Purpose: Verify another method's embedding is correctly retrieved.
        Quality Contribution: Confirms lookup works for multiple content items.

        This content exists in tests/fixtures/samples/python/auth_handler.py
        """
        # Arrange - exact content from AuthenticationError.__init__
        content = (
            'def __init__(self, message: str, code: str = "AUTH_ERROR"):\n'
            '        super().__init__(message)\n'
            '        self.code = code'
        )

        # Act
        embedding = await fake_embedding_adapter.embed_text(content)

        # Assert - returns real embedding
        assert len(embedding) == 1024

        # Verify specific values from fixture
        expected_first = 0.039552606642246246
        assert abs(embedding[0] - expected_first) < 1e-10, (
            f"Embedding mismatch. Got {embedding[0]}, expected {expected_first}"
        )

    async def test_embed_unknown_content_returns_deterministic_fallback(
        self, fake_embedding_adapter
    ):
        """
        Purpose: Verify unknown content falls back to deterministic embedding.
        Quality Contribution: Confirms graceful fallback for non-fixture content.
        """
        # Arrange - content NOT in fixture graph
        content = "def this_function_does_not_exist_in_fixtures(): pass"

        # Act
        embedding = await fake_embedding_adapter.embed_text(content)

        # Assert - returns deterministic fallback (default 1024 dims)
        assert len(embedding) == 1024

        # Should be deterministic - same content = same embedding
        embedding2 = await fake_embedding_adapter.embed_text(content)
        assert embedding == embedding2

    async def test_embed_go_content_returns_real_embedding(
        self, fake_embedding_adapter
    ):
        """
        Purpose: Verify cross-language support (Go content).
        Quality Contribution: Confirms fixture works for non-Python languages.

        This content exists in tests/fixtures/samples/go/server.go
        """
        # Arrange - exact content from DefaultConfig function
        content = (
            'func DefaultConfig() *Config {\n'
            '\treturn &Config{\n'
            '\t\tHost:            "0.0.0.0",\n'
            '\t\tPort:            8080,\n'
            '\t\tReadTimeout:     15 * time.Second,\n'
            '\t\tWriteTimeout:    15 * time.Second,\n'
            '\t\tShutdownTimeout: 30 * time.Second,\n'
            '\t\tMaxBodySize:     10 << 20, // 10 MB\n'
            '\t}\n'
            '}'
        )

        # Act
        embedding = await fake_embedding_adapter.embed_text(content)

        # Assert - returns real embedding
        assert len(embedding) == 1024

        # Verify specific values from fixture
        expected_first = 0.028660612180829048
        assert abs(embedding[0] - expected_first) < 1e-10, (
            f"Embedding mismatch. Got {embedding[0]}, expected {expected_first}"
        )


@pytest.mark.integration
class TestFixtureIndexWithRealGraph:
    """Tests that FixtureIndex correctly indexes the real fixture graph."""

    def test_fixture_index_has_embeddings(self, fixture_index):
        """
        Purpose: Verify fixture_index is populated from real graph.
        Quality Contribution: Confirms fixture loading works.
        """
        # Assert - should have nodes from fixture_graph.pkl
        assert fixture_index.node_count > 0, "FixtureIndex should have nodes"
        # We know fixture has 397 nodes
        assert fixture_index.node_count >= 100, (
            f"Expected many nodes, got {fixture_index.node_count}"
        )

    def test_lookup_embedding_for_known_content(self, fixture_index):
        """
        Purpose: Verify direct FixtureIndex lookup works.
        Quality Contribution: Tests the index lookup mechanism.
        """
        # Arrange - content from auth_handler.py
        content = (
            'def is_expired(self) -> bool:\n'
            '        """Check if the token has expired."""\n'
            '        return datetime.utcnow() > self.expires_at'
        )

        # Act
        embedding = fixture_index.lookup_embedding(content)

        # Assert - should find and return embedding tuple
        assert embedding is not None, "Should find embedding for known content"
        assert len(embedding) == 1  # Single chunk
        assert len(embedding[0]) == 1024  # 1024 dimensions


@pytest.mark.integration
class TestFixtureGraphContext:
    """Tests the full FixtureGraphContext from conftest.py."""

    def test_fixture_graph_context_provides_all_components(self, fixture_graph):
        """
        Purpose: Verify fixture_graph provides all expected components.
        Quality Contribution: Confirms conftest fixture is complete.
        """
        assert fixture_graph.fixture_index is not None
        assert fixture_graph.embedding_adapter is not None
        assert fixture_graph.llm_adapter is not None
        assert fixture_graph.graph_path.exists()

    def test_fixture_graph_path_is_correct(self, fixture_graph):
        """
        Purpose: Verify graph_path points to real file.
        Quality Contribution: Confirms file system integration.
        """
        assert fixture_graph.graph_path.name == "fixture_graph.pkl"
        assert "tests/fixtures" in str(fixture_graph.graph_path)
