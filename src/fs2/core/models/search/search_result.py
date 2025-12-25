"""SearchResult domain model for search results.

A frozen dataclass representing a single search result with:
- Core fields (always present in both detail levels)
- Max-only fields (content, matched_lines, chunk_offset, embedding_chunk_index)

Per Phase 1 tasks.md DYK-02: Normative 13-field reference.
Per Phase 1 tasks.md DYK-01: Max mode returns all 13 fields; null for mode-irrelevant.
Per Discovery 08: Frozen dataclass with to_dict(detail) method.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SearchResult:
    """Immutable search result with detail level support.

    Contains all fields needed for both min and max detail output.
    The to_dict(detail) method filters fields based on detail level.

    Attributes (9 min-mode fields):
        node_id: Node identifier string.
        start_line: Node start line (1-indexed).
        end_line: Node end line (1-indexed).
        match_start_line: Match start line within node.
        match_end_line: Match end line within node.
        smart_content: AI-generated summary (can be None).
        snippet: ~50 char context string.
        score: Match score 0.0-1.0.
        match_field: Which field matched (content, node_id, smart_content, embedding).

    Attributes (4 max-only fields - per DYK-01, null when not applicable):
        content: Full node content string.
        matched_lines: List of matched line numbers (text/regex only, None for semantic).
        chunk_offset: Tuple (start_line, end_line) for matched chunk (semantic only).
        embedding_chunk_index: Index of matched embedding chunk (semantic only).

    Example:
        >>> result = SearchResult(
        ...     node_id="callable:test.py:func",
        ...     start_line=10, end_line=20,
        ...     match_start_line=12, match_end_line=12,
        ...     smart_content="A test function",
        ...     snippet="def func():",
        ...     score=0.85,
        ...     match_field="content",
        ...     content="def func():\\n    pass"
        ... )
        >>> len(result.to_dict(detail="min"))
        9
        >>> len(result.to_dict(detail="max"))
        13
    """

    # === Min-mode fields (9 fields) ===
    node_id: str
    start_line: int
    end_line: int
    match_start_line: int
    match_end_line: int
    smart_content: str | None
    snippet: str
    score: float
    match_field: str

    # === Max-only fields (4 fields) ===
    # Per DYK-01: Set to None for mode-irrelevant results
    content: str | None = None
    matched_lines: list[int] | None = None  # Text/regex only, None for semantic
    chunk_offset: tuple[int, int] | None = None  # Semantic only, None for text/regex
    embedding_chunk_index: int | None = None  # Semantic only, None for text/regex

    def to_dict(self, detail: str = "min") -> dict[str, Any]:
        """Convert to dictionary with detail level filtering.

        Args:
            detail: Detail level - "min" (9 fields) or "max" (13 fields).
                    Default is "min".

        Returns:
            Dictionary with fields appropriate for the detail level.
            Per DYK-01, max mode always includes all 13 fields;
            mode-irrelevant fields are None.

        Example:
            >>> result.to_dict(detail="min")  # 9 fields
            {'node_id': '...', 'score': 0.85, ...}
            >>> result.to_dict(detail="max")  # 13 fields
            {'node_id': '...', 'content': '...', 'chunk_offset': None, ...}
        """
        # Min-mode: 9 core fields
        result = {
            "node_id": self.node_id,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "match_start_line": self.match_start_line,
            "match_end_line": self.match_end_line,
            "smart_content": self.smart_content,
            "snippet": self.snippet,
            "score": self.score,
            "match_field": self.match_field,
        }

        # Max-mode: Add 4 additional fields (DYK-01: all 13 fields, null if N/A)
        if detail == "max":
            result["content"] = self.content
            result["matched_lines"] = self.matched_lines
            result["chunk_offset"] = self.chunk_offset
            result["embedding_chunk_index"] = self.embedding_chunk_index

        return result
