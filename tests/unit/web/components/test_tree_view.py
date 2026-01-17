"""Tests for TreeView component - Lazy-loading tree display.

Per DYK Insight #4: TreeView always expands to show next depth on click.
Per DYK Insight #5: Uses FakeGraphStore via constructor injection.

These tests verify:
- No input → shows root nodes at depth 1
- starter_nodes → shows those nodes as roots
- Click node → lazy-loads children via get_children()
- Expanded state persists in session_state
- Node selection updates selected node
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


def make_file_node(file_path: str) -> CodeNode:
    """Create a file CodeNode for tests."""
    return CodeNode.create_file(
        file_path=file_path,
        language="python",
        ts_kind="module",
        start_byte=0,
        end_byte=100,
        start_line=1,
        end_line=10,
        content="# file content",
    )


def make_class_node(
    file_path: str, name: str, parent_node_id: str | None = None
) -> CodeNode:
    """Create a class CodeNode for tests."""
    return CodeNode.create_type(
        file_path=file_path,
        language="python",
        ts_kind="class_definition",
        name=name,
        qualified_name=name,
        start_line=1,
        end_line=10,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=100,
        content=f"class {name}: pass",
        signature=f"class {name}:",
        parent_node_id=parent_node_id,
    )


def make_method_node(
    file_path: str, class_name: str, method_name: str, parent_node_id: str
) -> CodeNode:
    """Create a method CodeNode for tests."""
    return CodeNode.create_callable(
        file_path=file_path,
        language="python",
        ts_kind="function_definition",
        name=method_name,
        qualified_name=f"{class_name}.{method_name}",
        start_line=5,
        end_line=8,
        start_column=4,
        end_column=0,
        start_byte=50,
        end_byte=90,
        content=f"def {method_name}(self): pass",
        signature=f"def {method_name}(self):",
        parent_node_id=parent_node_id,
    )


def create_fake_store() -> FakeGraphStore:
    """Create a FakeGraphStore with sample data."""
    config = FakeConfigurationService(ScanConfig())
    return FakeGraphStore(config)


# =============================================================================
# TREE VIEW BASIC TESTS
# =============================================================================


class TestTreeViewBasic:
    """Tests for basic TreeView functionality."""

    def test_given_no_input_when_get_nodes_then_returns_root_nodes(self):
        """
        Purpose: Verifies TreeView shows root nodes when no input provided.
        Quality Contribution: Default behavior for initial display.
        """
        from fs2.web.components.tree_view import TreeView

        store = create_fake_store()
        file1 = make_file_node("src/main.py")
        file2 = make_file_node("src/utils.py")
        store.set_nodes([file1, file2])

        tree_view = TreeView(graph_store=store)
        nodes = tree_view.get_root_nodes()

        assert len(nodes) == 2
        assert file1.node_id in [n.node_id for n in nodes]
        assert file2.node_id in [n.node_id for n in nodes]

    def test_given_starter_nodes_when_get_nodes_then_returns_those_nodes(self):
        """
        Purpose: Verifies TreeView shows specified starter_nodes.
        Quality Contribution: Foundation for search results display.
        """
        from fs2.web.components.tree_view import TreeView

        store = create_fake_store()
        file1 = make_file_node("src/main.py")
        file2 = make_file_node("src/utils.py")
        class1 = make_class_node("src/main.py", "MyClass", file1.node_id)
        store.set_nodes([file1, file2, class1])
        store.add_edge(file1.node_id, class1.node_id)

        tree_view = TreeView(graph_store=store, starter_nodes=[class1.node_id])
        nodes = tree_view.get_root_nodes()

        # Should only show the specified starter node
        assert len(nodes) == 1
        assert nodes[0].node_id == class1.node_id

    def test_given_empty_graph_when_get_nodes_then_returns_empty_list(self):
        """
        Purpose: Verifies TreeView handles empty graph gracefully.
        """
        from fs2.web.components.tree_view import TreeView

        store = create_fake_store()
        # No nodes added

        tree_view = TreeView(graph_store=store)
        nodes = tree_view.get_root_nodes()

        assert nodes == []


# =============================================================================
# TREE VIEW LAZY LOADING TESTS
# =============================================================================


class TestTreeViewLazyLoading:
    """Tests for lazy loading via get_children()."""

    def test_given_node_with_children_when_expand_then_loads_children(self):
        """
        Purpose: Verifies click node → lazy-loads children via get_children().
        Quality Contribution: Core lazy expansion functionality.
        Per DYK Insight #4: TreeView always expands to show next depth.
        """
        from fs2.web.components.tree_view import TreeView

        store = create_fake_store()
        file1 = make_file_node("src/main.py")
        class1 = make_class_node("src/main.py", "MyClass", file1.node_id)
        method1 = make_method_node(
            "src/main.py", "MyClass", "my_method", class1.node_id
        )
        store.set_nodes([file1, class1, method1])
        store.add_edge(file1.node_id, class1.node_id)
        store.add_edge(class1.node_id, method1.node_id)

        tree_view = TreeView(graph_store=store)
        children = tree_view.get_children(class1.node_id)

        assert len(children) == 1
        assert children[0].node_id == method1.node_id
        # Verify FakeGraphStore recorded the call
        get_children_calls = [
            c for c in store.call_history if c["method"] == "get_children"
        ]
        assert len(get_children_calls) == 1

    def test_given_leaf_node_when_expand_then_returns_empty_children(self):
        """
        Purpose: Verifies leaf nodes have no children.
        """
        from fs2.web.components.tree_view import TreeView

        store = create_fake_store()
        file1 = make_file_node("src/main.py")
        store.set_nodes([file1])

        tree_view = TreeView(graph_store=store)
        children = tree_view.get_children(file1.node_id)

        assert children == []

    def test_given_node_when_check_has_children_then_returns_correct_status(self):
        """
        Purpose: Verifies has_children detection for expand/collapse icon.
        """
        from fs2.web.components.tree_view import TreeView

        store = create_fake_store()
        file1 = make_file_node("src/main.py")
        class1 = make_class_node("src/main.py", "MyClass", file1.node_id)
        store.set_nodes([file1, class1])
        store.add_edge(file1.node_id, class1.node_id)

        tree_view = TreeView(graph_store=store)

        assert tree_view.has_children(file1.node_id) is True
        assert tree_view.has_children(class1.node_id) is False


# =============================================================================
# TREE VIEW SESSION STATE TESTS
# =============================================================================


class TestTreeViewSessionState:
    """Tests for session state management."""

    def test_session_state_keys_use_fs2_web_prefix(self):
        """
        Purpose: Verifies session state keys follow namespace convention.
        Per Discovery 06: All session keys use fs2_web_ prefix.
        """
        from fs2.web.components.tree_view import TreeView

        assert TreeView.EXPANDED_NODES_KEY == "fs2_web_expanded_nodes"
        assert TreeView.SELECTED_NODE_KEY == "fs2_web_selected_node"

    def test_given_expanded_nodes_when_is_expanded_then_returns_true(self):
        """
        Purpose: Verifies expanded state tracking.
        """
        from fs2.web.components.tree_view import TreeView

        store = create_fake_store()
        file1 = make_file_node("src/main.py")
        store.set_nodes([file1])

        mock_session_state = {"fs2_web_expanded_nodes": {file1.node_id}}

        tree_view = TreeView(graph_store=store)
        is_expanded = tree_view.is_expanded(file1.node_id, session_state=mock_session_state)

        assert is_expanded is True

    def test_given_collapsed_node_when_is_expanded_then_returns_false(self):
        """
        Purpose: Verifies collapsed state detection.
        """
        from fs2.web.components.tree_view import TreeView

        store = create_fake_store()
        file1 = make_file_node("src/main.py")
        store.set_nodes([file1])

        mock_session_state = {"fs2_web_expanded_nodes": set()}

        tree_view = TreeView(graph_store=store)
        is_expanded = tree_view.is_expanded(file1.node_id, session_state=mock_session_state)

        assert is_expanded is False

    def test_given_node_when_toggle_expanded_then_updates_state(self):
        """
        Purpose: Verifies toggle_expanded modifies session state.
        """
        from fs2.web.components.tree_view import TreeView

        store = create_fake_store()
        file1 = make_file_node("src/main.py")
        store.set_nodes([file1])

        mock_session_state = {"fs2_web_expanded_nodes": set()}

        tree_view = TreeView(graph_store=store)
        tree_view.toggle_expanded(file1.node_id, session_state=mock_session_state)

        assert file1.node_id in mock_session_state["fs2_web_expanded_nodes"]

        # Toggle again to collapse
        tree_view.toggle_expanded(file1.node_id, session_state=mock_session_state)
        assert file1.node_id not in mock_session_state["fs2_web_expanded_nodes"]


# =============================================================================
# TREE VIEW NODE SELECTION TESTS
# =============================================================================


class TestTreeViewNodeSelection:
    """Tests for node selection."""

    def test_given_node_when_select_then_updates_selected_node(self):
        """
        Purpose: Verifies node selection for NodeInspector display.
        """
        from fs2.web.components.tree_view import TreeView

        store = create_fake_store()
        file1 = make_file_node("src/main.py")
        store.set_nodes([file1])

        mock_session_state = {}

        tree_view = TreeView(graph_store=store)
        tree_view.select_node(file1.node_id, session_state=mock_session_state)

        assert mock_session_state["fs2_web_selected_node"] == file1.node_id

    def test_given_selected_node_when_get_selected_then_returns_node_id(self):
        """
        Purpose: Verifies get_selected returns current selection.
        """
        from fs2.web.components.tree_view import TreeView

        store = create_fake_store()
        file1 = make_file_node("src/main.py")
        store.set_nodes([file1])

        mock_session_state = {"fs2_web_selected_node": file1.node_id}

        tree_view = TreeView(graph_store=store)
        selected = tree_view.get_selected(session_state=mock_session_state)

        assert selected == file1.node_id

    def test_given_no_selection_when_get_selected_then_returns_none(self):
        """
        Purpose: Verifies get_selected returns None when nothing selected.
        """
        from fs2.web.components.tree_view import TreeView

        store = create_fake_store()
        mock_session_state = {}

        tree_view = TreeView(graph_store=store)
        selected = tree_view.get_selected(session_state=mock_session_state)

        assert selected is None
