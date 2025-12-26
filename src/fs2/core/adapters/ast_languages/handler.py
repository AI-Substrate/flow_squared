"""
Language Handler ABC and DefaultHandler implementation.

Implements the Strategy pattern for language-specific AST parsing behavior.
Each handler defines container types that should be traversed but not
extracted as code nodes.

Why:
    Tree-sitter produces different node types with the same name across
    languages. For example, Python's "block" is a body wrapper (skip it),
    while other languages may use "block" for actual code blocks.

Contract:
    - LanguageHandler: ABC with abstract `language` property
    - DefaultHandler: Concrete handler for unknown languages
    - Handlers define `container_types` property (set of node types to skip)

Example:
    handler = DefaultHandler()
    if "module_body" in handler.container_types:
        # Traverse but don't create a CodeNode for module_body
        pass
"""

from abc import ABC, abstractmethod


class LanguageHandler(ABC):
    """
    Abstract base class for language-specific AST handling.

    Each language handler defines:
    - `language`: The language this handler is for (e.g., "python", "go")
    - `container_types`: Node types that should be traversed but not extracted

    Container types are structural wrappers in tree-sitter ASTs that don't
    represent actual code elements. They should be recursed into to find
    the real nodes, but shouldn't create CodeNode instances themselves.
    """

    @property
    @abstractmethod
    def language(self) -> str:
        """The language this handler handles (e.g., 'python', 'go')."""
        ...

    @property
    def container_types(self) -> set[str]:
        """
        Node types that should be traversed but not extracted.

        These are structural wrappers in tree-sitter ASTs. The parser
        should recurse into them to find actual code nodes, but should
        not create CodeNode instances for the containers themselves.

        Returns:
            Set of tree-sitter node type names to skip during extraction.
        """
        return {
            "module_body",  # Various languages - module-level wrapper
            "compound_statement",  # C-family compound statements
            "declaration_list",  # Declaration sequences
            "statement_block",  # Block-scoped statements
            "body",  # Python/HCL body wrapper
        }


class DefaultHandler(LanguageHandler):
    """
    Default handler for languages without specific handling.

    Provides sensible defaults for container types that are common
    across many languages. Used as fallback when no language-specific
    handler is registered.
    """

    @property
    def language(self) -> str:
        """Returns 'default' to identify this as the fallback handler."""
        return "default"

    # container_types inherited from LanguageHandler base class
