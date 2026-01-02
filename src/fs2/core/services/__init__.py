"""Service composition layer - business logic orchestration.

Architecture:
- Services receive adapters and config via constructor (DI)
- Services depend on adapter ABCs, not implementations
- Services use domain types only (ProcessResult, not SDK types)
- Services are testable via fake adapters

Public API:
- SampleService: Canonical example demonstrating the full pattern
- SampleServiceConfig: Configuration for SampleService
- ScanPipeline: Pipeline orchestrator for file scanning
- PipelineContext: Mutable context flowing through stages
- PipelineStage: Protocol for pipeline stages
- DiscoveryStage, ParsingStage, StorageStage: Default pipeline stages
- GetNodeService: Service for retrieving nodes from the code graph
- TreeService: Service for building tree structures from the code graph

See tests/docs/test_sample_adapter_pattern.py for complete usage documentation.
"""

from fs2.core.services.get_node_service import GetNodeService
from fs2.core.services.graph_utilities_service import GraphUtilitiesService
from fs2.core.services.pipeline_context import PipelineContext
from fs2.core.services.pipeline_stage import PipelineStage
from fs2.core.services.sample_service import SampleService, SampleServiceConfig
from fs2.core.services.scan_pipeline import ScanPipeline
from fs2.core.services.stages import (
    DiscoveryStage,
    EmbeddingStage,
    ParsingStage,
    StorageStage,
)
from fs2.core.services.tree_service import TreeService

__all__ = [
    "SampleService",
    "SampleServiceConfig",
    "PipelineContext",
    "PipelineStage",
    "ScanPipeline",
    "DiscoveryStage",
    "EmbeddingStage",
    "ParsingStage",
    "StorageStage",
    "GetNodeService",
    "GraphUtilitiesService",
    "TreeService",
]
