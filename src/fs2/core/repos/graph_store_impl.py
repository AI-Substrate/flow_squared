"""NetworkXGraphStore - Production implementation of GraphStore ABC.

Provides graph persistence using networkx DiGraph and standard pickle.
Implements RestrictedUnpickler for security against arbitrary code execution.

Architecture:
- Inherits from GraphStore ABC
- Uses networkx.DiGraph for in-memory graph
- Persists via pickle.dump with format versioning
- Loads via RestrictedUnpickler for security

Per Critical Finding 01: Receives ConfigurationService, not extracted config.
Per Critical Finding 05: Uses pickle.dump, not deprecated nx.write_gpickle.
Per Critical Finding 14: Includes format_version metadata.
"""

import logging
import pickle
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import networkx as nx

from fs2.config.objects import ScanConfig
from fs2.core.adapters.exceptions import GraphStoreError
from fs2.core.models.code_node import CodeNode
from fs2.core.repos.graph_store import GraphStore

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService

logger = logging.getLogger(__name__)

# Current format version
FORMAT_VERSION = "1.0"

# Whitelist of allowed classes for unpickling
# Only CodeNode, networkx types, and stdlib types allowed
ALLOWED_MODULES = frozenset({
    "builtins",
    "collections",
    "datetime",
    "pathlib",
    "networkx",
    "networkx.classes.digraph",
    "networkx.classes.reportviews",
    "fs2.core.models.code_node",
})


class RestrictedUnpickler(pickle.Unpickler):
    """Restricted unpickler that only allows safe classes.

    Blocks arbitrary code execution from malicious pickle files by
    whitelisting only CodeNode, networkx types, and stdlib types.

    Security:
        - Only classes from ALLOWED_MODULES can be instantiated
        - Blocks os.system, subprocess, etc.
        - Raises GraphStoreError on forbidden classes
    """

    def find_class(self, module: str, name: str) -> Any:
        """Override to restrict which classes can be unpickled.

        Args:
            module: Module name of the class.
            name: Class name.

        Returns:
            The class if allowed.

        Raises:
            GraphStoreError: If class is not in whitelist.
        """
        # Check if module is allowed
        if module in ALLOWED_MODULES:
            return super().find_class(module, name)

        # Check for common safe stdlib modules
        if module.startswith("builtins") or module == "_collections_abc":
            return super().find_class(module, name)

        # Block everything else
        raise GraphStoreError(
            f"Forbidden class in pickle: {module}.{name}. "
            f"Only CodeNode, networkx, and stdlib types are allowed. "
            f"The graph file may be corrupted or malicious."
        )


