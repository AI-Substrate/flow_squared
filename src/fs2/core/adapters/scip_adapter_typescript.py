"""SCIP TypeScript adapter.

Maps TypeScript SCIP symbols to fs2 node_ids. Symbol format:
scip-typescript npm . . `file.ts`/Class#method().

The universal descriptor parser in SCIPAdapterBase handles this format
correctly — this adapter only needs to specify the language name.
"""

from __future__ import annotations

from fs2.core.adapters.scip_adapter import SCIPAdapterBase


class SCIPTypeScriptAdapter(SCIPAdapterBase):
    """SCIP adapter for TypeScript/JavaScript projects.

    TypeScript SCIP symbols use backtick-quoted file paths:
      scip-typescript npm . . `service.ts`/TaskService#addTask().

    The backtick segment is the file path (no slashes inside).
    The universal descriptor parser handles this — no overrides needed.
    """

    def language_name(self) -> str:
        return "typescript"
