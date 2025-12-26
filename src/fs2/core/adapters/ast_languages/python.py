"""
Python-specific Language Handler.

Handles Python-specific tree-sitter node behavior. The key difference
from other languages is that Python's "block" node type is a body
wrapper (just for indentation scope), not an actual code block.

Why:
    Tree-sitter's Python grammar wraps function/class bodies in "block"
    nodes, but these don't represent actual code elements. Extracting
    them as CodeNodes creates duplicate node_ids with the parent callable.

Contract:
    - `language` returns "python"
    - `container_types` extends defaults with {"block"}
    - "block" nodes are traversed but not extracted

Example:
    handler = PythonHandler()
    assert "block" in handler.container_types
    assert handler.language == "python"
"""

from fs2.core.adapters.ast_languages.handler import LanguageHandler


class PythonHandler(LanguageHandler):
    """
    Handler for Python-specific AST behavior.

    Python's tree-sitter grammar uses "block" nodes as body wrappers
    for functions, classes, and control structures. These should be
    traversed to find actual code nodes, but not extracted as nodes
    themselves.
    """

    @property
    def language(self) -> str:
        """Returns 'python' to identify this handler."""
        return "python"

    @property
    def container_types(self) -> set[str]:
        """
        Extends default containers with Python's "block" type.

        Python's "block" is a body wrapper that wraps the actual
        code inside functions, classes, if/for/while blocks, etc.
        It should be traversed but not extracted as a CodeNode.
        """
        return super().container_types | {"block"}
