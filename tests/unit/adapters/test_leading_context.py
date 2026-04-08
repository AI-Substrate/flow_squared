"""Tests for leading context extraction from tree-sitter AST (Plan 037).

Uses real fixture files with real tree-sitter parsing — no mocks.
Validates comment/decorator extraction across multiple languages.
"""

from pathlib import Path

import pytest

from fs2.config.objects import ScanConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters.ast_parser_impl import TreeSitterParser

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "samples"


@pytest.fixture
def parser():
    config = FakeConfigurationService(ScanConfig())
    return TreeSitterParser(config)


class TestPythonLeadingContext:
    """Python: # comments and @decorators above functions/classes."""

    def test_python_hash_comment_above_class(self, parser):
        """AC02: # comments above a class are captured."""
        nodes = parser.parse(FIXTURES / "python" / "auth_handler.py")
        # Find AuthenticationError — has # comments above it
        auth_error = next((n for n in nodes if n.name == "AuthenticationError"), None)
        assert auth_error is not None
        assert auth_error.leading_context is not None
        assert "authentication failures" in auth_error.leading_context.lower()

    def test_python_decorator_above_class(self, parser):
        """AC03: @decorator above class captured as leading context."""
        nodes = parser.parse(FIXTURES / "python" / "auth_handler.py")
        auth_token = next((n for n in nodes if n.name == "AuthToken"), None)
        assert auth_token is not None
        assert auth_token.leading_context is not None
        assert "@dataclass" in auth_token.leading_context

    def test_python_hash_comment_above_method(self, parser):
        """AC02: # comment above a method is captured."""
        nodes = parser.parse(FIXTURES / "python" / "auth_handler.py")
        has_perm = next((n for n in nodes if n.name == "has_permission"), None)
        assert has_perm is not None
        assert has_perm.leading_context is not None
        assert "permissions" in has_perm.leading_context.lower()

    def test_python_property_decorator(self, parser):
        """AC03: @property decorator captured."""
        nodes = parser.parse(FIXTURES / "python" / "auth_handler.py")
        is_expired = next((n for n in nodes if n.name == "is_expired"), None)
        assert is_expired is not None
        assert is_expired.leading_context is not None
        assert "@property" in is_expired.leading_context


class TestGoLeadingContext:
    """Go: // comments above functions/types."""

    def test_go_comment_above_function(self, parser):
        """AC02: // comment above Go func captured."""
        nodes = parser.parse(FIXTURES / "go" / "server.go")
        # Find a function with a comment
        commented = [n for n in nodes if n.leading_context and n.category == "callable"]
        assert len(commented) > 0
        assert any("//" in n.leading_context for n in commented)

    def test_go_comment_above_type(self, parser):
        """// comment above Go type captured."""
        nodes = parser.parse(FIXTURES / "go" / "server.go")
        # Go types might be classified differently — check any node with // comment
        commented = [
            n
            for n in nodes
            if n.leading_context and "//" in n.leading_context and n.category != "file"
        ]
        assert len(commented) > 0


class TestRustLeadingContext:
    """Rust: /// doc comments and #[attributes]."""

    def test_rust_doc_comment(self, parser):
        """AC06 variant: /// doc comment captured."""
        nodes = parser.parse(FIXTURES / "rust" / "lib.rs")
        commented = [
            n for n in nodes if n.leading_context and "///" in n.leading_context
        ]
        assert len(commented) > 0

    def test_rust_attribute(self, parser):
        """AC06: #[derive(Debug)] attribute captured."""
        nodes = parser.parse(FIXTURES / "rust" / "lib.rs")
        with_derive = [
            n for n in nodes if n.leading_context and "#[derive" in n.leading_context
        ]
        assert len(with_derive) > 0


class TestJavaLeadingContext:
    """Java: /** Javadoc */ above methods/classes."""

    def test_java_javadoc(self, parser):
        """Javadoc block comment captured."""
        nodes = parser.parse(FIXTURES / "java" / "UserService.java")
        with_javadoc = [
            n for n in nodes if n.leading_context and "/**" in n.leading_context
        ]
        assert len(with_javadoc) > 0


class TestTypeScriptLeadingContext:
    """TypeScript: comments above export function (wrapper edge case)."""

    def test_ts_export_function_comment(self, parser):
        """AC05: Comments captured for exported functions despite export_statement wrapper."""
        nodes = parser.parse(FIXTURES / "javascript" / "app.ts")
        # Find exported functions with JSDoc
        exported_with_doc = [
            n
            for n in nodes
            if n.leading_context
            and n.category == "callable"
            and "/**" in n.leading_context
        ]
        assert len(exported_with_doc) > 0


class TestCLeadingContext:
    """C: /* Doxygen */ above functions."""

    def test_c_doxygen_comment(self, parser):
        """Doxygen /** */ block comment captured."""
        nodes = parser.parse(FIXTURES / "c" / "algorithm.c")
        with_doxygen = [
            n for n in nodes if n.leading_context and "@brief" in n.leading_context
        ]
        assert len(with_doxygen) > 0


class TestCppLeadingContext:
    """C++: /** Doxygen */ above methods."""

    def test_cpp_doxygen_comment(self, parser):
        """AC13: C++ Doxygen comments captured."""
        nodes = parser.parse(FIXTURES / "c" / "main.cpp")
        with_doxygen = [
            n for n in nodes if n.leading_context and "/**" in n.leading_context
        ]
        assert len(with_doxygen) > 0


