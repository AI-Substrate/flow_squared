"""SCIP Adapter base class.

Provides the abstract base for all SCIP language adapters. Handles
universal protobuf parsing, cross-file edge extraction, deduplication,
and filtering. Per-language subclasses only override symbol_to_node_id().

Architecture:
- This file: SCIPAdapterBase ABC (contract)
- Implementations: scip_adapter_python.py, scip_adapter_fake.py, etc.
- Protobuf bindings: scip_pb2.py (generated from SCIP proto schema)

Edge format matches current Serena output: {"edge_type": "references"}
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from fs2.core.adapters import scip_pb2
from fs2.core.adapters.exceptions import SCIPIndexError

logger = logging.getLogger(__name__)


class SCIPAdapterBase(ABC):
    """Abstract base for SCIP language adapters.

    Subclasses override:
    1. language_name() — return language identifier (e.g., "python")
    2. symbol_to_node_id() — map SCIP symbol to fs2 node_id
    3. should_skip_document() — optionally filter generated files
    """

    # ── Public API ─────────────────────────────────────────

    def extract_cross_file_edges(
        self,
        index_path: str | Path,
        known_node_ids: set[str],
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """Parse index.scip and return fs2 edge tuples.

        Returns:
            List of (source_node_id, target_node_id, {"edge_type": "references"})
            where both source and target exist in known_node_ids.
        """
        index = self._load_index(index_path)
        raw_edges = self._extract_raw_edges(index)
        mapped_edges = self._map_to_node_ids(raw_edges, known_node_ids)
        deduped = self._deduplicate(mapped_edges)
        return deduped

    # ── Abstract methods (per-language) ────────────────────

    @abstractmethod
    def language_name(self) -> str:
        """Return the language identifier (e.g., 'python', 'typescript')."""
        ...

    @abstractmethod
    def symbol_to_node_id(
        self, symbol: str, file_path: str, known_node_ids: set[str]
    ) -> str | None:
        """Map a SCIP symbol + file to an fs2 node_id.

        Args:
            symbol: Full SCIP symbol string.
            file_path: Document relative path where the symbol is defined.
            known_node_ids: Set of valid fs2 node_ids to match against.

        Returns:
            Matching fs2 node_id, or None if unmappable.
        """
        ...

    # ── Protobuf parsing (universal) ──────────────────────

    def _load_index(self, path: str | Path) -> scip_pb2.Index:
        """Load and parse .scip protobuf file."""
        path = Path(path)
        if not path.exists():
            raise SCIPIndexError(
                f"SCIP index not found: {path}. "
                "Run the SCIP indexer for this project first."
            )
        try:
            index = scip_pb2.Index()
            index.ParseFromString(path.read_bytes())
        except Exception as e:
            raise SCIPIndexError(
                f"Failed to parse SCIP index {path}: {e}"
            ) from e

        if not index.documents:
            logger.warning("SCIP index %s contains 0 documents", path)

        return index

    # ── Edge extraction (universal) ───────────────────────

    def _extract_raw_edges(
        self, index: scip_pb2.Index
    ) -> list[tuple[str, str, str]]:
        """Extract (ref_file, def_file, symbol) triples.

        Algorithm (identical for all languages):
        1. Walk all documents and occurrences
        2. Build definitions map: symbol → file
        3. Build references map: symbol → [files]
        4. Yield edges where ref_file ≠ def_file
        """
        definitions: dict[str, str] = {}
        references: dict[str, list[str]] = {}

        for doc in index.documents:
            if self.should_skip_document(doc):
                continue
            rel_path = doc.relative_path

            for occ in doc.occurrences:
                sym = occ.symbol
                if not sym or sym.startswith("local "):
                    continue

                if occ.symbol_roles & 1:  # Definition bit
                    definitions[sym] = rel_path
                else:
                    references.setdefault(sym, []).append(rel_path)

        edges = []
        for sym, ref_files in references.items():
            if sym in definitions:
                def_file = definitions[sym]
                for ref_file in ref_files:
                    if ref_file != def_file:
                        edges.append((ref_file, def_file, sym))
        return edges

    # ── Node ID mapping ───────────────────────────────────

    def _map_to_node_ids(
        self,
        raw_edges: list[tuple[str, str, str]],
        known_node_ids: set[str],
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """Map raw SCIP edges to fs2 edges, filtering unknowns."""
        result = []
        unmapped_count = 0

        for ref_file, def_file, symbol in raw_edges:
            target_id = self.symbol_to_node_id(symbol, def_file, known_node_ids)
            if not target_id:
                unmapped_count += 1
                continue

            source_id = self._file_to_nearest_node(ref_file, symbol, known_node_ids)
            if not source_id:
                unmapped_count += 1
                continue

            if source_id == target_id:
                continue

            result.append((source_id, target_id, {"edge_type": "references"}))

        if unmapped_count > 0:
            logger.debug(
                "SCIP %s: %d symbols unmapped (not in known_node_ids)",
                self.language_name(),
                unmapped_count,
            )

        return result

    def _file_to_nearest_node(
        self, file_path: str, symbol: str, known_node_ids: set[str]
    ) -> str | None:
        """Find the best matching source node for a reference occurrence.

        Tries the symbol first (more precise), falls back to file node.
        """
        # Try mapping the referencing symbol itself
        source_id = self.symbol_to_node_id(symbol, file_path, known_node_ids)
        if source_id:
            return source_id

        # Fall back to file-level node
        file_node = f"file:{file_path}"
        if file_node in known_node_ids:
            return file_node

        return None

    # ── Filtering ─────────────────────────────────────────

    def should_skip_document(self, doc: scip_pb2.Document) -> bool:
        """Override to skip generated/unwanted documents.

        Default: skip nothing. C# overrides to skip
        GlobalUsings.g.cs and similar generated files.
        """
        return False

    # ── Deduplication ─────────────────────────────────────

    def _deduplicate(
        self, edges: list[tuple[str, str, dict[str, Any]]]
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """Remove duplicate edges (same source→target pair)."""
        seen: set[tuple[str, str]] = set()
        result = []
        for src, tgt, data in edges:
            key = (src, tgt)
            if key not in seen:
                seen.add(key)
                result.append((src, tgt, data))
        return result

    # ── Symbol parsing utilities ──────────────────────────

    @staticmethod
    def parse_symbol(symbol: str) -> dict[str, str] | None:
        """Parse a SCIP symbol string into components.

        Format: '<scheme> <manager> <package> <version> <descriptor>'
        Returns None for local symbols or unparseable strings.
        """
        if symbol.startswith("local "):
            return None
        parts = symbol.split(" ", 4)
        if len(parts) < 5:
            return None
        return {
            "scheme": parts[0],
            "manager": parts[1],
            "package": parts[2],
            "version": parts[3],
            "descriptor": parts[4],
        }

    @staticmethod
    def extract_name_from_descriptor(descriptor: str) -> list[str]:
        """Extract symbol name parts from a SCIP descriptor.

        Handles: `module.path`/Class#method().
        Returns: ["Class", "method"] (name parts for node_id construction)
        """
        name_parts = []
        for segment in descriptor.split("/"):
            segment = segment.strip("`")
            if "#" in segment:
                class_part, rest = segment.split("#", 1)
                if class_part and not class_part.startswith("__"):
                    name_parts.append(class_part)
                if rest:
                    method = rest.rstrip("().")
                    if method and not method.startswith("("):
                        name_parts.append(method)
            elif segment.endswith("()."):
                func = segment.rstrip("().")
                if func:
                    name_parts.append(func)
        return name_parts