class NetworkXGraphStore(GraphStore):
    """Production implementation of GraphStore using networkx.

    Uses networkx.DiGraph for in-memory graph storage and standard
    pickle for persistence. Implements RestrictedUnpickler for security.

    Usage:
        ```python
        config = ConfigurationService()
        config.register(ScanConfig())
        store = NetworkXGraphStore(config)

        store.add_node(code_node)
        store.add_edge(parent_id, child_id)
        store.save(Path(".fs2/graph.pickle"))

        # Later...
        store.load(Path(".fs2/graph.pickle"))
        node = store.get_node("file:src/main.py")
        ```

    Attributes:
        _graph: networkx.DiGraph storing nodes and edges.
        _scan_config: Extracted ScanConfig from registry.
    """

    def __init__(self, config: "ConfigurationService"):
        """Initialize with ConfigurationService registry.

        Args:
            config: ConfigurationService registry.
                    Repository will call config.require(ScanConfig) internally.

        Raises:
            MissingConfigurationError: If ScanConfig not in registry.
        """
        self._scan_config = config.require(ScanConfig)
        self._graph: nx.DiGraph = nx.DiGraph()
        self._metadata: dict[str, Any] | None = None

    def add_node(self, node: CodeNode) -> None:
        """Add a CodeNode to the graph.

        If a node with the same node_id already exists, it will be updated
        (upsert behavior).

        Args:
            node: CodeNode to add. All fields stored as node data.
        """
        # Store CodeNode directly as node data
        self._graph.add_node(node.node_id, data=node)

    def add_edge(self, parent_id: str, child_id: str) -> None:
        """Add a parent-child edge between two nodes.

        Edge direction: parent → child. This means:
        - successors(parent_id) returns child IDs
        - predecessors(child_id) returns parent ID

        Args:
            parent_id: node_id of the parent node.
            child_id: node_id of the child node.

        Raises:
            GraphStoreError: If either node does not exist.
        """
        if parent_id not in self._graph:
            raise GraphStoreError(
                f"Parent node not found: {parent_id}. "
                f"Add the node before creating edges."
            )
        if child_id not in self._graph:
            raise GraphStoreError(
                f"Child node not found: {child_id}. "
                f"Add the node before creating edges."
            )

        self._graph.add_edge(parent_id, child_id)

    def get_node(self, node_id: str) -> CodeNode | None:
        """Retrieve a CodeNode by its ID.

        Args:
            node_id: Unique identifier of the node.

        Returns:
            CodeNode if found, None otherwise.
        """
        if node_id not in self._graph:
            return None
        return self._graph.nodes[node_id].get("data")

    def get_children(self, node_id: str) -> list[CodeNode]:
        """Get all child nodes of a given node.

        Args:
            node_id: Parent node's identifier.

        Returns:
            List of child CodeNodes (may be empty).
        """
        if node_id not in self._graph:
            return []

        children = []
        for child_id in self._graph.successors(node_id):
            node = self.get_node(child_id)
            if node is not None:
                children.append(node)
        return children

    def get_parent(self, node_id: str) -> CodeNode | None:
        """Get the parent node of a given node.

        Args:
            node_id: Child node's identifier.

        Returns:
            Parent CodeNode if exists, None if node has no parent.
        """
        if node_id not in self._graph:
            return None

        # predecessors returns nodes pointing TO this node (parents)
        parents = list(self._graph.predecessors(node_id))
        if not parents:
            return None

        # Return first parent (tree structure has single parent)
        return self.get_node(parents[0])

    def get_all_nodes(self) -> list[CodeNode]:
        """Get all CodeNodes in the graph.

        Returns:
            List of all CodeNodes (may be empty).
        """
        nodes = []
        for node_id in self._graph.nodes:
            node = self.get_node(node_id)
            if node is not None:
                nodes.append(node)
        return nodes

    def save(self, path: Path) -> None:
        """Persist the graph to a file.

        Uses standard pickle with format versioning metadata.
        Creates parent directories if they don't exist.

        File format: (metadata_dict, networkx.DiGraph)
        - metadata contains format_version, created_at, node_count, edge_count

        Args:
            path: File path to save to (typically .fs2/graph.pickle).

        Raises:
            GraphStoreError: If save fails (permission, disk full, etc.).
        """
        try:
            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)

            # Build metadata
            metadata = {
                "format_version": FORMAT_VERSION,
                "created_at": datetime.now(UTC).isoformat(),
                "node_count": self._graph.number_of_nodes(),
                "edge_count": self._graph.number_of_edges(),
            }

            # Save as (metadata, graph) tuple
            with open(path, "wb") as f:
                pickle.dump((metadata, self._graph), f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(
                "Graph saved to %s (%d nodes, %d edges)",
                path,
                metadata["node_count"],
                metadata["edge_count"],
            )

        except OSError as e:
            raise GraphStoreError(
                f"Failed to save graph to {path}: {e}. "
                f"Check disk space and permissions."
            ) from e

    def load(self, path: Path) -> None:
        """Load a graph from a file.

        Validates format version and logs warning on mismatch.
        Attempts load even if version differs.

        Uses RestrictedUnpickler for security against arbitrary code execution.

        Args:
            path: File path to load from.

        Raises:
            GraphStoreError: If file doesn't exist, is corrupted, or
                contains malicious classes.
        """
        if not path.exists():
            raise GraphStoreError(
                f"Graph file not found: {path}. "
                f"Run 'fs2 scan' to create the graph."
            )

        try:
            with open(path, "rb") as f:
                # Use RestrictedUnpickler for security
                unpickler = RestrictedUnpickler(f)
                data = unpickler.load()

            if not isinstance(data, tuple) or len(data) != 2:
                raise GraphStoreError(
                    f"Invalid graph file format: {path}. "
                    f"Expected (metadata, graph) tuple. "
                    f"File may be corrupted or from incompatible version."
                )

            metadata, graph = data

            # Check version and warn on mismatch
            file_version = metadata.get("format_version", "unknown")
            if file_version != FORMAT_VERSION:
                logger.warning(
                    "Graph format version mismatch: file=%s, expected=%s. "
                    "Attempting to load anyway.",
                    file_version,
                    FORMAT_VERSION,
                )

            if not isinstance(graph, nx.DiGraph):
                raise GraphStoreError(
                    f"Invalid graph type in file: {path}. "
                    f"Expected networkx.DiGraph, got {type(graph).__name__}."
                )

            self._graph = graph
            self._metadata = metadata

            logger.info(
                "Graph loaded from %s (%d nodes, %d edges, version=%s)",
                path,
                self._graph.number_of_nodes(),
                self._graph.number_of_edges(),
                file_version,
            )

        except GraphStoreError:
            raise
        except pickle.UnpicklingError as e:
            raise GraphStoreError(
                f"Failed to unpickle graph file: {path}. "
                f"File appears corrupted: {e}"
            ) from e
        except Exception as e:
            raise GraphStoreError(
                f"Failed to load graph from {path}: {e}"
            ) from e

    def clear(self) -> None:
        """Remove all nodes and edges from the graph.

        Resets the graph to empty state, ready for fresh scan.
        """
        self._graph.clear()
        logger.debug("Graph cleared")

    def get_metadata(self) -> dict[str, Any]:
        """Return loaded graph metadata.

        Returns metadata from the most recently loaded graph file.
        This includes format version, creation timestamp, and counts.

        Returns:
            Dict with keys: format_version, created_at, node_count, edge_count.

        Raises:
            GraphStoreError: If no graph has been loaded yet.
        """
        if self._metadata is None:
            raise GraphStoreError(
                "Graph metadata not loaded. "
                "Call load() first to load a graph from disk."
            )
        return self._metadata
