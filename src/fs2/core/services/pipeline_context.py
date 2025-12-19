"""PipelineContext - Mutable context flowing through pipeline stages.

Each stage reads from and writes to this context:
- DiscoveryStage: writes scan_results
- ParsingStage: reads scan_results, writes nodes
- StorageStage: reads nodes, writes to graph_store

Errors are collected (not raised) to enable continuation.
Metrics track per-stage performance and counts.

Per Alignment Brief:
- PipelineContext is MUTABLE (unlike frozen domain models)
- This is intentional: stages need to modify shared state
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fs2.config.objects import ScanConfig
    from fs2.core.adapters.ast_parser import ASTParser
    from fs2.core.adapters.file_scanner import FileScanner
    from fs2.core.models.code_node import CodeNode
    from fs2.core.models.scan_result import ScanResult
    from fs2.core.repos.graph_store import GraphStore


@dataclass
class PipelineContext:
    """Mutable context that flows through pipeline stages.

    Each stage reads from and writes to this context:
    - DiscoveryStage: writes scan_results
    - ParsingStage: reads scan_results, writes nodes
    - StorageStage: reads nodes, writes to graph_store

    Errors are collected (not raised) to enable continuation.
    Metrics track per-stage performance and counts.

    Attributes:
        scan_config: Configuration for scanning (required).
        graph_path: Path to persist the graph (default: .fs2/graph.pickle).
        scan_results: Files discovered by DiscoveryStage.
        nodes: CodeNodes extracted by ParsingStage.
        errors: Error messages collected from all stages.
        metrics: Per-stage timing and counts.
        file_scanner: Injected FileScanner adapter (set by pipeline).
        ast_parser: Injected ASTParser adapter (set by pipeline).
        graph_store: Injected GraphStore repository (set by pipeline).
    """

    # Configuration (set at pipeline start)
    scan_config: "ScanConfig"
    graph_path: Path = field(default_factory=lambda: Path(".fs2/graph.pickle"))

    # Stage outputs (populated as pipeline runs)
    scan_results: list["ScanResult"] = field(default_factory=list)
    nodes: list["CodeNode"] = field(default_factory=list)

    # Error collection (append, don't raise)
    errors: list[str] = field(default_factory=list)

    # Metrics per stage
    metrics: dict[str, Any] = field(default_factory=dict)

    # Injected adapters (set by pipeline before running)
    file_scanner: "FileScanner | None" = None
    ast_parser: "ASTParser | None" = None
    graph_store: "GraphStore | None" = None

    # Prior graph state for smart content preservation (Phase 6 Subtask 001)
    # Populated by ScanPipeline.run() from existing graph before stages execute.
    # Enables hash-based skip logic (AC5/AC6) by preserving smart_content across scans.
    # None on first scan (no prior graph exists), dict[str, CodeNode] on subsequent scans.
    prior_nodes: "dict[str, CodeNode] | None" = None
