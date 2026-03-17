"""SCIP Adapter base class.

Provides the abstract base for all SCIP language adapters. Handles
universal protobuf parsing, cross-file edge extraction, deduplication,
and filtering. Per-language subclasses only need to override language_name().

Architecture:
- This file: SCIPAdapterBase ABC (contract) + factory + language aliases
- Implementations: scip_adapter_python.py, scip_adapter_fake.py, etc.
- Protobuf bindings: scip_pb2.py (generated from SCIP proto schema)

Edge format matches current Serena output: {"edge_type": "references"}

Design pattern: Template Method — symbol_to_node_id() is concrete in the
base class; subclasses override _extract_symbol_names() only if the
universal descriptor parser doesn't handle their language. See workshop 004.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from fs2.core.adapters import scip_pb2
from fs2.core.adapters.exceptions import SCIPAdapterError, SCIPIndexError

logger = logging.getLogger(__name__)


# ── Language aliases ──────────────────────────────────────

LANGUAGE_ALIASES: dict[str, str] = {
    "ts": "typescript",
    "js": "javascript",
    "cs": "dotnet",
    "csharp": "dotnet",
    "py": "python",
    "python": "python",
    "typescript": "typescript",
    "javascript": "javascript",
    "go": "go",
    "dotnet": "dotnet",
    "java": "java",
    "rust": "rust",
    "cpp": "cpp",
    "ruby": "ruby",
}


def normalise_language(language: str) -> str:
    """Normalise a language name/alias to its canonical form.

    Args:
        language: Language name or alias (e.g., "ts", "csharp", "python").

    Returns:
        Canonical language name (e.g., "typescript", "dotnet", "python").

    Raises:
        ValueError: If the language is not recognised.
    """
    canonical = LANGUAGE_ALIASES.get(language.lower())
    if canonical is None:
        known = sorted(set(LANGUAGE_ALIASES.values()))
        raise ValueError(
            f"Unknown language: {language!r}. "
            f"Known languages: {', '.join(known)}"
        )
    return canonical


def create_scip_adapter(language: str) -> SCIPAdapterBase:
    """Create the appropriate SCIP adapter for a language.

    Args:
        language: Canonical language name (use normalise_language() first).

    Returns:
        Language-specific SCIPAdapterBase subclass instance.

    Raises:
        SCIPAdapterError: If no adapter exists for the language.
    """
    from fs2.core.adapters.scip_adapter_dotnet import SCIPDotNetAdapter
    from fs2.core.adapters.scip_adapter_go import SCIPGoAdapter
    from fs2.core.adapters.scip_adapter_python import SCIPPythonAdapter
    from fs2.core.adapters.scip_adapter_typescript import SCIPTypeScriptAdapter

    adapters: dict[str, type[SCIPAdapterBase]] = {
        "python": SCIPPythonAdapter,
        "typescript": SCIPTypeScriptAdapter,
        "go": SCIPGoAdapter,
        "dotnet": SCIPDotNetAdapter,
    }

    adapter_cls = adapters.get(language)
    if adapter_cls is None:
        supported = ", ".join(sorted(adapters.keys()))
        raise SCIPAdapterError(
            f"No SCIP adapter for language: {language!r}. "
            f"Supported: {supported}. "
            f"Install the SCIP indexer and add adapter support."
        )
    return adapter_cls()


class SCIPAdapterBase(ABC):
    """Abstract base for SCIP language adapters.

    Subclasses MUST override:
    1. language_name() — return language identifier

    Subclasses MAY override:
    2. _extract_symbol_names() — custom descriptor-to-name-parts logic
    3. should_skip_document() — filter generated/unwanted files
    4. symbol_to_node_id() — entirely custom mapping (rarely needed)
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

    # ── Abstract methods (MUST override) ──────────────────

    @abstractmethod
    def language_name(self) -> str:
        """Return the language identifier (e.g., 'python', 'typescript')."""
        ...

    # ── Template method: symbol_to_node_id ────────────────

    def symbol_to_node_id(
        self, symbol: str, file_path: str, known_node_ids: set[str]
    ) -> str | None:
        """Map a SCIP symbol + file to an fs2 node_id.

        Template method: parses symbol, extracts names, fuzzy-matches.
        Override _extract_symbol_names() for custom descriptor parsing.
        Override this entirely for fundamentally different mapping.
        """
        parsed = self.parse_symbol(symbol)
        if not parsed:
            return None

        name_parts = self._extract_symbol_names(parsed["descriptor"])
        if not name_parts:
            return None

        return self._fuzzy_match_node_id(name_parts, file_path, known_node_ids)

    # ── Virtual hooks (MAY override) ──────────────────────

    def _extract_symbol_names(self, descriptor: str) -> list[str]:
        """Extract symbol name parts from a SCIP descriptor.

        Default uses the universal extract_name_from_descriptor() which
        handles all known languages (Python, TypeScript, Go, C#).
        Override for languages with fundamentally different descriptor formats.
        """
        return self.extract_name_from_descriptor(descriptor)

    def should_skip_document(self, doc: scip_pb2.Document) -> bool:
        """Override to skip generated/unwanted documents.

        Default: skip nothing. C# overrides to skip
        GlobalUsings.g.cs and similar generated files.
        """
        return False

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
        references: dict[str, set[str]] = {}

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
                    references.setdefault(sym, set()).add(rel_path)

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
        source_id = self.symbol_to_node_id(symbol, file_path, known_node_ids)
        if source_id:
            return source_id

        file_node = f"file:{file_path}"
        if file_node in known_node_ids:
            return file_node

        return None

    # ── Fuzzy match (shared lookup logic) ─────────────────

    def _fuzzy_match_node_id(
        self,
        name_parts: list[str],
        file_path: str,
        known_node_ids: set[str],
    ) -> str | None:
        """Try multiple category prefixes, then shorter names, then file-level.

        Lookup order:
        1. callable:path:Full.Name, class:path:Full.Name, type:path:Full.Name
        2. callable:path:ShortName (drop first part), etc.
        3. file:path (file-level fallback)
        """
        symbol_name = ".".join(name_parts)

        for category in ("callable", "class", "type"):
            candidate = f"{category}:{file_path}:{symbol_name}"
            if candidate in known_node_ids:
                return candidate

        if len(name_parts) > 1:
            short_name = ".".join(name_parts[1:])
            for category in ("callable", "class", "type"):
                candidate = f"{category}:{file_path}:{short_name}"
                if candidate in known_node_ids:
                    return candidate

        file_node = f"file:{file_path}"
        if file_node in known_node_ids:
            return file_node

        return None

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
    def _split_descriptor_segments(descriptor: str) -> list[str]:
        """Split SCIP descriptor by / while respecting backtick quoting.

        Backtick-quoted segments can contain / (e.g. Go import paths)
        and must be kept as single segments.

        Examples:
            `test.model`/Item#           → [`test.model`, Item#]
            `example.com/x/svc`/Type#    → [`example.com/x/svc`, Type#]
            TaskApp/TaskService#         → [TaskApp, TaskService#]
        """
        segments: list[str] = []
        current: list[str] = []
        in_backtick = False

        for char in descriptor:
            if char == "`":
                in_backtick = not in_backtick
                current.append(char)
            elif char == "/" and not in_backtick:
                if current:
                    segments.append("".join(current))
                current = []
            else:
                current.append(char)

        if current:
            segments.append("".join(current))

        return segments

    @staticmethod
    def extract_name_from_descriptor(descriptor: str) -> list[str]:
        """Extract symbol name parts from a SCIP descriptor.

        Handles backtick-quoted segments (skipped — module/import paths)
        and standard descriptor suffixes: # = type, (). = method, . = field.

        Examples:
            `pkg.module`/MyClass#method().  → ["MyClass", "method"]
            `example.com/x/y`/Type#Field.   → ["Type", "Field"]
            TaskApp/TaskService#AddTask().   → ["TaskService", "AddTask"]
        """
        segments = SCIPAdapterBase._split_descriptor_segments(descriptor)
        name_parts = []

        for segment in segments:
            # Skip backtick-quoted segments (module/import/file paths)
            if segment.startswith("`"):
                continue

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
