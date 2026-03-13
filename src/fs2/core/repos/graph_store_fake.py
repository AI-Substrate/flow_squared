"""FakeGraphStore - Test double implementing GraphStore ABC.

Provides a configurable fake for testing components that depend on GraphStore.
Follows the established repository fake pattern with configurable results
and call history recording.

Architecture:
- Inherits from GraphStore ABC
- Receives ConfigurationService (registry) via constructor
- Stores nodes in-memory without file persistence
- Records call history for test verification

Per Critical Finding 01: Receives ConfigurationService, not extracted config.
Per Critical Finding 02: Adapter ABC with Dual Implementation Pattern.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from fs2.config.objects import ScanConfig
from fs2.core.adapters.exceptions import GraphStoreError
from fs2.core.models.code_node import CodeNode
from fs2.core.repos.graph_store import GraphStore

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService


class FakeGraphStore(GraphStore):
    """Fake implementation of GraphStore for testing.

    This implementation provides deterministic behavior for testing:
    - Stores nodes in a dict (node_id → CodeNode)
    - Stores edges in a dict (parent_id → set of child_ids)
    - Records all method calls for verification
    - Supports error simulation via simulate_error_for set

    Usage in tests:
        ```python
        config = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config)

        # Configure nodes (alternative to add_node)
        store.set_nodes([node1, node2])

        # Use in test
        nodes = store.get_all_nodes()

        # Verify calls
        assert store.call_history[0]["method"] == "add_node"

        # Simulate errors
        store.simulate_error_for.add("save")
        ```
    """

    def __init__(self, config: "ConfigurationService"):
        """Initialize with ConfigurationService registry.

        Args:
            config: ConfigurationService registry.
                    Repository will call config.require(ScanConfig) internally.

        Raises:
            MissingConfigurationError: If ScanConfig not in registry.
        """
        # Extract config internally (per Critical Finding 01)
        self._scan_config = config.require(ScanConfig)
        self._nodes: dict[str, CodeNode] = {}
        self._edges: dict[str, dict[str, dict[str, Any]]] = {}  # parent → {child → edge_data}
        self._reverse_edges: dict[str, list[tuple[str, dict[str, Any]]]] = {}  # child → [(parent, edge_data)]
        self._call_history: list[dict[str, Any]] = []
        self.simulate_error_for: set[str] = set()
        self._metadata: dict[str, Any] | None = None

    @property
    def call_history(self) -> list[dict[str, Any]]:
        """Access recorded calls for test assertions.

        Returns:
            List of dicts with 'method', 'args', 'kwargs' for each call.
        """
        return self._call_history

    def set_nodes(self, nodes: list[CodeNode]) -> None:
        """Configure nodes directly (alternative to add_node).

        Args:
            nodes: List of CodeNodes to set as graph contents.
        """
        self._nodes = {node.node_id: node for node in nodes}

    def add_node(self, node: CodeNode) -> None:
        """Add a CodeNode to the in-memory graph.

        Args:
            node: CodeNode to add.
        """
        self._call_history.append(
            {
                "method": "add_node",
                "args": (node,),
                "kwargs": {},
            }
        )
        self._nodes[node.node_id] = node

    def add_edge(self, parent_id: str, child_id: str, **edge_data: Any) -> None:
        """Add a parent-child edge between two nodes.

        Args:
            parent_id: node_id of the parent node.
            child_id: node_id of the child node.
            **edge_data: Optional edge attributes.

        Raises:
            GraphStoreError: If simulating error or nodes don't exist.
        """
        self._call_history.append(
            {
                "method": "add_edge",
                "args": (parent_id, child_id),
                "kwargs": dict(edge_data),
            }
        )

        if "add_edge" in self.simulate_error_for:
            raise GraphStoreError("Simulated add_edge error")

        if parent_id not in self._edges:
            self._edges[parent_id] = {}
        self._edges[parent_id][child_id] = dict(edge_data)
        if child_id not in self._reverse_edges:
            self._reverse_edges[child_id] = []
        self._reverse_edges[child_id].append((parent_id, dict(edge_data)))

    def get_node(self, node_id: str) -> CodeNode | None:
        """Retrieve a CodeNode by its ID.

        Args:
            node_id: Unique identifier of the node.

        Returns:
            CodeNode if found, None otherwise.
        """
        self._call_history.append(
            {
                "method": "get_node",
                "args": (node_id,),
                "kwargs": {},
            }
        )
        return self._nodes.get(node_id)

    def get_children(self, node_id: str) -> list[CodeNode]:
        """Get all child nodes of a given node.

        Args:
            node_id: Parent node's identifier.

        Returns:
            List of child CodeNodes (may be empty).
        """
        self._call_history.append(
            {
                "method": "get_children",
                "args": (node_id,),
                "kwargs": {},
            }
        )
        child_ids = self._edges.get(node_id, {}).keys()
        return [self._nodes[cid] for cid in child_ids if cid in self._nodes]

    def get_parent(self, node_id: str) -> CodeNode | None:
        """Get the parent node of a given node.

        Args:
            node_id: Child node's identifier.

        Returns:
            Parent CodeNode if exists, None if node has no parent.
        """
        self._call_history.append(
            {
                "method": "get_parent",
                "args": (node_id,),
                "kwargs": {},
            }
        )
        # Filter to containment edges (no edge_type)
        parents = self._reverse_edges.get(node_id, [])
        for parent_id, edge_data in parents:
            if "edge_type" not in edge_data:
                return self._nodes.get(parent_id)
        return None

    def get_edges(
        self,
        node_id: str,
        direction: str = "outgoing",
        edge_type: str | None = None,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Get edges connected to a node, filtered by direction and type.

        Args:
            node_id: Node to query edges for.
            direction: "outgoing", "incoming", or "both".
            edge_type: Filter to edges with this edge_type attribute.

        Returns:
            List of (connected_node_id, edge_data_dict) tuples.
        """
        results: list[tuple[str, dict[str, Any]]] = []

        if direction in ("outgoing", "both"):
            children = self._edges.get(node_id, {})
            for child_id, data in children.items():
                if edge_type is None or data.get("edge_type") == edge_type:
                    results.append((child_id, dict(data)))

        if direction in ("incoming", "both"):
            parents = self._reverse_edges.get(node_id, [])
            for parent_id, data in parents:
                if edge_type is None or data.get("edge_type") == edge_type:
                    results.append((parent_id, dict(data)))

        return results

    def get_all_nodes(self) -> list[CodeNode]:
        """Get all CodeNodes in the graph.

        Returns:
            List of all CodeNodes (may be empty).
        """
        self._call_history.append(
            {
                "method": "get_all_nodes",
                "args": (),
                "kwargs": {},
            }
        )
        return list(self._nodes.values())

    def save(self, path: Path) -> None:
        """Fake save - records call but doesn't persist.

        Args:
            path: File path (recorded but not used).

        Raises:
            GraphStoreError: If simulating error.
        """
        self._call_history.append(
            {
                "method": "save",
                "args": (path,),
                "kwargs": {},
            }
        )

        if "save" in self.simulate_error_for:
            raise GraphStoreError("Simulated save error")

    def load(self, path: Path) -> None:
        """Fake load - records call but doesn't load.

        Args:
            path: File path (recorded but not used).

        Raises:
            GraphStoreError: If simulating error.
        """
        self._call_history.append(
            {
                "method": "load",
                "args": (path,),
                "kwargs": {},
            }
        )

        if "load" in self.simulate_error_for:
            raise GraphStoreError("Simulated load error")

    def clear(self) -> None:
        """Remove all nodes and edges from the in-memory graph."""
        self._call_history.append(
            {
                "method": "clear",
                "args": (),
                "kwargs": {},
            }
        )
        self._nodes.clear()
        self._edges.clear()
        self._reverse_edges.clear()

    def set_metadata(self, metadata: dict[str, Any]) -> None:
        """Configure metadata directly for testing.

        Args:
            metadata: Metadata dict to return from get_metadata().
        """
        if metadata is None:
            raise ValueError("metadata must not be None")
        self._metadata = metadata

    def get_metadata(self) -> dict[str, Any]:
        """Return configured metadata.

        Returns:
            Dict with metadata (must call set_metadata first or load).

        Raises:
            GraphStoreError: If metadata not configured.
        """
        self._call_history.append(
            {
                "method": "get_metadata",
                "args": (),
                "kwargs": {},
            }
        )

        if self._metadata is None:
            raise GraphStoreError(
                "Graph metadata not loaded. Call load() or set_metadata() first."
            )
        return self._metadata