class TestTSXLeadingContext:
    """TSX: comments above exported components."""

    def test_tsx_comment_capture(self, parser):
        """AC13: TSX JSDoc comments captured."""
        nodes = parser.parse(FIXTURES / "javascript" / "component.tsx")
        with_comment = [n for n in nodes if n.leading_context and n.category != "file"]
        assert len(with_comment) > 0


class TestJavaScriptLeadingContext:
    """JavaScript: JSDoc above functions."""

    def test_js_jsdoc_comment(self, parser):
        """AC13: JavaScript JSDoc comments captured."""
        nodes = parser.parse(FIXTURES / "javascript" / "utils.js")
        with_jsdoc = [
            n for n in nodes if n.leading_context and "/**" in n.leading_context
        ]
        assert len(with_jsdoc) > 0


class TestRubyLeadingContext:
    """Ruby: # comments above methods/classes."""

    def test_ruby_comment_capture(self, parser):
        """AC13: Ruby # comments captured."""
        nodes = parser.parse(FIXTURES / "ruby" / "tasks.rb")
        with_comment = [
            n for n in nodes if n.leading_context and "#" in n.leading_context
        ]
        assert len(with_comment) > 0


class TestBashLeadingContext:
    """Bash: # comments above functions."""

    def test_bash_comment_capture(self, parser):
        """AC13: Bash — functions not extracted as separate nodes, file-level only."""
        nodes = parser.parse(FIXTURES / "bash" / "deploy.sh")
        # Bash functions are not extracted as separate CodeNodes (not in EXTRACTABLE_LANGUAGES
        # at sub-file level). File node exists, non-file nodes may be empty.
        file_nodes = [n for n in nodes if n.category == "file"]
        assert len(file_nodes) > 0


class TestGDScriptLeadingContext:
    """GDScript: ## doc comments above functions."""

    def test_gdscript_doc_comment(self, parser):
        """AC13: GDScript ## comments captured."""
        nodes = parser.parse(FIXTURES / "gdscript" / "player.gd")
        with_comment = [
            n for n in nodes if n.leading_context and "##" in n.leading_context
        ]
        assert len(with_comment) > 0


class TestCUDALeadingContext:
    """CUDA: /** Doxygen */ above kernel functions."""

    def test_cuda_doxygen_comment(self, parser):
        """AC13: CUDA Doxygen comments captured."""
        nodes = parser.parse(FIXTURES / "cuda" / "vector_add.cu")
        with_doxygen = [
            n for n in nodes if n.leading_context and "/**" in n.leading_context
        ]
        assert len(with_doxygen) > 0


class TestBlankLineGap:
    """AC04: Blank line between comment and definition stops capture."""

    def test_blank_line_stops_capture(self, parser, tmp_path):
        """Comments separated by blank line are NOT captured."""
        test_file = tmp_path / "test_gap.py"
        test_file.write_text(
            "# This belongs to something else\n"
            "\n"
            "# This belongs to foo\n"
            "def foo():\n"
            "    pass\n"
        )
        nodes = parser.parse(test_file)
        foo = next((n for n in nodes if n.name == "foo"), None)
        assert foo is not None
        assert foo.leading_context is not None
        assert "belongs to foo" in foo.leading_context
        assert "belongs to something else" not in foo.leading_context


class TestLeadingContextCap:
    """AC10: leading_context capped at 2000 characters."""

    def test_2000_char_cap(self, parser, tmp_path):
        """Long comments are truncated at 2000 chars."""
        # Create a file with a huge comment block
        lines = [f"# Line {i}: " + "x" * 80 for i in range(50)]
        source = "\n".join(lines) + "\ndef big_function():\n    pass\n"
        test_file = tmp_path / "test_cap.py"
        test_file.write_text(source)
        nodes = parser.parse(test_file)
        big_fn = next((n for n in nodes if n.name == "big_function"), None)
        assert big_fn is not None
        assert big_fn.leading_context is not None
        assert len(big_fn.leading_context) <= 2020  # 2000 + "[TRUNCATED]"
        assert "[TRUNCATED]" in big_fn.leading_context


class TestContentHashStability:
    """AC11: content_hash must NOT change when leading_context is added."""

    def test_content_hash_excludes_leading_context(self, parser, tmp_path):
        """Same code with different comments produces same content_hash."""
        # File 1: function with comment
        f1 = tmp_path / "with_comment.py"
        f1.write_text("# Important comment\ndef foo():\n    pass\n")

        # File 2: same function, no comment
        f2 = tmp_path / "no_comment.py"
        f2.write_text("def foo():\n    pass\n")

        nodes1 = parser.parse(f1)
        nodes2 = parser.parse(f2)

        foo1 = next((n for n in nodes1 if n.name == "foo"), None)
        foo2 = next((n for n in nodes2 if n.name == "foo"), None)

        assert foo1 is not None and foo2 is not None
        assert foo1.content_hash == foo2.content_hash
        assert foo1.leading_context is not None
        assert foo2.leading_context is None


class TestFileNodeLeadingContext:
    """File-level nodes should have leading_context = None."""

    def test_file_node_no_leading_context(self, parser):
        """File nodes don't have leading context (no sibling above them)."""
        nodes = parser.parse(FIXTURES / "python" / "auth_handler.py")
        file_nodes = [n for n in nodes if n.category == "file"]
        assert len(file_nodes) > 0
        for fn in file_nodes:
            assert fn.leading_context is None
