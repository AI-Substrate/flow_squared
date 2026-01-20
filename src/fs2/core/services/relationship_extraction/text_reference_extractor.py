"""TextReferenceExtractor - combines NodeId and RawFilename detectors.

Orchestrates text reference detection by:
1. Running NodeIdDetector for explicit node_id patterns (confidence 1.0)
2. Running RawFilenameDetector for raw filename patterns (confidence 0.4-0.5)
3. Deduplicating by (source, target, source_line) tuple per DYK-7
4. Returning merged results with highest confidence wins

Deduplication Strategy (DYK-7):
- Preserves multiple mentions of same file on different lines
- Deduplicates matches on same line (highest confidence wins)
- Tuple key: (source_node_id, target_node_id, source_line)
"""

from fs2.core.models.code_edge import CodeEdge
from fs2.core.services.relationship_extraction.nodeid_detector import NodeIdDetector
from fs2.core.services.relationship_extraction.raw_filename_detector import (
    RawFilenameDetector,
)


class TextReferenceExtractor:
    """Combines NodeIdDetector and RawFilenameDetector with deduplication.

    Orchestrates both detectors and merges results using DYK-7 deduplication
    strategy: deduplicate by (source, target, source_line) tuple.

    This preserves multiple mentions of the same file on different lines
    while preventing duplicate edges on the same line.
    """

    def __init__(self) -> None:
        """Initialize extractor with both detectors."""
        self.nodeid_detector = NodeIdDetector()
        self.raw_filename_detector = RawFilenameDetector()

    def extract(self, source_file: str, content: str) -> list[CodeEdge]:
        """Extract all text references from content.

        Runs both detectors and merges results with deduplication.

        Args:
            source_file: Source file path (e.g., "file:README.md")
            content: Text content to scan

        Returns:
            List of CodeEdge instances with duplicates removed.
            Empty list if no references detected.

        Example:
            >>> extractor = TextReferenceExtractor()
            >>> edges = extractor.extract(
            ...     "file:README.md",
            ...     "See `file:src/app.py` and check auth.py"
            ... )
            >>> len(edges)
            2
            >>> {e.target_node_id for e in edges}
            {'file:src/app.py', 'file:auth.py'}
        """
        # Collect edges from both detectors
        all_edges: list[CodeEdge] = []

        # 1. Explicit node_ids (highest confidence)
        nodeid_edges = self.nodeid_detector.detect(source_file, content)
        all_edges.extend(nodeid_edges)

        # 2. Raw filenames (lower confidence)
        filename_edges = self.raw_filename_detector.detect(source_file, content)
        all_edges.extend(filename_edges)

        # 3. Deduplicate by (source, target, source_line) tuple per DYK-7
        # When duplicates exist on same line, keep highest confidence
        deduplicated = self._deduplicate_edges(all_edges)

        return deduplicated

    def _deduplicate_edges(self, edges: list[CodeEdge]) -> list[CodeEdge]:
        """Deduplicate edges by (source, target, source_line) tuple.

        Per DYK-7: Preserves multiple mentions on different lines,
        but deduplicates same target on same line (keeping highest confidence).

        Args:
            edges: List of potentially duplicate edges

        Returns:
            Deduplicated list with highest confidence edges
        """
        # Use dict with tuple key to track unique edges
        # Key: (source_node_id, target_node_id, source_line)
        # Value: CodeEdge (keep highest confidence)
        unique_edges: dict[tuple[str, str, int | None], CodeEdge] = {}

        for edge in edges:
            key = (edge.source_node_id, edge.target_node_id, edge.source_line)

            if key not in unique_edges:
                # First occurrence
                unique_edges[key] = edge
            else:
                # Duplicate - keep higher confidence
                existing = unique_edges[key]
                if edge.confidence > existing.confidence:
                    unique_edges[key] = edge

        # Return as list, sorted by line number for consistency
        result = list(unique_edges.values())
        result.sort(key=lambda e: (e.source_line or 0, e.target_node_id))
        return result
