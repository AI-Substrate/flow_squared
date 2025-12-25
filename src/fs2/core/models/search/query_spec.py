"""QuerySpec domain model for search query specification.

A frozen dataclass representing a validated search query with:
- Pattern: Non-empty search pattern (AC10)
- Mode: Search mode (TEXT, REGEX, SEMANTIC, AUTO)
- Limit: Maximum results (default 20)
- Min similarity: Semantic search threshold (default 0.25, per DYK-P3-04)

Per Phase 1 tasks.md: Frozen dataclass with __post_init__ validation.
Per DYK-05: min_similarity only applies to SEMANTIC mode (documented in docstring).
Per DYK-P3-04: min_similarity lowered from 0.5 to 0.25 to capture weakly-related code.
"""

from dataclasses import dataclass

from fs2.core.models.search.search_mode import SearchMode


@dataclass(frozen=True)
class QuerySpec:
    """Immutable specification for a search query.

    Validates that the pattern is non-empty and parameters are within
    valid ranges on construction.

    Attributes:
        pattern: Search pattern (cannot be empty or whitespace-only).
        mode: Search mode from SearchMode enum.
        limit: Maximum number of results to return (must be >= 1, default 20).
        min_similarity: Minimum similarity score for matches (0.0-1.0, default 0.25).
            Note: This parameter only applies to SEMANTIC mode searches.
            For TEXT and REGEX modes, this value is ignored.
            Per DYK-P3-04: Lowered from 0.5 to 0.25 to capture weakly-related code.

    Raises:
        ValueError: If pattern is empty/whitespace, limit < 1, or
                    min_similarity is outside 0.0-1.0 range.
        TypeError: If mode is not a SearchMode enum value.

    Example:
        >>> spec = QuerySpec(pattern="authentication", mode=SearchMode.SEMANTIC)
        >>> spec.limit
        20
        >>> spec.min_similarity
        0.25
    """

    pattern: str
    mode: SearchMode
    limit: int = 20
    min_similarity: float = 0.25

    def __post_init__(self) -> None:
        """Validate fields after construction.

        Raises:
            ValueError: If validation fails.
            TypeError: If mode is not SearchMode enum.
        """
        # Validate pattern is not empty or whitespace
        if not self.pattern or not self.pattern.strip():
            raise ValueError("Pattern cannot be empty or whitespace-only")

        # Validate mode is SearchMode enum
        if not isinstance(self.mode, SearchMode):
            raise TypeError(
                f"mode must be SearchMode enum, got {type(self.mode).__name__}"
            )

        # Validate limit is positive
        if self.limit < 1:
            raise ValueError(f"Limit must be >= 1, got {self.limit}")

        # Validate min_similarity is in 0.0-1.0 range
        if not 0.0 <= self.min_similarity <= 1.0:
            raise ValueError(
                f"min_similarity must be between 0.0 and 1.0, got {self.min_similarity}"
            )
