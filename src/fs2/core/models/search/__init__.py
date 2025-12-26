"""Search domain models for fs2.

This module provides the core domain models for the search capability:
- SearchMode: Enum for search mode selection (TEXT, REGEX, SEMANTIC, AUTO)
- QuerySpec: Frozen dataclass for search query specification
- SearchResult: Frozen dataclass for search results with to_dict(detail)
- ChunkMatch: Frozen dataclass for semantic chunk match tracking
- EmbeddingField: Enum for embedding field type (EMBEDDING, SMART_CONTENT)
- SearchResultMeta: Frozen dataclass for search result metadata envelope
- extract_folder: Extract folder from node_id
- compute_folder_distribution: Compute folder counts with threshold drilling
- FOLDER_DRILL_THRESHOLD: Tunable constant for drilling (0.9)

Per Phase 1: Core Models implementation.
Per Subtask 003: Metadata envelope for search results.
"""

from fs2.core.models.search.chunk_match import ChunkMatch, EmbeddingField
from fs2.core.models.search.query_spec import QuerySpec
from fs2.core.models.search.search_mode import SearchMode
from fs2.core.models.search.search_result import SearchResult
from fs2.core.models.search.search_result_meta import (
    FOLDER_DRILL_THRESHOLD,
    SearchResultMeta,
    compute_folder_distribution,
    extract_folder,
)

__all__ = [
    "SearchMode",
    "QuerySpec",
    "SearchResult",
    "ChunkMatch",
    "EmbeddingField",
    "SearchResultMeta",
    "extract_folder",
    "compute_folder_distribution",
    "FOLDER_DRILL_THRESHOLD",
]
