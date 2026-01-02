"""Domain models as frozen dataclasses.

Public API:
- LogLevel: Log severity levels (IntEnum)
- LogEntry: Immutable log entry with level, message, context, timestamp
- ProcessResult: Result type for adapter operations with ok()/fail() factories
- CodeNode: Universal code node for any structural code element
- classify_node: Language-agnostic classification utility
- ScanResult: File scan result with path and size
- ScanSummary: Pipeline execution result summary
- TreeNode: Recursive tree structure for tree rendering
- DocMetadata: Document metadata for catalog listings
- Doc: Complete document with metadata and content
"""

from fs2.core.models.code_node import CodeNode, classify_node
from fs2.core.models.doc import Doc, DocMetadata
from fs2.core.models.log_entry import LogEntry
from fs2.core.models.log_level import LogLevel
from fs2.core.models.process_result import ProcessResult
from fs2.core.models.scan_result import ScanResult
from fs2.core.models.scan_summary import ScanSummary
from fs2.core.models.tree_node import TreeNode

__all__ = [
    "LogLevel",
    "LogEntry",
    "ProcessResult",
    "CodeNode",
    "classify_node",
    "ScanResult",
    "ScanSummary",
    "TreeNode",
    "DocMetadata",
    "Doc",
]
