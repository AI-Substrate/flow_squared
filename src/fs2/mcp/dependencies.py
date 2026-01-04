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
    from fs2.core.adapters.embedding_adapter import EmbeddingAdapter
    from fs2.core.repos.graph_store import GraphStore
    from fs2.core.services.docs_service import DocsService


# Module-level singletons (None until first access)
_config: ConfigurationService | None = None
_graph_store: GraphStore | None = None
_embedding_adapter: EmbeddingAdapter | None = None
_docs_service: DocsService | None = None
_lock = (
    threading.RLock()
)  # RLock allows reentrant acquisition (needed since get_graph_store calls get_config)


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

            logger.debug(
                "Creating GraphStore singleton with ConfigurationService injection"
            )
            _graph_store = NetworkXGraphStore(get_config())
    return _graph_store


def set_graph_store(store: GraphStore) -> None:
    """Inject a GraphStore (for testing).

    Args:
        store: GraphStore instance (typically FakeGraphStore).
    """
    global _graph_store
    _graph_store = store


def get_embedding_adapter() -> EmbeddingAdapter | None:
    """Get the EmbeddingAdapter singleton.

    Returns the cached adapter if set, otherwise None.
    Unlike config/graph_store, we don't auto-create an embedding adapter
    since it requires API credentials that may not be configured.

    Per Phase 4: Semantic search requires explicit adapter injection.

    Returns:
        EmbeddingAdapter instance if set, None otherwise.
    """
    global _embedding_adapter
    with _lock:
        return _embedding_adapter


def set_embedding_adapter(adapter: EmbeddingAdapter) -> None:
    """Inject an EmbeddingAdapter (for testing or configuration).

    Args:
        adapter: EmbeddingAdapter instance (typically FakeEmbeddingAdapter).
    """
    global _embedding_adapter
    _embedding_adapter = adapter


def get_docs_service() -> DocsService:
    """Get the DocsService singleton.

    Creates the service on first access using default fs2.docs package.
    Returns cached instance on subsequent calls.

    Per DYK-4: DocsService has no ConfigurationService dependency - simpler.
    Per MCP Documentation Plan Phase 2.

    Returns:
        DocsService instance (real or injected for testing).
    """
    global _docs_service
    with _lock:
        if _docs_service is None:
            from fs2.core.services.docs_service import DocsService

            logger.debug("Creating DocsService singleton")
            _docs_service = DocsService()
    return _docs_service


def set_docs_service(service: DocsService) -> None:
    """Inject a DocsService (for testing).

    Args:
        service: DocsService instance (typically with fixture package).
    """
    global _docs_service
    _docs_service = service


def reset_docs_service() -> None:
    """Reset DocsService singleton to None.

    Used in tests to ensure clean state between test cases.
    """
    global _docs_service
    _docs_service = None


def reset_services() -> None:
    """Reset all service singletons to None.

    Used in tests to ensure clean state between test cases.
    """
    global _config, _graph_store, _embedding_adapter, _docs_service
    _config = None
    _graph_store = None
    _embedding_adapter = None
    _docs_service = None
