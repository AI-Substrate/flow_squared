"""GetNodeService - Service for retrieving nodes from the code graph.

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

    service = GetNodeService(config=config, graph_store=graph_store)

    # Service auto-loads graph on first access
    node = service.get_node("file:src/main.py")
    if node:
        print(node.qualified_name)
    ```
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fs2.config.objects import GraphConfig
from fs2.core.adapters.exceptions import GraphNotFoundError
from fs2.core.models.code_node import CodeNode

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService
    from fs2.core.repos.graph_store import GraphStore


class GetNodeService:
    """Service for retrieving nodes from the code graph.

    Provides a clean interface for node retrieval with lazy graph loading.
    CLI commands use this service instead of directly accessing GraphStore.

    CRITICAL: This service MUST NOT store copies of graph data.
    All access goes through GraphStore ABC. See rules.md R3.5.

    Attributes:
        _config: GraphConfig with graph_path
        _graph_store: GraphStore ABC for graph access (NOT a copy)
        _loaded: Flag for lazy loading

    Example:
        ```python
        service = GetNodeService(config, graph_store)
        node = service.get_node("callable:src/main.py:Calculator.add")
        ```
    """

    def __init__(
        self,
        config: ConfigurationService,
        graph_store: GraphStore,
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
        """Lazy load graph on first access.

        Raises:
            GraphNotFoundError: If graph file does not exist.
            GraphStoreError: If graph file is corrupted.
        """
        if self._loaded:
            return
        graph_path = Path(self._config.graph_path)
        if not graph_path.exists():
            raise GraphNotFoundError(graph_path)
        self._graph_store.load(graph_path)
        self._loaded = True

    def get_node(self, node_id: str) -> CodeNode | None:
        """Retrieve node by ID.

        Auto-loads graph on first call (lazy loading pattern).

        Args:
            node_id: The node_id to retrieve (e.g., 'file:src/main.py',
                    'callable:src/main.py:main')

        Returns:
            CodeNode if found, None if not found.

        Raises:
            GraphNotFoundError: If graph file does not exist.
            GraphStoreError: If graph file is corrupted.
        """
        self._ensure_loaded()
        return self._graph_store.get_node(node_id)
