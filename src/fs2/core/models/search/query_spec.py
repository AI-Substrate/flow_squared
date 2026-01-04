"""QuerySpec domain model for search query specification.

A frozen dataclass representing a validated search query with:
- Pattern: Non-empty search pattern (AC10)
- Mode: Search mode (TEXT, REGEX, SEMANTIC, AUTO)
- Limit: Maximum results (default 20)
- Min similarity: Semantic search threshold (default 0.25, per DYK-P3-04)
- Include/Exclude: Node ID filters applied BEFORE limit/offset

Per Phase 1 tasks.md: Frozen dataclass with __post_init__ validation.
Per DYK-05: min_similarity only applies to SEMANTIC mode (documented in docstring).
Per DYK-P3-04: min_similarity lowered from 0.5 to 0.25 to capture weakly-related code.
Per fix 2025-12-26: include/exclude filters applied in service layer before pagination.
"""

import re
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
        offset: Number of results to skip for pagination (must be >= 0, default 0).
        min_similarity: Minimum similarity score for matches (0.0-1.0, default 0.25).
            Note: This parameter only applies to SEMANTIC mode searches.
            For TEXT and REGEX modes, this value is ignored.
            Per DYK-P3-04: Lowered from 0.5 to 0.25 to capture weakly-related code.
        include: Tuple of regex patterns - keep only node_ids matching ANY pattern.
            Applied BEFORE limit/offset. None means no filtering.
        exclude: Tuple of regex patterns - remove node_ids matching ANY pattern.
            Applied AFTER include, BEFORE limit/offset. None means no filtering.

    Raises:
        ValueError: If pattern is empty/whitespace, limit < 1,
                    min_similarity is outside 0.0-1.0 range,
                    or include/exclude contain invalid regex patterns.
        TypeError: If mode is not a SearchMode enum value.

    Example:
        >>> spec = QuerySpec(pattern="authentication", mode=SearchMode.SEMANTIC)
        >>> spec.limit
        20
        >>> spec.min_similarity
        0.25
        >>> spec = QuerySpec(
        ...     pattern="handler",
        ...     mode=SearchMode.AUTO,
        ...     include=("src/",),
        ...     exclude=("test",),
        ... )
    """

    pattern: str
    mode: SearchMode
    limit: int = 20
    offset: int = 0
    min_similarity: float = 0.25
    include: tuple[str, ...] | None = None
    exclude: tuple[str, ...] | None = None

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

        # Validate offset is non-negative
        if self.offset < 0:
            raise ValueError(f"Offset must be >= 0, got {self.offset}")

        # Validate min_similarity is in 0.0-1.0 range
        if not 0.0 <= self.min_similarity <= 1.0:
            raise ValueError(
                f"min_similarity must be between 0.0 and 1.0, got {self.min_similarity}"
            )

        # Validate include patterns are valid regex
        if self.include:
            for p in self.include:
                try:
                    re.compile(p)
                except re.error as e:
                    raise ValueError(
                        f"Invalid regex in include pattern '{p}': {e}"
                    ) from None

        # Validate exclude patterns are valid regex
        if self.exclude:
            for p in self.exclude:
                try:
                    re.compile(p)
                except re.error as e:
                    raise ValueError(
                        f"Invalid regex in exclude pattern '{p}': {e}"
                    ) from None
