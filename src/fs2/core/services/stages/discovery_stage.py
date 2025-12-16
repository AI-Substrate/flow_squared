"""DiscoveryStage - Pipeline stage for file discovery.

Wraps FileScanner adapter to discover files in configured scan paths.
Populates context.scan_results for downstream ParsingStage.

Per Alignment Brief:
- Validates file_scanner not None (raises ValueError)
- Catches FileScannerError, appends to context.errors
- Records metrics: discovery_files count
"""

from typing import TYPE_CHECKING

from fs2.core.adapters.exceptions import FileScannerError

if TYPE_CHECKING:
    from fs2.core.services.pipeline_context import PipelineContext


class DiscoveryStage:
    """Pipeline stage that discovers files using FileScanner.

    This stage:
    - Validates file_scanner is present in context
    - Calls file_scanner.scan() to discover files
    - Populates context.scan_results
    - Catches FileScannerError and appends to context.errors
    - Records discovery_files count in context.metrics
    """

    @property
    def name(self) -> str:
        """Human-readable stage name for logging and metrics."""
        return "discovery"

    def process(self, context: "PipelineContext") -> "PipelineContext":
        """Discover files using the file scanner.

        Args:
            context: Pipeline context with file_scanner adapter.

        Returns:
            Context with scan_results populated.

        Raises:
            ValueError: If context.file_scanner is None.
        """
        # Validate precondition
        if context.file_scanner is None:
            raise ValueError(
                "DiscoveryStage requires file_scanner to be set in context. "
                "Ensure ScanPipeline injects the FileScanner adapter."
            )

        try:
            # Discover files
            results = context.file_scanner.scan()
            context.scan_results = results

            # Record metrics
            context.metrics["discovery_files"] = len(results)

        except FileScannerError as e:
            # Collect error, don't raise
            context.errors.append(str(e))
            context.scan_results = []
            context.metrics["discovery_files"] = 0

        return context
