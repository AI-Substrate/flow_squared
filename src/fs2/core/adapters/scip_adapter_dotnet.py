"""SCIP C#/.NET adapter.

Maps C# SCIP symbols to fs2 node_ids. Symbol format:
scip-dotnet nuget . . Namespace/Class#Method().

No backtick quoting — namespace segments use / directly.
Filters generated documents under obj/ from the SCIP index.
"""

from __future__ import annotations

from fs2.core.adapters import scip_pb2
from fs2.core.adapters.scip_adapter import SCIPAdapterBase


class SCIPDotNetAdapter(SCIPAdapterBase):
    """SCIP adapter for C#/.NET projects.

    C# SCIP symbols use plain namespace paths (no backtick quoting):
      scip-dotnet nuget . . TaskApp/TaskService#AddTask().

    Namespace segments (e.g. "TaskApp") are skipped by the universal
    descriptor parser since they don't contain # or ().

    Overrides should_skip_document() to filter generated files that
    scip-dotnet includes from the obj/ build output directory.
    """

    _SKIP_PREFIXES = ("obj/",)

    def language_name(self) -> str:
        return "dotnet"

    def should_skip_document(self, doc: scip_pb2.Document) -> bool:
        """Skip C# generated files under obj/."""
        return any(doc.relative_path.startswith(p) for p in self._SKIP_PREFIXES)
