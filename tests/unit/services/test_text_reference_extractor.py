"""Tests for TextReferenceExtractor - combines NodeId and RawFilename detectors.

Purpose: Validate extractor combines detectors with correct deduplication
Quality Contribution: Ensures DYK-7 deduplication strategy works
Acceptance Criteria:
- Combines NodeIdDetector and RawFilenameDetector results
- Deduplicates by (source, target, source_line) tuple per DYK-7
- Explicit node_ids take precedence over raw filenames
- Multiple mentions on different lines preserved
"""

import pytest

from fs2.core.models.code_edge import CodeEdge
from fs2.core.models.edge_type import EdgeType
from fs2.core.services.relationship_extraction.text_reference_extractor import (
    TextReferenceExtractor,
)


class TestTextReferenceExtractor:
    """Test suite for TextReferenceExtractor."""

    def test_given_explicit_nodeid_when_extract_then_returns_edge(self):
        """
        Purpose: Validate basic extraction works
        Quality Contribution: Ensures extractor uses NodeIdDetector
        Acceptance Criteria: Explicit node_id detected
        """
        extractor = TextReferenceExtractor()
        source_file = "file:README.md"
        content = "See `file:src/app.py` for details."

        edges = extractor.extract(source_file, content)

        assert len(edges) == 1
        edge = edges[0]
        assert edge.target_node_id == "file:src/app.py"
        assert edge.edge_type == EdgeType.REFERENCES
        assert edge.confidence == 1.0

    def test_given_raw_filename_when_extract_then_returns_edge(self):
        """
        Purpose: Validate raw filename extraction works
        Quality Contribution: Ensures extractor uses RawFilenameDetector
        Acceptance Criteria: Raw filename detected
        """
        extractor = TextReferenceExtractor()
        source_file = "file:README.md"
        content = "Check `auth.py` for authentication."

        edges = extractor.extract(source_file, content)

        assert len(edges) == 1
        edge = edges[0]
        assert edge.target_node_id == "file:auth.py"
        assert edge.edge_type == EdgeType.DOCUMENTS
        assert edge.confidence == 0.5

    def test_given_both_nodeid_and_filename_when_extract_then_returns_both(self):
        """
        Purpose: Validate both detectors work together
        Quality Contribution: Ensures combination works
        Acceptance Criteria: Both patterns detected
        """
        extractor = TextReferenceExtractor()
        source_file = "file:README.md"
        content = "See `file:src/app.py` and also check models.py"

        edges = extractor.extract(source_file, content)

        assert len(edges) == 2
        targets = {e.target_node_id for e in edges}
        assert "file:src/app.py" in targets
        assert "file:models.py" in targets

    def test_given_same_file_different_lines_when_extract_then_preserves_both(self):
        """
        Purpose: Validate DYK-7 deduplication strategy
        Quality Contribution: Ensures multiple mentions preserved
        Acceptance Criteria: Same file on lines 1 and 3 → 2 edges
        """
        extractor = TextReferenceExtractor()
        source_file = "file:README.md"
        content = """Line 1: See `auth.py` first
Line 2: Some other text
Line 3: Review `auth.py` again"""

        edges = extractor.extract(source_file, content)

        # Should have 2 edges for auth.py (lines 1 and 3)
        auth_edges = [e for e in edges if e.target_node_id == "file:auth.py"]
        assert len(auth_edges) == 2
        
        lines = {e.source_line for e in auth_edges}
        assert lines == {1, 3}

    def test_given_same_file_same_line_when_extract_then_deduplicates(self):
        """
        Purpose: Validate deduplication on same line
        Quality Contribution: Prevents duplicate edges on same line
        Acceptance Criteria: Same file twice on same line → 1 edge
        """
        extractor = TextReferenceExtractor()
        source_file = "file:README.md"
        content = "Check `auth.py` and auth.py on same line"

        edges = extractor.extract(source_file, content)

        # Should deduplicate to 1 edge (same source, target, line)
        # But RawFilenameDetector will find both matches
        # Deduplication by (source, target, source_line) should keep only 1
        auth_edges = [e for e in edges if e.target_node_id == "file:auth.py"]
        
        # Actually, they have different confidences (0.5 vs 0.4) so might be different
        # Let me check: backtick `auth.py` (0.5) and bare auth.py (0.4)
        # Both on line 1, same target → should deduplicate
        # The question is which one wins? Higher confidence should win
        assert len(auth_edges) == 1
        assert auth_edges[0].confidence == 0.5  # Higher confidence wins

    def test_given_nodeid_overlaps_filename_when_extract_then_nodeid_wins(self):
        """
        Purpose: Validate explicit node_ids take precedence
        Quality Contribution: Ensures higher confidence wins
        Acceptance Criteria: file:auth.py (1.0) beats auth.py (0.4)
        """
        extractor = TextReferenceExtractor()
        source_file = "file:README.md"
        content = "See file:auth.py for details"
        
        # Both NodeIdDetector (file:auth.py → 1.0) and 
        # RawFilenameDetector (auth.py → 0.4) will match
        edges = extractor.extract(source_file, content)
        
        # Should have 1 edge with confidence 1.0 (node_id wins)
        auth_edges = [e for e in edges if e.target_node_id == "file:auth.py"]
        assert len(auth_edges) == 1
        assert auth_edges[0].confidence == 1.0
        assert auth_edges[0].edge_type == EdgeType.REFERENCES

    def test_given_empty_content_when_extract_then_returns_empty(self):
        """
        Purpose: Validate empty content handling
        Quality Contribution: Edge case handling
        Acceptance Criteria: Empty content → empty list
        """
        extractor = TextReferenceExtractor()
        source_file = "file:README.md"
        content = ""

        edges = extractor.extract(source_file, content)

        assert edges == []

    def test_given_url_in_content_when_extract_then_no_false_positives(self):
        """
        Purpose: Validate URL filtering (DYK-6)
        Quality Contribution: Ensures URL pre-filtering works end-to-end
        Acceptance Criteria: URLs don't create edges
        """
        extractor = TextReferenceExtractor()
        source_file = "file:README.md"
        content = "Visit https://github.com/user/repo.git for code"

        edges = extractor.extract(source_file, content)

        # Should not match "repo.git" due to URL filtering
        assert edges == []
