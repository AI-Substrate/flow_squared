"""Unit tests for symbol-level node ID resolution in RelationshipExtractionStage.

Purpose: Verifies that _extract_lsp_relationships() upgrades file-level edges
         to symbol-level edges using find_node_at_line().

Quality Contribution: Ensures method→method relationships are captured correctly
                     for cross-file call graph analysis.

Per Phase 8 Tasks:
- T016: Update SolidLspAdapter to use symbol-level node IDs

Per Design (Workshopped 2026-01-21):
- LSP adapter returns file-level edges with source_line and target_line
- Stage uses find_node_at_line() to upgrade to symbol-level node IDs
- Edges where resolution fails are filtered out

Test Naming: Given-When-Then format
"""

from pathlib import Path

from fs2.config.objects import LspConfig, ScanConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters.lsp_adapter_fake import FakeLspAdapter
from fs2.core.models.code_edge import CodeEdge, EdgeType
from fs2.core.models.code_node import CodeNode
from fs2.core.services.pipeline_context import PipelineContext
from fs2.core.services.stages.relationship_extraction_stage import (
    RelationshipExtractionStage,
)


class TestSymbolLevelResolution:
    """Tests for symbol-level node ID resolution in LSP extraction."""

    def test_given_lsp_edge_with_lines_when_processing_then_upgrades_to_method_node_ids(
        self,
    ):
        """
        Purpose: Verifies file-level edges are upgraded to method-level.
        Quality Contribution: Core symbol resolution functionality.
        Acceptance Criteria: Edge node_ids contain method names, not just file paths.

        Worked Example:
        - Input: edge from file:a.py (line 10) → file:b.py (line 5)
        - Context has: method:a.py:ClassA.caller at lines 8-15
                       method:b.py:ClassB.target at lines 3-10
        - Output: edge from method:a.py:ClassA.caller → method:b.py:ClassB.target
        """
        # Create nodes with method-level granularity
        ctx = _create_context_with_methods()

        # Create LSP adapter with file-level edge (has source_line and target_line)
        config = FakeConfigurationService(LspConfig())
        adapter = FakeLspAdapter(config)
        adapter.initialize("python", Path("/project"))

        # Configure edge: caller (line 10) calls target (line 5)
        adapter.set_definition_response(
            [
                CodeEdge(
                    source_node_id="file:src/a.py",  # File-level (to be upgraded)
                    target_node_id="file:src/b.py",  # File-level (to be upgraded)
                    edge_type=EdgeType.CALLS,
                    confidence=1.0,
                    source_line=10,  # Inside ClassA.caller (8-15)
                    target_line=5,  # Inside ClassB.target (3-10)
                    resolution_rule="lsp:definition",
                )
            ]
        )

        # Create stage with LSP adapter
        stage = RelationshipExtractionStage(lsp_adapter=adapter)

        # Process
        result = stage.process(ctx)

        # Find the LSP-derived edge
        lsp_edges = [
            e for e in result.relationships if e.resolution_rule == "lsp:definition"
        ]
        assert len(lsp_edges) == 1

        edge = lsp_edges[0]
        # Should be upgraded to method-level
        assert edge.source_node_id == "method:src/a.py:ClassA.caller"
        assert edge.target_node_id == "method:src/b.py:ClassB.target"

    def test_given_lsp_edge_without_target_line_when_processing_then_keeps_file_level(
        self,
    ):
        """
        Purpose: Verifies edges without target_line use file-level target.
        Quality Contribution: Graceful handling of missing line info.
        Acceptance Criteria: Source upgraded, target stays file-level.
        """
        ctx = _create_context_with_methods()

        config = FakeConfigurationService(LspConfig())
        adapter = FakeLspAdapter(config)
        adapter.initialize("python", Path("/project"))

        # Edge without target_line
        adapter.set_definition_response(
            [
                CodeEdge(
                    source_node_id="file:src/a.py",
                    target_node_id="file:src/b.py",
                    edge_type=EdgeType.CALLS,
                    confidence=1.0,
                    source_line=10,
                    target_line=None,  # No target line info
                    resolution_rule="lsp:definition",
                )
            ]
        )

        stage = RelationshipExtractionStage(lsp_adapter=adapter)
        result = stage.process(ctx)

        lsp_edges = [
            e for e in result.relationships if e.resolution_rule == "lsp:definition"
        ]
        assert len(lsp_edges) == 1

        edge = lsp_edges[0]
        # Source upgraded, target stays file-level
        assert edge.source_node_id == "method:src/a.py:ClassA.caller"
        assert edge.target_node_id == "file:src/b.py"

    def test_given_lsp_edge_to_nonexistent_line_when_processing_then_filtered_out(
        self,
    ):
        """
        Purpose: Verifies edges pointing to lines with no symbols are filtered.
        Quality Contribution: Prevents orphan edges in graph.
        Acceptance Criteria: Edge filtered when target line has no symbol.
        """
        ctx = _create_context_with_methods()

        config = FakeConfigurationService(LspConfig())
        adapter = FakeLspAdapter(config)
        adapter.initialize("python", Path("/project"))

        # Edge to line 100 (outside any method in b.py which goes to line 10)
        adapter.set_definition_response(
            [
                CodeEdge(
                    source_node_id="file:src/a.py",
                    target_node_id="file:src/b.py",
                    edge_type=EdgeType.CALLS,
                    confidence=1.0,
                    source_line=10,
                    target_line=100,  # No symbol at this line
                    resolution_rule="lsp:definition",
                )
            ]
        )

        stage = RelationshipExtractionStage(lsp_adapter=adapter)
        result = stage.process(ctx)

        # Should be filtered out - target has no symbol at line 100
        lsp_edges = [
            e for e in result.relationships if e.resolution_rule == "lsp:definition"
        ]
        assert len(lsp_edges) == 0

    def test_given_class_level_target_when_processing_then_resolves_to_class(self):
        """
        Purpose: Verifies resolution works for class-level (not just method).
        Quality Contribution: Supports class→class relationships.
        Acceptance Criteria: Edge target resolves to class node_id.
        """
        ctx = _create_context_with_methods()

        config = FakeConfigurationService(LspConfig())
        adapter = FakeLspAdapter(config)
        adapter.initialize("python", Path("/project"))

        # Edge from method to class (line 1 is inside ClassB but outside method target)
        # ClassB is at lines 2-12, method target is at lines 3-10
        # So line 2 (0-indexed=1) should resolve to class, not method
        # But find_node_at_line uses 1-indexed, so we need target_line=1 (0-indexed)
        # to get 1+1=2 which is ClassB start line
        adapter.set_definition_response(
            [
                CodeEdge(
                    source_node_id="file:src/a.py",
                    target_node_id="file:src/b.py",
                    edge_type=EdgeType.CALLS,
                    confidence=1.0,
                    source_line=10,
                    target_line=1,  # 0-indexed line 1 -> 1-indexed line 2 (ClassB start)
                    resolution_rule="lsp:definition",
                )
            ]
        )

        stage = RelationshipExtractionStage(lsp_adapter=adapter)
        result = stage.process(ctx)

        lsp_edges = [
            e for e in result.relationships if e.resolution_rule == "lsp:definition"
        ]
        assert len(lsp_edges) == 1

        edge = lsp_edges[0]
        # Line 2 (1-indexed) is ClassB start line but also contains method (3-10)
        # find_node_at_line returns innermost, so this will be class since
        # method doesn't start until line 3
        assert edge.target_node_id == "class:src/b.py:ClassB"

    def test_given_same_file_call_when_processing_then_both_endpoints_resolved(self):
        """
        Purpose: Verifies same-file calls also get symbol-level resolution.
        Quality Contribution: Supports method→method within same file.
        Acceptance Criteria: Both source and target in same file resolved correctly.
        """
        ctx = _create_context_with_same_file_methods()

        config = FakeConfigurationService(LspConfig())
        adapter = FakeLspAdapter(config)
        adapter.initialize("python", Path("/project"))

        # Same-file call: foo() at line 5 calls bar() at line 15
        adapter.set_definition_response(
            [
                CodeEdge(
                    source_node_id="file:src/utils.py",
                    target_node_id="file:src/utils.py",  # Same file
                    edge_type=EdgeType.CALLS,
                    confidence=1.0,
                    source_line=5,  # Inside foo (1-10)
                    target_line=15,  # Inside bar (11-20)
                    resolution_rule="lsp:definition",
                )
            ]
        )

        stage = RelationshipExtractionStage(lsp_adapter=adapter)
        result = stage.process(ctx)

        lsp_edges = [
            e for e in result.relationships if e.resolution_rule == "lsp:definition"
        ]
        assert len(lsp_edges) == 1

        edge = lsp_edges[0]
        assert edge.source_node_id == "function:src/utils.py:foo"
        assert edge.target_node_id == "function:src/utils.py:bar"

    def test_given_reference_edge_when_processing_then_resolves_symmetrically(self):
        """
        Purpose: Verifies REFERENCES edges also get symbol-level resolution.
        Quality Contribution: Supports bidirectional navigation.
        Acceptance Criteria: Reference edges upgraded to symbol-level.
        """
        ctx = _create_context_with_methods()

        config = FakeConfigurationService(LspConfig())
        adapter = FakeLspAdapter(config)
        adapter.initialize("python", Path("/project"))

        # Reference edge
        adapter.set_references_response(
            [
                CodeEdge(
                    source_node_id="file:src/a.py",
                    target_node_id="file:src/b.py",
                    edge_type=EdgeType.REFERENCES,
                    confidence=1.0,
                    source_line=10,
                    target_line=5,
                    resolution_rule="lsp:references",
                )
            ]
        )

        stage = RelationshipExtractionStage(lsp_adapter=adapter)
        result = stage.process(ctx)

        ref_edges = [
            e for e in result.relationships if e.resolution_rule == "lsp:references"
        ]
        assert len(ref_edges) == 1

        edge = ref_edges[0]
        assert edge.source_node_id == "method:src/a.py:ClassA.caller"
        assert edge.target_node_id == "method:src/b.py:ClassB.target"


