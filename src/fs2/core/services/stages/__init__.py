"""Pipeline stages for scan orchestration.

Public API:
- DiscoveryStage: Wraps FileScanner, discovers files
- ParsingStage: Wraps ASTParser, extracts CodeNodes
- StorageStage: Wraps GraphStore, persists nodes and edges
"""

from fs2.core.services.stages.discovery_stage import DiscoveryStage
from fs2.core.services.stages.embedding_stage import EmbeddingStage
from fs2.core.services.stages.parsing_stage import ParsingStage
from fs2.core.services.stages.storage_stage import StorageStage

__all__ = [
    "DiscoveryStage",
    "EmbeddingStage",
    "ParsingStage",
    "StorageStage",
]
