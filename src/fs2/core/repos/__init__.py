"""Repository implementations for data access."""

from fs2.core.repos.graph_store import GraphStore
from fs2.core.repos.graph_store_fake import FakeGraphStore
from fs2.core.repos.graph_store_impl import NetworkXGraphStore

__all__ = [
    "GraphStore",
    "FakeGraphStore",
    "NetworkXGraphStore",
]