# ============ Helper Functions ============


def _create_context_with_methods() -> PipelineContext:
    """Create context with method-level nodes for symbol resolution tests.

    Structure:
    - src/a.py: file (1-20), ClassA (5-18), ClassA.caller (8-15)
    - src/b.py: file (1-20), ClassB (2-12), ClassB.target (3-10)
    """
    ctx = PipelineContext(scan_config=ScanConfig())

    # File a.py nodes
    file_a = CodeNode.create_file(
        file_path="src/a.py",
        language="python",
        ts_kind="module",
        start_byte=0,
        end_byte=500,
        start_line=1,
        end_line=20,
        content="# Module a",
    )
    class_a = _create_class_node(
        file_path="src/a.py",
        class_name="ClassA",
        start_line=5,
        end_line=18,
    )
    method_caller = _create_method_node(
        file_path="src/a.py",
        class_name="ClassA",
        method_name="caller",
        start_line=8,
        end_line=15,
        call_target="target",  # Will generate "target()" call for extraction
    )

    # File b.py nodes
    file_b = CodeNode.create_file(
        file_path="src/b.py",
        language="python",
        ts_kind="module",
        start_byte=0,
        end_byte=400,
        start_line=1,
        end_line=20,
        content="# Module b",
    )
    class_b = _create_class_node(
        file_path="src/b.py",
        class_name="ClassB",
        start_line=2,
        end_line=12,
    )
    method_target = _create_method_node(
        file_path="src/b.py",
        class_name="ClassB",
        method_name="target",
        start_line=3,
        end_line=10,
    )

    ctx.nodes = [file_a, class_a, method_caller, file_b, class_b, method_target]
    return ctx


