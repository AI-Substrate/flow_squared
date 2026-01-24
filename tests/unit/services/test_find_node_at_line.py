"""Tests for find_node_at_line() utility function.

Per Phase 8 Tasks:
- T014: Write tests for find_node_at_line() utility (TDD RED)
- T015: Implementation to make these tests pass (TDD GREEN)

Per DYK-2: O(n) scan for MVP; defer index optimization if profiling shows bottleneck.

The find_node_at_line() function finds the innermost CodeNode that contains
a given line number, enabling symbol-level resolution from LSP locations.
"""

from fs2.core.models.code_node import CodeNode


class TestFindNodeAtLineBasic:
    """Basic tests for find_node_at_line()."""

    def test_given_file_node_when_line_in_file_then_returns_file_node(self) -> None:
        """File node returned when no nested symbols."""
        from fs2.core.services.relationship_extraction.symbol_resolver import (
            find_node_at_line,
        )

        file_node = CodeNode.create_file(
            file_path="src/app.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# file content",
        )

        result = find_node_at_line([file_node], 5)

        assert result is not None
        assert result.node_id == file_node.node_id

    def test_given_line_outside_all_nodes_when_searching_then_returns_none(
        self,
    ) -> None:
        """Returns None when line isn't in any node."""
        from fs2.core.services.relationship_extraction.symbol_resolver import (
            find_node_at_line,
        )

        file_node = CodeNode.create_file(
            file_path="src/app.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# file content",
        )

        result = find_node_at_line([file_node], 50)

        assert result is None

    def test_given_empty_nodes_when_searching_then_returns_none(self) -> None:
        """Returns None for empty node list."""
        from fs2.core.services.relationship_extraction.symbol_resolver import (
            find_node_at_line,
        )

        result = find_node_at_line([], 5)

        assert result is None


class TestFindNodeAtLineNestedSymbols:
    """Tests for nested symbol resolution."""

    def test_given_method_inside_class_when_line_in_method_then_returns_method(
        self,
    ) -> None:
        """Returns innermost (method) node, not containing class."""
        from fs2.core.services.relationship_extraction.symbol_resolver import (
            find_node_at_line,
        )

        # File node
        file_node = CodeNode.create_file(
            file_path="src/app.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=200,
            start_line=1,
            end_line=20,
            content="",
        )

        # Class node (lines 2-15)
        class_node = _create_class_node(
            file_path="src/app.py",
            name="MyClass",
            start_line=2,
            end_line=15,
        )

        # Method node inside class (lines 5-10)
        method_node = _create_method_node(
            file_path="src/app.py",
            class_name="MyClass",
            method_name="my_method",
            start_line=5,
            end_line=10,
        )

        result = find_node_at_line([file_node, class_node, method_node], 7)

        # Should return method, not class or file
        assert result is not None
        assert result.node_id == method_node.node_id

    def test_given_line_in_class_outside_method_when_searching_then_returns_class(
        self,
    ) -> None:
        """Returns class node when line is in class but not in any method."""
        from fs2.core.services.relationship_extraction.symbol_resolver import (
            find_node_at_line,
        )

        file_node = CodeNode.create_file(
            file_path="src/app.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=200,
            start_line=1,
            end_line=20,
            content="",
        )

        # Class node (lines 2-15)
        class_node = _create_class_node(
            file_path="src/app.py",
            name="MyClass",
            start_line=2,
            end_line=15,
        )

        # Method node (lines 5-10) - line 12 is in class but NOT in method
        method_node = _create_method_node(
            file_path="src/app.py",
            class_name="MyClass",
            method_name="my_method",
            start_line=5,
            end_line=10,
        )

        result = find_node_at_line([file_node, class_node, method_node], 12)

        # Should return class (innermost containing line 12)
        assert result is not None
        assert result.node_id == class_node.node_id


class TestFindNodeAtLineEdgeCases:
    """Edge cases for find_node_at_line()."""

    def test_given_line_at_node_boundary_when_searching_then_matches(self) -> None:
        """Line on start/end boundary is included."""
        from fs2.core.services.relationship_extraction.symbol_resolver import (
            find_node_at_line,
        )

        method_node = _create_method_node(
            file_path="src/app.py",
            class_name="MyClass",
            method_name="my_method",
            start_line=5,
            end_line=10,
        )

        # Test start boundary
        result_start = find_node_at_line([method_node], 5)
        assert result_start is not None
        assert result_start.node_id == method_node.node_id

        # Test end boundary
        result_end = find_node_at_line([method_node], 10)
        assert result_end is not None
        assert result_end.node_id == method_node.node_id

    def test_given_multiple_siblings_when_line_in_one_then_returns_correct(
        self,
    ) -> None:
        """Returns correct sibling when multiple at same level."""
        from fs2.core.services.relationship_extraction.symbol_resolver import (
            find_node_at_line,
        )

        method_a = _create_method_node(
            file_path="src/app.py",
            class_name="MyClass",
            method_name="method_a",
            start_line=2,
            end_line=5,
        )
        method_b = _create_method_node(
            file_path="src/app.py",
            class_name="MyClass",
            method_name="method_b",
            start_line=7,
            end_line=10,
        )

        result = find_node_at_line([method_a, method_b], 8)

        assert result is not None
        assert result.node_id == method_b.node_id


class TestFindNodeAtLineFilePath:
    """Tests for file path filtering."""

    def test_given_file_path_filter_when_searching_then_only_matches_file(
        self,
    ) -> None:
        """Can filter by file path."""
        from fs2.core.services.relationship_extraction.symbol_resolver import (
            find_node_at_line,
        )

        node_a = CodeNode.create_file(
            file_path="src/app.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="",
        )
        node_b = CodeNode.create_file(
            file_path="src/other.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="",
        )

        # With file filter, should only search nodes from that file
        result = find_node_at_line([node_a, node_b], 5, file_path="src/other.py")

        assert result is not None
        assert result.node_id == node_b.node_id


# ============ Helper Functions ============


def _create_class_node(
    file_path: str,
    name: str,
    start_line: int,
    end_line: int,
) -> CodeNode:
    """Create a class node for testing."""
    return CodeNode(
        node_id=f"class:{file_path}:{name}",
        category="class",
        ts_kind="class_definition",
        name=name,
        qualified_name=name,
        start_line=start_line,
        end_line=end_line,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=100,
        content="",
        content_hash="",
        signature=None,
        field_name=None,
        language="python",
        is_named=True,
    )


def _create_method_node(
    file_path: str,
    class_name: str,
    method_name: str,
    start_line: int,
    end_line: int,
) -> CodeNode:
    """Create a method node for testing."""
    qualified_name = f"{class_name}.{method_name}"
    return CodeNode(
        node_id=f"method:{file_path}:{qualified_name}",
        category="method",
        ts_kind="function_definition",
        name=method_name,
        qualified_name=qualified_name,
        start_line=start_line,
        end_line=end_line,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=50,
        content="",
        content_hash="",
        signature=None,
        field_name=None,
        language="python",
        is_named=True,
        parent_node_id=f"class:{file_path}:{class_name}",
    )
