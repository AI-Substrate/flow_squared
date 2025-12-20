"""Tests for FakeEmbeddingAdapter.

Phase 2: Embedding Adapters - Fake adapter tests.
Purpose: Verify FakeEmbeddingAdapter implementation for testing.

Per DYK-5: Uses content_hash lookup with deterministic fallback.
Per Finding 05: Returns list[float], not numpy.
"""

import pytest


@pytest.mark.unit
class TestFakeEmbeddingAdapterInit:
    """T010: Tests for FakeEmbeddingAdapter initialization."""

    def test_given_no_args_when_constructed_then_succeeds(self):
        """
        Purpose: Proves FakeEmbeddingAdapter can be constructed.
        Quality Contribution: Ensures simple test setup.
        Acceptance Criteria: Adapter can be constructed without args.

        Task: T010
        """
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        # Arrange / Act
        adapter = FakeEmbeddingAdapter()

        # Assert
        assert adapter is not None

    def test_given_valid_adapter_when_provider_name_then_returns_fake(self):
        """
        Purpose: Proves provider_name returns 'fake'.
        Quality Contribution: Documents expected provider name.
        Acceptance Criteria: provider_name == 'fake'.

        Task: T010
        """
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        # Arrange / Act
        adapter = FakeEmbeddingAdapter()

        # Assert
        assert adapter.provider_name == "fake"


@pytest.mark.unit
class TestFakeEmbeddingAdapterSetResponse:
    """T010: Tests for FakeEmbeddingAdapter.set_response()."""

    async def test_given_set_response_when_embed_text_then_returns_configured_embedding(
        self,
    ):
        """
        Purpose: Proves set_response controls embed_text output.
        Quality Contribution: Enables test control of outputs.
        Acceptance Criteria: Returns configured embedding.

        Task: T010
        """
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        # Arrange
        adapter = FakeEmbeddingAdapter()
        expected = [0.1, 0.2, 0.3, 0.4, 0.5]
        adapter.set_response(expected)

        # Act
        result = await adapter.embed_text("any text")

        # Assert
        assert result == expected

    async def test_given_set_response_when_embed_batch_then_returns_same_for_all(
        self,
    ):
        """
        Purpose: Proves set_response controls embed_batch output.
        Quality Contribution: Enables test control of outputs.
        Acceptance Criteria: All texts get same configured embedding.

        Task: T010
        """
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        # Arrange
        adapter = FakeEmbeddingAdapter()
        expected = [0.1, 0.2, 0.3]
        adapter.set_response(expected)

        # Act
        result = await adapter.embed_batch(["text1", "text2", "text3"])

        # Assert
        assert len(result) == 3
        for embedding in result:
            assert embedding == expected


@pytest.mark.unit
class TestFakeEmbeddingAdapterDeterministic:
    """T010: Tests for FakeEmbeddingAdapter deterministic fallback per DYK-5."""

    async def test_given_no_set_response_when_embed_text_then_returns_deterministic_embedding(
        self,
    ):
        """
        Purpose: Per DYK-5: Proves deterministic fallback for unknown content.
        Quality Contribution: Enables consistent test behavior.
        Acceptance Criteria: Same text always returns same embedding.

        Task: T010
        """
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        # Arrange
        adapter = FakeEmbeddingAdapter(dimensions=1024)

        # Act
        result1 = await adapter.embed_text("same text")
        result2 = await adapter.embed_text("same text")

        # Assert
        assert result1 == result2
        assert len(result1) == 1024

    async def test_given_different_texts_when_embed_text_then_returns_different_embeddings(
        self,
    ):
        """
        Purpose: Proves different texts get different embeddings.
        Quality Contribution: Enables meaningful similarity tests.
        Acceptance Criteria: Different texts return different embeddings.

        Task: T010
        """
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        # Arrange
        adapter = FakeEmbeddingAdapter(dimensions=1024)

        # Act
        result1 = await adapter.embed_text("text one")
        result2 = await adapter.embed_text("text two")

        # Assert
        assert result1 != result2


@pytest.mark.unit
class TestFakeEmbeddingAdapterCallHistory:
    """T010: Tests for FakeEmbeddingAdapter call tracking."""

    async def test_given_embed_text_calls_when_checking_history_then_recorded(self):
        """
        Purpose: Proves call_history tracks embed_text calls.
        Quality Contribution: Enables test assertions on call patterns.
        Acceptance Criteria: Calls recorded in call_history.

        Task: T010
        """
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        # Arrange
        adapter = FakeEmbeddingAdapter()

        # Act
        await adapter.embed_text("first text")
        await adapter.embed_text("second text")

        # Assert
        assert len(adapter.call_history) == 2
        assert adapter.call_history[0]["text"] == "first text"
        assert adapter.call_history[1]["text"] == "second text"

    async def test_given_embed_batch_call_when_checking_history_then_recorded(self):
        """
        Purpose: Proves call_history tracks embed_batch calls.
        Quality Contribution: Enables test assertions on call patterns.
        Acceptance Criteria: Batch calls recorded in call_history.

        Task: T010
        """
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        # Arrange
        adapter = FakeEmbeddingAdapter()

        # Act
        await adapter.embed_batch(["a", "b", "c"])

        # Assert
        assert len(adapter.call_history) == 1
        assert adapter.call_history[0]["texts"] == ["a", "b", "c"]


@pytest.mark.unit
class TestFakeEmbeddingAdapterSetError:
    """T010: Tests for FakeEmbeddingAdapter.set_error()."""

    async def test_given_set_error_when_embed_text_then_raises_error(self):
        """
        Purpose: Proves set_error controls error raising.
        Quality Contribution: Enables error simulation in tests.
        Acceptance Criteria: Configured error is raised.

        Task: T010
        """
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter
        from fs2.core.adapters.exceptions import EmbeddingRateLimitError

        # Arrange
        adapter = FakeEmbeddingAdapter()
        adapter.set_error(EmbeddingRateLimitError("Test rate limit"))

        # Act / Assert
        with pytest.raises(EmbeddingRateLimitError, match="Test rate limit"):
            await adapter.embed_text("any text")


@pytest.mark.unit
class TestFakeEmbeddingAdapterReset:
    """T010: Tests for FakeEmbeddingAdapter.reset()."""

    async def test_given_reset_when_after_set_response_then_returns_deterministic(
        self,
    ):
        """
        Purpose: Proves reset clears configured response.
        Quality Contribution: Enables clean test isolation.
        Acceptance Criteria: After reset, returns deterministic fallback.

        Task: T010
        """
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        # Arrange
        adapter = FakeEmbeddingAdapter(dimensions=1024)
        adapter.set_response([0.1, 0.2])

        # Act
        adapter.reset()
        result = await adapter.embed_text("test")

        # Assert
        assert len(result) == 1024  # Back to deterministic

    def test_given_reset_when_after_calls_then_clears_history(self):
        """
        Purpose: Proves reset clears call_history.
        Quality Contribution: Enables clean test isolation.
        Acceptance Criteria: After reset, call_history is empty.

        Task: T010
        """
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        # Arrange
        adapter = FakeEmbeddingAdapter()
        adapter.call_history.append({"text": "previous"})

        # Act
        adapter.reset()

        # Assert
        assert len(adapter.call_history) == 0