def _create_context_with_same_file_methods() -> PipelineContext:
    """Create context with two functions in the same file.

    Structure:
    - src/utils.py: file (1-25), foo (1-10), bar (11-20)
    """
    ctx = PipelineContext(scan_config=ScanConfig())

    file_utils = CodeNode.create_file(
        file_path="src/utils.py",
        language="python",
        ts_kind="module",
        start_byte=0,
        end_byte=600,
        start_line=1,
        end_line=25,
        content="# Utils module",
    )
    func_foo = _create_function_node(
        file_path="src/utils.py",
        func_name="foo",
        start_line=1,
        end_line=10,
        call_target="bar",  # Will generate "bar()" call for extraction
    )
    func_bar = _create_function_node(
        file_path="src/utils.py",
        func_name="bar",
        start_line=11,
        end_line=20,
    )

    ctx.nodes = [file_utils, func_foo, func_bar]
    return ctx


def _create_class_node(
    file_path: str,
    class_name: str,
    start_line: int,
    end_line: int,
) -> CodeNode:
    """Helper to create a class CodeNode."""
    return CodeNode(
        node_id=f"class:{file_path}:{class_name}",
        category="class",
        name=class_name,
        qualified_name=class_name,
        language="python",
        ts_kind="class_definition",
        start_byte=start_line * 50,
        end_byte=end_line * 50,
        start_line=start_line,
        end_line=end_line,
        start_column=0,
        end_column=0,
        content=f"class {class_name}:\n    pass",
        content_hash="test-hash",
        signature=f"class {class_name}:",
        is_named=True,
        field_name=None,
    )


def _create_method_node(
    file_path: str,
    class_name: str,
    method_name: str,
    start_line: int,
    end_line: int,
    call_target: str | None = None,
) -> CodeNode:
    """Helper to create a method CodeNode.

    Args:
        call_target: If provided, the method content will include a call to this target.
                     Example: "target" produces "target()" in the body.
    """
    if call_target:
        content = f"def {method_name}(self):\n    {call_target}()"
    else:
        content = f"def {method_name}(self):\n    pass"

    return CodeNode(
        node_id=f"method:{file_path}:{class_name}.{method_name}",
        category="method",
        name=method_name,
        qualified_name=f"{class_name}.{method_name}",
        language="python",
        ts_kind="function_definition",
        start_byte=start_line * 50,
        end_byte=end_line * 50,
        start_line=start_line,
        end_line=end_line,
        start_column=0,
        end_column=0,
        content=content,
        content_hash="test-hash",
        signature=f"def {method_name}(self):",
        is_named=True,
        field_name=None,
    )


def _create_function_node(
    file_path: str,
    func_name: str,
    start_line: int,
    end_line: int,
    call_target: str | None = None,
) -> CodeNode:
    """Helper to create a function CodeNode.

    Args:
        call_target: If provided, the function content will include a call to this target.
    """
    if call_target:
        content = f"def {func_name}():\n    {call_target}()"
    else:
        content = f"def {func_name}():\n    pass"

    return CodeNode(
        node_id=f"function:{file_path}:{func_name}",
        category="function",
        name=func_name,
        qualified_name=func_name,
        language="python",
        ts_kind="function_definition",
        start_byte=start_line * 50,
        end_byte=end_line * 50,
        start_line=start_line,
        end_line=end_line,
        start_column=0,
        end_column=0,
        content=content,
        content_hash="test-hash",
        signature=f"def {func_name}():",
        is_named=True,
        field_name=None,
    )
