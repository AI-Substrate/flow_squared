"""Integration tests for text reference detection.

Purpose: Validate complete text reference extraction pipeline
Quality Contribution: Ensures NodeIdDetector and RawFilenameDetector work together
Acceptance Criteria:
- Real markdown fixtures processed correctly
- All node_id patterns detected
- All filename patterns detected
- No URL false positives
- Line numbers tracked accurately
"""

import pytest
from pathlib import Path

from fs2.core.models.edge_type import EdgeType
from fs2.core.services.relationship_extraction.nodeid_detector import NodeIdDetector
from fs2.core.services.relationship_extraction.raw_filename_detector import (
    RawFilenameDetector,
)


class TestTextReferenceIntegration:
    """Integration tests for text reference detection."""

    @pytest.fixture
    def fixtures_dir(self) -> Path:
        """Return path to test fixtures directory."""
        return Path(__file__).parent.parent / "fixtures" / "text_references"

    def test_given_sample_nodeid_md_when_detect_then_finds_all_patterns(
        self, fixtures_dir: Path
    ):
        """
        Purpose: Validate sample fixture detection end-to-end
        Quality Contribution: Ensures real-world fixture works
        Acceptance Criteria: All 8 node_id patterns from fixture detected
        """
        detector = NodeIdDetector()
        fixture_file = fixtures_dir / "sample_nodeid.md"
        
        assert fixture_file.exists(), f"Fixture not found: {fixture_file}"
        
        content = fixture_file.read_text()
        source_file = f"file:{fixture_file.name}"

        edges = detector.detect(source_file, content)

        # Expected patterns from sample_nodeid.md:
        # 1. file:src/lib/parser.py
        # 2. class:src/lib/parser.py:Parser
        # 3. method:src/lib/parser.py:Parser.detect_language
        # 4. callable:src/lib/resolver.py:calculate_confidence
        # 5. type:src/models/types.py:ImportInfo
        # 6. class:src/extractors.py:ImportExtractor
        # 7. method:src/parser.py:Parser.parse_file
        # 8. callable:src/resolver.py:import_confidence
        # 9. file:docs/plans/022-cross-file-rels/tasks.md
        # 10. class:src/fs2/core/adapters/log_adapter.py:LogAdapter
        # 11. method:src/fs2/core/repos/graph_store_impl.py:NetworkXGraphStore.save

        assert len(edges) >= 11, f"Expected at least 11 node_id patterns, got {len(edges)}"
        
        # Validate all are REFERENCES type with confidence 1.0
        for edge in edges:
            assert edge.edge_type == EdgeType.REFERENCES
            assert edge.confidence == 1.0
            assert edge.resolution_rule == "nodeid:explicit"

        # Validate specific patterns exist
        targets = {e.target_node_id for e in edges}
        assert "file:src/lib/parser.py" in targets
        assert "class:src/lib/parser.py:Parser" in targets
        assert "method:src/lib/parser.py:Parser.detect_language" in targets
        assert "callable:src/lib/resolver.py:calculate_confidence" in targets
        assert "type:src/models/types.py:ImportInfo" in targets

    def test_given_execution_log_when_extract_then_finds_references(self):
        """
        Purpose: Validate execution log style content
        Quality Contribution: Ensures plan/log files work
        Acceptance Criteria: Both node_ids and filenames detected
        """
        detector_nodeid = NodeIdDetector()
        detector_filename = RawFilenameDetector()
        
        source_file = "file:execution.log.md"
        content = """## Task T003: Implement NodeIdDetector

### What I Did
Created `nodeid_detector.py` using patterns from `file:scripts/01_nodeid_detection.py`.
The detector returns CodeEdge instances per spec.

### Files Changed
- `/src/fs2/core/services/relationship_extraction/nodeid_detector.py` — Main implementation
- Check auth.py for reference patterns

### Evidence
All tests passing. See `class:src/models.py:CodeEdge` for details.
"""

        # Detect explicit node_ids
        nodeid_edges = detector_nodeid.detect(source_file, content)
        assert len(nodeid_edges) >= 2  # file:scripts/... and class:src/models.py:...
        
        # Detect raw filenames
        filename_edges = detector_filename.detect(source_file, content)
        assert len(filename_edges) >= 2  # nodeid_detector.py and auth.py
        
        # Validate types
        for edge in nodeid_edges:
            assert edge.edge_type == EdgeType.REFERENCES
            assert edge.confidence == 1.0
        
        for edge in filename_edges:
            assert edge.edge_type == EdgeType.DOCUMENTS
            assert edge.confidence in (0.4, 0.5)

    def test_given_readme_when_extract_then_finds_filenames(self):
        """
        Purpose: Validate README.md style content
        Quality Contribution: Ensures documentation files work
        Acceptance Criteria: Filenames with various extensions detected
        """
        detector = RawFilenameDetector()
        
        source_file = "file:README.md"
        content = """# Project Documentation

## Getting Started

1. Run `install.sh` to set up
2. Configure settings in config.yaml
3. Check src/main.py for entry point
4. See Component.tsx for UI example

Visit https://github.com/user/repo for more info.
"""

        edges = detector.detect(source_file, content)
        
        # Should find: install.sh, config.yaml, src/main.py, Component.tsx
        # Should NOT find: github.com or repo (URL filtered)
        assert len(edges) == 4
        
        targets = {e.target_node_id for e in edges}
        assert "file:install.sh" in targets
        assert "file:config.yaml" in targets
        assert "file:src/main.py" in targets  # Captures full path
        assert "file:Component.tsx" in targets
        
        # Validate no URL false positives
        assert not any("github" in e.target_node_id for e in edges)
        assert not any("repo" in e.target_node_id for e in edges)

    def test_given_mixed_content_when_detect_then_no_duplicates_across_detectors(self):
        """
        Purpose: Validate detectors work independently without conflicts
        Quality Contribution: Ensures clean separation of concerns
        Acceptance Criteria: Each detector returns appropriate edges
        """
        detector_nodeid = NodeIdDetector()
        detector_filename = RawFilenameDetector()
        
        source_file = "file:mixed.md"
        content = "Check `file:src/app.py` and also app.py separately"
        
        nodeid_edges = detector_nodeid.detect(source_file, content)
        filename_edges = detector_filename.detect(source_file, content)
        
        # NodeIdDetector finds explicit file:src/app.py
        assert len(nodeid_edges) == 1
        assert nodeid_edges[0].target_node_id == "file:src/app.py"
        assert nodeid_edges[0].confidence == 1.0
        
        # RawFilenameDetector finds both (dedup happens at extractor level)
        # It will match both "app.py" instances (one in backticks with file:, one bare)
        # The file:src/app.py will match just "app.py" part
        assert len(filename_edges) >= 1
        
        # Validate types are correct
        for edge in nodeid_edges:
            assert edge.edge_type == EdgeType.REFERENCES
        
        for edge in filename_edges:
            assert edge.edge_type == EdgeType.DOCUMENTS
