"""
Tests for Language Handler Strategy pattern.

Why:
    Implements Language Handler Strategy pattern to isolate language-specific
    AST parsing behavior, enabling unique node_id generation across languages.

Contract:
    - LanguageHandler ABC cannot be instantiated directly
    - All handlers must declare a `language` property (abstract)
    - All handlers inherit `container_types` property with defaults
    - DefaultHandler provides common container types for unknown languages
    - PythonHandler extends defaults with language-specific container types

Quality Contribution:
    Validates the Strategy pattern implementation that prevents duplicate
    node_ids caused by language-specific tree-sitter node behavior (e.g.,
    Python's "block" nodes are body wrappers, not actual code blocks).

Worked Example:
    handler = get_handler("python")
    assert "block" in handler.container_types  # Python-specific
    handler = get_handler("unknown")
    assert handler.language == "default"  # Fallback to DefaultHandler
"""

import pytest


# =============================================================================
# ST001: LanguageHandler ABC Tests
# =============================================================================


class TestLanguageHandlerABC:
    """Tests for LanguageHandler abstract base class."""

    def test_language_handler_abc_cannot_be_instantiated(self) -> None:
        """
        LanguageHandler ABC should raise TypeError when instantiated directly.

        Why: Enforce that only concrete implementations can be used.
        """
        from fs2.core.adapters.ast_languages.handler import LanguageHandler

        with pytest.raises(TypeError, match="abstract"):
            LanguageHandler()  # type: ignore[abstract]

    def test_language_handler_has_language_property(self) -> None:
        """
        LanguageHandler ABC should define language as abstract property.

        Why: Each handler must identify which language it handles.
        """
        from fs2.core.adapters.ast_languages.handler import LanguageHandler
        import inspect

        # Check that language is defined as abstract
        assert hasattr(LanguageHandler, "language")
        # It should be a property
        assert isinstance(
            inspect.getattr_static(LanguageHandler, "language"), property
        )

    def test_language_handler_has_container_types_property(self) -> None:
        """
        LanguageHandler ABC should define container_types as property with defaults.

        Why: Container types determine which tree-sitter nodes to traverse
        but not extract (skip wrappers like Python's "block" nodes).
        """
        from fs2.core.adapters.ast_languages.handler import LanguageHandler
        import inspect

        assert hasattr(LanguageHandler, "container_types")
        assert isinstance(
            inspect.getattr_static(LanguageHandler, "container_types"), property
        )


class TestDefaultHandler:
    """Tests for DefaultHandler - fallback for unknown languages."""

    def test_default_handler_language_is_default(self) -> None:
        """
        DefaultHandler should identify as "default" language.

        Why: Unknown languages should get a sensible fallback identity.
        """
        from fs2.core.adapters.ast_languages.handler import DefaultHandler

        handler = DefaultHandler()
        assert handler.language == "default"

    def test_default_handler_container_types_includes_common(self) -> None:
        """
        DefaultHandler should include common container types across languages.

        Why: These are structural wrappers that should be traversed but not
        extracted as nodes (they wrap actual code elements).
        """
        from fs2.core.adapters.ast_languages.handler import DefaultHandler

        handler = DefaultHandler()
        containers = handler.container_types

        # Must include common structural wrappers
        expected = {"module_body", "compound_statement", "declaration_list",
                    "statement_block", "body"}
        assert expected <= containers, (
            f"Missing containers: {expected - containers}"
        )

    def test_default_handler_container_types_is_set(self) -> None:
        """
        container_types should be a set for O(1) membership testing.

        Why: Parser checks `ts_kind in handler.container_types` frequently.
        """
        from fs2.core.adapters.ast_languages.handler import DefaultHandler

        handler = DefaultHandler()
        assert isinstance(handler.container_types, set)


# =============================================================================
# ST003: Handler Registry Tests
# =============================================================================


