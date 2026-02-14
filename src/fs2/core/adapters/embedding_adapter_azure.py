"""AzureEmbeddingAdapter implementation.

Azure OpenAI embedding API integration with retry logic.
Per DYK-2: Pass dimensions to API, warn if response length mismatches.
Per DYK-4: Retry config with exponential backoff, max 60s cap.
Per Critical Finding 05: Returns list[float], not numpy.
"""

import asyncio
import logging
import random
from typing import TYPE_CHECKING

from openai import AsyncAzureOpenAI

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


class AzureEmbeddingAdapter(EmbeddingAdapter):
    """Azure OpenAI embedding API adapter.

    Provides embedding generation via Azure OpenAI's API with:
    - ConfigurationService DI pattern
    - Exponential backoff retry on transient errors (429, 502, 503)
    - Status-code-based exception translation
    - Dimension validation with warnings

    Example:
        >>> config_service = FS2ConfigurationService()
        >>> adapter = AzureEmbeddingAdapter(config_service)
        >>> embedding = await adapter.embed_text("def add(a, b): return a + b")
        >>> len(embedding)  # 1024 floats
    """

    # Status codes that trigger retry with backoff
    RETRYABLE_STATUS_CODES = {429, 502, 503}

    def __init__(self, config: "ConfigurationService") -> None:
        """Initialize the adapter with ConfigurationService.

        Args:
            config: ConfigurationService to get EmbeddingConfig from.

        Raises:
            EmbeddingAdapterError: If azure nested config is missing.
        """
        self._config_service = config
        self._embedding_config = config.require(EmbeddingConfig)
        self._client: AsyncAzureOpenAI | None = None

        # Validate azure config exists
        if self._embedding_config.azure is None:
            raise EmbeddingAdapterError(
                "Azure config is required for mode='azure'. "
                "Set embedding.azure.endpoint."
            )

        self._azure_config = self._embedding_config.azure

    @property
    def provider_name(self) -> str:
        """Return 'azure' as the provider name."""
        return "azure"

    def _get_client(self) -> AsyncAzureOpenAI:
        """Get or create the Azure OpenAI client.

        Auth: key present → api_key; key absent → Azure AD via DefaultAzureCredential.

        Returns:
            AsyncAzureOpenAI client configured for the deployment.
        """
        if self._client is None:
            if self._azure_config.api_key:
                # Key-based auth
                self._client = AsyncAzureOpenAI(
                    api_key=self._azure_config.api_key,
                    azure_endpoint=self._azure_config.endpoint,
                    api_version=self._azure_config.api_version,
                )
            else:
                # Azure AD auth (az login / DefaultAzureCredential)
                try:
                    from azure.identity import (
                        DefaultAzureCredential,
                        get_bearer_token_provider,
                    )
                except ImportError:
                    raise EmbeddingAdapterError(
                        "azure-identity package is required for Azure AD authentication. "
                        "Install it with: pip install fs2[azure-ad]"
                    ) from None
                credential = DefaultAzureCredential()
                token_provider = get_bearer_token_provider(
                    credential,
                    "https://cognitiveservices.azure.com/.default",  # Public Azure; sovereign clouds need different scope
                )
                self._client = AsyncAzureOpenAI(
                    azure_ad_token_provider=token_provider,
                    azure_endpoint=self._azure_config.endpoint,
                    api_version=self._azure_config.api_version,
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

        Per DYK-3: This method makes a single API call with all texts.

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
                response = await client.embeddings.create(
                    model=self._azure_config.deployment_name,
                    input=texts,
                    dimensions=self._embedding_config.dimensions,
                )

                # Extract embeddings from response
                embeddings: list[list[float]] = []
                for item in response.data:
                    embedding = list(item.embedding)

                    # Per DYK-2: Warn if dimensions mismatch
                    if len(embedding) != self._embedding_config.dimensions:
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
                        "Authentication failed. Check your Azure embedding API key."
                    ) from e

                # Check if retryable
                if status_code in self.RETRYABLE_STATUS_CODES:
                    last_retry_after = self._extract_retry_after(e)

                    if attempt < max_retries:
                        # Calculate backoff: base * 2^attempt + jitter
                        delay = self._embedding_config.base_delay * (2**attempt)
                        delay += random.uniform(0, 1)

                        # Cap at max_delay per DYK-4
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
                raise EmbeddingAdapterError(f"Azure embedding API error: {e}") from e

        # Should not reach here, but just in case
        raise EmbeddingAdapterError(f"Unexpected error: {last_error}") from last_error
