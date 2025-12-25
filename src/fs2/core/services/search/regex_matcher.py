"""RegexMatcher - Pattern matching with timeout protection.

Provides regex-based search with the `regex` module's timeout protection
against catastrophic backtracking (ReDoS attacks).

Per Phase 2 tasks.md:
- Discovery 04: Use `regex` module with timeout parameter
- DYK-P2-02: Absolute file-level line extraction
- DYK-P2-05: Snippet contains full matched line
- DYK-P2-06: Compile pattern once, search many nodes
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

import regex

from fs2.core.models.code_node import CodeNode
from fs2.core.models.search import QuerySpec, SearchResult
from fs2.core.services.search.exceptions import SearchError

if TYPE_CHECKING:
    pass


@dataclass
class FieldMatch:
    """Internal result from matching a single field."""

    field_name: str  # "node_id", "content", "smart_content"
    match: regex.Match[str]
    score: float


class RegexMatcher:
    """Regex pattern matching with timeout protection.

    Uses the `regex` module (not `re`) which provides a timeout parameter
    for protection against catastrophic backtracking.

    Per Discovery 04: Pattern is compiled once before iterating nodes.
    Per DYK-P2-02: Line numbers are absolute file-level lines.
    Per DYK-P2-05: Snippet contains full matched line.

    Scoring:
        - node_id exact match: 1.0
        - node_id partial match: 0.8
        - content/smart_content match: 0.5
        - Multiple fields: highest score wins (no accumulation)

    Example:
        >>> matcher = RegexMatcher(timeout=2.0)
        >>> results = matcher.match(spec, nodes)
    """

    def __init__(self, timeout: float = 2.0) -> None:
        """Initialize RegexMatcher with timeout protection.

        Args:
            timeout: Maximum time in seconds for each regex search operation.
                     Default is 2.0 seconds (from SearchConfig.regex_timeout).
        """
        self._timeout = timeout

    def match(
        self,
        spec: QuerySpec,
        nodes: list[CodeNode],
    ) -> list[SearchResult]:
        """Match pattern against nodes and return scored results.

        Searches three fields per node: node_id, content, smart_content.
        Returns SearchResult for each node with at least one match.

        Per DYK-P2-06: Pattern is compiled once before iterating.

        Args:
            spec: Query specification with pattern and options.
            nodes: List of CodeNodes to search.

        Returns:
            List of SearchResult, one per matching node.
            Results are NOT sorted (caller handles sorting).

        Raises:
            SearchError: If the regex pattern is invalid.
        """
        # Compile pattern once (DYK-P2-06 optimization)
        try:
            compiled = regex.compile(spec.pattern)
        except regex.error as e:
            raise SearchError(f"Invalid regex pattern: {e}") from e

        results: list[SearchResult] = []

        for node in nodes:
            field_match = self._find_best_field_match(compiled, node)
            if field_match:
                result = self._build_result(node, field_match)
                results.append(result)

        return results

    def match_raw(
        self,
        pattern: str,
        nodes: list[CodeNode],
    ) -> list[SearchResult]:
        """Match a pre-transformed pattern against nodes.

        Used by TextMatcher after escaping special characters.
        This method takes a raw regex pattern string directly.

        Args:
            pattern: Pre-formed regex pattern string.
            nodes: List of CodeNodes to search.

        Returns:
            List of SearchResult, one per matching node.

        Raises:
            SearchError: If the regex pattern is invalid.
        """
        # Compile pattern once (DYK-P2-06 optimization)
        try:
            compiled = regex.compile(pattern)
        except regex.error as e:
            raise SearchError(f"Invalid regex pattern: {e}") from e

        results: list[SearchResult] = []

        for node in nodes:
            field_match = self._find_best_field_match(compiled, node)
            if field_match:
                result = self._build_result(node, field_match)
                results.append(result)

        return results

    def _find_best_field_match(
        self,
        compiled: regex.Pattern[str],
        node: CodeNode,
    ) -> FieldMatch | None:
        """Find the best (highest scoring) field match for a node.

        Searches: node_id, content, smart_content in that order.
        Returns the match with highest score (DYK-P2-03: highest wins).

        Args:
            compiled: Compiled regex pattern.
            node: CodeNode to search.

        Returns:
            FieldMatch with best score, or None if no match.
        """
        best: FieldMatch | None = None

        # Search node_id first (highest priority scoring)
        node_id_match = self._search_with_timeout(compiled, node.node_id)
        if node_id_match:
            # Check if exact match (pattern matches entire node_id)
            score = 1.0 if node_id_match.group() == node.node_id else 0.8
            best = FieldMatch("node_id", node_id_match, score)

        # Search content (only if it might beat current best)
        if node.content:
            content_match = self._search_with_timeout(compiled, node.content)
            if content_match:
                score = 0.5
                if best is None or score > best.score:
                    best = FieldMatch("content", content_match, score)

        # Search smart_content (only if it might beat current best)
        if node.smart_content:
            smart_match = self._search_with_timeout(compiled, node.smart_content)
            if smart_match:
                score = 0.5
                if best is None or score > best.score:
                    best = FieldMatch("smart_content", smart_match, score)

        return best

    def _search_with_timeout(
        self,
        compiled: regex.Pattern[str],
        text: str,
    ) -> regex.Match[str] | None:
        """Search text with timeout protection.

        Uses the regex module's timeout parameter to prevent
        catastrophic backtracking (ReDoS).

        Args:
            compiled: Compiled regex pattern.
            text: Text to search.

        Returns:
            Match object if found, None if no match or timeout.
        """
        if not text:
            return None
        try:
            return compiled.search(text, timeout=self._timeout)
        except TimeoutError:
            # Graceful degradation - treat timeout as no match
            return None

    def _build_result(
        self,
        node: CodeNode,
        field_match: FieldMatch,
    ) -> SearchResult:
        """Build SearchResult from node and field match.

        Per DYK-P2-02: Line numbers are absolute file-level lines.
        Per DYK-P2-04: smart_content uses node's full range.
        Per DYK-P2-05: Snippet is full line at match start.

        Args:
            node: The matched CodeNode.
            field_match: The winning field match.

        Returns:
            SearchResult with all fields populated.
        """
        # Calculate line numbers (DYK-P2-02, DYK-P2-04)
        match_start_line, match_end_line = self._extract_match_lines(
            node, field_match
        )

        # Extract snippet (DYK-P2-05)
        snippet = self._extract_snippet(node, field_match)

        return SearchResult(
            node_id=node.node_id,
            start_line=node.start_line,
            end_line=node.end_line,
            match_start_line=match_start_line,
            match_end_line=match_end_line,
            smart_content=node.smart_content,
            snippet=snippet,
            score=field_match.score,
            match_field=field_match.field_name,
            content=node.content,
            matched_lines=list(range(match_start_line, match_end_line + 1)),
        )

    def _extract_match_lines(
        self,
        node: CodeNode,
        field_match: FieldMatch,
    ) -> tuple[int, int]:
        """Extract absolute file-level line numbers for the match.

        Per DYK-P2-02: Line numbers must be absolute (file-level).
        Per DYK-P2-04: smart_content matches use node's full range.

        Args:
            node: The matched CodeNode (has start_line from TreeSitter).
            field_match: The field match with Match object.

        Returns:
            (match_start_line, match_end_line) as absolute file line numbers.
        """
        if field_match.field_name == "smart_content":
            # DYK-P2-04: AI summary doesn't map to file lines - use node's range
            return node.start_line, node.end_line

        if field_match.field_name == "node_id":
            # node_id matches span the first line of the node
            return node.start_line, node.start_line

        # Content match - calculate from character offsets
        content = node.content or ""
        match = field_match.match

        # Count newlines before match start
        lines_before_start = content[: match.start()].count("\n")
        match_start_line = node.start_line + lines_before_start

        # Count newlines before match end
        lines_before_end = content[: match.end()].count("\n")
        match_end_line = node.start_line + lines_before_end

        return match_start_line, match_end_line

    def _extract_snippet(
        self,
        node: CodeNode,
        field_match: FieldMatch,
    ) -> str:
        """Extract snippet for the match.

        Per DYK-P2-05: Snippet contains full line where match starts.
        For node_id matches, use the node_id itself.
        For multiline matches, show first matched line only.

        Args:
            node: The matched CodeNode.
            field_match: The field match.

        Returns:
            Snippet string (full line at match start).
        """
        if field_match.field_name == "node_id":
            # For node_id matches, the snippet is the node_id itself
            return node.node_id

        # Get the text that was searched
        if field_match.field_name == "content":
            text = node.content or ""
        else:  # smart_content
            text = node.smart_content or ""

        # Find the line containing the match start
        lines = text.split("\n")
        line_index = text[: field_match.match.start()].count("\n")

        if line_index < len(lines):
            return lines[line_index]

        # Fallback (shouldn't happen)
        return text[:50] if text else ""
