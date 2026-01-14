"""Backward compatibility re-exports from fs2.core.dependencies.

Per Phase 4 DYK-02: The actual dependency container has been moved to
fs2.core.dependencies to enable sharing between MCP server and CLI.
This module re-exports everything for backward compatibility with
existing code that imports from fs2.mcp.dependencies.

Usage (preferred - new code should use this):
    from fs2.core.dependencies import get_config, get_graph_store

Usage (backward compatible - existing code continues to work):
    from fs2.mcp.dependencies import get_config, get_graph_store
    from fs2.mcp import dependencies
    dependencies.reset_services()
"""

# Re-export everything from core.dependencies for backward compatibility
# This includes public API functions
from fs2.core.dependencies import (
    get_config,
    get_docs_service,
    get_embedding_adapter,
    get_graph_service,
    get_graph_store,
    reset_docs_service,
    reset_services,
    set_config,
    set_docs_service,
    set_embedding_adapter,
    set_graph_service,
    set_graph_store,
)

# Re-export module-level private singletons for tests that check them directly
# (e.g., test_dependencies.py::test_config_none_before_first_access)
# Uses __getattr__ for module-level attribute forwarding (PEP 562)
from fs2.core import dependencies as _core_deps

__all__ = [
    "get_config",
    "set_config",
    "get_graph_store",
    "set_graph_store",
    "get_graph_service",
    "set_graph_service",
    "get_embedding_adapter",
    "set_embedding_adapter",
    "get_docs_service",
    "set_docs_service",
    "reset_docs_service",
    "reset_services",
]


def __getattr__(name: str):
    """Forward private variable access to core.dependencies module."""
    if name in ("_config", "_graph_store", "_graph_service", "_embedding_adapter",
                "_docs_service", "_lock"):
        return getattr(_core_deps, name)
    raise AttributeError(f"module 'fs2.mcp.dependencies' has no attribute '{name}'")
