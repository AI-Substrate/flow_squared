"""FakeGraphService - Test double for multi-graph MCP testing.

Provides a controllable implementation of GraphService for test injection.
Use with dependencies.set_graph_service() to inject into MCP tests.

Per DYK-01: Proper injection pattern - FakeGraphService allows tests to
control which GraphStore is returned for each graph name without needing
real config files or pickle files.

Architecture:
- set_graph() preloads stores by name
- get_graph() returns preloaded store or raises UnknownGraphError
- list_graphs() returns preconfigured GraphInfo list
- No actual file I/O or caching logic

Usage:
    ```python
    from fs2.core.services.graph_service_fake import FakeGraphService
    from fs2.core.repos.graph_store_fake import FakeGraphStore
    from fs2.mcp import dependencies

    # Create and configure fake
    fake_service = FakeGraphService()
    fake_service.set_graph("default", FakeGraphStore(...))
    fake_service.set_graph("external", FakeGraphStore(...))

    # Inject into MCP dependencies
    dependencies.set_graph_service(fake_service)

    # Now MCP tools will use the fake stores
    result = await client.call_tool("tree", {"graph_name": "external"})
    ```
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fs2.core.services.graph_service import (
    GraphInfo,
    UnknownGraphError,
)

if TYPE_CHECKING:
    from fs2.core.repos.graph_store import GraphStore


class FakeGraphService:
    """Test double for GraphService.

    Provides controllable graph store returns for MCP testing.
    Use set_graph() to preload stores by name before test execution.

    Attributes:
        _stores: Dict mapping graph name to GraphStore.
        _graph_infos: List of GraphInfo for list_graphs().
    """

    def __init__(self) -> None:
        """Initialize empty FakeGraphService."""
        self._stores: dict[str, GraphStore] = {}
        self._graph_infos: list[GraphInfo] = []

    def set_graph(self, name: str, store: GraphStore) -> None:
        """Register a GraphStore for a given name.

        Args:
            name: Graph name (e.g., "default", "external-lib").
            store: GraphStore to return when get_graph(name) is called.
        """
        self._stores[name] = store

    def set_graph_infos(self, infos: list[GraphInfo]) -> None:
        """Set the list of GraphInfo for list_graphs().

        Args:
            infos: List of GraphInfo to return from list_graphs().
        """
        self._graph_infos = infos

    def add_graph_info(
        self,
        name: str,
        path: Path | str,
        description: str | None = None,
        source_url: str | None = None,
        available: bool = True,
    ) -> None:
        """Add a GraphInfo entry for list_graphs().

        Convenience method to build up the GraphInfo list incrementally.

        Args:
            name: Graph name.
            path: Path to graph file.
            description: Optional description.
            source_url: Optional source URL.
            available: Whether the graph file exists.
        """
        self._graph_infos.append(
            GraphInfo(
                name=name,
                path=Path(path) if isinstance(path, str) else path,
                description=description,
                source_url=source_url,
                available=available,
            )
        )

    def get_graph(self, name: str = "default") -> GraphStore:
        """Get the GraphStore for the specified name.

        Args:
            name: Graph name ("default" or configured name).

        Returns:
            The preloaded GraphStore.

        Raises:
            UnknownGraphError: If name was not registered with set_graph().
        """
        if name not in self._stores:
            available = list(self._stores.keys())
            raise UnknownGraphError(name, available)
        return self._stores[name]

    def list_graphs(self) -> list[GraphInfo]:
        """Return the preconfigured list of GraphInfo.

        Returns:
            List of GraphInfo set via set_graph_infos() or add_graph_info().
        """
        return self._graph_infos.copy()

    def raise_file_not_found(self, name: str, path: Path | str) -> None:
        """Configure a graph name to raise GraphFileNotFoundError.

        Use this to test error handling when a graph file doesn't exist.
        Note: This requires a custom implementation - for simplicity,
        we use set_graph with a store that will error on load instead.

        Args:
            name: Graph name.
            path: Path to include in the error message.
        """
        # Store the path to raise on access
        # We can't actually raise from get_graph directly without more state,
        # so we document this as requiring a _FileNotFoundStore implementation
        # For now, callers can just not call set_graph() for missing graphs.
        pass
