"""ScanPipeline - Orchestrates pipeline stages sequentially.

The main entry point for scanning a codebase. Receives ConfigurationService
and adapters via constructor, runs stages in order, returns ScanSummary.

Per Alignment Brief:
- Receives ConfigurationService, calls config.require(ScanConfig)
- Receives adapters via constructor, injects into PipelineContext
- Default stages: Discovery → Parsing → SmartContent → Storage
- Custom stages can override defaults
- Returns ScanSummary with success, counts, errors, metrics

Per Subtask 001 (Graph Loading for Smart Content Preservation):
- Loads existing graph before running stages
- Builds prior_nodes dict for O(1) lookup by node_id
- Enables hash-based skip logic (AC5/AC6) for smart content

Per Phase 6 T005 (ScanPipeline Constructor):
- Accepts optional SmartContentService
- Injects service into PipelineContext.smart_content_service
- SmartContentStage placed between ParsingStage and StorageStage
- Stage order: Discovery → Parsing → SmartContent → Storage
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from fs2.config.objects import ScanConfig
from fs2.core.adapters.exceptions import GraphStoreError
from fs2.core.models.scan_summary import ScanSummary
from fs2.core.services.pipeline_context import PipelineContext
from fs2.core.services.pipeline_stage import PipelineStage
from fs2.core.services.stages.discovery_stage import DiscoveryStage
from fs2.core.services.stages.embedding_stage import EmbeddingStage
from fs2.core.services.stages.parsing_stage import ParsingStage
from fs2.core.services.stages.smart_content_stage import SmartContentStage
from fs2.core.services.stages.storage_stage import StorageStage

if TYPE_CHECKING:
    from collections.abc import Callable

    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.ast_parser import ASTParser
    from fs2.core.adapters.file_scanner import FileScanner
    from fs2.core.models.code_node import CodeNode
    from fs2.core.repos.graph_store import GraphStore
    from fs2.core.services.embedding.embedding_service import EmbeddingService
    from fs2.core.services.smart_content.smart_content_service import (
        ProgressCallback,
        SmartContentService,
    )

logger = logging.getLogger(__name__)


class ScanPipeline:
    """Orchestrates pipeline stages sequentially.

    Usage:
        ```python
        pipeline = ScanPipeline(
            config=config_service,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            smart_content_service=smart_service,  # Optional
        )
        summary = pipeline.run()
        ```

    The pipeline:
    1. Creates PipelineContext with injected adapters
    2. Runs each stage in order (Discovery → Parsing → SmartContent → Embedding → Storage)
    3. Collects errors without stopping
    4. Returns ScanSummary with final metrics

    Custom stages can be provided via the `stages` parameter to override
    the default Discovery → Parsing → SmartContent → Embedding → Storage sequence.

    Stage Order (per Session 2 Insight #5):
        SmartContentStage MUST be between ParsingStage and EmbeddingStage.
        EmbeddingStage MUST be between SmartContentStage and StorageStage.
        This ensures nodes are enriched before embedding and persistence.
    """

    def __init__(
        self,
        config: "ConfigurationService",
        file_scanner: "FileScanner",
        ast_parser: "ASTParser",
        graph_store: "GraphStore",
        stages: list[PipelineStage] | None = None,
        smart_content_service: "SmartContentService | None" = None,
        smart_content_progress_callback: "ProgressCallback | None" = None,
        embedding_service: "EmbeddingService | None" = None,
        embedding_progress_callback: "EmbeddingService.ProgressCallback | None" = None,
        parsing_progress_callback: "Callable[[int, int], None] | None" = None,
        parsing_complete_callback: "Callable[..., None] | None" = None,
        graph_path: Path | None = None,
    ):
        """Initialize pipeline with config and adapters.

        Args:
            config: ConfigurationService registry.
                    Pipeline will call config.require(ScanConfig) internally.
            file_scanner: FileScanner adapter for file discovery.
            ast_parser: ASTParser adapter for code parsing.
            graph_store: GraphStore repository for persistence.
            stages: Optional custom stage list. If None, uses default stages.
            smart_content_service: Optional SmartContentService for AI summaries.
                                   If None, SmartContentStage still runs but
                                   skips generation gracefully.
            smart_content_progress_callback: Optional callback for smart content
                                             progress updates (called every 10 items
                                             and on errors).
            embedding_service: Optional EmbeddingService for vector embeddings.
                               If None, EmbeddingStage still runs but skips generation.
            embedding_progress_callback: Optional callback for embedding
                                         progress updates (processed, total, skipped).
            parsing_progress_callback: Optional callback for parsing progress
                                       updates (processed, total). Called every
                                       100 files when total > 100.
            graph_path: Path to save graph. REQUIRED to prevent accidental
                        corruption of project graph during tests. Use
                        tmp_path / "graph.pickle" in tests.

        Raises:
            MissingConfigurationError: If ScanConfig not in registry.
            ValueError: If graph_path is None.

        Note:
            When custom stages are provided, caller is responsible for stage
            ordering. SmartContentStage MUST be between ParsingStage and
            EmbeddingStage, and EmbeddingStage MUST be between SmartContentStage
            and StorageStage.
        """
        # Validate graph_path is provided (prevent accidental project graph corruption)
        if graph_path is None:
            raise ValueError(
                "graph_path is required. Pass an explicit path to prevent "
                "accidental corruption of .fs2/graph.pickle. "
                "In tests, use: graph_path=tmp_path / 'graph.pickle'"
            )

        # Extract config internally (per Critical Finding 01)
        self._scan_config = config.require(ScanConfig)
        self._file_scanner = file_scanner
        self._ast_parser = ast_parser
        self._graph_store = graph_store
        self._smart_content_service = smart_content_service
        self._smart_content_progress_callback = smart_content_progress_callback
        self._embedding_service = embedding_service
        self._embedding_progress_callback = embedding_progress_callback
        self._parsing_progress_callback = parsing_progress_callback
        self._parsing_complete_callback = parsing_complete_callback
        self._graph_path = graph_path

        # Default stages if not provided
        # Order: Discovery → Parsing → SmartContent → Embedding → Storage
        self._stages = (
            stages
            if stages is not None
            else [
                DiscoveryStage(),
                ParsingStage(),
                SmartContentStage(),
                EmbeddingStage(),
                StorageStage(),
            ]
        )

    def run(self) -> ScanSummary:
        """Execute the pipeline and return summary.

        Creates a PipelineContext, loads prior graph state, runs each
        stage in order, and builds a ScanSummary from the final context.

        Per Subtask 001: Loads existing graph before stages execute to
        enable hash-based skip logic (AC5/AC6) for smart content.

        Returns:
            ScanSummary with success, files_scanned, nodes_created,
            errors, and metrics.
        """
        # Build context with adapters
        # Per Subtask 001: Use custom graph_path if provided, otherwise use default
        context_kwargs = {
            "scan_config": self._scan_config,
            "file_scanner": self._file_scanner,
            "ast_parser": self._ast_parser,
            "graph_store": self._graph_store,
            "smart_content_service": self._smart_content_service,
            "smart_content_progress_callback": self._smart_content_progress_callback,
            "embedding_service": self._embedding_service,
            "embedding_progress_callback": self._embedding_progress_callback,
            "parsing_progress_callback": self._parsing_progress_callback,
            "parsing_complete_callback": self._parsing_complete_callback,
        }
        if self._graph_path is not None:
            context_kwargs["graph_path"] = self._graph_path
        context = PipelineContext(**context_kwargs)

        # Load prior graph state for smart content preservation (Subtask 001)
        # This enables hash-based skip logic (AC5/AC6) by providing prior
        # smart_content and smart_content_hash values to SmartContentStage.
        context.prior_nodes = self._load_prior_nodes(context)

        # Clear graph after extracting prior_nodes - we build fresh each scan
        if context.graph_store is not None:
            context.graph_store.clear()

        # Run each stage sequentially
        for stage in self._stages:
            context = stage.process(context)

        # Build summary from final context
        return ScanSummary(
            success=len(context.errors) == 0,
            files_scanned=len(context.scan_results),
            nodes_created=len(context.nodes),
            errors=context.errors,
            metrics=context.metrics,
        )

    def _load_prior_nodes(
        self, context: PipelineContext
    ) -> dict[str, "CodeNode"] | None:
        """Load prior graph state into a dict for O(1) lookup.

        Per Subtask 001 (Graph Loading for Smart Content Preservation):
        - Loads existing graph from context.graph_path
        - Builds dict mapping node_id -> CodeNode for efficient merge
        - Returns None on first scan (no graph exists) or corrupted graph

        Args:
            context: PipelineContext with graph_store and graph_path.

        Returns:
            Dict mapping node_id to CodeNode, or None if no prior graph.
        """
        if context.graph_store is None:
            logger.warning("No graph_store in context, skipping prior graph loading")
            return None

        try:
            # Load existing graph
            context.graph_store.load(context.graph_path)

            # Build dict for O(1) lookup by node_id
            nodes = context.graph_store.get_all_nodes()
            prior_nodes: dict[str, CodeNode] = {node.node_id: node for node in nodes}

            logger.info(
                "Loaded %d prior nodes from %s for smart content preservation",
                len(prior_nodes),
                context.graph_path,
            )

            return prior_nodes

        except GraphStoreError as e:
            # First scan (no graph exists) or corrupted graph
            # This is expected on first scan, so log at debug level
            logger.debug(
                "No prior graph loaded from %s: %s. "
                "This is normal for first scan or if graph was deleted.",
                context.graph_path,
                str(e),
            )
            return None
