"""SCIP fake adapter for testing.

Provides a test double that returns pre-configured edges without
needing real SCIP indexers or .scip files. Follows the project's
"fakes over mocks" pattern.
"""

from __future__ import annotations

from typing import Any

from fs2.core.adapters import scip_pb2
from fs2.core.adapters.scip_adapter import SCIPAdapterBase


class SCIPFakeAdapter(SCIPAdapterBase):
    """Test double for SCIP adapters.

    Usage:
        adapter = SCIPFakeAdapter()
        adapter.set_edges([("file:a.py", "callable:b.py:foo", {"edge_type": "references"})])
        edges = adapter.extract_cross_file_edges("unused", set())
        assert len(edges) == 1
    """

    def __init__(self) -> None:
        self._edges: list[tuple[str, str, dict[str, Any]]] = []
        self._index: scip_pb2.Index | None = None
        self.call_history: list[dict[str, Any]] = []

    def language_name(self) -> str:
        return "fake"

    def set_edges(
        self, edges: list[tuple[str, str, dict[str, Any]]]
    ) -> None:
        """Set edges to return from extract_cross_file_edges."""
        self._edges = edges

    def set_index(self, index: scip_pb2.Index) -> None:
        """Set a protobuf index for real parsing tests."""
        self._index = index

    def extract_cross_file_edges(
        self,
        index_path: str,
        known_node_ids: set[str],
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """Return pre-configured edges, or parse real index if set."""
        self.call_history.append({
            "method": "extract_cross_file_edges",
            "index_path": index_path,
            "known_node_ids_count": len(known_node_ids),
        })

        if self._edges:
            return self._edges

        if self._index is not None:
            raw_edges = self._extract_raw_edges(self._index)
            mapped = self._map_to_node_ids(raw_edges, known_node_ids)
            return self._deduplicate(mapped)

        return []

    def symbol_to_node_id(
        self, symbol: str, file_path: str, known_node_ids: set[str]
    ) -> str | None:
        """Simple identity mapping for testing."""
        parsed = self.parse_symbol(symbol)
        if not parsed:
            return None
        name_parts = self.extract_name_from_descriptor(parsed["descriptor"])
        if not name_parts:
            return None
        symbol_name = ".".join(name_parts)
        for category in ("callable", "class", "type", "file"):
            candidate = f"{category}:{file_path}:{symbol_name}"
            if candidate in known_node_ids:
                return candidate
        return None
