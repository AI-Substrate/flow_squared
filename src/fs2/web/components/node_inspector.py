"""NodeInspector component - Source code viewer with syntax highlighting.

Per AC-12: Node inspector displays syntax-highlighted source code.
Uses Pygments for syntax highlighting.

Example:
    >>> from fs2.web.components.node_inspector import NodeInspector
    >>> from fs2.core.repos.graph_store_impl import NetworkXGraphStore
    >>>
    >>> inspector = NodeInspector(graph_store=store)
    >>> inspector.render()  # Renders selected node with syntax highlighting
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fs2.core.models.code_node import CodeNode

if TYPE_CHECKING:
    from fs2.core.repos.graph_store import GraphStore


# Language mapping for Pygments
LANGUAGE_MAPPING = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "java": "java",
    "go": "go",
    "rust": "rust",
    "c": "c",
    "cpp": "cpp",
    "csharp": "csharp",
    "ruby": "ruby",
    "php": "php",
    "swift": "swift",
    "kotlin": "kotlin",
    "scala": "scala",
    "dart": "dart",
    "yaml": "yaml",
    "json": "json",
    "markdown": "markdown",
    "html": "html",
    "css": "css",
    "sql": "sql",
    "bash": "bash",
    "shell": "bash",
}


class NodeInspector:
    """Source code viewer component with syntax highlighting.

    Per AC-12: Displays syntax-highlighted source code.
    Per Discovery 06: Reads selected node from session state.

    Uses Pygments for syntax highlighting via Streamlit's st.code().
    """

    SELECTED_NODE_KEY = "fs2_web_selected_node"

    def __init__(self, graph_store: "GraphStore") -> None:
        """Initialize NodeInspector with dependencies.

        Args:
            graph_store: GraphStore for retrieving node content.
        """
        self._graph_store = graph_store

    def get_node(self, node_id: str) -> CodeNode | None:
        """Retrieve a node by ID.

        Args:
            node_id: Node identifier to retrieve.

        Returns:
            CodeNode if found, None otherwise.
        """
        return self._graph_store.get_node(node_id)

    def get_selected_node(
        self, session_state: dict[str, Any] | None = None
    ) -> CodeNode | None:
        """Get the currently selected node from session state.

        Args:
            session_state: Session state dict (for testing).

        Returns:
            Selected CodeNode or None if nothing selected.
        """
        if session_state is not None:
            node_id = session_state.get(self.SELECTED_NODE_KEY)
        else:
            import streamlit as st

            node_id = st.session_state.get(self.SELECTED_NODE_KEY)

        if node_id:
            return self.get_node(node_id)
        return None

    def format_code(self, node: CodeNode) -> str:
        """Format node content with syntax highlighting.

        Per AC-12: Syntax highlighting using Pygments.

        Args:
            node: CodeNode to format.

        Returns:
            Formatted code string (HTML or plain text).
        """
        if not node.content:
            return ""

        # Get language for highlighting
        language = self._get_pygments_language(node)

        # For now, return the content with language marker
        # Streamlit's st.code() will handle actual highlighting
        return node.content

    def _get_pygments_language(self, node: CodeNode) -> str:
        """Get Pygments language identifier for node.

        Args:
            node: CodeNode to get language for.

        Returns:
            Pygments language identifier or "text" for unknown.
        """
        # Try node's language attribute
        if hasattr(node, "language") and node.language:
            lang = node.language.lower()
            return LANGUAGE_MAPPING.get(lang, "text")

        # Try to infer from file extension
        if node.node_id and ":" in node.node_id:
            # Extract file path from node_id
            parts = node.node_id.split(":")
            if len(parts) >= 2:
                file_path = parts[1]
                if "." in file_path:
                    ext = file_path.rsplit(".", 1)[-1].lower()
                    ext_mapping = {
                        "py": "python",
                        "js": "javascript",
                        "ts": "typescript",
                        "java": "java",
                        "go": "go",
                        "rs": "rust",
                        "c": "c",
                        "cpp": "cpp",
                        "cs": "csharp",
                        "rb": "ruby",
                        "php": "php",
                        "swift": "swift",
                        "kt": "kotlin",
                        "scala": "scala",
                        "dart": "dart",
                        "yaml": "yaml",
                        "yml": "yaml",
                        "json": "json",
                        "md": "markdown",
                        "html": "html",
                        "css": "css",
                        "sql": "sql",
                        "sh": "bash",
                    }
                    return ext_mapping.get(ext, "text")

        return "text"

    def get_metadata(self, node: CodeNode) -> dict[str, Any]:
        """Get metadata for display.

        Args:
            node: CodeNode to extract metadata from.

        Returns:
            Dict with file_path, start_line, end_line, category.
        """
        # Extract file path from node_id or use name
        file_path = ""
        if node.node_id and ":" in node.node_id:
            parts = node.node_id.split(":")
            if len(parts) >= 2:
                file_path = parts[1]
        else:
            file_path = node.name

        return {
            "file_path": file_path,
            "start_line": node.start_line,
            "end_line": node.end_line,
            "category": node.category,
            "name": node.name,
            "language": getattr(node, "language", "unknown"),
        }

    def get_empty_state_message(self) -> str:
        """Get message to display when no node is selected.

        Returns:
            Empty state message string.
        """
        return "Select a node from the tree to view its source code."

    def render(self) -> None:
        """Render the node inspector.

        Displays:
        - Metadata header (file path, line numbers, category)
        - Syntax-highlighted source code
        - Empty state message if nothing selected
        """
        import streamlit as st

        node = self.get_selected_node()

        if node is None:
            st.info(self.get_empty_state_message())
            return

        # Display metadata
        metadata = self.get_metadata(node)

        st.markdown(f"### {metadata['name']}")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.caption(f"📄 {metadata['file_path']}")
        with col2:
            st.caption(f"📍 Lines {metadata['start_line']}-{metadata['end_line']}")
        with col3:
            st.caption(f"🏷️ {metadata['category']}")

        # Display code with syntax highlighting
        language = self._get_pygments_language(node)
        code = self.format_code(node)

        if code:
            st.code(code, language=language, line_numbers=True)
        else:
            st.warning("No content available for this node.")
