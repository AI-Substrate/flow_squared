"""OpenAICompatibleEmbeddingAdapter implementation.

OpenAI-compatible embedding API integration with retry logic.
Works with any OpenAI-compatible API (OpenAI, local models, etc.)
"""

import asyncio
import logging
import random
from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from fs2.config.objects import EmbeddingConfig
from fs2.core.adapters.embedding_adapter import EmbeddingAdapter
from fs2.core.adapters.exceptions import (
    EmbeddingAdapterError,
    EmbeddingAuthenticationError,
    EmbeddingRateLimitError,
)

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService

logger = logging.getLogger(__name__)


class OpenAICompatibleEmbeddingAdapter(EmbeddingAdapter):
    """OpenAI-compatible embedding API adapter.

    Provides embedding generation via any OpenAI-compatible API with:
    - ConfigurationService DI pattern
    - Exponential backoff retry on transient errors (429, 502, 503)
    - Status-code-based exception translation

    This adapter is more flexible than AzureEmbeddingAdapter as it:
    - Accepts api_key, base_url, and model directly in constructor
    - Works with any OpenAI-compatible endpoint (OpenAI, local, etc.)

    Example:
        >>> config_service = FS2ConfigurationService()
        >>> adapter = OpenAICompatibleEmbeddingAdapter(
        ...     config_service,
        ...     api_key="sk-...",
        ...     base_url="https://api.openai.com/v1",
        ...     model="text-embedding-3-small",
        ... )
        >>> embedding = await adapter.embed_text("Hello, world!")
    """

    # Status codes that trigger retry with backoff
    RETRYABLE_STATUS_CODES = {429, 502, 503}

    def __init__(
        self,
        config: "ConfigurationService",
        api_key: str,
        base_url: str,
        model: str,
    ) -> None:
        """Initialize the adapter with ConfigurationService and connection details.

        Args:
            config: ConfigurationService to get EmbeddingConfig from.
            api_key: OpenAI API key.
            base_url: OpenAI-compatible API base URL.
            model: Model name for embeddings.
        """
        self._config_service = config
        self._embedding_config = config.require(EmbeddingConfig)
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._client: AsyncOpenAI | None = None

    @property
    def provider_name(self) -> str:
        """Return 'openai_compatible' as the provider name."""
        return "openai_compatible"

    def _get_client(self) -> AsyncOpenAI:
        """Get or create the OpenAI client.

        Returns:
            AsyncOpenAI client configured for the endpoint.
        """
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
            )
        return self._client

    def _extract_retry_after(self, error: Exception) -> float | None:
        """Extract Retry-After header from error response.

        Args:
            error: The exception with potential response headers.

        Returns:
            Retry-After value in seconds, or None if not present.
        """
        response = getattr(error, "response", None)
        if response is None:
            return None

        headers = getattr(response, "headers", {})
        retry_after = headers.get("Retry-After")
        if retry_after is None:
            return None

        try:
            return float(retry_after)
        except (ValueError, TypeError):
            return None

    async def embed_text(self, text: str) -> list[float]:
        """Generate an embedding for a single text.

        Args:
            text: The input text to embed.

        Returns:
            Embedding vector as list[float] with dimensions matching config.

        Raises:
            EmbeddingAuthenticationError: For HTTP 401.
            EmbeddingRateLimitError: After max retries exceeded.
            EmbeddingAdapterError: For other errors.
        """
        result = await self.embed_batch([text])
        return result[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts in a single API call.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors, one per input text.

        Raises:
            EmbeddingAuthenticationError: For HTTP 401.
            EmbeddingRateLimitError: After max retries exceeded.
            EmbeddingAdapterError: For other errors.
        """
        client = self._get_client()

        # Retry loop with exponential backoff
        last_error: Exception | None = None
        last_retry_after: float | None = None
        max_retries = self._embedding_config.max_retries

        for attempt in range(max_retries + 1):
            try:
                # Build kwargs - dimensions is optional for some models
                kwargs: dict = {
                    "model": self._model,
                    "input": texts,
                }

                # Only add dimensions if configured
                if self._embedding_config.dimensions:
                    kwargs["dimensions"] = self._embedding_config.dimensions

                response = await client.embeddings.create(**kwargs)

                # Extract embeddings from response
                embeddings: list[list[float]] = []
                for item in response.data:
                    embedding = list(item.embedding)

                    # Warn if dimensions mismatch (if dimensions was configured)
                    if (
                        self._embedding_config.dimensions
                        and len(embedding) != self._embedding_config.dimensions
                    ):
                        logger.warning(
                            f"Embedding dimension mismatch: expected {self._embedding_config.dimensions}, "
                            f"got {len(embedding)}. This may indicate the model ignored the dimensions parameter."
                        )

                    embeddings.append(embedding)

                return embeddings

            except Exception as e:
                last_error = e
                status_code = getattr(e, "status_code", None)

                # Translate status codes to domain exceptions
                if status_code == 401:
                    raise EmbeddingAuthenticationError(
                        "Authentication failed. Check your OpenAI API key."
                    ) from e

                # Check if retryable
                if status_code in self.RETRYABLE_STATUS_CODES:
                    last_retry_after = self._extract_retry_after(e)

                    if attempt < max_retries:
                        # Calculate backoff: base * 2^attempt + jitter
                        delay = self._embedding_config.base_delay * (2**attempt)
                        delay += random.uniform(0, 1)

                        # Cap at max_delay
                        delay = min(delay, self._embedding_config.max_delay)

                        await asyncio.sleep(delay)
                        continue
                    else:
                        # Max retries exceeded
                        raise EmbeddingRateLimitError(
                            f"Rate limit exceeded after {max_retries} retries.",
                            retry_after=last_retry_after,
                            attempts_made=attempt + 1,
                        ) from e

                # Non-retryable error
                raise EmbeddingAdapterError(f"OpenAI embedding API error: {e}") from e

        # Should not reach here, but just in case
        raise EmbeddingAdapterError(f"Unexpected error: {last_error}") from last_error
