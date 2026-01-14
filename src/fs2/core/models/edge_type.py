"""EdgeType enum for cross-file relationship classification.

Defines the types of relationships that can exist between code elements:
- IMPORTS: File A imports module/symbol from File B
- CALLS: Function A calls function B
- REFERENCES: Text file contains explicit node_id reference
- DOCUMENTS: Markdown/docs file mentions a code element

Set by relationship extraction stage, stored on CodeEdge for downstream use.
"""

from enum import Enum


class EdgeType(str, Enum):
    """Edge type for cross-file relationship classification.

    Type-safe enum for categorizing relationship edges in the code graph.
    Inherits from str for JSON/pickle serialization compatibility.

    Types:
    - IMPORTS: Import dependency between files/modules
    - CALLS: Function/method call relationship
    - REFERENCES: Explicit node_id pattern in text (confidence 1.0)
    - DOCUMENTS: Raw filename mention in documentation

    Example:
        >>> edge = CodeEdge(
        ...     source_node_id="file:src/app.py",
        ...     target_node_id="file:src/auth.py",
        ...     edge_type=EdgeType.IMPORTS,
        ...     confidence=0.9
        ... )
        >>> edge.edge_type == "imports"
        True
        >>> str(edge.edge_type)
        'imports'
    """

    IMPORTS = "imports"
    """Import dependency: source file imports from target file/module."""

    CALLS = "calls"
    """Call relationship: source function/method calls target function/method."""

    REFERENCES = "references"
    """Explicit reference: source text contains target's node_id pattern."""

    DOCUMENTS = "documents"
    """Documentation link: source doc/markdown mentions target code element."""

    def __str__(self) -> str:
        """Return the string value."""
        return self.value
