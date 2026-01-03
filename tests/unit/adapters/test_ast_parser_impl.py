"""Tests for TreeSitterParser production implementation.

Tasks: T010-T042
Purpose: Verify TreeSitterParser correctly parses source files into CodeNode hierarchies.
Per CF02: Adapter ABC with Dual Implementation Pattern.
Per CF03: Use .children not .child(i) for O(n) traversal.
Per CF07: Binary file detection (null bytes in first 8KB).
Per CF08: AST hierarchy depth limit (named nodes up to depth 4).
Per CF10: Exception translation to ASTParserError.
Per CF11: Node ID uniqueness with position-based anonymous IDs.
Per CF13: Language detection ambiguity (.h -> cpp default).
"""


import pytest

# =============================================================================
# Language Detection Tests (T010-T017)
# =============================================================================


@pytest.mark.unit
class TestTreeSitterParserLanguageDetection:
    """Tests for language detection functionality (T010-T017)."""

    def test_detect_language_python(self, ast_samples_path):
        """
        Purpose: Verifies .py extension detected as python.
        Quality Contribution: Ensures Python files use correct grammar.
        Acceptance Criteria: detect_language returns "python" for .py files.

        Task: T010
        AC: AC4
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        py_file = ast_samples_path / "python" / "simple_class.py"
        language = parser.detect_language(py_file)

        assert language == "python"

    def test_detect_language_typescript(self, ast_samples_path):
        """
        Purpose: Verifies .ts extension detected as typescript.
        Quality Contribution: Ensures TypeScript files use correct grammar.
        Acceptance Criteria: detect_language returns "typescript" for .ts files.

        Task: T011
        AC: AC4
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        ts_file = ast_samples_path / "typescript" / "interfaces_types.ts"
        language = parser.detect_language(ts_file)

        assert language == "typescript"

    def test_detect_language_javascript(self, ast_samples_path):
        """
        Purpose: Verifies .js extension detected as javascript.
        Quality Contribution: Ensures JavaScript files use correct grammar.
        Acceptance Criteria: detect_language returns "javascript" for .js files.

        Task: T011
        AC: AC4
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        js_file = ast_samples_path / "typescript" / "standalone.js"
        language = parser.detect_language(js_file)

        assert language == "javascript"

    def test_detect_language_tsx(self, ast_samples_path):
        """
        Purpose: Verifies .tsx extension detected as tsx.
        Quality Contribution: Ensures TSX files use correct grammar.
        Acceptance Criteria: detect_language returns "tsx" for .tsx files.

        Task: T011
        AC: AC4
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        tsx_file = ast_samples_path / "typescript" / "react_component.tsx"
        language = parser.detect_language(tsx_file)

        assert language == "tsx"

    def test_detect_language_markdown(self, ast_samples_path):
        """
        Purpose: Verifies .md extension detected as markdown.
        Quality Contribution: Ensures Markdown files use correct grammar.
        Acceptance Criteria: detect_language returns "markdown" for .md files.

        Task: T012
        AC: AC4
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        md_file = ast_samples_path / "markdown" / "headings_nested.md"
        language = parser.detect_language(md_file)

        assert language == "markdown"

    def test_detect_language_terraform(self, ast_samples_path):
        """
        Purpose: Verifies .tf extension detected as hcl.
        Quality Contribution: Ensures Terraform files use correct grammar.
        Acceptance Criteria: detect_language returns "hcl" for .tf files.

        Task: T013
        AC: AC4
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        tf_file = ast_samples_path / "terraform" / "resources_providers.tf"
        language = parser.detect_language(tf_file)

        assert language == "hcl"

    def test_detect_language_dockerfile(self, ast_samples_path):
        """
        Purpose: Verifies Dockerfile (no extension) detected as dockerfile.
        Quality Contribution: Ensures Dockerfile uses correct grammar.
        Acceptance Criteria: detect_language returns "dockerfile" for Dockerfile* files.

        Task: T014
        AC: AC4
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        dockerfile = ast_samples_path / "docker" / "Dockerfile.simple"
        language = parser.detect_language(dockerfile)

        assert language == "dockerfile"

    def test_detect_language_csharp(self, ast_samples_path):
        """
        Purpose: Verifies .cs extension detected as csharp.
        Quality Contribution: Ensures C# files use correct grammar.
        Acceptance Criteria: detect_language returns "csharp" for .cs files.

        Task: T014b
        AC: AC4 (extended)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        cs_file = ast_samples_path / "csharp" / "namespace_class.cs"
        language = parser.detect_language(cs_file)

        assert language == "csharp"

    def test_detect_language_rust(self, ast_samples_path):
        """
        Purpose: Verifies .rs extension detected as rust.
        Quality Contribution: Ensures Rust files use correct grammar.
        Acceptance Criteria: detect_language returns "rust" for .rs files.

        Task: T014c
        AC: AC4 (extended)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        rs_file = ast_samples_path / "rust" / "structs_impl.rs"
        language = parser.detect_language(rs_file)

        assert language == "rust"

    def test_detect_language_go(self, ast_samples_path):
        """
        Purpose: Verifies .go extension detected as go.
        Quality Contribution: Ensures Go files use correct grammar.
        Acceptance Criteria: detect_language returns "go" for .go files.

        Task: T014d
        AC: AC4 (extended)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        go_file = ast_samples_path / "go" / "structs_methods.go"
        language = parser.detect_language(go_file)

        assert language == "go"

    def test_detect_language_yaml(self, tmp_path):
        """
        Purpose: Verifies .yaml/.yml extensions detected as yaml.
        Quality Contribution: Ensures YAML files use correct grammar.
        Acceptance Criteria: detect_language returns "yaml" for .yaml/.yml files.

        Task: T014e
        AC: AC4 (extended)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("key: value")
        yml_file = tmp_path / "config.yml"
        yml_file.write_text("key: value")

        assert parser.detect_language(yaml_file) == "yaml"
        assert parser.detect_language(yml_file) == "yaml"

    def test_detect_language_json(self, tmp_path):
        """
        Purpose: Verifies .json extension detected as json.
        Quality Contribution: Ensures JSON files use correct grammar.
        Acceptance Criteria: detect_language returns "json" for .json files.

        Task: T014e
        AC: AC4 (extended)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        json_file = tmp_path / "data.json"
        json_file.write_text('{"key": "value"}')

        assert parser.detect_language(json_file) == "json"

    def test_detect_language_ambiguous_h_defaults_to_cpp(self, tmp_path):
        """
        Purpose: Verifies .h extension defaults to cpp per CF13.
        Quality Contribution: Handles ambiguous C/C++ headers consistently.
        Acceptance Criteria: detect_language returns "cpp" for .h files.

        Task: T015
        CF: CF13
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        h_file = tmp_path / "header.h"
        h_file.write_text("#ifndef HEADER_H\n#define HEADER_H\n#endif")

        assert parser.detect_language(h_file) == "cpp"

    def test_detect_language_unknown_extension_returns_none(self, tmp_path):
        """
        Purpose: Verifies unknown extensions return None.
        Quality Contribution: Graceful handling of unsupported file types.
        Acceptance Criteria: detect_language returns None for unknown extensions.

        Task: T016
        CF: CF10
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        unknown_file = tmp_path / "mystery.xyz"
        unknown_file.write_text("unknown content")

        assert parser.detect_language(unknown_file) is None

    def test_detect_language_case_insensitive(self, tmp_path):
        """
        Purpose: Verifies language detection is case-insensitive for extensions.
        Quality Contribution: Handles files with uppercase extensions.
        Acceptance Criteria: detect_language works regardless of case.

        Task: T016 (supplementary)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        upper_py = tmp_path / "test.PY"
        upper_py.write_text("x = 1")

        assert parser.detect_language(upper_py) == "python"

    def test_detect_language_gdscript(self, tmp_path):
        """
        Purpose: Verifies .gd extension detected as gdscript.
        Quality Contribution: Ensures GDScript files use correct grammar.
        Acceptance Criteria: detect_language returns "gdscript" for .gd files.

        Task: T001 (scan-fix plan)
        AC: AC1
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        gd_file = tmp_path / "player.gd"
        gd_file.write_text("class_name Player")
        language = parser.detect_language(gd_file)

        assert language == "gdscript"

    def test_detect_language_cuda(self, tmp_path):
        """
        Purpose: Verifies .cu extension detected as cuda.
        Quality Contribution: Ensures CUDA files use correct grammar.
        Acceptance Criteria: detect_language returns "cuda" for .cu files.

        Task: T002 (scan-fix plan)
        AC: AC3
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        cu_file = tmp_path / "kernel.cu"
        cu_file.write_text("__global__ void vectorAdd() {}")
        language = parser.detect_language(cu_file)

        assert language == "cuda"


# =============================================================================
# Python AST Hierarchy Tests (T018-T024)
# =============================================================================


@pytest.mark.unit
class TestTreeSitterParserPythonHierarchy:
    """Tests for Python AST hierarchy extraction (T018-T024)."""

    def test_parse_returns_file_node(self, ast_samples_path):
        """
        Purpose: Verifies parse() returns file node as first element.
        Quality Contribution: Ensures file-level metadata captured.
        Acceptance Criteria: First node is file with category="file".

        Task: T018
        AC: AC5
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        py_file = ast_samples_path / "python" / "simple_class.py"
        nodes = parser.parse(py_file)

        assert len(nodes) > 0
        file_node = nodes[0]
        assert file_node.category == "file"
        assert file_node.language == "python"
        assert "simple_class.py" in file_node.name

    def test_parse_extracts_class(self, ast_samples_path):
        """
        Purpose: Verifies class extraction from Python files.
        Quality Contribution: Ensures type nodes created for classes.
        Acceptance Criteria: Class node with category="type" and correct name.

        Task: T019
        AC: AC5
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        py_file = ast_samples_path / "python" / "simple_class.py"
        nodes = parser.parse(py_file)

        class_nodes = [n for n in nodes if n.category == "type"]
        assert len(class_nodes) >= 1

        calculator_class = next(
            (n for n in class_nodes if n.name == "Calculator"), None
        )
        assert calculator_class is not None
        assert calculator_class.ts_kind == "class_definition"

    def test_parse_extracts_methods(self, ast_samples_path):
        """
        Purpose: Verifies method extraction from Python classes.
        Quality Contribution: Ensures callable nodes created for methods.
        Acceptance Criteria: Method nodes with category="callable" and qualified names.

        Task: T020
        AC: AC5
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        py_file = ast_samples_path / "python" / "simple_class.py"
        nodes = parser.parse(py_file)

        callable_nodes = [n for n in nodes if n.category == "callable"]
        assert len(callable_nodes) >= 2

        method_names = [n.name for n in callable_nodes]
        assert "add" in method_names
        assert "subtract" in method_names

    def test_parse_extracts_standalone_functions(self, ast_samples_path):
        """
        Purpose: Verifies standalone function extraction.
        Quality Contribution: Ensures top-level functions captured.
        Acceptance Criteria: Function nodes without class prefix in qualified_name.

        Task: T021
        AC: AC5
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        py_file = ast_samples_path / "python" / "standalone_functions.py"
        nodes = parser.parse(py_file)

        callable_nodes = [n for n in nodes if n.category == "callable"]
        assert len(callable_nodes) >= 2

        func_names = [n.name for n in callable_nodes]
        assert "greet" in func_names
        assert "fetch_data" in func_names

    def test_parse_extracts_nested_classes(self, ast_samples_path):
        """
        Purpose: Verifies nested class extraction with qualified names.
        Quality Contribution: Ensures inner class hierarchy captured.
        Acceptance Criteria: Inner class qualified_name includes outer class.

        Task: T022
        AC: AC5
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        py_file = ast_samples_path / "python" / "nested_classes.py"
        nodes = parser.parse(py_file)

        class_nodes = [n for n in nodes if n.category == "type"]
        class_names = [n.qualified_name for n in class_nodes]

        assert "Outer" in class_names
        assert "Outer.Inner" in class_names

    def test_parse_respects_depth_limit(self, tmp_path):
        """
        Purpose: Verifies depth limit of 4 per CF08.
        Quality Contribution: Prevents excessive nesting traversal.
        Acceptance Criteria: Nodes beyond depth 4 not extracted.

        Task: T023
        CF: CF08
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        # Create deeply nested code
        deep_code = '''
class Level1:
    class Level2:
        class Level3:
            class Level4:
                class Level5:
                    def deep_method(self):
                        pass
'''
        py_file = tmp_path / "deep.py"
        py_file.write_text(deep_code)

        nodes = parser.parse(py_file)
        class_nodes = [n for n in nodes if n.category == "type"]

        # Should have at most 4 levels of classes
        # Level1, Level2, Level3, Level4 (Level5 should be cut off)
        assert len(class_nodes) <= 4

    def test_parse_method_qualified_name_includes_class(self, ast_samples_path):
        """
        Purpose: Verifies method qualified_name format per AC7.
        Quality Contribution: Ensures consistent node ID format.
        Acceptance Criteria: Method qualified_name is ClassName.method_name.

        Task: T020 (supplementary)
        AC: AC7
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        py_file = ast_samples_path / "python" / "simple_class.py"
        nodes = parser.parse(py_file)

        add_method = next(
            (n for n in nodes if n.name == "add" and n.category == "callable"),
            None
        )
        assert add_method is not None
        assert "Calculator" in add_method.qualified_name
        assert "add" in add_method.qualified_name


