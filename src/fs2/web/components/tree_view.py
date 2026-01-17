"""TreeView component - Lazy-loading tree display for code exploration.

Per DYK Insight #4: TreeView always expands to show next depth on click.
No depth parameter - click node → calls GraphStore.get_children() → shows next depth.

Per DYK Insight #5: Uses FakeGraphStore via constructor injection for testing.

Example:
    >>> from fs2.web.components.tree_view import TreeView
    >>> from fs2.core.repos.graph_store_impl import NetworkXGraphStore
    >>>
    >>> tree_view = TreeView(graph_store=store)
    >>> tree_view.render()  # Renders tree with expand/collapse
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fs2.core.models.code_node import CodeNode

if TYPE_CHECKING:
    from fs2.core.repos.graph_store import GraphStore


class TreeView:
    """Lazy-loading tree display component.

    Per DYK Insight #4: No depth parameter. Click node to expand and show
    children via GraphStore.get_children().

    Per Discovery 06: Uses session state with fs2_web_ prefix for:
    - fs2_web_expanded_nodes: Set of expanded node_ids
    - fs2_web_selected_node: Currently selected node_id

    Attributes:
        EXPANDED_NODES_KEY: Session state key for expanded nodes.
        SELECTED_NODE_KEY: Session state key for selected node.
    """

    EXPANDED_NODES_KEY = "fs2_web_expanded_nodes"
    SELECTED_NODE_KEY = "fs2_web_selected_node"

    def __init__(
        self,
        graph_store: "GraphStore",
        starter_nodes: list[str] | None = None,
    ) -> None:
        """Initialize TreeView with dependencies.

        Args:
            graph_store: GraphStore containing the code graph.
            starter_nodes: Optional list of node_ids to show as roots.
                If None, shows all root nodes (nodes without parents).
        """
        self._graph_store = graph_store
        self._starter_nodes = starter_nodes

    def get_root_nodes(self) -> list[CodeNode]:
        """Get nodes to display at tree root level.

        If starter_nodes provided, returns those nodes.
        Otherwise, returns all nodes without parents (true roots).

        Returns:
            List of CodeNode to display as tree roots.
        """
        if self._starter_nodes:
            # Get specified starter nodes
            nodes = []
            for node_id in self._starter_nodes:
                node = self._graph_store.get_node(node_id)
                if node:
                    nodes.append(node)
            return nodes

        # Get all nodes and filter to roots (no parent)
        all_nodes = self._graph_store.get_all_nodes()
        roots = []
        for node in all_nodes:
            parent = self._graph_store.get_parent(node.node_id)
            if parent is None:
                roots.append(node)
        return roots

    def get_children(self, node_id: str) -> list[CodeNode]:
        """Get children of a node (lazy loading).

        Per DYK Insight #4: Called when user clicks to expand a node.

        Args:
            node_id: Parent node to get children for.

        Returns:
            List of child CodeNodes (may be empty for leaf nodes).
        """
        return self._graph_store.get_children(node_id)

    def has_children(self, node_id: str) -> bool:
        """Check if a node has children (for expand/collapse icon).

        Args:
            node_id: Node to check.

        Returns:
            True if node has children, False otherwise.
        """
        children = self._graph_store.get_children(node_id)
        return len(children) > 0

    def is_expanded(
        self, node_id: str, session_state: dict[str, Any] | None = None
    ) -> bool:
        """Check if a node is currently expanded.

        Args:
            node_id: Node to check.
            session_state: Session state dict (for testing).

        Returns:
            True if node is expanded, False otherwise.
        """
        if session_state is not None:
            expanded = session_state.get(self.EXPANDED_NODES_KEY, set())
        else:
            import streamlit as st

            if self.EXPANDED_NODES_KEY not in st.session_state:
                st.session_state[self.EXPANDED_NODES_KEY] = set()
            expanded = st.session_state[self.EXPANDED_NODES_KEY]

        return node_id in expanded

    def toggle_expanded(
        self, node_id: str, session_state: dict[str, Any] | None = None
    ) -> None:
        """Toggle the expanded state of a node.

        Args:
            node_id: Node to toggle.
            session_state: Session state dict (for testing).
        """
        if session_state is not None:
            if self.EXPANDED_NODES_KEY not in session_state:
                session_state[self.EXPANDED_NODES_KEY] = set()
            expanded = session_state[self.EXPANDED_NODES_KEY]
        else:
            import streamlit as st

            if self.EXPANDED_NODES_KEY not in st.session_state:
                st.session_state[self.EXPANDED_NODES_KEY] = set()
            expanded = st.session_state[self.EXPANDED_NODES_KEY]

        if node_id in expanded:
            expanded.remove(node_id)
        else:
            expanded.add(node_id)

    def select_node(
        self, node_id: str, session_state: dict[str, Any] | None = None
    ) -> None:
        """Set the currently selected node.

        Args:
            node_id: Node to select.
            session_state: Session state dict (for testing).
        """
        if session_state is not None:
            session_state[self.SELECTED_NODE_KEY] = node_id
        else:
            import streamlit as st

            st.session_state[self.SELECTED_NODE_KEY] = node_id

    def get_selected(
        self, session_state: dict[str, Any] | None = None
    ) -> str | None:
        """Get the currently selected node_id.

        Args:
            session_state: Session state dict (for testing).

        Returns:
            Selected node_id or None if nothing selected.
        """
        if session_state is not None:
            return session_state.get(self.SELECTED_NODE_KEY)
        else:
            import streamlit as st

            return st.session_state.get(self.SELECTED_NODE_KEY)

    def render(self) -> str | None:
        """Render the tree view.

        Returns:
            Selected node_id or None if nothing selected.
        """
        import streamlit as st

        roots = self.get_root_nodes()
        if not roots:
            st.info("No nodes to display.")
            return None

        # Render tree recursively
        for node in roots:
            self._render_node(node, indent=0)

        return self.get_selected()

    def _render_node(self, node: CodeNode, indent: int) -> None:
        """Render a single node with expand/collapse.

        Args:
            node: Node to render.
            indent: Indentation level.
        """
        import streamlit as st

        # Build icon and label
        has_children = self.has_children(node.node_id)
        is_expanded = self.is_expanded(node.node_id)

        if has_children:
            icon = "📂" if is_expanded else "📁"
        else:
            icon = self._get_category_icon(node.category)

        # Indentation
        prefix = "  " * indent

        # Create columns for expand button and label
        col1, col2 = st.columns([0.1, 0.9])

        with col1:
            if has_children:
                if st.button(
                    "▼" if is_expanded else "▶",
                    key=f"expand_{node.node_id}",
                    help="Expand/collapse",
                ):
                    self.toggle_expanded(node.node_id)
                    st.rerun()
            else:
                st.write("")  # Placeholder for alignment

        with col2:
            label = f"{prefix}{icon} {node.name}"
            if st.button(label, key=f"select_{node.node_id}"):
                self.select_node(node.node_id)
                st.rerun()

        # Render children if expanded
        if is_expanded and has_children:
            children = self.get_children(node.node_id)
            for child in children:
                self._render_node(child, indent + 1)

    @staticmethod
    def _get_category_icon(category: str) -> str:
        """Get icon for node category.

        Args:
            category: Node category.

        Returns:
            Emoji icon for the category.
        """
        icons = {
            "file": "📄",
            "type": "📦",
            "callable": "ƒ",
            "folder": "📁",
            "section": "§",
            "block": "▪",
        }
        return icons.get(category, "•")
