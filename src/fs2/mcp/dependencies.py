"""Lazy service initialization for MCP server.

Provides singleton access to core services with lazy initialization.
Services are created on first access and cached thereafter, enabling
fast server startup.

Architecture:
- Module-level singletons: _config, _graph_store
- Getter functions: get_config(), get_graph_store()
- Setter functions: set_config(), set_graph_store() for test injection
- Reset function: reset_services() for test cleanup

Per Critical Discovery 03: GraphStore requires ConfigurationService injection.

Usage:
    # In MCP tool implementations
    from fs2.mcp.dependencies import get_config, get_graph_store

    config = get_config()  # Created on first call, cached thereafter
    store = get_graph_store()  # Uses config for injection

    # In tests
    from fs2.mcp import dependencies
    dependencies.reset_services()
    dependencies.set_config(fake_config)
"""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService
    from fs2.core.repos.graph_store import GraphStore


# Module-level singletons (None until first access)
_config: ConfigurationService | None = None
_graph_store: GraphStore | None = None
_lock = threading.RLock()  # RLock allows reentrant acquisition (needed since get_graph_store calls get_config)


def get_config() -> ConfigurationService:
    """Get the ConfigurationService singleton.

    Creates the service on first access using FS2ConfigurationService.
    Returns cached instance on subsequent calls.

    Returns:
        ConfigurationService instance (real or injected fake).
    """
    global _config
    with _lock:
        if _config is None:
            from fs2.config.service import FS2ConfigurationService

            logger.debug("Creating ConfigurationService singleton")
            _config = FS2ConfigurationService()
    return _config


def set_config(config: ConfigurationService) -> None:
    """Inject a ConfigurationService (for testing).

    Args:
        config: ConfigurationService instance (typically FakeConfigurationService).
    """
    global _config
    _config = config


def get_graph_store() -> GraphStore:
    """Get the GraphStore singleton.

    Creates the store on first access using NetworkXGraphStore
    with ConfigurationService injection.
    Returns cached instance on subsequent calls.

    Per Critical Discovery 03: GraphStore requires ConfigurationService
    injection, not extracted config objects.

    Returns:
        GraphStore instance (real or injected fake).
    """
    global _graph_store
    with _lock:
        if _graph_store is None:
            from fs2.core.repos.graph_store_impl import NetworkXGraphStore

            logger.debug("Creating GraphStore singleton with ConfigurationService injection")
            _graph_store = NetworkXGraphStore(get_config())
    return _graph_store


def set_graph_store(store: GraphStore) -> None:
    """Inject a GraphStore (for testing).

    Args:
        store: GraphStore instance (typically FakeGraphStore).
    """
    global _graph_store
    _graph_store = store


def reset_services() -> None:
    """Reset all service singletons to None.

    Used in tests to ensure clean state between test cases.
    """
    global _config, _graph_store
    _config = None
    _graph_store = None
