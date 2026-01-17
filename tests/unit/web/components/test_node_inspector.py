"""Tests for NodeInspector component - Source code viewer with syntax highlighting.

Per AC-12: Node inspector displays syntax-highlighted source code.
Per DYK Insight #5: Uses FakeGraphStore via constructor injection.

These tests verify:
- Syntax highlighting with Pygments
- Metadata display (file path, line numbers, category)
- Empty state handling
"""

import pytest
from pathlib import Path

from fs2.config.objects import ScanConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.models.code_node import CodeNode
from fs2.core.repos.graph_store_fake import FakeGraphStore


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def make_file_node(file_path: str, content: str = "# file content") -> CodeNode:
    """Create a file CodeNode for tests."""
    return CodeNode.create_file(
        file_path=file_path,
        language="python",
        ts_kind="module",
        start_byte=0,
        end_byte=len(content),
        start_line=1,
        end_line=content.count("\n") + 1,
        content=content,
    )


def make_class_node(
    file_path: str,
    name: str,
    content: str = "class MyClass:\n    pass",
    parent_node_id: str | None = None,
) -> CodeNode:
    """Create a class CodeNode for tests."""
    return CodeNode.create_type(
        file_path=file_path,
        language="python",
        ts_kind="class_definition",
        name=name,
        qualified_name=name,
        start_line=1,
        end_line=content.count("\n") + 1,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=len(content),
        content=content,
        signature=f"class {name}:",
        parent_node_id=parent_node_id,
    )


def create_fake_store() -> FakeGraphStore:
    """Create a FakeGraphStore with sample data."""
    config = FakeConfigurationService(ScanConfig())
    return FakeGraphStore(config)


# =============================================================================
# NODE INSPECTOR BASIC TESTS
# =============================================================================


class TestNodeInspectorBasic:
    """Tests for basic NodeInspector functionality."""

    def test_given_node_id_when_get_node_then_returns_node(self):
        """
        Purpose: Verifies NodeInspector retrieves node from store.
        Quality Contribution: Foundation for display functionality.
        """
        from fs2.web.components.node_inspector import NodeInspector

        store = create_fake_store()
        node = make_file_node("src/main.py", "print('hello')")
        store.set_nodes([node])

        inspector = NodeInspector(graph_store=store)
        retrieved = inspector.get_node(node.node_id)

        assert retrieved is not None
        assert retrieved.node_id == node.node_id

    def test_given_invalid_node_id_when_get_node_then_returns_none(self):
        """
        Purpose: Verifies NodeInspector handles missing nodes gracefully.
        """
        from fs2.web.components.node_inspector import NodeInspector

        store = create_fake_store()

        inspector = NodeInspector(graph_store=store)
        retrieved = inspector.get_node("nonexistent:node:id")

        assert retrieved is None


# =============================================================================
# SYNTAX HIGHLIGHTING TESTS
# =============================================================================


class TestNodeInspectorSyntaxHighlighting:
    """Tests for syntax highlighting functionality."""

    def test_given_python_content_when_format_code_then_returns_highlighted(self):
        """
        Purpose: Verifies Python code is syntax highlighted.
        Per AC-12: Node inspector displays syntax-highlighted source code.
        """
        from fs2.web.components.node_inspector import NodeInspector

        store = create_fake_store()
        content = "def hello():\n    print('world')"
        node = make_file_node("src/main.py", content)
        store.set_nodes([node])

        inspector = NodeInspector(graph_store=store)
        formatted = inspector.format_code(node)

        # Pygments output contains HTML classes or ANSI codes
        assert formatted is not None
        assert len(formatted) > 0
        # The formatted output should contain the original content
        assert "hello" in formatted or "def" in formatted

    def test_given_unknown_language_when_format_code_then_returns_plain_text(self):
        """
        Purpose: Verifies unknown languages fall back to plain text.
        """
        from fs2.web.components.node_inspector import NodeInspector

        store = create_fake_store()
        node = CodeNode.create_file(
            file_path="src/data.xyz",
            language="unknown",
            ts_kind="module",
            start_byte=0,
            end_byte=10,
            start_line=1,
            end_line=1,
            content="some data",
        )
        store.set_nodes([node])

        inspector = NodeInspector(graph_store=store)
        formatted = inspector.format_code(node)

        # Should still return something (plain text fallback)
        assert formatted is not None
        assert "some data" in formatted


# =============================================================================
# METADATA DISPLAY TESTS
# =============================================================================


class TestNodeInspectorMetadata:
    """Tests for metadata display functionality."""

    def test_given_node_when_get_metadata_then_includes_file_path(self):
        """
        Purpose: Verifies file path is included in metadata.
        """
        from fs2.web.components.node_inspector import NodeInspector

        store = create_fake_store()
        node = make_file_node("src/main.py")
        store.set_nodes([node])

        inspector = NodeInspector(graph_store=store)
        metadata = inspector.get_metadata(node)

        assert "src/main.py" in metadata["file_path"]

    def test_given_node_when_get_metadata_then_includes_line_numbers(self):
        """
        Purpose: Verifies line numbers are included in metadata.
        """
        from fs2.web.components.node_inspector import NodeInspector

        store = create_fake_store()
        content = "line1\nline2\nline3"
        node = make_file_node("src/main.py", content)
        store.set_nodes([node])

        inspector = NodeInspector(graph_store=store)
        metadata = inspector.get_metadata(node)

        assert metadata["start_line"] == 1
        assert metadata["end_line"] == 3

    def test_given_node_when_get_metadata_then_includes_category(self):
        """
        Purpose: Verifies category is included in metadata.
        """
        from fs2.web.components.node_inspector import NodeInspector

        store = create_fake_store()
        node = make_class_node("src/main.py", "MyClass")
        store.set_nodes([node])

        inspector = NodeInspector(graph_store=store)
        metadata = inspector.get_metadata(node)

        assert metadata["category"] == "type"


# =============================================================================
# EMPTY STATE TESTS
# =============================================================================


class TestNodeInspectorEmptyState:
    """Tests for empty state handling."""

    def test_given_no_node_when_render_empty_state_then_shows_message(self):
        """
        Purpose: Verifies empty state message is displayed.
        """
        from fs2.web.components.node_inspector import NodeInspector

        store = create_fake_store()

        inspector = NodeInspector(graph_store=store)
        message = inspector.get_empty_state_message()

        assert message is not None
        assert len(message) > 0
        assert "select" in message.lower() or "node" in message.lower()


# =============================================================================
# SESSION STATE TESTS
# =============================================================================


class TestNodeInspectorSessionState:
    """Tests for session state integration."""

    def test_given_selected_node_when_render_then_displays_that_node(self):
        """
        Purpose: Verifies NodeInspector displays selected node.
        """
        from fs2.web.components.node_inspector import NodeInspector

        store = create_fake_store()
        node = make_file_node("src/main.py", "print('test')")
        store.set_nodes([node])

        mock_session_state = {"fs2_web_selected_node": node.node_id}

        inspector = NodeInspector(graph_store=store)
        selected_node = inspector.get_selected_node(session_state=mock_session_state)

        assert selected_node is not None
        assert selected_node.node_id == node.node_id
