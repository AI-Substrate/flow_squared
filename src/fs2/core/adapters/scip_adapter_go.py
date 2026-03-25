"""SCIP Go adapter.

Maps Go SCIP symbols to fs2 node_ids. Symbol format:
scip-go gomod <module> <hash> `import/path`/Type#Method().

The backtick-quoted segment contains Go import paths with slashes.
The fixed _split_descriptor_segments() handles this correctly.
"""

from __future__ import annotations

from fs2.core.adapters.scip_adapter import SCIPAdapterBase


class SCIPGoAdapter(SCIPAdapterBase):
    """SCIP adapter for Go projects.

    Go SCIP symbols use backtick-quoted import paths that contain slashes:
      scip-go gomod example.com/taskapp hash `example.com/taskapp/service`/TaskService#AddTask().

    The fixed _split_descriptor_segments() respects backtick quoting,
    so slashes inside import paths don't break the descriptor parser.
    No overrides needed.
    """

    def language_name(self) -> str:
        return "go"
