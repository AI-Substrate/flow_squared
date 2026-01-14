"""CodeEdge frozen dataclass for cross-file relationship representation.

Represents a directional relationship edge between two code elements:
- source_node_id: Origin of the relationship (e.g., file doing the import)
- target_node_id: Destination of the relationship (e.g., file being imported)
- edge_type: Type of relationship (IMPORTS, CALLS, REFERENCES, DOCUMENTS)
- confidence: How certain we are about this relationship (0.0-1.0)
- source_line: Line number in source where relationship is defined (optional)
- resolution_rule: How the relationship was resolved (for debugging)

Immutable for thread safety. Validated at construction time.
Per Critical Discovery 02: Must follow ChunkMatch pattern exactly.
"""

from dataclasses import dataclass

from fs2.core.models.edge_type import EdgeType


@dataclass(frozen=True)
class CodeEdge:
    """Immutable cross-file relationship edge.

    Represents a directional relationship between two code elements.
    Source → Target direction (e.g., "X imports Y" = edge X→Y).

    Attributes:
        source_node_id: Origin node_id (e.g., "file:src/app.py").
        target_node_id: Destination node_id (e.g., "file:src/auth.py").
        edge_type: Relationship type (EdgeType enum).
                   Must be EdgeType enum value, not string.
        confidence: Certainty score from 0.0 to 1.0.
                   1.0 = explicit node_id reference
                   0.9 = top-level import statement
                   0.4-0.5 = raw filename in documentation
        source_line: Line number in source file where relationship is defined.
                     Optional - used for documentation discovery navigation.
        resolution_rule: How this relationship was determined (for debugging).
                        Default "unknown" for backwards compatibility.

    Raises:
        ValueError: If confidence is outside 0.0-1.0 range.
        TypeError: If edge_type is not an EdgeType enum value.

    Example:
        >>> edge = CodeEdge(
        ...     source_node_id="file:src/app.py",
        ...     target_node_id="file:src/auth.py",
        ...     edge_type=EdgeType.IMPORTS,
        ...     confidence=0.9,
        ...     source_line=5,
        ... )
        >>> edge.confidence
        0.9
        >>> edge.edge_type == EdgeType.IMPORTS
        True
    """

    source_node_id: str
    target_node_id: str
    edge_type: EdgeType
    confidence: float
    source_line: int | None = None
    resolution_rule: str = "unknown"

    def __post_init__(self) -> None:
        """Validate fields after construction.

        Raises:
            ValueError: If confidence outside 0.0-1.0 range.
            TypeError: If edge_type is not EdgeType enum.
        """
        # Validate edge_type is EdgeType enum
        if not isinstance(self.edge_type, EdgeType):
            raise TypeError(
                f"edge_type must be EdgeType enum, got {type(self.edge_type).__name__}"
            )

        # Validate confidence is in 0.0-1.0 range
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
