"""Search domain models for fs2.

This module provides the core domain models for the search capability:
- SearchMode: Enum for search mode selection (TEXT, REGEX, SEMANTIC, AUTO)
- QuerySpec: Frozen dataclass for search query specification
- SearchResult: Frozen dataclass for search results with to_dict(detail)
- ChunkMatch: Frozen dataclass for semantic chunk match tracking
- EmbeddingField: Enum for embedding field type (EMBEDDING, SMART_CONTENT)

Per Phase 1: Core Models implementation.
"""

from fs2.core.models.search.chunk_match import ChunkMatch, EmbeddingField
from fs2.core.models.search.query_spec import QuerySpec
from fs2.core.models.search.search_mode import SearchMode
from fs2.core.models.search.search_result import SearchResult

__all__ = [
    "SearchMode",
    "QuerySpec",
    "SearchResult",
    "ChunkMatch",
    "EmbeddingField",
]
