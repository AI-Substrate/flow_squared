"""
Tests for PythonHandler - Python-specific language handler.

Why:
    Python's tree-sitter grammar uses "block" nodes as body wrappers.
    These are not actual code blocks but indentation scopes that wrap
    function bodies, class bodies, and control structure bodies.

Contract:
    - PythonHandler.language returns "python"
    - PythonHandler.container_types includes "block"
    - PythonHandler.container_types extends default containers

Quality Contribution:
    Validates Python-specific handling that prevents duplicate node_ids.
    Without this handler, every Python function/class would generate
    duplicate node_ids (one for the callable, one for its block wrapper).

Worked Example:
    handler = PythonHandler()
    assert "block" in handler.container_types
    assert "body" in handler.container_types  # Inherited from default
"""

import pytest


class TestPythonHandler:
    """Tests for PythonHandler - Python-specific container types."""

    def test_python_handler_language_is_python(self) -> None:
        """
        PythonHandler should identify as "python" language.

        Why: Handler registry uses language property to select handlers.
        """
        from fs2.core.adapters.ast_languages.python import PythonHandler

        handler = PythonHandler()
        assert handler.language == "python"

    def test_python_handler_container_types_includes_block(self) -> None:
        """
        PythonHandler should include "block" in container_types.

        Why: Python's tree-sitter uses "block" for body wrappers (not
        actual code blocks). Extracting these creates duplicate node_ids.
        """
        from fs2.core.adapters.ast_languages.python import PythonHandler

        handler = PythonHandler()
        assert "block" in handler.container_types

    def test_python_handler_container_types_extends_default(self) -> None:
        """
        PythonHandler should extend default container types, not replace.

        Why: Python still needs common containers like "body", "module_body",
        etc. The handler should add "block" to these, not replace them.
        """
        from fs2.core.adapters.ast_languages.handler import DefaultHandler
        from fs2.core.adapters.ast_languages.python import PythonHandler

        python_handler = PythonHandler()
        default_handler = DefaultHandler()

        # Python handler should have all default containers
        assert default_handler.container_types <= python_handler.container_types

        # Python handler should have additional "block" type
        assert "block" in python_handler.container_types
        assert "block" not in default_handler.container_types

    def test_python_handler_container_types_is_set(self) -> None:
        """
        container_types should be a set for O(1) membership testing.

        Why: Parser checks `ts_kind in handler.container_types` frequently.
        """
        from fs2.core.adapters.ast_languages.python import PythonHandler

        handler = PythonHandler()
        assert isinstance(handler.container_types, set)

    def test_python_handler_registered_in_registry(self) -> None:
        """
        PythonHandler should be accessible via get_handler("python").

        Why: Parser uses registry to get handlers by language name.
        """
        from fs2.core.adapters.ast_languages import get_handler
        from fs2.core.adapters.ast_languages.python import PythonHandler

        handler = get_handler("python")
        assert isinstance(handler, PythonHandler)
        assert handler.language == "python"
