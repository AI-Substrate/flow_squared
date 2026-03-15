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

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fs2.config.objects import CrossFileRelsConfig, ScanConfig
    from fs2.core.adapters.ast_parser import ASTParser
    from fs2.core.adapters.file_scanner import FileScanner
    from fs2.core.models.code_node import CodeNode
    from fs2.core.models.scan_result import ScanResult
    from fs2.core.repos.graph_store import GraphStore
    from fs2.core.services.embedding.embedding_service import EmbeddingService
    from fs2.core.services.smart_content.smart_content_service import (
        ProgressCallback,
        SmartContentService,
    )


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

    # Cross-file relationship edges collected by CrossFileRelsStage.
    # Each tuple is (source_node_id, target_node_id, edge_data_dict).
    # Written to graph by StorageStage after containment edges.
    cross_file_edges: list[tuple[str, str, dict[str, Any]]] = field(
        default_factory=list
    )

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

    # Prior graph reference edges for incremental cross-file resolution (Phase 3 T008).
    # Populated by ScanPipeline.run() from existing graph before clear().
    # Each tuple: (source_node_id, target_node_id, edge_data_dict).
    # Enables skipping Serena calls for unchanged files by reusing prior edges.
    # None on first scan.
    prior_cross_file_edges: "list[tuple[str, str, dict[str, Any]]] | None" = None

    # Cross-file relationship config (Phase 4 T002).
    # Populated by ScanPipeline from constructor param.
    # CrossFileRelsStage reads this for enabled, parallel_instances, etc.
    # None when config not provided (stage skips per DYK-P4-02).
    cross_file_rels_config: "CrossFileRelsConfig | None" = None

    # Scan root directory (Phase 4 DYK-P4-04).
    # Canonical project root, always set to CWD at pipeline start.
    # Used by CrossFileRelsStage for project root detection.
    scan_root: Path = field(default_factory=lambda: Path.cwd().resolve())

    # SmartContentService for AI-powered smart content generation (Phase 6 T004)
    # Injected by ScanPipeline when smart content is enabled.
    # None when --no-smart-content flag is used or LLM not configured.
    # Per Session 2 Insight #3: Stage reads service from context, not constructor.
    smart_content_service: "SmartContentService | None" = None

    # Progress callback for smart content batch processing.
    # Called every 10 items and on errors with SmartContentProgress info.
    # CLI uses this to display real-time progress (blue for progress, red for errors).
    smart_content_progress_callback: "ProgressCallback | None" = None

    # EmbeddingService for vector embedding generation (Phase 4 T003)
    # Injected by ScanPipeline when embeddings are enabled.
    # None when --no-embeddings flag is used or embedding config missing.
    embedding_service: "EmbeddingService | None" = None

    # Force re-embedding: when True, dimension mismatch is a warning not error,
    # and all existing embeddings are cleared for re-generation.
    # Set via CLI --force flag (032-T008, DYK-2).
    force_embeddings: bool = False

    # Progress callback for embedding batch processing.
    # Called with (processed, total, skipped) counts from EmbeddingService.
    embedding_progress_callback: "Callable[[int, int, int], None] | None" = None

    # Progress callback for parsing stage (Phase 2: Quiet Scan Output).
    # Called every 100 files with (processed, total) counts.
    # Only called when total > 100 to avoid noise on small scans.
    parsing_progress_callback: Callable[[int, int], None] | None = None

    # Completion callback for parsing stage (Phase 2: Quiet Scan Output).
    # Called after parsing completes with files_scanned, nodes_created, skip_summary.
    # Allows CLI to display summary before smart content stage starts.
    parsing_complete_callback: Callable[..., None] | None = None

    # Progress callback for cross-file relationship resolution.
    # Called with (status: str, detail: str) at key milestones:
    #   "starting"  — resolution is beginning (detail: node count)
    #   "progress"  — batch progress (detail: "N/M nodes, K edges")
    #   "reused"    — all files unchanged (detail: reused edge count)
    #   "complete"  — resolution finished (detail: summary)
    #   "skipped"   — stage skipped (detail: reason)
    cross_file_rels_progress_callback: Callable[[str, str], None] | None = None
