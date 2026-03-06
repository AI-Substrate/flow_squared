"""Search services for fs2.

This module provides the search capability implementation:
- RegexMatcher: Pattern matching with timeout protection
- TextMatcher: Case-insensitive substring search (delegates to RegexMatcher)
- SemanticMatcher: Embedding-based semantic search (Phase 3)
- SearchService: Orchestration layer routing to appropriate matchers

Per Phase 2: Text/Regex Matchers implementation.
Per Phase 3: Semantic Matcher implementation.
"""

from fs2.core.services.search.exceptions import SearchError
from fs2.core.services.search.pgvector_matcher import PgvectorSemanticMatcher
from fs2.core.services.search.regex_matcher import RegexMatcher
from fs2.core.services.search.search_service import SearchService
from fs2.core.services.search.semantic_matcher import SemanticMatcher, cosine_similarity
from fs2.core.services.search.text_matcher import TextMatcher

__all__ = [
    "PgvectorSemanticMatcher",
    "SearchError",
    "RegexMatcher",
    "SearchService",
    "SemanticMatcher",
    "TextMatcher",
    "cosine_similarity",
]
