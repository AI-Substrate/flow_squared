"""ContentType enum for explicit content classification.

Determines processing strategy at scan time:
- CODE: Languages with extractable structure (functions, classes, methods)
- CONTENT: Everything else (docs, config, infra) - file-level only

Set by ASTParser based on language, stored on CodeNode for downstream use.
"""

from enum import Enum


class ContentType(str, Enum):
    """Content type for embedding and processing strategies.

    Simple binary classification set at scan time:
    - CODE: Real programming languages (Python, JS, Rust, etc.)
            Parser extracts functions, classes, methods.
    - CONTENT: Everything else (Markdown, YAML, HCL, etc.)
               Parser returns file-level nodes only.

    Example:
        >>> node.content_type == ContentType.CODE
        True
        >>> node.content_type.value
        'code'
    """

    CODE = "code"
    """Programming languages with extractable structure."""

    CONTENT = "content"
    """Documentation, configuration, infrastructure, data formats."""

    def __str__(self) -> str:
        """Return the string value."""
        return self.value