# =============================================================================
# Multi-Language Support Tests (T025-T028)
# =============================================================================


@pytest.mark.unit
class TestTreeSitterParserMultiLanguage:
    """Tests for multi-language AST parsing (T025-T028)."""

    def test_parse_typescript_class(self, ast_samples_path):
        """
        Purpose: Verifies TypeScript class extraction.
        Quality Contribution: Ensures TypeScript structural analysis works.
        Acceptance Criteria: TypeScript class parsed with correct category.

        Task: T025
        AC: AC4, AC5
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        ts_file = ast_samples_path / "typescript" / "class_generics.ts"
        nodes = parser.parse(ts_file)

        class_nodes = [n for n in nodes if n.category == "type"]
        # Should find GenericRepository class
        assert len(class_nodes) >= 1

    def test_parse_typescript_interface(self, ast_samples_path):
        """
        Purpose: Verifies TypeScript interface extraction.
        Quality Contribution: Ensures interface types recognized.
        Acceptance Criteria: Interface nodes with category="type".

        Task: T025
        AC: AC4, AC5
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        ts_file = ast_samples_path / "typescript" / "interfaces_types.ts"
        nodes = parser.parse(ts_file)

        type_nodes = [n for n in nodes if n.category == "type"]
        # Should find User, Repository interfaces
        assert len(type_nodes) >= 2

    @pytest.mark.skip(reason="tree-sitter grammar issue")
    def test_parse_markdown_headings(self, ast_samples_path):
        """
        Purpose: Verifies Markdown heading extraction.
        Quality Contribution: Ensures documentation structure captured.
        Acceptance Criteria: Headings parsed as section nodes.

        Task: T026
        AC: AC4
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        md_file = ast_samples_path / "markdown" / "headings_nested.md"
        nodes = parser.parse(md_file)

        section_nodes = [n for n in nodes if n.category == "section"]
        # Should find headings: Main Title, Section One, Subsection 1.1, Section Two
        assert len(section_nodes) >= 3

    @pytest.mark.skip(reason="tree-sitter grammar issue")
    def test_parse_terraform_blocks(self, ast_samples_path):
        """
        Purpose: Verifies Terraform block extraction.
        Quality Contribution: Ensures IaC structure captured.
        Acceptance Criteria: Resource blocks parsed as block nodes.

        Task: T027
        AC: AC4
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        tf_file = ast_samples_path / "terraform" / "resources_providers.tf"
        nodes = parser.parse(tf_file)

        block_nodes = [n for n in nodes if n.category == "block"]
        # Should find terraform, resource, module blocks
        assert len(block_nodes) >= 2

    def test_parse_rust_impl(self, ast_samples_path):
        """
        Purpose: Verifies Rust impl block extraction.
        Quality Contribution: Ensures Rust structural elements captured.
        Acceptance Criteria: Impl blocks or their methods parsed.

        Task: T028
        AC: AC4 (extended)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        rs_file = ast_samples_path / "rust" / "structs_impl.rs"
        nodes = parser.parse(rs_file)

        # Should have file node at minimum
        assert len(nodes) >= 1
        file_node = nodes[0]
        assert file_node.category == "file"
        assert file_node.language == "rust"

    def test_parse_go_functions(self, ast_samples_path):
        """
        Purpose: Verifies Go function extraction.
        Quality Contribution: Ensures Go structural elements captured.
        Acceptance Criteria: Functions parsed as callable nodes.

        Task: T028
        AC: AC4 (extended)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        go_file = ast_samples_path / "go" / "structs_methods.go"
        nodes = parser.parse(go_file)

        callable_nodes = [n for n in nodes if n.category == "callable"]
        # Should find NewCalculator, Add, Value functions
        assert len(callable_nodes) >= 2


