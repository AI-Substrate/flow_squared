"""RawFilenameDetector - detects raw filename mentions in text.

Scans text content for raw filename patterns like:
- `auth_handler.py` (backtick-quoted, confidence 0.5)
- auth_handler.py (bare inline, confidence 0.4)
- src/auth/handler.py (nested paths)
- Component.tsx (TypeScript)

Returns CodeEdge instances with:
- edge_type: EdgeType.DOCUMENTS (documentation reference)
- confidence: 0.5 (backtick) or 0.4 (bare)
- resolution_rule: "filename:backtick" or "filename:bare"

Implements URL pre-filtering per DYK-6 to avoid false positives:
- Filters out URLs: https://example.com/file.py
- Filters out domains: github.com

Pattern ported from 022 experiment: 01_nodeid_detection.py
"""

import re

from fs2.core.models.code_edge import CodeEdge
from fs2.core.models.edge_type import EdgeType


class RawFilenameDetector:
    """Detects raw filename mentions in text content.

    Uses regex patterns to find filenames with code extensions.
    Implements confidence tiers based on quoting:
    - Backtick/quote wrapped: 0.5 (intentional reference)
    - Bare inline: 0.4 (uncertain reference)

    Filters URLs per DYK-6 to prevent false positives.
    """

    # URL patterns to filter out before filename detection (DYK-6)
    # Matches: http://, https://, ftp://, file://, etc.
    URL_PATTERN = re.compile(
        r'\b(?:https?|ftp|file)://[^\s]+',
        re.IGNORECASE
    )

    # Domain-like patterns: github.com, example.org, etc.
    # Prevents "github.com" → "github.c" false positive from 022
    DOMAIN_PATTERN = re.compile(
        r'\b(?:[\w-]+\.)+(?:com|org|net|edu|gov|io|co|dev|app|ai|'
        r'uk|de|fr|cn|ru|jp|au|ca|br|in|info|xyz|tech|me|tv)\b',
        re.IGNORECASE
    )

    # Raw filename pattern - detects filenames with code extensions
    # Captures filename with path, with optional backticks/quotes
    # Note: Longer extensions (tsx, jsx, hpp, etc.) MUST come before shorter ones (ts, js, etc.)
    RAW_FILENAME_PATTERN = re.compile(
        r'([`"\'])?'  # Optional opening quote/backtick (group 1)
        r'((?:[\w.-]+/)*[\w.-]+\.(?:tsx|jsx|hpp|cpp|bash|yaml|toml|graphql|proto|scss|sass|html|json|java|swift|scala|ts|js|py|go|rs|c|h|rb|kt|cs|php|lua|sh|zsh|yml|xml|css|sql|md))'  # Filename with path (group 2)
        r'([`"\'])?',  # Optional closing quote/backtick (group 3)
        re.IGNORECASE
    )

    def detect(self, source_file: str, content: str) -> list[CodeEdge]:
        """Detect raw filename patterns in text content.

        Args:
            source_file: Source file path (e.g., "file:README.md")
            content: Text content to scan

        Returns:
            List of CodeEdge instances for each filename found.
            Empty list if no filenames detected.

        Example:
            >>> detector = RawFilenameDetector()
            >>> edges = detector.detect(
            ...     "file:README.md",
            ...     "Check `auth.py` for authentication"
            ... )
            >>> len(edges)
            1
            >>> edges[0].target_node_id
            'file:auth.py'
            >>> edges[0].confidence
            0.5
        """
        # Validate inputs
        if not isinstance(source_file, str):
            raise TypeError(f'source_file must be string, got {type(source_file).__name__}')
        if not isinstance(content, str):
            raise TypeError(f'content must be string, got {type(content).__name__}')

        edges: list[CodeEdge] = []

        # Pre-filter: Remove URLs and domains from content (DYK-6)
        # This prevents "github.com/repo.git" from matching "repo.git"
        filtered_content = self._filter_urls(content)

        # Split into lines for line number tracking
        lines = filtered_content.split('\n')

        for line_num, filtered_line in enumerate(lines, start=1):
            # Find all filename patterns in this line
            for match in self.RAW_FILENAME_PATTERN.finditer(filtered_line):
                opening_quote = match.group(1) or ''
                filename = match.group(2)
                closing_quote = match.group(3) or ''

                # Determine confidence based on quoting
                # Backticks/quotes suggest intentional code reference
                if opening_quote or closing_quote:
                    confidence = 0.5
                    resolution_rule = "filename:backtick"
                else:
                    confidence = 0.4
                    resolution_rule = "filename:bare"

                # Create CodeEdge for this match
                edge = CodeEdge(
                    source_node_id=source_file,
                    target_node_id=f"file:{filename}",
                    edge_type=EdgeType.DOCUMENTS,
                    confidence=confidence,
                    source_line=line_num,
                    resolution_rule=resolution_rule,
                )
                edges.append(edge)

        return edges

    def _filter_urls(self, content: str) -> str:
        """Filter out URLs and domain patterns from content.

        Per DYK-6: Prevents false positives like:
        - "https://github.com/repo.git" → "repo.git"
        - "github.com" → "github.c"

        Args:
            content: Original text content

        Returns:
            Content with URLs and domains replaced by spaces
        """
        # Replace URLs with spaces (preserve line structure)
        filtered = self.URL_PATTERN.sub(lambda m: ' ' * len(m.group(0)), content)

        # Replace domains with spaces
        filtered = self.DOMAIN_PATTERN.sub(lambda m: ' ' * len(m.group(0)), filtered)

        return filtered
