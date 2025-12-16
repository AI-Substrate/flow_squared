"""ScanPipeline - Orchestrates pipeline stages sequentially.

The main entry point for scanning a codebase. Receives ConfigurationService
and adapters via constructor, runs stages in order, returns ScanSummary.

Per Alignment Brief:
- Receives ConfigurationService, calls config.require(ScanConfig)
- Receives adapters via constructor, injects into PipelineContext
- Default stages: Discovery → Parsing → Storage
- Custom stages can override defaults
- Returns ScanSummary with success, counts, errors, metrics
"""

from typing import TYPE_CHECKING

from fs2.config.objects import ScanConfig
from fs2.core.models.scan_summary import ScanSummary
from fs2.core.services.pipeline_context import PipelineContext
from fs2.core.services.pipeline_stage import PipelineStage
from fs2.core.services.stages.discovery_stage import DiscoveryStage
from fs2.core.services.stages.parsing_stage import ParsingStage
from fs2.core.services.stages.storage_stage import StorageStage

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.ast_parser import ASTParser
    from fs2.core.adapters.file_scanner import FileScanner
    from fs2.core.repos.graph_store import GraphStore


class ScanPipeline:
    """Orchestrates pipeline stages sequentially.

    Usage:
        ```python
        pipeline = ScanPipeline(
            config=config_service,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
        )
        summary = pipeline.run()
        ```

    The pipeline:
    1. Creates PipelineContext with injected adapters
    2. Runs each stage in order (Discovery → Parsing → Storage)
    3. Collects errors without stopping
    4. Returns ScanSummary with final metrics

    Custom stages can be provided via the `stages` parameter to override
    the default Discovery → Parsing → Storage sequence.
    """

    def __init__(
        self,
        config: "ConfigurationService",
        file_scanner: "FileScanner",
        ast_parser: "ASTParser",
        graph_store: "GraphStore",
        stages: list[PipelineStage] | None = None,
    ):
        """Initialize pipeline with config and adapters.

        Args:
            config: ConfigurationService registry.
                    Pipeline will call config.require(ScanConfig) internally.
            file_scanner: FileScanner adapter for file discovery.
            ast_parser: ASTParser adapter for code parsing.
            graph_store: GraphStore repository for persistence.
            stages: Optional custom stage list. If None, uses default stages.

        Raises:
            MissingConfigurationError: If ScanConfig not in registry.
        """
        # Extract config internally (per Critical Finding 01)
        self._scan_config = config.require(ScanConfig)
        self._file_scanner = file_scanner
        self._ast_parser = ast_parser
        self._graph_store = graph_store

        # Default stages if not provided
        self._stages = stages if stages is not None else [
            DiscoveryStage(),
            ParsingStage(),
            StorageStage(),
        ]

    def run(self) -> ScanSummary:
        """Execute the pipeline and return summary.

        Creates a PipelineContext, runs each stage in order,
        and builds a ScanSummary from the final context state.

        Returns:
            ScanSummary with success, files_scanned, nodes_created,
            errors, and metrics.
        """
        # Build context with adapters
        context = PipelineContext(
            scan_config=self._scan_config,
            file_scanner=self._file_scanner,
            ast_parser=self._ast_parser,
            graph_store=self._graph_store,
        )

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