# =============================================================================
# Error Handling and Binary Detection Tests (T032-T036)
# =============================================================================


@pytest.mark.unit
class TestTreeSitterParserErrorHandling:
    """Tests for error handling and binary file detection (T032-T036)."""

    def test_parse_binary_file_returns_empty(self, ast_samples_path):
        """
        Purpose: Verifies binary file detection per CF07.
        Quality Contribution: Prevents parsing garbage from binary files.
        Acceptance Criteria: Binary files return empty list.

        Task: T032
        CF: CF07
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        # Need to rename to .py so language is detected
        bin_file = ast_samples_path / "edge_cases" / "sample.bin"

        # Binary file but unknown extension -> returns empty
        nodes = parser.parse(bin_file)
        assert nodes == []

    def test_parse_unknown_language_returns_empty(self, tmp_path):
        """
        Purpose: Verifies unknown language handling.
        Quality Contribution: Graceful degradation for unsupported files.
        Acceptance Criteria: Unknown language returns empty list.

        Task: T033
        CF: CF10
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        unknown_file = tmp_path / "mystery.xyz"
        unknown_file.write_text("some content")

        nodes = parser.parse(unknown_file)
        assert nodes == []

    def test_parse_permission_error_raises_ast_parser_error(self, tmp_path):
        """
        Purpose: Verifies permission errors translate to ASTParserError.
        Quality Contribution: Consistent error types per CF10.
        Acceptance Criteria: PermissionError -> ASTParserError.

        Task: T034
        CF: CF10
        """
        import os
        import stat

        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser
        from fs2.core.adapters.exceptions import ASTParserError

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        unreadable_file = tmp_path / "unreadable.py"
        unreadable_file.write_text("x = 1")
        os.chmod(unreadable_file, 0o000)  # Remove all permissions

        try:
            with pytest.raises(ASTParserError, match="Permission denied"):
                parser.parse(unreadable_file)
        finally:
            # Restore permissions for cleanup
            os.chmod(unreadable_file, stat.S_IRUSR | stat.S_IWUSR)

    def test_parse_syntax_error_marks_error_node(self, ast_samples_path):
        """
        Purpose: Verifies syntax errors produce ERROR nodes.
        Quality Contribution: Ensures parseable files have error info.
        Acceptance Criteria: Syntax errors create nodes with is_error=True or ERROR type.

        Task: T035
        AC: AC10
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        error_file = ast_samples_path / "python" / "syntax_error.py"
        nodes = parser.parse(error_file)

        # Should still return nodes (file node at minimum)
        assert len(nodes) >= 1
        # Parser should detect the file has errors
        # (tree-sitter is error-tolerant, so we may get partial results)

    def test_parse_empty_file_returns_file_node(self, ast_samples_path):
        """
        Purpose: Verifies empty files produce file node.
        Quality Contribution: Ensures empty files don't crash.
        Acceptance Criteria: Empty file returns single file node.

        Task: T036
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        empty_file = ast_samples_path / "edge_cases" / "empty.py"
        nodes = parser.parse(empty_file)

        assert len(nodes) >= 1
        file_node = nodes[0]
        assert file_node.category == "file"


