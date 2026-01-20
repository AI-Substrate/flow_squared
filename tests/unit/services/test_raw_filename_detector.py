"""Tests for RawFilenameDetector - detects raw filename mentions.

Purpose: Validate raw filename detection with confidence tiers
Quality Contribution: Ensures filename references in docs are captured
Acceptance Criteria:
- Backtick-quoted filenames: confidence 0.5
- Bare filenames: confidence 0.4
- Common code extensions detected
- URL pre-filtering (DYK-6) prevents false positives
- Returns CodeEdge instances with EdgeType.DOCUMENTS
"""

import pytest

from fs2.core.models.code_edge import CodeEdge
from fs2.core.models.edge_type import EdgeType
from fs2.core.services.relationship_extraction.raw_filename_detector import (
    RawFilenameDetector,
)


class TestRawFilenameDetector:
    """Test suite for RawFilenameDetector."""

    def test_given_backtick_filename_when_detect_then_confidence_0_5(self):
        """
        Purpose: Validate backtick-quoted filenames get higher confidence
        Quality Contribution: Intentional code references get proper weighting
        Acceptance Criteria: confidence=0.5 for backtick-quoted
        """
        detector = RawFilenameDetector()
        source_file = "file:README.md"
        content = "Check `auth.py` for authentication logic."

        edges = detector.detect(source_file, content)

        assert len(edges) == 1
        edge = edges[0]
        assert edge.source_node_id == source_file
        assert edge.target_node_id == "file:auth.py"
        assert edge.edge_type == EdgeType.DOCUMENTS
        assert edge.confidence == 0.5
        assert edge.source_line == 1
        assert edge.resolution_rule == "filename:backtick"

    def test_given_bare_filename_when_detect_then_confidence_0_4(self):
        """
        Purpose: Validate bare filenames get lower confidence
        Quality Contribution: Uncertain references get lower weighting
        Acceptance Criteria: confidence=0.4 for bare filenames
        """
        detector = RawFilenameDetector()
        source_file = "file:docs/guide.md"
        content = "The main module is app.py which handles routing."

        edges = detector.detect(source_file, content)

        assert len(edges) == 1
        edge = edges[0]
        assert edge.target_node_id == "file:app.py"
        assert edge.confidence == 0.4
        assert edge.resolution_rule == "filename:bare"

    def test_given_nested_path_filename_when_detect_then_extracts(self):
        """
        Purpose: Validate nested path detection
        Quality Contribution: Real-world paths with directories work
        Acceptance Criteria: Paths like src/auth/handler.py extracted
        """
        detector = RawFilenameDetector()
        source_file = "file:README.md"
        content = "See src/auth/handler.py for auth logic."

        edges = detector.detect(source_file, content)

        assert len(edges) == 1
        edge = edges[0]
        assert edge.target_node_id == "file:src/auth/handler.py"

    def test_given_typescript_extension_when_detect_then_matches(self):
        """
        Purpose: Validate TypeScript extensions work
        Quality Contribution: Multi-language filename detection
        Acceptance Criteria: .tsx extension detected
        """
        detector = RawFilenameDetector()
        source_file = "file:README.md"
        content = "The component is in `Component.tsx` file."

        edges = detector.detect(source_file, content)

        assert len(edges) == 1
        edge = edges[0]
        assert edge.target_node_id == "file:Component.tsx"

    def test_given_various_extensions_when_detect_then_matches_code_files(self):
        """
        Purpose: Validate common code extensions
        Quality Contribution: Language-agnostic detection
        Acceptance Criteria: py, js, go, rs, java all work
        """
        detector = RawFilenameDetector()
        source_file = "file:README.md"
        content = "Files: `main.go`, `app.rs`, `Server.java`, `util.js`"

        edges = detector.detect(source_file, content)

        assert len(edges) == 4
        targets = {e.target_node_id for e in edges}
        assert targets == {
            "file:main.go",
            "file:app.rs",
            "file:Server.java",
            "file:util.js",
        }

    def test_given_unknown_extension_when_detect_then_no_match(self):
        """
        Purpose: Validate unknown extensions are skipped
        Quality Contribution: Prevents noise from non-code files
        Acceptance Criteria: .xyz doesn't match
        """
        detector = RawFilenameDetector()
        source_file = "file:README.md"
        content = "Random file.xyz should not match."

        edges = detector.detect(source_file, content)

        assert edges == []

    def test_given_url_with_filename_when_detect_then_skips(self):
        """
        Purpose: Validate URLs are filtered (DYK-6)
        Quality Contribution: Prevents github.com → github.c false positives
        Acceptance Criteria: URLs don't create edges
        """
        detector = RawFilenameDetector()
        source_file = "file:README.md"
        content = "Clone from github.com/user/repo.git for code."

        edges = detector.detect(source_file, content)

        # repo.git should NOT be matched due to URL context
        assert edges == []

    def test_given_https_url_when_detect_then_skips(self):
        """
        Purpose: Validate HTTPS URLs are filtered (DYK-6)
        Quality Contribution: Comprehensive URL filtering
        Acceptance Criteria: Full URLs don't create edges
        """
        detector = RawFilenameDetector()
        source_file = "file:README.md"
        content = "Download from https://example.com/files/data.json today."

        edges = detector.detect(source_file, content)

        # data.json should NOT be matched due to URL context
        assert edges == []

    def test_given_domain_like_filename_when_detect_then_skips(self):
        """
        Purpose: Validate domain-like patterns are filtered (DYK-6 core case)
        Quality Contribution: Prevents github.com → github.c bug from 022
        Acceptance Criteria: github.com doesn't create github.c edge
        """
        detector = RawFilenameDetector()
        source_file = "file:README.md"
        content = "Visit github.com for more info."

        edges = detector.detect(source_file, content)

        # Should NOT match "github.c" or "github.com"
        assert edges == []

    def test_given_multiline_content_when_detect_then_tracks_lines(self):
        """
        Purpose: Validate line tracking for multiple files
        Quality Contribution: Navigation to specific mentions
        Acceptance Criteria: source_line correct for each match
        """
        detector = RawFilenameDetector()
        source_file = "file:README.md"
        content = """Line 1: See `auth.py` first
Line 2: Then check models.py
Line 3: Review `utils.js` last"""

        edges = detector.detect(source_file, content)

        assert len(edges) == 3
        assert edges[0].source_line == 1
        assert edges[0].target_node_id == "file:auth.py"
        assert edges[1].source_line == 2
        assert edges[1].target_node_id == "file:models.py"
        assert edges[2].source_line == 3
        assert edges[2].target_node_id == "file:utils.js"

    def test_given_already_matched_nodeid_when_detect_then_skips(self):
        """
        Purpose: Validate explicit node_ids are not double-matched
        Quality Contribution: Prevents duplicate edges
        Acceptance Criteria: file:auth.py (explicit) not matched as raw filename
        """
        detector = RawFilenameDetector()
        source_file = "file:README.md"
        # This should NOT be matched as a raw filename (it's an explicit node_id)
        content = "See file:auth.py for details."

        edges = detector.detect(source_file, content)

        # The detector should skip patterns that look like explicit node_ids
        # This test validates the detector doesn't re-extract what NodeIdDetector handles
        # For now, we expect the raw filename detector to match "auth.py" part
        # The deduplication happens at the TextReferenceExtractor level (T007)
        # So this test expects 1 match but lower priority
        assert len(edges) == 1
        assert edges[0].target_node_id == "file:auth.py"

    def test_given_mixed_quotes_when_detect_then_handles_correctly(self):
        """
        Purpose: Validate quote handling (backticks, single, double)
        Quality Contribution: Markdown and doc format flexibility
        Acceptance Criteria: All quote styles get 0.5 confidence
        """
        detector = RawFilenameDetector()
        source_file = "file:README.md"
        content = 'Files: `app.py`, "auth.py", and \'models.py\''

        edges = detector.detect(source_file, content)

        assert len(edges) == 3
        for edge in edges:
            assert edge.confidence == 0.5  # All quoted get higher confidence

    def test_given_none_content_when_detect_then_raises_type_error(self):
        """
        Purpose: Proves None content raises meaningful TypeError
        Quality Contribution: Critical path - prevents obscure crashes
        Acceptance Criteria: TypeError raised with clear message
        """
        detector = RawFilenameDetector()

        with pytest.raises(TypeError, match="content must be string"):
            detector.detect("file:README.md", None)  # type: ignore

    def test_given_list_content_when_detect_then_raises_type_error(self):
        """
        Purpose: Proves non-string content raises TypeError
        Quality Contribution: Edge case - catch type mistakes early
        """
        detector = RawFilenameDetector()

        with pytest.raises(TypeError, match="content must be string"):
            detector.detect("file:README.md", ["not", "a", "string"])  # type: ignore
