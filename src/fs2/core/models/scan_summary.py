"""ScanSummary - Pipeline execution result model.

Frozen dataclass containing the final results of a pipeline execution.
Returned by ScanPipeline.run() to report success, counts, errors, and metrics.

Per Alignment Brief:
- ScanSummary is frozen (immutable like other domain models)
- success = True only when errors list is empty
- Contains files_scanned, nodes_created, errors, metrics
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ScanSummary:
    """Immutable summary of a pipeline execution.

    Returned by ScanPipeline.run() to report the final state after
    all stages have completed. Contains success status, counts, errors,
    and metrics collected from each stage.

    Attributes:
        success: True if no errors occurred during execution.
        files_scanned: Number of files discovered by DiscoveryStage.
        nodes_created: Number of CodeNodes created by ParsingStage.
        errors: List of error messages collected from all stages.
        metrics: Dictionary of per-stage metrics (timing, counts, etc.).

    Example:
        >>> summary = ScanSummary(
        ...     success=True,
        ...     files_scanned=100,
        ...     nodes_created=500,
        ...     errors=[],
        ...     metrics={"discovery_files": 100, "parsing_nodes": 500},
        ... )
        >>> summary.success
        True
        >>> summary.nodes_created
        500
    """

    success: bool
    files_scanned: int
    nodes_created: int
    errors: list[str]
    metrics: dict[str, Any]
