"""ChunkMatch domain model for semantic chunk match tracking.

Provides:
- EmbeddingField: Enum for embedding field type (EMBEDDING, SMART_CONTENT)
- ChunkMatch: Frozen dataclass for tracking which chunk matched in semantic search

Per Phase 1 tasks.md Discovery 05: CodeNode embeddings are arrays of chunk embeddings.
Per Phase 1 tasks.md DYK-03: EmbeddingField enum for type-safe field identification.
"""

from dataclasses import dataclass
from enum import Enum


class EmbeddingField(str, Enum):
    """Embedding field type enumeration.

    Identifies which embedding field was matched in semantic search.
    Per DYK-03: Type-safe enum instead of stringly-typed field names.

    Attributes:
        EMBEDDING: Raw content embedding (from node.content chunked).
        SMART_CONTENT: AI-generated summary embedding (from node.smart_content chunked).
    """

    EMBEDDING = "embedding"
    SMART_CONTENT = "smart_content"


@dataclass(frozen=True)
class ChunkMatch:
    """Immutable semantic chunk match result.

    Tracks which chunk within a node's embeddings matched a query.
    Per Discovery 05: CodeNode embeddings are tuple[tuple[float, ...], ...]
    where each inner tuple is a chunk embedding.

    Attributes:
        field: Which embedding field matched (EMBEDDING or SMART_CONTENT).
               Must be EmbeddingField enum value (per DYK-03).
        chunk_index: Index of the matched chunk within the embedding array.
                     Must be >= 0 (valid array index).
        score: Cosine similarity score between query and chunk.
               Must be in range 0.0 to 1.0.

    Raises:
        ValueError: If chunk_index < 0 or score is outside 0.0-1.0 range.
        TypeError: If field is not an EmbeddingField enum value.

    Example:
        >>> match = ChunkMatch(
        ...     field=EmbeddingField.EMBEDDING,
        ...     chunk_index=2,
        ...     score=0.92
        ... )
        >>> match.field
        <EmbeddingField.EMBEDDING: 'embedding'>
        >>> match.chunk_index
        2
    """

    field: EmbeddingField
    chunk_index: int
    score: float

    def __post_init__(self) -> None:
        """Validate fields after construction.

        Raises:
            ValueError: If validation fails.
            TypeError: If field is not EmbeddingField enum.
        """
        # Validate field is EmbeddingField enum
        if not isinstance(self.field, EmbeddingField):
            raise TypeError(
                f"field must be EmbeddingField enum, got {type(self.field).__name__}"
            )

        # Validate chunk_index is non-negative
        if self.chunk_index < 0:
            raise ValueError(
                f"chunk_index must be >= 0, got {self.chunk_index}"
            )

        # Validate score is in 0.0-1.0 range
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(
                f"score must be between 0.0 and 1.0, got {self.score}"
            )
