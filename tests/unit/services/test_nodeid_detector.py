"""Tests for NodeIdDetector - detects explicit fs2 node_id patterns.

Purpose: Validate node_id pattern detection with 1.0 confidence
Quality Contribution: Ensures all 5 node_id prefixes are detected correctly
Acceptance Criteria:
- file:, callable:, type:, class:, method: prefixes detected
- Confidence always 1.0 for explicit patterns
- Returns CodeEdge instances with EdgeType.REFERENCES
- Word boundaries prevent URL false positives
- Multiple patterns in same line detected
"""

import pytest

from fs2.core.models.edge_type import EdgeType
from fs2.core.services.relationship_extraction.nodeid_detector import NodeIdDetector


class TestNodeIdDetector:
    """Test suite for NodeIdDetector."""

    def test_given_explicit_file_nodeid_when_detect_then_confidence_1_0(self):
        """
        Purpose: Validate file: prefix detection with correct confidence
        Quality Contribution: Ensures highest confidence for explicit patterns
        Acceptance Criteria: Returns CodeEdge with confidence=1.0, EdgeType.REFERENCES
        """
        detector = NodeIdDetector()
        source_file = "file:README.md"
        content = "See `file:src/app.py` for details."

        edges = detector.detect(source_file, content)

        assert len(edges) == 1
        edge = edges[0]
        assert edge.source_node_id == source_file
        assert edge.target_node_id == "file:src/app.py"
        assert edge.edge_type == EdgeType.REFERENCES
        assert edge.confidence == 1.0
        assert edge.source_line == 1
        assert edge.resolution_rule == "nodeid:explicit"

    def test_given_explicit_callable_nodeid_when_detect_then_returns_edge(self):
        """
        Purpose: Validate callable: prefix with symbol detection
        Quality Contribution: Ensures callable references are captured
        Acceptance Criteria: target_node_id extracted correctly with symbol
        """
        detector = NodeIdDetector()
        source_file = "file:docs/api.md"
        content = (
            "The resolver is at `callable:src/lib/resolver.py:calculate_confidence`"
        )

        edges = detector.detect(source_file, content)

        assert len(edges) == 1
        edge = edges[0]
        assert (
            edge.target_node_id == "callable:src/lib/resolver.py:calculate_confidence"
        )
        assert edge.confidence == 1.0
        assert edge.edge_type == EdgeType.REFERENCES

    def test_given_explicit_class_nodeid_when_detect_then_returns_edge(self):
        """
        Purpose: Validate class: prefix detection
        Quality Contribution: Ensures class references work
        Acceptance Criteria: Correct target_node_id with class symbol
        """
        detector = NodeIdDetector()
        source_file = "file:README.md"
        content = "The main class is `class:src/lib/parser.py:Parser`"

        edges = detector.detect(source_file, content)

        assert len(edges) == 1
        edge = edges[0]
        assert edge.target_node_id == "class:src/lib/parser.py:Parser"
        assert edge.confidence == 1.0

    def test_given_explicit_method_nodeid_when_detect_then_returns_edge(self):
        """
        Purpose: Validate method: prefix detection
        Quality Contribution: Ensures method references work
        Acceptance Criteria: Correct target_node_id with method symbol
        """
        detector = NodeIdDetector()
        source_file = "file:docs/guide.md"
        content = "For language detection, see `method:src/lib/parser.py:Parser.detect_language`"

        edges = detector.detect(source_file, content)

        assert len(edges) == 1
        edge = edges[0]
        assert edge.target_node_id == "method:src/lib/parser.py:Parser.detect_language"
        assert edge.confidence == 1.0

    def test_given_explicit_type_nodeid_when_detect_then_returns_edge(self):
        """
        Purpose: Validate type: prefix detection
        Quality Contribution: Ensures type references work
        Acceptance Criteria: Correct target_node_id with type symbol
        """
        detector = NodeIdDetector()
        source_file = "file:README.md"
        content = "Check `type:src/models/types.py:ImportInfo` for type definitions"

        edges = detector.detect(source_file, content)

        assert len(edges) == 1
        edge = edges[0]
        assert edge.target_node_id == "type:src/models/types.py:ImportInfo"
        assert edge.confidence == 1.0

    def test_given_no_nodeid_when_detect_then_returns_empty_list(self):
        """
        Purpose: Validate no false positives on plain text
        Quality Contribution: Ensures precision of pattern matching
        Acceptance Criteria: Returns empty list for non-matching content
        """
        detector = NodeIdDetector()
        source_file = "file:README.md"
        content = "This is just plain text with no node_id patterns."

        edges = detector.detect(source_file, content)

        assert edges == []

    def test_given_url_when_detect_then_not_matched(self):
        """
        Purpose: Validate URLs are not matched as node_ids
        Quality Contribution: Prevents false positives from URLs
        Acceptance Criteria: URLs with colons don't trigger matches
        """
        detector = NodeIdDetector()
        source_file = "file:README.md"
        content = "See https://example.com and http://github.com for more info."

        edges = detector.detect(source_file, content)

        assert edges == []

    def test_given_multiple_nodeids_when_detect_then_returns_all(self):
        """
        Purpose: Validate multiple patterns in one line
        Quality Contribution: Ensures all references are captured
        Acceptance Criteria: Returns 2 edges for 2 patterns
        """
        detector = NodeIdDetector()
        source_file = "file:docs/plan.md"
        content = "The `class:src/extractors.py:ImportExtractor` uses `callable:src/resolver.py:import_confidence`"

        edges = detector.detect(source_file, content)

        assert len(edges) == 2
        assert edges[0].target_node_id == "class:src/extractors.py:ImportExtractor"
        assert edges[1].target_node_id == "callable:src/resolver.py:import_confidence"

    def test_given_nested_path_when_detect_then_extracts_correctly(self):
        """
        Purpose: Validate deeply nested paths work
        Quality Contribution: Ensures real-world nested paths don't break
        Acceptance Criteria: Deep paths with slashes extracted correctly
        """
        detector = NodeIdDetector()
        source_file = "file:README.md"
        content = "See `class:src/fs2/core/adapters/log_adapter.py:LogAdapter`"

        edges = detector.detect(source_file, content)

        assert len(edges) == 1
        assert (
            edges[0].target_node_id
            == "class:src/fs2/core/adapters/log_adapter.py:LogAdapter"
        )

    def test_given_multiline_content_when_detect_then_tracks_line_numbers(self):
        """
        Purpose: Validate source_line tracking across multiple lines
        Quality Contribution: Ensures navigation to specific line works
        Acceptance Criteria: source_line set correctly for each match
        """
        detector = NodeIdDetector()
        source_file = "file:docs/plan.md"
        content = """Line 1: See `file:src/app.py` first
Line 2: Then check `class:src/models.py:User`
Line 3: Finally review `method:src/auth.py:Auth.login`"""

        edges = detector.detect(source_file, content)

        assert len(edges) == 3
        assert edges[0].source_line == 1
        assert edges[0].target_node_id == "file:src/app.py"
        assert edges[1].source_line == 2
        assert edges[1].target_node_id == "class:src/models.py:User"
        assert edges[2].source_line == 3
        assert edges[2].target_node_id == "method:src/auth.py:Auth.login"

    def test_given_colons_in_text_when_detect_then_no_false_positives(self):
        """
        Purpose: Validate word boundaries prevent false matches
        Quality Contribution: Ensures key:value pairs don't match
        Acceptance Criteria: Returns empty for non-node_id colons
        """
        detector = NodeIdDetector()
        source_file = "file:config.md"
        content = "Configuration: key:value, time:10:30:45, ratio:1:2"

        edges = detector.detect(source_file, content)

        assert edges == []

    def test_given_hyphenated_path_when_detect_then_full_path_captured(self):
        """
        Purpose: Proves hyphenated paths work correctly
        Quality Contribution: Regression-prone - hyphenated paths common in real projects
        Acceptance Criteria: Full path with hyphens captured, not truncated
        """
        content = "See file:docs/plans/022-cross-file-rels/tasks.md for details"
        detector = NodeIdDetector()

        edges = detector.detect("file:README.md", content)

        assert len(edges) == 1
        assert edges[0].target_node_id == "file:docs/plans/022-cross-file-rels/tasks.md"
        assert edges[0].confidence == 1.0

    def test_given_hyphenated_package_name_when_detect_then_matches(self):
        """
        Purpose: Proves Python package names with hyphens work
        Quality Contribution: Edge case - npm/pip packages often have hyphens
        Acceptance Criteria: Packages like my-cool-lib captured correctly
        """
        content = "Import from callable:src/my-cool-lib/handler.py:process"
        detector = NodeIdDetector()

        edges = detector.detect("file:app.py", content)

        assert len(edges) == 1
        assert edges[0].target_node_id == "callable:src/my-cool-lib/handler.py:process"

    def test_given_none_content_when_detect_then_raises_type_error(self):
        """
        Purpose: Proves None content raises meaningful TypeError
        Quality Contribution: Critical path - prevents obscure AttributeError crashes
        Acceptance Criteria: TypeError raised with clear message
        """
        detector = NodeIdDetector()

        with pytest.raises(TypeError, match="content must be string"):
            detector.detect("file:README.md", None)  # type: ignore

    def test_given_int_content_when_detect_then_raises_type_error(self):
        """
        Purpose: Proves non-string content raises TypeError
        Quality Contribution: Edge case - catch type mistakes early
        """
        detector = NodeIdDetector()

        with pytest.raises(TypeError, match="content must be string"):
            detector.detect("file:README.md", 123)  # type: ignore