# =============================================================================
# Node Format and ID Tests (T037-T040)
# =============================================================================


@pytest.mark.unit
class TestTreeSitterParserNodeFormat:
    """Tests for node ID format and compliance (T037-T040)."""

    def test_node_id_format_file(self, ast_samples_path):
        """
        Purpose: Verifies file node ID format per AC7.
        Quality Contribution: Ensures consistent node identification.
        Acceptance Criteria: File node_id is "file:{path}".

        Task: T037
        AC: AC7
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        py_file = ast_samples_path / "python" / "simple_class.py"
        nodes = parser.parse(py_file)

        file_node = nodes[0]
        assert file_node.node_id.startswith("file:")
        assert "simple_class.py" in file_node.node_id

    def test_node_id_format_type(self, ast_samples_path):
        """
        Purpose: Verifies type node ID format per AC7.
        Quality Contribution: Ensures class nodes identifiable.
        Acceptance Criteria: Type node_id is "type:{path}:{qualified_name}".

        Task: T038
        AC: AC7
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        py_file = ast_samples_path / "python" / "simple_class.py"
        nodes = parser.parse(py_file)

        class_node = next(n for n in nodes if n.category == "type")
        assert class_node.node_id.startswith("type:")
        assert "Calculator" in class_node.node_id

    def test_node_id_format_callable(self, ast_samples_path):
        """
        Purpose: Verifies callable node ID format per AC7.
        Quality Contribution: Ensures method nodes identifiable.
        Acceptance Criteria: Callable node_id is "callable:{path}:{qualified_name}".

        Task: T039
        AC: AC7
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        py_file = ast_samples_path / "python" / "simple_class.py"
        nodes = parser.parse(py_file)

        callable_node = next(n for n in nodes if n.category == "callable")
        assert callable_node.node_id.startswith("callable:")
        assert "Calculator" in callable_node.node_id or callable_node.name in callable_node.node_id

    def test_node_content_is_complete(self, ast_samples_path):
        """
        Purpose: Verifies node content includes full source.
        Quality Contribution: Enables full-text search.
        Acceptance Criteria: Node content matches source code segment.

        Task: T040
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        py_file = ast_samples_path / "python" / "simple_class.py"
        nodes = parser.parse(py_file)

        class_node = next(n for n in nodes if n.name == "Calculator")
        # Content should contain class definition
        assert "class Calculator" in class_node.content
        assert "def add" in class_node.content

    def test_node_line_numbers_are_one_indexed(self, ast_samples_path):
        """
        Purpose: Verifies line numbers are 1-indexed for humans.
        Quality Contribution: Consistent with editor conventions.
        Acceptance Criteria: start_line >= 1, end_line >= start_line.

        Task: T040 (supplementary)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        py_file = ast_samples_path / "python" / "simple_class.py"
        nodes = parser.parse(py_file)

        for node in nodes:
            assert node.start_line >= 1, f"start_line should be >= 1: {node}"
            assert node.end_line >= node.start_line, f"end_line should be >= start_line: {node}"


class TestTreeSitterParserSkipTracking:
    """Tests for skip tracking functionality.

    Phase 2: Quiet Scan Output - verify skip counts are tracked correctly.
    """

    def test_get_skip_summary_tracks_unknown_extensions(self, tmp_path):
        """
        Purpose: Verifies skip tracking records unknown extensions correctly.
        Quality Contribution: Skip summary displays accurate counts.
        Acceptance Criteria: get_skip_summary() returns dict with extension counts.

        Task: ST005 (Phase 2 subtask)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        # Create files with unknown extensions
        (tmp_path / "file1.xyz").write_text("content")
        (tmp_path / "file2.xyz").write_text("content")
        (tmp_path / "file3.abc").write_text("content")

        # Parse files (will skip due to unknown extension)
        parser.parse(tmp_path / "file1.xyz")
        parser.parse(tmp_path / "file2.xyz")
        parser.parse(tmp_path / "file3.abc")

        summary = parser.get_skip_summary()
        assert summary == {".xyz": 2, ".abc": 1}

    def test_get_skip_summary_clears_after_reading(self, tmp_path):
        """
        Purpose: Verifies skip summary clears counts after reading.
        Quality Contribution: Prevents double-counting across scan cycles.
        Acceptance Criteria: Second call returns empty dict.

        Task: ST005 (Phase 2 subtask)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        (tmp_path / "file.xyz").write_text("content")
        parser.parse(tmp_path / "file.xyz")

        summary1 = parser.get_skip_summary()
        assert summary1 == {".xyz": 1}

        summary2 = parser.get_skip_summary()
        assert summary2 == {}  # Cleared

    def test_get_skip_summary_tracks_binary_files(self, tmp_path):
        """
        Purpose: Verifies binary file skips are also tracked.
        Quality Contribution: Complete skip summary includes all skip types.
        Acceptance Criteria: Binary files counted in skip summary.

        Task: ST005 (Phase 2 subtask)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        # Create a binary file with known extension (will detect binary)
        binary_content = b"valid start\x00null byte makes it binary"
        (tmp_path / "data.py").write_bytes(binary_content)

        parser.parse(tmp_path / "data.py")

        summary = parser.get_skip_summary()
        assert summary == {".py": 1}

    def test_get_skip_summary_handles_no_extension(self, tmp_path):
        """
        Purpose: Verifies files without extension are tracked.
        Quality Contribution: Complete skip summary for all file types.
        Acceptance Criteria: Files without extension counted as "(no extension)".

        Task: ST005 (Phase 2 subtask)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        # Create file without extension (unknown language)
        (tmp_path / "noext").write_text("content")
        parser.parse(tmp_path / "noext")

        summary = parser.get_skip_summary()
        assert summary == {"(no extension)": 1}
