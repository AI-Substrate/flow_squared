"""TextMatcher - Case-insensitive substring search.

Provides text-mode search by escaping patterns and delegating to RegexMatcher.
Per Discovery 03: TextMatcher delegates to RegexMatcher after escaping.
Per R1-09: Escape once, not twice.
"""

import re

from fs2.core.models.code_node import CodeNode
from fs2.core.models.search import QuerySpec, SearchResult
from fs2.core.services.search.regex_matcher import RegexMatcher


class TextMatcher:
    """Case-insensitive substring search.

    Transforms text patterns to regex by:
    1. Escaping all regex metacharacters (., *, ?, etc.)
    2. Adding case-insensitive flag (?i)
    3. Delegating to RegexMatcher

    Per Discovery 03: TextMatcher is a thin delegation layer.
    Per R1-09: Escape once only - regex module handles the rest.

    Example:
        >>> matcher = TextMatcher(timeout=2.0)
        >>> results = matcher.match(spec, nodes)
    """

    def __init__(self, timeout: float = 2.0) -> None:
        """Initialize TextMatcher.

        Args:
            timeout: Timeout passed to underlying RegexMatcher.
        """
        self._regex_matcher = RegexMatcher(timeout=timeout)

    def match(
        self,
        spec: QuerySpec,
        nodes: list[CodeNode],
    ) -> list[SearchResult]:
        """Match pattern as case-insensitive substring.

        Transforms the text pattern to regex:
        1. Escape all metacharacters using re.escape()
        2. Prepend (?i) for case-insensitive matching
        3. Delegate to RegexMatcher.match_raw()

        Per Discovery 03: Escape once, delegate to regex.
        Per R1-09: No double escaping.

        Args:
            spec: Query specification (pattern used, mode ignored).
            nodes: List of CodeNodes to search.

        Returns:
            List of SearchResult from matching nodes.
        """
        # Step 1: Escape all regex metacharacters
        escaped = re.escape(spec.pattern)

        # Step 2: Prepend case-insensitive flag
        regex_pattern = f"(?i){escaped}"

        # Step 3: Delegate to RegexMatcher
        return self._regex_matcher.match_raw(regex_pattern, nodes)