class TestHandlerRegistry:
    """Tests for handler registry - simple dict-based lookup."""

    def test_get_handler_returns_default_for_unknown(self) -> None:
        """
        get_handler should return DefaultHandler for unknown languages.

        Why: Unknown languages should get sensible defaults instead of errors.
        """
        from fs2.core.adapters.ast_languages import get_handler
        from fs2.core.adapters.ast_languages.handler import DefaultHandler

        handler = get_handler("unknown_language")
        assert isinstance(handler, DefaultHandler)
        assert handler.language == "default"

    def test_get_handler_returns_registered_handler(self) -> None:
        """
        get_handler should return the registered handler for known languages.

        Why: Language-specific handlers need to be accessible by language name.
        """
        from fs2.core.adapters.ast_languages import get_handler

        # Python is the only language we're implementing now
        handler = get_handler("python")
        assert handler.language == "python"

    def test_registry_is_case_sensitive(self) -> None:
        """
        get_handler should be case-sensitive for language names.

        Why: Tree-sitter uses lowercase language names consistently.
        """
        from fs2.core.adapters.ast_languages import get_handler
        from fs2.core.adapters.ast_languages.handler import DefaultHandler

        # "Python" (capital P) should get default, not python handler
        handler = get_handler("Python")
        assert isinstance(handler, DefaultHandler)

    def test_get_handler_returns_same_instance(self) -> None:
        """
        get_handler should return cached handler instances.

        Why: Avoid creating new handler objects on every lookup (parser
        calls this frequently during AST traversal).
        """
        from fs2.core.adapters.ast_languages import get_handler

        handler1 = get_handler("python")
        handler2 = get_handler("python")
        assert handler1 is handler2


# =============================================================================
# ST007: Parser Handler Integration Tests
# =============================================================================


class TestParserHandlerIntegration:
    """Tests verifying TreeSitterParser uses language handlers correctly."""

    def test_parser_uses_handler_for_container_detection(self) -> None:
        """
        Parser should use handler.container_types for container detection.

        Why: This replaces the hardcoded container_types set in the parser.
        """
        import tempfile
        from pathlib import Path
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser
        from fs2.config.service import FakeConfigurationService
        from fs2.config.objects import ScanConfig, GraphConfig

        config = FakeConfigurationService(
            ScanConfig(scan_paths=["src"], respect_gitignore=True),
            GraphConfig(graph_path=".fs2/graph.pickle"),
        )
        parser = TreeSitterParser(config)

        # Parser should have access to handlers
        # (We can't easily test private methods, so we test behavior)
        # Parse a simple Python file and verify no "block" nodes extracted
        python_code = '''
def hello():
    print("Hello")
'''
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(python_code)
            temp_path = Path(f.name)

        try:
            nodes = parser.parse(temp_path)

            # Should have the function, but no "block" nodes
            node_types = {n.ts_kind for n in nodes}
            assert "block" not in node_types, (
                "Python 'block' nodes should not be extracted as CodeNodes"
            )
        finally:
            temp_path.unlink()

    def test_parser_extracts_python_function_without_block_duplicate(self) -> None:
        """
        Parser should not create duplicate nodes for Python functions.

        Why: Before handler integration, both the function and its block
        wrapper would be extracted, creating duplicate node_ids.
        """
        import tempfile
        from pathlib import Path
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser
        from fs2.config.service import FakeConfigurationService
        from fs2.config.objects import ScanConfig, GraphConfig

        config = FakeConfigurationService(
            ScanConfig(scan_paths=["src"], respect_gitignore=True),
            GraphConfig(graph_path=".fs2/graph.pickle"),
        )
        parser = TreeSitterParser(config)

        python_code = '''
def my_function():
    x = 1
    return x

class MyClass:
    def my_method(self):
        pass
'''
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(python_code)
            temp_path = Path(f.name)

        try:
            nodes = parser.parse(temp_path)

            # Count how many nodes have each node_id
            from collections import Counter
            node_id_counts = Counter(n.node_id for n in nodes)
            duplicates = [(nid, count) for nid, count in node_id_counts.items() if count > 1]

            assert not duplicates, (
                f"Found duplicate node_ids: {duplicates}. "
                "Python block nodes should not be extracted."
            )
        finally:
            temp_path.unlink()

    def test_parser_no_hardcoded_container_types_in_code(self) -> None:
        """
        Parser should not have hardcoded container_types set.

        Why: Container types should come from handlers, not be hardcoded.
        This test inspects the source code to verify no hardcoded set.
        """
        import inspect
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        # Get the source code of _extract_nodes method
        source = inspect.getsource(TreeSitterParser._extract_nodes)

        # After refactoring, there should be no hardcoded container_types set
        # The old pattern was: container_types = {"module_body", ...}
        # This test will fail before ST008 and pass after
        assert "container_types = {" not in source, (
            "Parser still has hardcoded container_types set. "
            "Should use handler.container_types instead."
        )
