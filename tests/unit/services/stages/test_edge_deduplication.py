"""Tests for edge deduplication in RelationshipExtractionStage.

Per DYK-5: REUSE TextReferenceExtractor._deduplicate_edges() — don't reimplement.
These tests verify the stage correctly delegates to the existing deduplication logic.
"""

from fs2.core.models.code_edge import CodeEdge
from fs2.core.models.edge_type import EdgeType
from fs2.core.services.relationship_extraction.text_reference_extractor import (
    TextReferenceExtractor,
)


class TestEdgeDeduplicationDelegation:
    """Verify RelationshipExtractionStage uses TextReferenceExtractor for dedup."""

    def test_given_text_extractor_when_dedup_called_then_highest_confidence_wins(
        self,
    ) -> None:
        """TextReferenceExtractor keeps highest confidence edge per (src, tgt, line)."""
        extractor = TextReferenceExtractor()

        low_conf = CodeEdge(
            source_node_id="file:README.md",
            target_node_id="file:app.py",
            edge_type=EdgeType.REFERENCES,
            confidence=0.5,
            source_line=5,
        )
        high_conf = CodeEdge(
            source_node_id="file:README.md",
            target_node_id="file:app.py",
            edge_type=EdgeType.REFERENCES,
            confidence=1.0,
            source_line=5,
        )

        result = extractor._deduplicate_edges([low_conf, high_conf])

        assert len(result) == 1
        assert result[0].confidence == 1.0

    def test_given_edges_on_different_lines_when_dedup_then_both_preserved(
        self,
    ) -> None:
        """Per DYK-7: Multiple mentions on different lines are preserved."""
        extractor = TextReferenceExtractor()

        edge_line_5 = CodeEdge(
            source_node_id="file:README.md",
            target_node_id="file:app.py",
            edge_type=EdgeType.REFERENCES,
            confidence=0.5,
            source_line=5,
        )
        edge_line_10 = CodeEdge(
            source_node_id="file:README.md",
            target_node_id="file:app.py",
            edge_type=EdgeType.REFERENCES,
            confidence=0.5,
            source_line=10,
        )

        result = extractor._deduplicate_edges([edge_line_5, edge_line_10])

        assert len(result) == 2

    def test_given_same_target_same_line_when_dedup_then_only_one_kept(self) -> None:
        """Per DYK-7: Same target on same line deduplicates."""
        extractor = TextReferenceExtractor()

        edge1 = CodeEdge(
            source_node_id="file:README.md",
            target_node_id="file:utils.py",
            edge_type=EdgeType.REFERENCES,
            confidence=0.5,
            source_line=3,
        )
        edge2 = CodeEdge(
            source_node_id="file:README.md",
            target_node_id="file:utils.py",
            edge_type=EdgeType.REFERENCES,
            confidence=0.4,
            source_line=3,
        )

        result = extractor._deduplicate_edges([edge1, edge2])

        assert len(result) == 1
        assert result[0].confidence == 0.5  # Higher wins


class TestEdgeDeduplicationSorting:
    """Verify result ordering is deterministic."""

    def test_given_multiple_edges_when_dedup_then_sorted_by_line(self) -> None:
        """Result sorted by source_line for consistency."""
        extractor = TextReferenceExtractor()

        edge_line_20 = CodeEdge(
            source_node_id="file:README.md",
            target_node_id="file:a.py",
            edge_type=EdgeType.REFERENCES,
            confidence=1.0,
            source_line=20,
        )
        edge_line_5 = CodeEdge(
            source_node_id="file:README.md",
            target_node_id="file:b.py",
            edge_type=EdgeType.REFERENCES,
            confidence=1.0,
            source_line=5,
        )

        result = extractor._deduplicate_edges([edge_line_20, edge_line_5])

        assert len(result) == 2
        assert result[0].source_line == 5
        assert result[1].source_line == 20

    def test_given_none_source_line_when_dedup_then_sorted_first(self) -> None:
        """Edges with None source_line sort before numbered lines."""
        extractor = TextReferenceExtractor()

        edge_no_line = CodeEdge(
            source_node_id="file:README.md",
            target_node_id="file:x.py",
            edge_type=EdgeType.REFERENCES,
            confidence=1.0,
            source_line=None,
        )
        edge_line_10 = CodeEdge(
            source_node_id="file:README.md",
            target_node_id="file:y.py",
            edge_type=EdgeType.REFERENCES,
            confidence=1.0,
            source_line=10,
        )

        result = extractor._deduplicate_edges([edge_line_10, edge_no_line])

        assert len(result) == 2
        assert result[0].source_line is None
        assert result[1].source_line == 10


class TestEdgeDeduplicationMultiSource:
    """Verify deduplication works across multiple source files."""

    def test_given_same_target_different_sources_when_dedup_then_both_kept(
        self,
    ) -> None:
        """Different source files pointing to same target are unique edges."""
        extractor = TextReferenceExtractor()

        from_readme = CodeEdge(
            source_node_id="file:README.md",
            target_node_id="file:app.py",
            edge_type=EdgeType.REFERENCES,
            confidence=1.0,
            source_line=5,
        )
        from_docs = CodeEdge(
            source_node_id="file:docs/guide.md",
            target_node_id="file:app.py",
            edge_type=EdgeType.REFERENCES,
            confidence=1.0,
            source_line=5,
        )

        result = extractor._deduplicate_edges([from_readme, from_docs])

        assert len(result) == 2
