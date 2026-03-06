"""Secure pickle deserialization for fs2 graph files.

Provides RestrictedUnpickler — a public contract for safely loading
graph pickle files with a class whitelist. Used by both the local
NetworkXGraphStore and the server ingestion pipeline.
"""

import pickle
from typing import Any

from fs2.core.adapters.exceptions import GraphStoreError

# Whitelist of allowed classes for unpickling
ALLOWED_MODULES = frozenset(
    {
        "builtins",
        "collections",
        "datetime",
        "pathlib",
        "networkx",
        "networkx.classes.digraph",
        "networkx.classes.reportviews",
        "fs2.core.models.code_node",
        "fs2.core.models.content_type",
    }
)


class RestrictedUnpickler(pickle.Unpickler):
    """Restricted unpickler that only allows safe classes.

    Blocks arbitrary code execution from malicious pickle files by
    whitelisting only CodeNode, networkx types, and stdlib types.

    Security:
        - Only classes from ALLOWED_MODULES can be instantiated
        - Blocks os.system, subprocess, etc.
        - Raises GraphStoreError on forbidden classes

    Usage::

        with open("graph.pickle", "rb") as f:
            unpickler = RestrictedUnpickler(f)
            data = unpickler.load()
    """

    def find_class(self, module: str, name: str) -> Any:
        """Override to restrict which classes can be unpickled."""
        if module in ALLOWED_MODULES:
            return super().find_class(module, name)

        if module.startswith("builtins") or module == "_collections_abc":
            return super().find_class(module, name)

        raise GraphStoreError(
            f"Forbidden class in pickle: {module}.{name}. "
            f"Only CodeNode, networkx, and stdlib types are allowed. "
            f"The graph file may be corrupted or malicious."
        )
