"""GraphService - Service for multi-graph management.

This service provides thread-safe access to multiple code graphs with caching
and automatic staleness detection.

Phase 2: GraphService Implementation
Per spec AC2-AC6: Graph retrieval, caching, listing, error handling
Per DYK-01: Double-checked locking for thread safety
Per DYK-02: Path resolution from config source directory
Per DYK-03: Distinct error types for unknown vs missing file

Architecture:
- Receives ConfigurationService registry via constructor
- Uses NetworkXGraphStore for each graph (created on demand)
- Thread-safe via RLock with double-checked locking
- Staleness detection via mtime + size comparison

Usage:
    ```python
    config = FS2ConfigurationService()
    service = GraphService(config=config)

    # Get default project graph
    store = service.get_graph("default")

    # Get named external graph
    store = service.get_graph("shared-lib")

    # List all available graphs
    graphs = service.list_graphs()
    for g in graphs:
        print(f"{g.name}: available={g.available}")
    ```
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING

from fs2.config.objects import GraphConfig, OtherGraph, OtherGraphsConfig

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService
    from fs2.core.repos.graph_store import GraphStore

logger = logging.getLogger(__name__)


# =============================================================================
# T006: Exception Hierarchy
# =============================================================================


class GraphServiceError(Exception):
    """Base exception for GraphService errors.

    Per DYK-03: Distinct error hierarchy for catch-all handling.
    All GraphService errors inherit from this class.
    """

    pass


class UnknownGraphError(GraphServiceError):
    """Raised when requested graph name is not configured.

    Per DYK-03: Distinct from GraphFileNotFoundError.
    Indicates the graph name is not recognized (typo or missing config).

    Attributes:
        name: The unknown graph name that was requested.
        available: List of available graph names for user guidance.
    """

    def __init__(self, name: str, available: list[str]) -> None:
        self.name = name
        self.available = available
        super().__init__(
            f"Unknown graph '{name}'. Available graphs: {', '.join(sorted(available))}"
        )


class GraphFileNotFoundError(GraphServiceError):
    """Raised when graph file doesn't exist on disk.

    Per DYK-03: Distinct from UnknownGraphError.
    Indicates the graph is configured but the file is missing.
    Provides guidance on how to resolve (run fs2 scan).

    Attributes:
        name: The graph name that was requested.
        path: The resolved path that doesn't exist.
    """

    def __init__(self, name: str, path: Path) -> None:
        self.name = name
        self.path = path
        super().__init__(
            f"Graph file for '{name}' not found at: {path}. "
            f"Run 'fs2 scan' in the target project to create it."
        )


# =============================================================================
# T006: GraphInfo Dataclass
# =============================================================================


@dataclass(frozen=True)
class GraphInfo:
    """Information about an available graph.

    Per AC6: Used by list_graphs() to return metadata about each graph.
    Per Critical Finding 08: Includes availability status.

    Attributes:
        name: Unique identifier (e.g., "default", "shared-lib").
        path: Resolved absolute path to the graph file.
        description: Human-readable description (if provided).
        source_url: URL of source repository (if provided).
        available: True if the graph file exists on disk.
    """

    name: str
    path: Path
    description: str | None = None
    source_url: str | None = None
    available: bool = False


# =============================================================================
# T006-T010: GraphService Implementation
# =============================================================================


@dataclass
class _CacheEntry:
    """Internal cache entry for loaded graphs.

    Stores GraphStore instance along with file stats for staleness detection.
    """

    store: GraphStore
    mtime: float
    size: int


class GraphService:
    """Service for multi-graph management with caching.

    Provides thread-safe access to multiple code graphs:
    - Default graph: The local project's graph from GraphConfig.graph_path
    - Named graphs: External graphs from OtherGraphsConfig

    Per DYK-01: Uses double-checked locking pattern for thread safety.
    Per DYK-02: Resolves paths from config source directory.
    Per DYK-03: Raises distinct exceptions for unknown vs missing.

    Attributes:
        _graph_config: GraphConfig with default graph path.
        _other_graphs_config: OtherGraphsConfig with named graphs.
        _cache: Dict of name -> _CacheEntry for loaded graphs.
        _lock: RLock for thread-safe cache operations.
    """

    def __init__(self, config: ConfigurationService) -> None:
        """Initialize with configuration service registry.

        Args:
            config: ConfigurationService registry (NOT individual configs).
                    Service will call config.require() internally.

        Raises:
            MissingConfigurationError: If GraphConfig not in registry.
        """
        self._graph_config = config.require(GraphConfig)
        self._other_graphs_config = config.get(OtherGraphsConfig)
        self._cache: dict[str, _CacheEntry] = {}
        self._lock = RLock()

    def _get_available_names(self) -> list[str]:
        """Get list of all available graph names.

        Returns:
            List containing "default" plus all configured graph names.
        """
        names = ["default"]
        if self._other_graphs_config:
            names.extend(g.name for g in self._other_graphs_config.graphs)
        return names

    def _resolve_path(self, graph: OtherGraph) -> Path:
        """Resolve graph path supporting absolute, tilde, and relative paths.

        Per Critical Finding 09: Support multiple path formats.
        Per DYK-02: Relative paths resolve from config source directory.

        Args:
            graph: OtherGraph with path and _source_dir.

        Returns:
            Resolved absolute Path.
        """
        path_str = graph.path

        # Handle tilde expansion
        path = Path(path_str).expanduser()

        # If already absolute, return as-is
        if path.is_absolute():
            return path

        # Relative path: resolve from config source directory
        # Per DYK-02: Use _source_dir if available, otherwise CWD
        if graph._source_dir is not None:
            return (graph._source_dir / path).resolve()
        else:
            # Fallback to CWD (shouldn't happen if config loading is correct)
            logger.warning(
                "Graph '%s' has relative path but no _source_dir. "
                "Resolving from CWD (may be incorrect).",
                graph.name,
            )
            return path.resolve()

    def _get_graph_path(self, name: str) -> Path:
        """Get the resolved path for a graph by name.

        Args:
            name: Graph name ("default" or configured name).

        Returns:
            Resolved absolute Path.

        Raises:
            UnknownGraphError: If name is not recognized.
        """
        if name == "default":
            return Path(self._graph_config.graph_path).expanduser().resolve()

        # Look up in configured graphs
        if self._other_graphs_config:
            for graph in self._other_graphs_config.graphs:
                if graph.name == name:
                    return self._resolve_path(graph)

        # Not found
        raise UnknownGraphError(name, self._get_available_names())

    def _is_stale(self, name: str, path: Path) -> bool:
        """Check if cached graph is stale.

        Per AC4: Detect when file has changed since last load.
        Compares mtime and size to detect changes.

        Args:
            name: Graph name for cache lookup.
            path: Path to check against.

        Returns:
            True if cache is stale (or missing), False if still valid.
        """
        # Use dict.get() for atomic read to avoid TOCTOU race
        entry = self._cache.get(name)
        if entry is None:
            return True

        try:
            stat = path.stat()
            return stat.st_mtime != entry.mtime or stat.st_size != entry.size
        except OSError:
            # File no longer exists or inaccessible
            return True

    def _load_graph(self, name: str, path: Path) -> GraphStore:
        """Load a graph from disk and update cache.

        Creates a new NetworkXGraphStore instance and loads the graph.

        Args:
            name: Graph name for cache key.
            path: Path to load from.

        Returns:
            Loaded GraphStore instance.

        Raises:
            GraphFileNotFoundError: If file doesn't exist.
            GraphStoreError: If file is corrupted.
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        if not path.exists():
            raise GraphFileNotFoundError(name, path)

        # Create a minimal config for the GraphStore
        # NetworkXGraphStore needs ConfigurationService with ScanConfig
        store_config = FakeConfigurationService(
            ScanConfig(scan_paths=["."]),  # Minimal required config
            GraphConfig(graph_path=str(path)),
        )
        store = NetworkXGraphStore(store_config)
        store.load(path)

        # Update cache with file stats
        stat = path.stat()
        self._cache[name] = _CacheEntry(
            store=store,
            mtime=stat.st_mtime,
            size=stat.st_size,
        )

        logger.debug("Loaded graph '%s' from %s", name, path)
        return store

    def get_graph(self, name: str = "default") -> GraphStore:
        """Get a GraphStore for the specified graph.

        Per AC2: Returns GraphStore for named graph.
        Per AC3: Default graph uses GraphConfig.graph_path.
        Per AC4: Caches loaded graphs, reloads when stale.
        Per DYK-01: Uses double-checked locking pattern.
        Per DYK-03: Raises distinct exceptions.

        Args:
            name: Graph name ("default" or configured name).

        Returns:
            GraphStore instance for the graph.

        Raises:
            UnknownGraphError: If name is not recognized.
            GraphFileNotFoundError: If graph file doesn't exist.
            GraphStoreError: If graph file is corrupted.
        """
        # Per DYK-01: Double-checked locking
        # First check: outside lock (fast path)
        path = self._get_graph_path(name)

        if not self._is_stale(name, path):
            return self._cache[name].store

        # Second check: inside lock (prevents double-load race)
        with self._lock:
            # Re-check staleness after acquiring lock
            if not self._is_stale(name, path):
                return self._cache[name].store

            # Load the graph
            return self._load_graph(name, path)

    def list_graphs(self) -> list[GraphInfo]:
        """List all available graphs with metadata.

        Per AC6: Returns info for all configured graphs.
        Per Critical Finding 08: Includes availability status.

        Returns:
            List of GraphInfo for default and all configured graphs.
        """
        result: list[GraphInfo] = []

        # Add default graph
        default_path = Path(self._graph_config.graph_path).expanduser().resolve()
        result.append(
            GraphInfo(
                name="default",
                path=default_path,
                description="Local project graph",
                source_url=None,
                available=default_path.exists(),
            )
        )

        # Add configured graphs
        if self._other_graphs_config:
            for graph in self._other_graphs_config.graphs:
                resolved_path = self._resolve_path(graph)
                result.append(
                    GraphInfo(
                        name=graph.name,
                        path=resolved_path,
                        description=graph.description,
                        source_url=graph.source_url,
                        available=resolved_path.exists(),
                    )
                )

        return result
