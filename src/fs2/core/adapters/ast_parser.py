"""ASTParser ABC interface.

Abstract base class defining the AST parsing contract.
Implementations transform source files into CodeNode hierarchies
using tree-sitter for language-specific parsing.

Architecture:
- This file: ABC definition only
- Implementations: ast_parser_fake.py, ast_parser_impl.py

Per Critical Finding 02: Adapter ABC with Dual Implementation Pattern.
Per Critical Finding 01: Implementations receive ConfigurationService.
Per Critical Finding 03: Use .children not .child(i) for traversal.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from fs2.core.models.code_node import CodeNode


class ASTParser(ABC):
    """Abstract base class for AST parsing adapters.

    This interface defines the contract for transforming source files
    into structured CodeNode hierarchies using tree-sitter.

    Implementations must:
    - Receive ConfigurationService in constructor (not ScanConfig directly)
    - Return list[CodeNode] with file, type, callable, section, block nodes
    - Use .children for tree traversal (per CF03 - O(n) vs O(n log n))
    - Translate SDK errors to ASTParserError
    - Skip binary files gracefully (per CF07)

    See Also:
        - ast_parser_fake.py: Test double implementation
        - ast_parser_impl.py: Production TreeSitterParser implementation
    """

    @abstractmethod
    def parse(self, file_path: Path) -> list[CodeNode]:
        """Parse a source file and extract CodeNode hierarchy.

        Transforms a source file into structural CodeNode elements
        (file, classes, functions, methods, etc.) using tree-sitter.

        Args:
            file_path: Path to the source file to parse.

        Returns:
            List of CodeNode representing structural elements.
            Returns empty list for binary files or unsupported languages.
            Minimum return is a file-level node for parseable files.

        Raises:
            ASTParserError: If file cannot be read or has encoding issues.
        """
        ...

    @abstractmethod
    def detect_language(self, file_path: Path) -> str | None:
        """Detect programming language from file extension or name.

        Uses static mapping of extensions to language names.
        Handles ambiguous extensions like .h (defaults to cpp).
        Handles filename matching for Dockerfile, Makefile, etc.

        Args:
            file_path: Path to check for language detection.

        Returns:
            Language name string (e.g., "python", "typescript", "markdown")
            or None if language cannot be determined.
        """
        ...
