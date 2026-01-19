"""Unit tests for SolidLspAdapter type translation.

TDD Phase: RED - These tests will fail until SolidLspAdapter is implemented.

Tests cover:
- AC08: LSP Location → CodeEdge with EdgeType.REFERENCES
- AC09: LSP Location → CodeEdge with EdgeType.CALLS  
- AC10: All LSP-derived edges have confidence=1.0 and resolution_rule="lsp:{method}"

Per Testing Philosophy: Full TDD approach.
Per DYK-3: definition → CALLS (semantically correct for call-site → definition).
Per DYK-5: Node ID correlation using tree-sitter format.
"""

import pytest

from fs2.core.models.code_edge import CodeEdge
from fs2.core.models.edge_type import EdgeType


@pytest.mark.unit
class TestSolidLspTypeTranslation:
    """Tests for SolidLspAdapter internal translation methods.
    
    These tests verify the correctness of LSP Location → CodeEdge translation.
    """

    def test_given_lsp_location_when_translating_reference_then_creates_code_edge(self):
        """AC08: LSP Location translates to CodeEdge with REFERENCES type.
        
        Why: Validates references translation produces correct edge structure.
        Contract: _translate_reference(Location, source) -> CodeEdge(REFERENCES)
        Quality Contribution: Catches edge type mapping errors.
        
        Semantics for references:
        - Query: "Where is symbol X referenced?"
        - source_file: File where X is DEFINED (lib.py)
        - location: Points to WHERE X is REFERENCED (app.py:10)
        - Edge: app.py (referrer) -> lib.py (referenced symbol's file)
        
        Worked Example:
            Query: References to `greet` function defined in lib.py
            Location: app.py:5 (where greet is called)
            Edge: source=file:app.py, target=file:lib.py (app references lib's symbol)
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        # Create a mock Location from SolidLSP representing WHERE a reference is
        # This is where lib.py's symbol is being referenced (in another file)
        location = {
            "uri": "file:///project/app.py",  # WHERE the reference is
            "range": {
                "start": {"line": 5, "character": 10},
                "end": {"line": 5, "character": 15},
            },
            "absolutePath": "/project/app.py",
            "relativePath": "app.py",
        }

        # source_file is WHERE the symbol being queried is DEFINED
        edge = SolidLspAdapter._translate_reference(
            location=location,
            source_file="lib.py",  # Where the symbol is defined
            source_line=10,  # Line of symbol definition
            project_root="/project",
        )

        assert isinstance(edge, CodeEdge)
        assert edge.edge_type == EdgeType.REFERENCES
        assert edge.confidence == 1.0
        assert edge.resolution_rule == "lsp:references"
        # Source is the referencing file (app.py - where the reference is)
        assert "app.py" in edge.source_node_id
        # Target is the referenced symbol's file (lib.py - where symbol is defined)
        assert "lib.py" in edge.target_node_id

    def test_given_lsp_location_when_translating_definition_then_creates_code_edge(self):
        """AC09: LSP definition Location translates to CodeEdge with CALLS type.
        
        Why: Per DYK-3, definition lookups represent call relationships.
        Contract: _translate_definition(Location, source) -> CodeEdge(CALLS)
        Quality Contribution: Validates semantic mapping decision from DYK session.
        
        Worked Example:
            Input: Location pointing to function definition in lib.py
            Output: CodeEdge(source_node_id from app.py, target_node_id to lib.py,
                           edge_type=CALLS, resolution_rule="lsp:definition")
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        # Create a mock Location representing a definition
        location = {
            "uri": "file:///project/lib.py",
            "range": {
                "start": {"line": 0, "character": 4},
                "end": {"line": 0, "character": 9},
            },
            "absolutePath": "/project/lib.py",
            "relativePath": "lib.py",
        }

        edge = SolidLspAdapter._translate_definition(
            location=location,
            source_file="app.py",
            source_line=3,
            project_root="/project",
        )

        assert isinstance(edge, CodeEdge)
        assert edge.edge_type == EdgeType.CALLS
        assert edge.confidence == 1.0
        assert edge.resolution_rule == "lsp:definition"

    def test_given_translation_when_creating_edge_then_confidence_is_1_0(self):
        """AC10: All LSP-derived edges have confidence=1.0.
        
        Why: LSP provides definitive answers (type-aware resolution).
        Contract: All CodeEdges from LSP have confidence=1.0 (invariant).
        Quality Contribution: Validates confidence invariant is enforced.
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        location = {
            "uri": "file:///project/lib.py",
            "range": {"start": {"line": 5, "character": 10}, "end": {"line": 5, "character": 15}},
            "absolutePath": "/project/lib.py",
            "relativePath": "lib.py",
        }

        # Test both translation methods
        ref_edge = SolidLspAdapter._translate_reference(
            location=location, source_file="app.py", source_line=10, project_root="/project"
        )
        def_edge = SolidLspAdapter._translate_definition(
            location=location, source_file="app.py", source_line=3, project_root="/project"
        )

        assert ref_edge.confidence == 1.0
        assert def_edge.confidence == 1.0

    def test_given_translation_when_creating_edge_then_resolution_rule_has_prefix(self):
        """AC10: All edges have resolution_rule with "lsp:" prefix.
        
        Why: Distinguishes LSP-derived edges from Tree-sitter heuristics.
        Contract: resolution_rule starts with "lsp:" for all LSP edges.
        Quality Contribution: Enables tracing edge provenance.
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        location = {
            "uri": "file:///project/lib.py",
            "range": {"start": {"line": 5, "character": 10}, "end": {"line": 5, "character": 15}},
            "absolutePath": "/project/lib.py",
            "relativePath": "lib.py",
        }

        ref_edge = SolidLspAdapter._translate_reference(
            location=location, source_file="app.py", source_line=10, project_root="/project"
        )
        def_edge = SolidLspAdapter._translate_definition(
            location=location, source_file="app.py", source_line=3, project_root="/project"
        )

        assert ref_edge.resolution_rule.startswith("lsp:")
        assert def_edge.resolution_rule.startswith("lsp:")

    def test_given_empty_response_when_translating_then_returns_empty_list(self):
        """Empty LSP response translates to empty CodeEdge list.
        
        Why: Validates graceful handling of no-result responses.
        Contract: Empty Location list -> Empty CodeEdge list.
        Quality Contribution: Prevents NPE on empty responses.
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        # Test the translation method handles empty input
        edges = SolidLspAdapter._translate_references(
            locations=[], source_file="app.py", source_line=10, project_root="/project"
        )

        assert edges == []

    def test_given_location_when_translating_then_source_line_is_set(self):
        """CodeEdge includes source_line from the reference location.
        
        Why: Source line is needed for navigation and debugging.
        Contract: CodeEdge.source_line matches the line from the Location.
        Quality Contribution: Enables precise code navigation.
        
        Note: For references, source_line is WHERE the reference is (from Location),
        not the passed source_line parameter (which is the definition location).
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        location = {
            "uri": "file:///project/app.py",
            "range": {"start": {"line": 42, "character": 10}, "end": {"line": 42, "character": 15}},
            "absolutePath": "/project/app.py",
            "relativePath": "app.py",
        }

        edge = SolidLspAdapter._translate_reference(
            location=location, source_file="lib.py", source_line=10, project_root="/project"
        )

        # source_line comes from the Location (where reference is), not from source_line param
        assert edge.source_line == 42


