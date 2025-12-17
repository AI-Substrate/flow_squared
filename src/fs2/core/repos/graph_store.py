"""GraphStore ABC interface.

Abstract base class defining the graph storage contract.
Implementations persist code structure graphs with CodeNode data.

Architecture:
- This file: ABC definition only
- Implementations: graph_store_fake.py, graph_store_impl.py

Per Critical Finding 02: Adapter ABC with Dual Implementation Pattern.
Per Critical Finding 01: Implementations receive ConfigurationService.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from fs2.core.models.code_node import CodeNode


class GraphStore(ABC):
    """Abstract base class for graph storage repositories.

    This interface defines the contract for persisting code structure
    as a networkx DiGraph with CodeNode data.

    Implementations must:
    - Receive ConfigurationService in constructor (not ScanConfig directly)
    - Store CodeNode objects as graph nodes with all 17 fields preserved
    - Create parent-child edges (parent → child direction)
    - Persist using standard pickle (not deprecated nx.write_gpickle)
    - Include format versioning metadata for compatibility

    Per Critical Finding 01: Receives ConfigurationService registry.

    See Also:
        - graph_store_fake.py: Test double implementation
        - graph_store_impl.py: Production NetworkXGraphStore implementation
    """

    @abstractmethod
    def add_node(self, node: CodeNode) -> None:
        """Add a CodeNode to the graph.

        If a node with the same node_id already exists, it will be updated
        (upsert behavior).

        Args:
            node: CodeNode to add. All 17 fields must be preserved.
        """
        ...

    @abstractmethod
    def add_edge(self, parent_id: str, child_id: str) -> None:
        """Add a parent-child edge between two nodes.

        Edge direction: parent → child. This means:
        - successors(parent_id) returns child nodes
        - predecessors(child_id) returns parent nodes

        Args:
            parent_id: node_id of the parent node.
            child_id: node_id of the child node.

        Raises:
            GraphStoreError: If either node does not exist.
        """
        ...

    @abstractmethod
    def get_node(self, node_id: str) -> CodeNode | None:
        """Retrieve a CodeNode by its ID.

        Args:
            node_id: Unique identifier of the node.

        Returns:
            CodeNode if found, None otherwise.
        """
        ...

    @abstractmethod
    def get_children(self, node_id: str) -> list[CodeNode]:
        """Get all child nodes of a given node.

        Args:
            node_id: Parent node's identifier.

        Returns:
            List of child CodeNodes (may be empty).
        """
        ...

    @abstractmethod
    def get_parent(self, node_id: str) -> CodeNode | None:
        """Get the parent node of a given node.

        Args:
            node_id: Child node's identifier.

        Returns:
            Parent CodeNode if exists, None if node has no parent.
        """
        ...

    @abstractmethod
    def get_all_nodes(self) -> list[CodeNode]:
        """Get all CodeNodes in the graph.

        Returns:
            List of all CodeNodes (may be empty).
        """
        ...

    @abstractmethod
    def save(self, path: Path) -> None:
        """Persist the graph to a file.

        Uses standard pickle with format versioning metadata.
        Creates parent directories if they don't exist.

        Args:
            path: File path to save to (typically .fs2/graph.pickle).

        Raises:
            GraphStoreError: If save fails (permission, disk full, etc.).
        """
        ...

    @abstractmethod
    def load(self, path: Path) -> None:
        """Load a graph from a file.

        Validates format version and logs warning on mismatch.
        Attempts load even if version differs.

        Args:
            path: File path to load from.

        Raises:
            GraphStoreError: If file doesn't exist, is corrupted, or
                contains malicious classes.
        """
        ...

    @abstractmethod
    def clear(self) -> None:
        """Remove all nodes and edges from the graph.

        Resets the graph to empty state, ready for fresh scan.
        """
        ...

    @abstractmethod
    def get_metadata(self) -> dict[str, Any]:
        """Return loaded graph metadata.

        Returns metadata from the most recently loaded graph file.
        This includes format version, creation timestamp, and counts.

        Returns:
            Dict with keys: format_version, created_at, node_count, edge_count.

        Raises:
            GraphStoreError: If no graph has been loaded yet.
        """
        ...
