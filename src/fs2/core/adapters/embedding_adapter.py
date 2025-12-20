"""EmbeddingAdapter ABC interface.

Provides the abstract interface for embedding provider adapters.
Per Critical Finding 05: Embeddings returned as list[float] (not numpy).
Per DYK-3: embed_batch semantics - adapter takes array, makes one API call.

Architecture:
- This file: ABC definition only
- Implementations: embedding_adapter_fake.py, embedding_adapter_azure.py, embedding_adapter_openai.py

Pattern demonstrates:
- Async-first design for I/O-bound embedding operations
- Provider abstraction for swappable implementations
- ConfigurationService DI pattern (in implementations)
"""

from abc import ABC, abstractmethod


class EmbeddingAdapter(ABC):
    """Abstract base class for embedding provider adapters.

    This interface defines the contract for all embedding adapters,
    enabling provider-agnostic embedding operations.

    All methods are async to support efficient I/O handling
    for embedding API calls.

    Return type is list[float] (not numpy) per Critical Finding 05:
    RestrictedUnpickler only allows whitelisted classes, so embeddings
    must be stored as plain Python lists for pickle safety.

    Implementations:
    - FakeEmbeddingAdapter: Test double with graph-based lookup
    - AzureEmbeddingAdapter: Azure OpenAI API integration
    - OpenAICompatibleEmbeddingAdapter: OpenAI-compatible API integration

    Example:
        >>> class MyAdapter(EmbeddingAdapter):
        ...     @property
        ...     def provider_name(self) -> str:
        ...         return "my-provider"
        ...
        ...     async def embed_text(self, text: str) -> list[float]:
        ...         # Call embedding API
        ...         return [0.1, 0.2, ...]  # 1024 floats
        ...
        ...     async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...         # Single API call with batch
        ...         return [[0.1, 0.2, ...] for _ in texts]
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name for this adapter.

        Used to identify the provider in logging and metrics.

        Returns:
            Provider name string (e.g., "azure", "openai", "fake").
        """
        ...

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Generate an embedding for a single text.

        Args:
            text: The input text to embed.

        Returns:
            Embedding vector as list[float] with dimensions matching config.
            Per Finding 05: Must be list[float], not numpy array.

        Raises:
            EmbeddingAdapterError: For generic embedding failures.
            EmbeddingAuthenticationError: For authentication failures (HTTP 401).
            EmbeddingRateLimitError: After max retries exceeded (HTTP 429).
        """
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts in a single API call.

        Per DYK-3: This method makes a single API call with all texts.
        The service layer (Phase 3) handles batch sizing/chunking.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors, one per input text.
            Each embedding is list[float] with dimensions matching config.
            Per Finding 05: Must be list[list[float]], not numpy arrays.

        Raises:
            EmbeddingAdapterError: For generic embedding failures.
            EmbeddingAuthenticationError: For authentication failures (HTTP 401).
            EmbeddingRateLimitError: After max retries exceeded (HTTP 429).
        """
        ...
