"""Tests for OpenAICompatibleEmbeddingAdapter.

Phase 2: Embedding Adapters - OpenAI-compatible adapter tests.
Purpose: Verify OpenAICompatibleEmbeddingAdapter implementation.

Per Plan Task 2.7/2.8: TDD tests for OpenAI-compatible embedding adapter.
This adapter works with any OpenAI-compatible API (OpenAI, local models, etc.)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.unit
class TestOpenAICompatibleAdapterInit:
    """T007: Tests for OpenAICompatibleEmbeddingAdapter initialization."""

    def test_given_config_service_when_constructed_then_succeeds(self):
        """
        Purpose: Proves DI pattern with ConfigurationService.
        Quality Contribution: Ensures clean architecture compliance.
        Acceptance Criteria: Adapter can be constructed with valid config.

        Task: T007
        """
        from fs2.config.objects import EmbeddingConfig
        from fs2.config.service import ConfigurationService
        from fs2.core.adapters.embedding_adapter_openai import (
            OpenAICompatibleEmbeddingAdapter,
        )

        # Arrange
        mock_config = MagicMock(spec=ConfigurationService)
        mock_config.require.return_value = EmbeddingConfig(
            mode="openai_compatible",
        )

        # Act
        adapter = OpenAICompatibleEmbeddingAdapter(
            mock_config,
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model="text-embedding-3-small",
        )

        # Assert
        assert adapter is not None

    def test_given_valid_config_when_provider_name_then_returns_openai(self):
        """
        Purpose: Proves provider_name returns 'openai_compatible'.
        Quality Contribution: Documents expected provider name.
        Acceptance Criteria: provider_name == 'openai_compatible'.

        Task: T007
        """
        from fs2.config.objects import EmbeddingConfig
        from fs2.config.service import ConfigurationService
        from fs2.core.adapters.embedding_adapter_openai import (
            OpenAICompatibleEmbeddingAdapter,
        )

        # Arrange
        mock_config = MagicMock(spec=ConfigurationService)
        mock_config.require.return_value = EmbeddingConfig(
            mode="openai_compatible",
        )

        # Act
        adapter = OpenAICompatibleEmbeddingAdapter(
            mock_config,
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model="text-embedding-3-small",
        )

        # Assert
        assert adapter.provider_name == "openai_compatible"


@pytest.mark.unit
class TestOpenAICompatibleAdapterEmbedText:
    """T007: Tests for OpenAICompatibleEmbeddingAdapter.embed_text()."""

    async def test_given_valid_text_when_embed_text_then_returns_list_float(self):
        """
        Purpose: Proves embed_text returns list[float].
        Quality Contribution: Ensures pickle-safe return type.
        Acceptance Criteria: Returns list[float] with correct dimensions.

        Task: T007
        """
        from fs2.config.objects import EmbeddingConfig
        from fs2.config.service import ConfigurationService
        from fs2.core.adapters.embedding_adapter_openai import (
            OpenAICompatibleEmbeddingAdapter,
        )

        # Arrange
        mock_config = MagicMock(spec=ConfigurationService)
        mock_config.require.return_value = EmbeddingConfig(
            mode="openai_compatible",
            dimensions=1024,
        )

        adapter = OpenAICompatibleEmbeddingAdapter(
            mock_config,
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model="text-embedding-3-small",
        )

        # Mock API response
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1024)]

        with patch.object(
            adapter,
            "_get_client",
            return_value=MagicMock(
                embeddings=MagicMock(create=AsyncMock(return_value=mock_response))
            ),
        ):
            # Act
            result = await adapter.embed_text("test content")

        # Assert
        assert isinstance(result, list)
        assert len(result) == 1024
        assert all(isinstance(x, float) for x in result)


@pytest.mark.unit
class TestOpenAICompatibleAdapterEmbedBatch:
    """T007: Tests for OpenAICompatibleEmbeddingAdapter.embed_batch()."""

    async def test_given_multiple_texts_when_embed_batch_then_returns_list_of_list_float(
        self,
    ):
        """
        Purpose: Proves embed_batch returns list[list[float]].
        Quality Contribution: Ensures pickle-safe return type.
        Acceptance Criteria: Returns list[list[float]] with correct dimensions.

        Task: T007
        """
        from fs2.config.objects import EmbeddingConfig
        from fs2.config.service import ConfigurationService
        from fs2.core.adapters.embedding_adapter_openai import (
            OpenAICompatibleEmbeddingAdapter,
        )

        # Arrange
        mock_config = MagicMock(spec=ConfigurationService)
        mock_config.require.return_value = EmbeddingConfig(
            mode="openai_compatible",
            dimensions=1024,
        )

        adapter = OpenAICompatibleEmbeddingAdapter(
            mock_config,
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model="text-embedding-3-small",
        )

        # Mock API response with 3 embeddings
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.1] * 1024),
            MagicMock(embedding=[0.2] * 1024),
            MagicMock(embedding=[0.3] * 1024),
        ]

        with patch.object(
            adapter,
            "_get_client",
            return_value=MagicMock(
                embeddings=MagicMock(create=AsyncMock(return_value=mock_response))
            ),
        ):
            # Act
            result = await adapter.embed_batch(["text1", "text2", "text3"])

        # Assert
        assert isinstance(result, list)
        assert len(result) == 3
        for embedding in result:
            assert isinstance(embedding, list)
            assert len(embedding) == 1024
            assert all(isinstance(x, float) for x in embedding)


@pytest.mark.unit
class TestOpenAICompatibleAdapterErrors:
    """T007: Tests for OpenAICompatibleEmbeddingAdapter error handling."""

    async def test_given_401_error_when_embed_text_then_raises_auth_error(self):
        """
        Purpose: Proves HTTP 401 becomes EmbeddingAuthenticationError.
        Quality Contribution: Translates status codes to domain exceptions.
        Acceptance Criteria: EmbeddingAuthenticationError raised on 401.

        Task: T007
        """
        from fs2.config.objects import EmbeddingConfig
        from fs2.config.service import ConfigurationService
        from fs2.core.adapters.embedding_adapter_openai import (
            OpenAICompatibleEmbeddingAdapter,
        )
        from fs2.core.adapters.exceptions import EmbeddingAuthenticationError

        # Arrange
        mock_config = MagicMock(spec=ConfigurationService)
        mock_config.require.return_value = EmbeddingConfig(
            mode="openai_compatible",
        )

        adapter = OpenAICompatibleEmbeddingAdapter(
            mock_config,
            api_key="bad-key",
            base_url="https://api.openai.com/v1",
            model="text-embedding-3-small",
        )

        # Mock 401 error
        mock_error = Exception("Unauthorized")
        mock_error.status_code = 401

        with patch.object(
            adapter,
            "_get_client",
            return_value=MagicMock(
                embeddings=MagicMock(create=AsyncMock(side_effect=mock_error))
            ),
        ):
            # Act / Assert
            with pytest.raises(EmbeddingAuthenticationError):
                await adapter.embed_text("test")

    async def test_given_429_error_when_max_retries_exceeded_then_raises_rate_limit_error(
        self,
    ):
        """
        Purpose: Proves rate limit error after max retries.
        Quality Contribution: Prevents infinite retry loops.
        Acceptance Criteria: EmbeddingRateLimitError raised after max_retries.

        Task: T007
        """
        from fs2.config.objects import EmbeddingConfig
        from fs2.config.service import ConfigurationService
        from fs2.core.adapters.embedding_adapter_openai import (
            OpenAICompatibleEmbeddingAdapter,
        )
        from fs2.core.adapters.exceptions import EmbeddingRateLimitError

        # Arrange
        mock_config = MagicMock(spec=ConfigurationService)
        mock_config.require.return_value = EmbeddingConfig(
            mode="openai_compatible",
            max_retries=2,
        )

        adapter = OpenAICompatibleEmbeddingAdapter(
            mock_config,
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model="text-embedding-3-small",
        )

        # Mock 429 error every time
        mock_error = Exception("Rate limited")
        mock_error.status_code = 429

        with patch.object(
            adapter,
            "_get_client",
            return_value=MagicMock(
                embeddings=MagicMock(create=AsyncMock(side_effect=mock_error))
            ),
        ):
            # Act / Assert
            with pytest.raises(EmbeddingRateLimitError):
                await adapter.embed_text("test")
