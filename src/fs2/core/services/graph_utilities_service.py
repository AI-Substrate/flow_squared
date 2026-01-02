"""GraphUtilitiesService - Reusable graph analysis utilities.

Reports on persisted graph state (what's IN the graph),
not transient scan data. Independent of scan pipeline.

This service follows the Clean Architecture pattern:
- Receives ConfigurationService (registry) and GraphStore (ABC) via constructor
- Extracts its own config internally via config.require()
- Depends on interfaces, not implementations
- Uses lazy loading for graph access

CRITICAL: This service MUST NOT store copies of graph data.
All access goes through GraphStore ABC. See rules.md R3.5.

Usage:
    ```python
    # In composition root
    config = FS2ConfigurationService()
    graph_store = NetworkXGraphStore(config)

    service = GraphUtilitiesService(config=config, graph_store=graph_store)

    # Get extension summary
    ext_summary = service.get_extension_summary()
    print(f"Files: {ext_summary.total_files}")
    print(f"Nodes: {ext_summary.total_nodes}")
    ```
"""

from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

from fs2.config.objects import GraphConfig
from fs2.core.models.extension_summary import ExtensionSummary

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService
    from fs2.core.repos.graph_store import GraphStore


class GraphUtilitiesService:
    """Service for graph analysis utilities.

    This service analyzes persisted graph state - what's IN the graph,
    not what was just scanned. It loads from GraphStore on demand.

    First method: extension breakdown for summary.
    Future: graph_report-style analysis methods.

    Follows same pattern as TreeService/GetNodeService:
    - Receives ConfigurationService + GraphStore via DI
    - Lazy loads graph on first access
    - Does NOT cache graph data (per R3.5)

    Attributes:
        _config: GraphConfig with graph_path
        _graph_store: GraphStore ABC for graph access (NOT a copy)
        _loaded: Flag for lazy loading
    """

    @staticmethod
    def extract_file_path(node_id: str) -> str:
        """Extract file path from a node_id string.

        Node IDs follow the format: {category}:{file_path}:{qualified_name}
        This method extracts the file_path component.

        Args:
            node_id: Node identifier string (e.g., "class:src/main.py:MyClass")

        Returns:
            The file path component (e.g., "src/main.py")

        Raises:
            ValueError: If node_id format is invalid (fewer than 2 colons).

        Example:
            >>> GraphUtilitiesService.extract_file_path("callable:src/calc.py:Calc.add")
            'src/calc.py'
            >>> GraphUtilitiesService.extract_file_path("file:src/main.py")
            'src/main.py'
        """
        parts = node_id.split(":", 2)  # Split into at most 3 parts
        if len(parts) < 2:
            raise ValueError(
                f"Invalid node_id format: '{node_id}'. "
                "Expected format: {{category}}:{{file_path}}:{{qualified_name}}"
            )
        return parts[1]

    def __init__(
        self,
        config: "ConfigurationService",
        graph_store: "GraphStore",
    ) -> None:
        """Initialize with config registry and graph store.

        Args:
            config: ConfigurationService registry (NOT GraphConfig).
                    Service will call config.require(GraphConfig) internally.
            graph_store: GraphStore ABC for graph operations.

        Raises:
            MissingConfigurationError: If GraphConfig not in registry.
        """
        self._config = config.require(GraphConfig)
        self._graph_store = graph_store
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Lazy load graph on first access."""
        if self._loaded:
            return
        graph_path = Path(self._config.graph_path)
        self._graph_store.load(graph_path)
        self._loaded = True

    def get_extension_summary(self) -> ExtensionSummary:
        """Get extension breakdown from persisted graph.

        Loads graph from disk and counts files/nodes by extension.
        Reports on what's IN the graph, not transient scan state.

        Returns:
            ExtensionSummary with files_by_ext and nodes_by_ext.
        """
        self._ensure_loaded()

        files_by_ext: Counter[str] = Counter()
        nodes_by_ext: Counter[str] = Counter()
        seen_files: set[str] = set()

        # Query graph store on demand (never cache - per R3.5)
        for node in self._graph_store.get_all_nodes():
            file_path = self.extract_file_path(node.node_id)
            ext = Path(file_path).suffix.lower() or "(no ext)"
            nodes_by_ext[ext] += 1
            if file_path not in seen_files:
                seen_files.add(file_path)
                files_by_ext[ext] += 1

        return ExtensionSummary(
            files_by_ext=dict(files_by_ext),
            nodes_by_ext=dict(nodes_by_ext),
        )
