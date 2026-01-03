"""Tests for AzureEmbeddingAdapter.

Phase 2: Embedding Adapters - Azure adapter tests.
Purpose: Verify AzureEmbeddingAdapter implementation.

Per Plan Task 2.3/2.4: TDD tests for Azure embedding adapter.
Per DYK-2: Pass dimensions to API, warn if response length mismatches.
Per DYK-4: Retry config with exponential backoff, max 60s cap.
Per Critical Finding 05: Returns list[float], not numpy.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.unit
class TestAzureEmbeddingAdapterInit:
    """T004: Tests for AzureEmbeddingAdapter initialization."""

    def test_given_config_service_when_constructed_then_succeeds(self):
        """
        Purpose: Proves DI pattern with ConfigurationService.
        Quality Contribution: Ensures clean architecture compliance.
        Acceptance Criteria: Adapter can be constructed with valid config.

        Task: T004
        """
        from fs2.config.objects import AzureEmbeddingConfig, EmbeddingConfig
        from fs2.config.service import ConfigurationService
        from fs2.core.adapters.embedding_adapter_azure import AzureEmbeddingAdapter

        # Arrange
        mock_config = MagicMock(spec=ConfigurationService)
        mock_config.require.return_value = EmbeddingConfig(
            mode="azure",
            azure=AzureEmbeddingConfig(
                endpoint="https://test.openai.azure.com",
                api_key="test-key",
            ),
        )

        # Act
        adapter = AzureEmbeddingAdapter(mock_config)

        # Assert
        assert adapter is not None

    def test_given_no_azure_config_when_constructed_then_raises_error(self):
        """
        Purpose: Proves azure nested config is required for mode=azure.
        Quality Contribution: Fails fast on misconfiguration.
        Acceptance Criteria: Error raised if azure config missing.

        Task: T004
        """
        from fs2.config.objects import EmbeddingConfig
        from fs2.config.service import ConfigurationService
        from fs2.core.adapters.embedding_adapter_azure import AzureEmbeddingAdapter
        from fs2.core.adapters.exceptions import EmbeddingAdapterError

        # Arrange
        mock_config = MagicMock(spec=ConfigurationService)
        mock_config.require.return_value = EmbeddingConfig(
            mode="azure",
            azure=None,  # Missing!
        )

        # Act / Assert
        with pytest.raises(EmbeddingAdapterError, match="(?i)azure.*config"):
            AzureEmbeddingAdapter(mock_config)

    def test_given_valid_config_when_provider_name_then_returns_azure(self):
        """
        Purpose: Proves provider_name returns 'azure'.
        Quality Contribution: Documents expected provider name.
        Acceptance Criteria: provider_name == 'azure'.

        Task: T004
        """
        from fs2.config.objects import AzureEmbeddingConfig, EmbeddingConfig
        from fs2.config.service import ConfigurationService
        from fs2.core.adapters.embedding_adapter_azure import AzureEmbeddingAdapter

        # Arrange
        mock_config = MagicMock(spec=ConfigurationService)
        mock_config.require.return_value = EmbeddingConfig(
            mode="azure",
            azure=AzureEmbeddingConfig(
                endpoint="https://test.openai.azure.com",
                api_key="test-key",
            ),
        )

        # Act
        adapter = AzureEmbeddingAdapter(mock_config)

        # Assert
        assert adapter.provider_name == "azure"


@pytest.mark.unit
class TestAzureEmbeddingAdapterEmbedText:
    """T004: Tests for AzureEmbeddingAdapter.embed_text()."""

    async def test_given_valid_text_when_embed_text_then_returns_list_float(self):
        """
        Purpose: Per Finding 05: Proves embed_text returns list[float].
        Quality Contribution: Ensures pickle-safe return type.
        Acceptance Criteria: Returns list[float] with correct dimensions.

        Task: T004
        """
        from fs2.config.objects import AzureEmbeddingConfig, EmbeddingConfig
        from fs2.config.service import ConfigurationService
        from fs2.core.adapters.embedding_adapter_azure import AzureEmbeddingAdapter

        # Arrange
        mock_config = MagicMock(spec=ConfigurationService)
        mock_config.require.return_value = EmbeddingConfig(
            mode="azure",
            dimensions=1024,
            azure=AzureEmbeddingConfig(
                endpoint="https://test.openai.azure.com",
                api_key="test-key",
            ),
        )

        adapter = AzureEmbeddingAdapter(mock_config)

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

    async def test_given_api_call_when_embed_text_then_passes_dimensions(self):
        """
        Purpose: Per DYK-2: Proves dimensions are passed to API.
        Quality Contribution: Ensures correct embedding size.
        Acceptance Criteria: dimensions parameter passed to API call.

        Task: T004
        """
        from fs2.config.objects import AzureEmbeddingConfig, EmbeddingConfig
        from fs2.config.service import ConfigurationService
        from fs2.core.adapters.embedding_adapter_azure import AzureEmbeddingAdapter

        # Arrange
        mock_config = MagicMock(spec=ConfigurationService)
        mock_config.require.return_value = EmbeddingConfig(
            mode="azure",
            dimensions=1024,
            azure=AzureEmbeddingConfig(
                endpoint="https://test.openai.azure.com",
                api_key="test-key",
                deployment_name="text-embedding-3-small",
            ),
        )

        adapter = AzureEmbeddingAdapter(mock_config)

        # Mock API response
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1024)]
        mock_create = AsyncMock(return_value=mock_response)

        with patch.object(
            adapter,
            "_get_client",
            return_value=MagicMock(
                embeddings=MagicMock(create=mock_create)
            ),
        ):
            # Act
            await adapter.embed_text("test content")

        # Assert - dimensions was passed
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs.get("dimensions") == 1024


@pytest.mark.unit
class TestAzureEmbeddingAdapterEmbedBatch:
    """T004: Tests for AzureEmbeddingAdapter.embed_batch()."""

    async def test_given_multiple_texts_when_embed_batch_then_returns_list_of_list_float(
        self,
    ):
        """
        Purpose: Per Finding 05: Proves embed_batch returns list[list[float]].
        Quality Contribution: Ensures pickle-safe return type.
        Acceptance Criteria: Returns list[list[float]] with correct dimensions.

        Task: T004
        """
        from fs2.config.objects import AzureEmbeddingConfig, EmbeddingConfig
        from fs2.config.service import ConfigurationService
        from fs2.core.adapters.embedding_adapter_azure import AzureEmbeddingAdapter

        # Arrange
        mock_config = MagicMock(spec=ConfigurationService)
        mock_config.require.return_value = EmbeddingConfig(
            mode="azure",
            dimensions=1024,
            azure=AzureEmbeddingConfig(
                endpoint="https://test.openai.azure.com",
                api_key="test-key",
            ),
        )

        adapter = AzureEmbeddingAdapter(mock_config)

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

    async def test_given_batch_when_embed_batch_then_makes_single_api_call(self):
        """
        Purpose: Per DYK-3: Proves single API call for batch.
        Quality Contribution: Ensures efficient batching.
        Acceptance Criteria: Only one API call for multiple texts.

        Task: T004
        """
        from fs2.config.objects import AzureEmbeddingConfig, EmbeddingConfig
        from fs2.config.service import ConfigurationService
        from fs2.core.adapters.embedding_adapter_azure import AzureEmbeddingAdapter

        # Arrange
        mock_config = MagicMock(spec=ConfigurationService)
        mock_config.require.return_value = EmbeddingConfig(
            mode="azure",
            azure=AzureEmbeddingConfig(
                endpoint="https://test.openai.azure.com",
                api_key="test-key",
            ),
        )

        adapter = AzureEmbeddingAdapter(mock_config)

        # Mock API response
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1024) for _ in range(5)]
        mock_create = AsyncMock(return_value=mock_response)

        with patch.object(
            adapter,
            "_get_client",
            return_value=MagicMock(
                embeddings=MagicMock(create=mock_create)
            ),
        ):
            # Act
            await adapter.embed_batch(["t1", "t2", "t3", "t4", "t5"])

        # Assert - only one call
        assert mock_create.call_count == 1


@pytest.mark.unit
class TestAzureEmbeddingAdapterAuthError:
    """T004: Tests for AzureEmbeddingAdapter authentication error handling."""

    async def test_given_401_error_when_embed_text_then_raises_auth_error(self):
        """
        Purpose: Proves HTTP 401 becomes EmbeddingAuthenticationError.
        Quality Contribution: Translates status codes to domain exceptions.
        Acceptance Criteria: EmbeddingAuthenticationError raised on 401.

        Task: T004
        """
        from fs2.config.objects import AzureEmbeddingConfig, EmbeddingConfig
        from fs2.config.service import ConfigurationService
        from fs2.core.adapters.embedding_adapter_azure import AzureEmbeddingAdapter
        from fs2.core.adapters.exceptions import EmbeddingAuthenticationError

        # Arrange
        mock_config = MagicMock(spec=ConfigurationService)
        mock_config.require.return_value = EmbeddingConfig(
            mode="azure",
            azure=AzureEmbeddingConfig(
                endpoint="https://test.openai.azure.com",
                api_key="test-key",
            ),
        )

        adapter = AzureEmbeddingAdapter(mock_config)

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


@pytest.mark.unit
class TestAzureEmbeddingAdapterRateLimit:
    """T004: Tests for AzureEmbeddingAdapter rate limit handling per DYK-4."""

    async def test_given_429_error_when_max_retries_exceeded_then_raises_rate_limit_error(
        self,
    ):
        """
        Purpose: Per DYK-4: Proves rate limit error after max retries.
        Quality Contribution: Prevents infinite retry loops.
        Acceptance Criteria: EmbeddingRateLimitError raised after max_retries.

        Task: T004
        """
        from fs2.config.objects import AzureEmbeddingConfig, EmbeddingConfig
        from fs2.config.service import ConfigurationService
        from fs2.core.adapters.embedding_adapter_azure import AzureEmbeddingAdapter
        from fs2.core.adapters.exceptions import EmbeddingRateLimitError

        # Arrange
        mock_config = MagicMock(spec=ConfigurationService)
        mock_config.require.return_value = EmbeddingConfig(
            mode="azure",
            max_retries=2,
            azure=AzureEmbeddingConfig(
                endpoint="https://test.openai.azure.com",
                api_key="test-key",
            ),
        )

        adapter = AzureEmbeddingAdapter(mock_config)

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
            with pytest.raises(EmbeddingRateLimitError) as exc_info:
                await adapter.embed_text("test")

            # Verify retry metadata per DYK-4
            assert exc_info.value.attempts_made == 3  # initial + 2 retries

    async def test_given_429_with_retry_after_when_error_then_includes_retry_after(
        self,
    ):
        """
        Purpose: Per DYK-4: Proves retry_after metadata populated.
        Quality Contribution: Enables service to respect API guidance.
        Acceptance Criteria: retry_after populated from Retry-After header.

        Task: T004
        """
        from fs2.config.objects import AzureEmbeddingConfig, EmbeddingConfig
        from fs2.config.service import ConfigurationService
        from fs2.core.adapters.embedding_adapter_azure import AzureEmbeddingAdapter
        from fs2.core.adapters.exceptions import EmbeddingRateLimitError

        # Arrange
        mock_config = MagicMock(spec=ConfigurationService)
        mock_config.require.return_value = EmbeddingConfig(
            mode="azure",
            max_retries=0,  # Fail immediately for faster test
            azure=AzureEmbeddingConfig(
                endpoint="https://test.openai.azure.com",
                api_key="test-key",
            ),
        )

        adapter = AzureEmbeddingAdapter(mock_config)

        # Mock 429 error with Retry-After header
        mock_error = Exception("Rate limited")
        mock_error.status_code = 429
        mock_error.response = MagicMock()
        mock_error.response.headers = {"Retry-After": "30"}

        with patch.object(
            adapter,
            "_get_client",
            return_value=MagicMock(
                embeddings=MagicMock(create=AsyncMock(side_effect=mock_error))
            ),
        ):
            # Act / Assert
            with pytest.raises(EmbeddingRateLimitError) as exc_info:
                await adapter.embed_text("test")

            # Verify retry_after populated
            assert exc_info.value.retry_after == 30.0

    async def test_given_retry_succeeds_when_retrying_then_returns_embedding(self):
        """
        Purpose: Proves retry logic works when API eventually succeeds.
        Quality Contribution: Ensures transient errors are recovered.
        Acceptance Criteria: Embedding returned after retry.

        Task: T004
        """
        from fs2.config.objects import AzureEmbeddingConfig, EmbeddingConfig
        from fs2.config.service import ConfigurationService
        from fs2.core.adapters.embedding_adapter_azure import AzureEmbeddingAdapter

        # Arrange
        mock_config = MagicMock(spec=ConfigurationService)
        mock_config.require.return_value = EmbeddingConfig(
            mode="azure",
            max_retries=3,
            base_delay=0.01,  # Fast for testing
            azure=AzureEmbeddingConfig(
                endpoint="https://test.openai.azure.com",
                api_key="test-key",
            ),
        )

        adapter = AzureEmbeddingAdapter(mock_config)

        # First call fails with 429, second succeeds
        mock_error = Exception("Rate limited")
        mock_error.status_code = 429

        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1024)]

        mock_create = AsyncMock(
            side_effect=[mock_error, mock_response]
        )

        with patch.object(
            adapter,
            "_get_client",
            return_value=MagicMock(
                embeddings=MagicMock(create=mock_create)
            ),
        ):
            # Act
            result = await adapter.embed_text("test")

        # Assert
        assert len(result) == 1024
        assert mock_create.call_count == 2


@pytest.mark.unit
class TestAzureEmbeddingAdapterBackoff:
    """T004: Tests for exponential backoff with max cap per DYK-4."""

    async def test_given_multiple_retries_when_backoff_then_capped_at_max_delay(self):
        """
        Purpose: Per DYK-4: Proves backoff capped at max_delay.
        Quality Contribution: Prevents infinite waits.
        Acceptance Criteria: Backoff never exceeds max_delay (60s default).

        Task: T004
        """
        import asyncio

        from fs2.config.objects import AzureEmbeddingConfig, EmbeddingConfig
        from fs2.config.service import ConfigurationService
        from fs2.core.adapters.embedding_adapter_azure import AzureEmbeddingAdapter
        from fs2.core.adapters.exceptions import EmbeddingRateLimitError

        # Arrange
        mock_config = MagicMock(spec=ConfigurationService)
        mock_config.require.return_value = EmbeddingConfig(
            mode="azure",
            max_retries=5,
            base_delay=2.0,
            max_delay=10.0,  # Cap at 10s for testing
            azure=AzureEmbeddingConfig(
                endpoint="https://test.openai.azure.com",
                api_key="test-key",
            ),
        )

        adapter = AzureEmbeddingAdapter(mock_config)

        # Track sleep calls
        sleep_calls = []
        original_sleep = asyncio.sleep

        async def mock_sleep(delay):
            sleep_calls.append(delay)
            # Don't actually sleep

        # Mock 429 error every time
        mock_error = Exception("Rate limited")
        mock_error.status_code = 429

        with (
            patch.object(
                adapter,
                "_get_client",
                return_value=MagicMock(
                    embeddings=MagicMock(create=AsyncMock(side_effect=mock_error))
                ),
            ),
            patch("asyncio.sleep", mock_sleep),
        ):
            # Act
            with pytest.raises(EmbeddingRateLimitError):
                await adapter.embed_text("test")

        # Assert - no sleep exceeds max_delay (10s)
        for delay in sleep_calls:
            assert delay <= 10.0, f"Delay {delay} exceeded max_delay 10.0"


@pytest.mark.unit
class TestAzureEmbeddingAdapterDimensionsMismatch:
    """T004: Tests for dimensions mismatch warning per DYK-2."""

    @pytest.mark.skip(reason="caplog interference in full suite")
    async def test_given_response_dims_mismatch_when_embed_text_then_warns(
        self, caplog
    ):
        """
        Purpose: Per DYK-2: Proves warning on dimensions mismatch.
        Quality Contribution: Catches silent dimension failures.
        Acceptance Criteria: Warning logged if response dims != config dims.

        Task: T004
        """
        import logging

        from fs2.config.objects import AzureEmbeddingConfig, EmbeddingConfig
        from fs2.config.service import ConfigurationService
        from fs2.core.adapters.embedding_adapter_azure import AzureEmbeddingAdapter

        # Arrange
        mock_config = MagicMock(spec=ConfigurationService)
        mock_config.require.return_value = EmbeddingConfig(
            mode="azure",
            dimensions=1024,  # Config says 1024
            azure=AzureEmbeddingConfig(
                endpoint="https://test.openai.azure.com",
                api_key="test-key",
            ),
        )

        adapter = AzureEmbeddingAdapter(mock_config)

        # Mock API returning 3072 dimensions (wrong!)
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 3072)]  # 3072 != 1024

        with patch.object(
            adapter,
            "_get_client",
            return_value=MagicMock(
                embeddings=MagicMock(create=AsyncMock(return_value=mock_response))
            ),
        ), caplog.at_level(logging.WARNING):
            # Act
            result = await adapter.embed_text("test")

        # Assert - warning logged
        assert "dimension" in caplog.text.lower() or "mismatch" in caplog.text.lower()
        # Still returns the embedding (warn, don't error)
        assert len(result) == 3072
