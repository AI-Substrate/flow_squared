"""SCIP Python adapter.

Maps Python SCIP symbols to fs2 node_ids. Uses Pyright-based symbol
format: scip-python python <pkg> <ver> `dotted.module.path`/Class#method().

DYK-038-04: Symbol mapping is a fuzzy lookup — tries multiple candidate
patterns (callable/class/type prefixes), falls back to file-level match.
"""

from __future__ import annotations

import logging

from fs2.core.adapters.scip_adapter import SCIPAdapterBase

logger = logging.getLogger(__name__)


class SCIPPythonAdapter(SCIPAdapterBase):
    """SCIP adapter for Python projects."""

    def language_name(self) -> str:
        return "python"

    def symbol_to_node_id(
        self, symbol: str, file_path: str, known_node_ids: set[str]
    ) -> str | None:
        """Map Python SCIP symbol to fs2 node_id.

        Python SCIP symbols look like:
          scip-python python pkg 0.1.0 `pkg.module`/Class#method().

        fs2 node_ids look like:
          callable:module.py:Class.method
          class:module.py:ClassName
        """
        parsed = self.parse_symbol(symbol)
        if not parsed:
            return None

        descriptor = parsed["descriptor"]
        name_parts = self.extract_name_from_descriptor(descriptor)

        if not name_parts:
            return None

        symbol_name = ".".join(name_parts)

        # Try callable, class, type categories
        for category in ("callable", "class", "type"):
            candidate = f"{category}:{file_path}:{symbol_name}"
            if candidate in known_node_ids:
                return candidate

        # Try without the first name part (might be module-qualified)
        if len(name_parts) > 1:
            short_name = ".".join(name_parts[1:])
            for category in ("callable", "class", "type"):
                candidate = f"{category}:{file_path}:{short_name}"
                if candidate in known_node_ids:
                    return candidate

        # Fall back to file-level node
        file_node = f"file:{file_path}"
        if file_node in known_node_ids:
            return file_node

        return None
