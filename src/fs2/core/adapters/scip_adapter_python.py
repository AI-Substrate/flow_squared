"""SCIP Python adapter.

Maps Python SCIP symbols to fs2 node_ids. Uses Pyright-based symbol
format: scip-python python <pkg> <ver> `dotted.module.path`/Class#method().

The universal descriptor parser in SCIPAdapterBase handles this format
correctly — this adapter only needs to specify the language name.
"""

from __future__ import annotations

from fs2.core.adapters.scip_adapter import SCIPAdapterBase


class SCIPPythonAdapter(SCIPAdapterBase):
    """SCIP adapter for Python projects.

    Python SCIP symbols use backtick-quoted dotted module paths:
      scip-python python pkg 0.1.0 `pkg.module`/Class#method().

    The universal descriptor parser handles this format — no overrides needed.
    """

    def language_name(self) -> str:
        return "python"