@pytest.mark.unit
class TestSolidLspNodeIdGeneration:
    """Tests for node_id generation matching tree-sitter format.
    
    Per DYK-5: LSP must construct node_ids matching tree-sitter format.
    Format: {category}:{rel_path}:{qualified_name}
    """

    def test_given_file_location_when_generating_node_id_then_matches_file_format(self):
        """File-level node_id uses format: file:{rel_path}.
        
        Why: Must match tree-sitter format for graph correlation.
        Contract: File locations produce "file:path/to/file.py" format.
        Quality Contribution: Enables edge creation between existing nodes.
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        location = {
            "uri": "file:///project/lib.py",
            "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}},
            "absolutePath": "/project/lib.py",
            "relativePath": "lib.py",
        }

        node_id = SolidLspAdapter._location_to_node_id(location, project_root="/project")

        # File-level node_id
        assert node_id == "file:lib.py"

    def test_given_nested_path_when_generating_node_id_then_uses_relative_path(self):
        """Nested file paths use relative paths in node_id.
        
        Why: Node IDs must be relative to project root.
        Contract: /project/src/models/user.py -> "file:src/models/user.py"
        Quality Contribution: Ensures portable node_ids.
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        location = {
            "uri": "file:///project/src/models/user.py",
            "range": {"start": {"line": 10, "character": 0}, "end": {"line": 10, "character": 10}},
            "absolutePath": "/project/src/models/user.py",
            "relativePath": "src/models/user.py",
        }

        node_id = SolidLspAdapter._location_to_node_id(location, project_root="/project")

        assert node_id == "file:src/models/user.py"

    def test_given_source_file_when_creating_source_node_id_then_matches_file_format(self):
        """Source node_id uses same format as target.
        
        Why: Both ends of edge must use consistent format.
        Contract: Source file produces "file:{rel_path}" format.
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        source_node_id = SolidLspAdapter._source_to_node_id(
            source_file="app.py", source_line=10, project_root="/project"
        )

        assert source_node_id == "file:app.py"
