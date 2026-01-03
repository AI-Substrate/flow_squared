"""FakeEmbeddingAdapter implementation.

Test double for embedding adapters with explicit control via set_response().
Per DYK-5: Uses content_hash lookup with deterministic fallback.
Per Finding 05: Returns list[float], not numpy.
Per DYK-2: Converts tuple[tuple[float, ...], ...] from FixtureIndex to list[float].

Usage:
    adapter = FakeEmbeddingAdapter()
    adapter.set_response([0.1, 0.2, 0.3])
    embedding = await adapter.embed_text("Any text")
    assert embedding == [0.1, 0.2, 0.3]

    # Deterministic fallback (when no set_response)
    adapter = FakeEmbeddingAdapter(dimensions=1024)
    embedding = await adapter.embed_text("text")
    assert len(embedding) == 1024  # Deterministic based on content hash

    # Fixture-backed lookup (Subtask 001)
    index = FixtureIndex.from_nodes(nodes)
    adapter = FakeEmbeddingAdapter(fixture_index=index)
    embedding = await adapter.embed_text("known content")
    # Returns real pre-computed embedding from fixture graph

    # Error simulation
    adapter.set_error(EmbeddingRateLimitError("Test error"))
    with pytest.raises(EmbeddingRateLimitError):
        await adapter.embed_text("any text")

    # Call verification
    await adapter.embed_text("first")
    await adapter.embed_batch(["a", "b"])
    assert len(adapter.call_history) == 2
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from fs2.core.adapters.embedding_adapter import EmbeddingAdapter

if TYPE_CHECKING:
    from fs2.core.models.fixture_index import FixtureIndex


class FakeEmbeddingAdapter(EmbeddingAdapter):
    """Fake embedding adapter for testing.

    Provides explicit control over embeddings via set_response() and
    tracks all calls for assertion in tests.

    Features:
    - set_response(): Configure a fixed embedding to return (highest priority)
    - fixture_index: Optional FixtureIndex for pre-computed embedding lookup
    - set_error(): Configure an exception to raise
    - call_history: Track all embed calls for assertions
    - Deterministic fallback: Hash-based embeddings when no response or fixture hit

    Priority order (Subtask 001):
    1. set_response() - explicit test control always wins
    2. fixture_index lookup - returns real pre-computed embeddings
    3. Deterministic fallback - hash-based consistent values

    Attributes:
        call_history: List of all embed calls with arguments.

    Example:
        >>> adapter = FakeEmbeddingAdapter()
        >>> adapter.set_response([0.1, 0.2, 0.3])
        >>> embedding = await adapter.embed_text("hello")
        >>> embedding
        [0.1, 0.2, 0.3]

        >>> # With fixture_index
        >>> index = FixtureIndex.from_nodes(nodes)
        >>> adapter = FakeEmbeddingAdapter(fixture_index=index)
        >>> embedding = await adapter.embed_text("known content")
        >>> # Returns real embedding from fixture
    """

    def __init__(
        self,
        dimensions: int = 1024,
        fixture_index: FixtureIndex | None = None,
    ) -> None:
        """Initialize the fake adapter with optional dimensions and fixture index.

        Args:
            dimensions: Vector dimensions for deterministic fallback.
            fixture_index: Optional FixtureIndex for pre-computed embedding lookup.
                          When provided, embed_text/embed_batch will look up
                          embeddings by content before falling back to deterministic.
        """
        self._dimensions = dimensions
        self._fixture_index = fixture_index
        self._response: list[float] | None = None
        self._error: Exception | None = None
        self.call_history: list[dict[str, Any]] = []

    @property
    def provider_name(self) -> str:
        """Return 'fake' as the provider name."""
        return "fake"

    def set_response(self, embedding: list[float]) -> None:
        """Set the embedding that embed_text/embed_batch will return.

        Args:
            embedding: The embedding vector to return.
        """
        self._response = embedding
        self._error = None  # Clear any error

    def set_error(self, error: Exception) -> None:
        """Set an exception that embed_text/embed_batch will raise.

        Args:
            error: The exception to raise.
        """
        self._error = error

    def reset(self) -> None:
        """Reset the adapter to its initial state."""
        self._response = None
        self._error = None
        self.call_history = []

    def _deterministic_embedding(self, text: str) -> list[float]:
        """Generate a deterministic embedding based on content hash.

        Per DYK-5: Uses content hash for deterministic fallback.

        Args:
            text: The input text.

        Returns:
            Deterministic embedding vector based on text hash.
        """
        # Use SHA256 hash of text to generate deterministic floats
        hash_bytes = hashlib.sha256(text.encode()).digest()

        # Generate deterministic floats from hash
        # Extend the hash to cover all dimensions
        embedding = []
        for i in range(self._dimensions):
            # Use hash position to get a deterministic byte value
            byte_idx = i % len(hash_bytes)
            # Combine with position for variation across dimensions
            seed_value = hash_bytes[byte_idx] ^ (i & 0xFF)
            # Normalize to [-1, 1] range
            normalized = (seed_value / 127.5) - 1.0
            embedding.append(float(normalized))

        return embedding

    def _lookup_fixture_embedding(self, text: str) -> list[float] | None:
        """Look up embedding from fixture_index by content.

        Per DYK-2: Converts tuple[tuple[float, ...], ...] to list[float]
        using the first chunk.

        Args:
            text: The input text to look up.

        Returns:
            Embedding as list[float] if found, None otherwise.
        """
        if self._fixture_index is None:
            return None

        # Look up by content (index computes hash internally)
        embedding_tuple = self._fixture_index.lookup_embedding(text)
        if embedding_tuple is None:
            return None

        # Per DYK-2: Convert tuple[tuple[float, ...], ...] to list[float]
        # Use the first chunk for now (single-chunk embeddings)
        return list(embedding_tuple[0])

    async def embed_text(self, text: str) -> list[float]:
        """Generate an embedding for a single text.

        Records the call in call_history and returns the configured
        response, fixture lookup, deterministic fallback, or raises error.

        Priority order:
        1. set_response() - explicit test control
        2. fixture_index lookup - real pre-computed embeddings
        3. Deterministic fallback - hash-based consistent values

        Args:
            text: The input text.

        Returns:
            Embedding vector as list[float].

        Raises:
            Exception configured via set_error().
        """
        # Record the call
        self.call_history.append({"text": text})

        # Raise error if configured
        if self._error is not None:
            raise self._error

        # Priority 1: Return configured response
        if self._response is not None:
            return self._response.copy()

        # Priority 2: Look up in fixture_index
        fixture_embedding = self._lookup_fixture_embedding(text)
        if fixture_embedding is not None:
            return fixture_embedding

        # Priority 3: Deterministic fallback
        return self._deterministic_embedding(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Records the call in call_history and returns configured
        embeddings for each text. Each text is looked up independently
        when using fixture_index.

        Priority order (per text):
        1. set_response() - returns same for all texts
        2. fixture_index lookup - returns real pre-computed embeddings
        3. Deterministic fallback - hash-based consistent values

        Args:
            texts: List of texts to embed.

        Returns:
            List of embeddings, one per input text.

        Raises:
            Exception configured via set_error().
        """
        # Record the call
        self.call_history.append({"texts": texts})

        # Raise error if configured
        if self._error is not None:
            raise self._error

        # Priority 1: Return configured response (same for all)
        if self._response is not None:
            return [self._response.copy() for _ in texts]

        # Priority 2 & 3: Look up each text individually
        # (fixture hit or deterministic fallback per text)
        results: list[list[float]] = []
        for text in texts:
            fixture_embedding = self._lookup_fixture_embedding(text)
            if fixture_embedding is not None:
                results.append(fixture_embedding)
            else:
                results.append(self._deterministic_embedding(text))
        return results
