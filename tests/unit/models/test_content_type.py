"""Tests for ContentType enum.

Phase 3: T012 - ContentType enum unit tests.
Purpose: Verify ContentType enum and its integration with CodeNode/Parser.
"""

import pytest


@pytest.mark.unit
class TestContentTypeEnum:
    """Tests for ContentType enum values and behavior."""

    def test_content_type_has_code_value(self):
        """
        Purpose: Verify CODE enum member exists with correct value.
        Quality Contribution: Ensures embedding service can identify code.
        Acceptance Criteria: ContentType.CODE.value == "code"
        """
        from fs2.core.models.content_type import ContentType

        assert ContentType.CODE.value == "code"

    def test_content_type_has_content_value(self):
        """
        Purpose: Verify CONTENT enum member exists with correct value.
        Quality Contribution: Ensures embedding service can identify non-code.
        Acceptance Criteria: ContentType.CONTENT.value == "content"
        """
        from fs2.core.models.content_type import ContentType

        assert ContentType.CONTENT.value == "content"

    def test_content_type_is_str_enum(self):
        """
        Purpose: Verify ContentType is a string enum for serialization.
        Quality Contribution: Ensures JSON/pickle compatibility.
        Acceptance Criteria: str(ContentType.CODE) == "code"
        """
        from fs2.core.models.content_type import ContentType

        assert str(ContentType.CODE) == "code"
        assert str(ContentType.CONTENT) == "content"

    def test_content_type_equality_with_string(self):
        """
        Purpose: Verify ContentType can be compared with strings.
        Quality Contribution: Enables flexible usage in conditionals.
        Acceptance Criteria: ContentType.CODE == "code"
        """
        from fs2.core.models.content_type import ContentType

        assert ContentType.CODE == "code"
        assert ContentType.CONTENT == "content"


@pytest.mark.unit
class TestCodeNodeContentTypeField:
    """Tests for content_type field on CodeNode."""

    def test_code_node_has_content_type_field(self):
        """
        Purpose: Verify CodeNode dataclass includes content_type.
        Quality Contribution: Ensures explicit classification at scan time.
        Acceptance Criteria: CodeNode has content_type attribute.
        """
        from fs2.core.models.code_node import CodeNode

        assert hasattr(CodeNode, "__dataclass_fields__")
        assert "content_type" in CodeNode.__dataclass_fields__

    def test_code_node_content_type_defaults_to_code(self):
        """
        Purpose: Verify content_type defaults to CODE for backwards compat.
        Quality Contribution: Existing tests work without modification.
        Acceptance Criteria: New CodeNode without content_type gets CODE.
        """
        from fs2.core.models.code_node import CodeNode
        from fs2.core.models.content_type import ContentType
        from fs2.core.utils.hash import compute_content_hash

        node = CodeNode(
            node_id="test:node",
            category="callable",
            ts_kind="function_definition",
            name="test",
            qualified_name="test",
            start_line=1,
            end_line=1,
            start_column=0,
            end_column=10,
            start_byte=0,
            end_byte=10,
            content="def test(): pass",
            content_hash=compute_content_hash("def test(): pass"),
            signature="def test():",
            language="python",
            is_named=True,
            field_name=None,
        )

        assert node.content_type == ContentType.CODE


@pytest.mark.unit
class TestCodeNodeFactoryContentType:
    """Tests for content_type in CodeNode factory methods."""

    def test_create_file_defaults_to_code(self):
        """
        Purpose: Verify create_file() defaults content_type to CODE.
        Quality Contribution: Backwards compatibility for existing tests.
        Acceptance Criteria: create_file() without content_type gets CODE.
        """
        from fs2.core.models.code_node import CodeNode
        from fs2.core.models.content_type import ContentType

        node = CodeNode.create_file(
            file_path="test.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# test",
        )

        assert node.content_type == ContentType.CODE

    def test_create_file_accepts_explicit_content_type(self):
        """
        Purpose: Verify create_file() accepts explicit content_type.
        Quality Contribution: Parser can set correct type at scan time.
        Acceptance Criteria: create_file(content_type=CONTENT) uses CONTENT.
        """
        from fs2.core.models.code_node import CodeNode
        from fs2.core.models.content_type import ContentType

        node = CodeNode.create_file(
            file_path="README.md",
            language="markdown",
            ts_kind="document",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# README",
            content_type=ContentType.CONTENT,
        )

        assert node.content_type == ContentType.CONTENT

    def test_create_callable_defaults_to_code(self):
        """
        Purpose: Verify create_callable() defaults content_type to CODE.
        Quality Contribution: Functions/methods are always code.
        Acceptance Criteria: create_callable() without content_type gets CODE.
        """
        from fs2.core.models.code_node import CodeNode
        from fs2.core.models.content_type import ContentType

        node = CodeNode.create_callable(
            file_path="test.py",
            language="python",
            ts_kind="function_definition",
            name="my_func",
            qualified_name="my_func",
            start_line=1,
            end_line=2,
            start_column=0,
            end_column=20,
            start_byte=0,
            end_byte=30,
            content="def my_func(): pass",
            signature="def my_func():",
        )

        assert node.content_type == ContentType.CODE

    def test_create_section_defaults_to_content(self):
        """
        Purpose: Verify create_section() defaults content_type to CONTENT.
        Quality Contribution: Markdown sections are documentation, not code.
        Acceptance Criteria: create_section() without content_type gets CONTENT.
        """
        from fs2.core.models.code_node import CodeNode
        from fs2.core.models.content_type import ContentType

        node = CodeNode.create_section(
            file_path="README.md",
            language="markdown",
            ts_kind="atx_heading",
            name="Introduction",
            qualified_name="Introduction",
            start_line=1,
            end_line=5,
            start_column=0,
            end_column=20,
            start_byte=0,
            end_byte=100,
            content="# Introduction\n\nThis is a test.",
            signature="# Introduction",
        )

        assert node.content_type == ContentType.CONTENT

    def test_create_block_defaults_to_content(self):
        """
        Purpose: Verify create_block() defaults content_type to CONTENT.
        Quality Contribution: Infrastructure blocks are not executable code.
        Acceptance Criteria: create_block() without content_type gets CONTENT.
        """
        from fs2.core.models.code_node import CodeNode
        from fs2.core.models.content_type import ContentType

        node = CodeNode.create_block(
            file_path="main.tf",
            language="hcl",
            ts_kind="block",
            name="resource.aws_instance.web",
            qualified_name="resource.aws_instance.web",
            start_line=1,
            end_line=5,
            start_column=0,
            end_column=1,
            start_byte=0,
            end_byte=100,
            content='resource "aws_instance" "web" {}',
            signature='resource "aws_instance" "web" {',
        )

        assert node.content_type == ContentType.CONTENT


@pytest.mark.unit
class TestTreeSitterParserContentType:
    """Tests for content_type set by TreeSitterParser at scan time."""

    @pytest.fixture
    def parser(self):
        """Create a TreeSitterParser instance."""
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        return TreeSitterParser(config)

    def test_python_file_gets_code_content_type(self, parser, tmp_path):
        """
        Purpose: Verify Python files are classified as CODE.
        Quality Contribution: Code languages get CODE type for embedding.
        Acceptance Criteria: Python file node has content_type=CODE.
        """
        from fs2.core.models.content_type import ContentType

        py_file = tmp_path / "test.py"
        py_file.write_text("def hello(): pass")

        nodes = parser.parse(py_file)

        assert len(nodes) >= 1
        assert nodes[0].content_type == ContentType.CODE

    def test_markdown_file_gets_content_content_type(self, parser, tmp_path):
        """
        Purpose: Verify Markdown files are classified as CONTENT.
        Quality Contribution: Docs get CONTENT type for embedding strategy.
        Acceptance Criteria: Markdown file node has content_type=CONTENT.
        """
        from fs2.core.models.content_type import ContentType

        md_file = tmp_path / "README.md"
        md_file.write_text("# Hello\n\nWorld")

        nodes = parser.parse(md_file)

        assert len(nodes) >= 1
        assert nodes[0].content_type == ContentType.CONTENT

    def test_yaml_file_gets_content_content_type(self, parser, tmp_path):
        """
        Purpose: Verify YAML config files are classified as CONTENT.
        Quality Contribution: Config files get CONTENT type.
        Acceptance Criteria: YAML file node has content_type=CONTENT.
        """
        from fs2.core.models.content_type import ContentType

        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("key: value")

        nodes = parser.parse(yaml_file)

        assert len(nodes) >= 1
        assert nodes[0].content_type == ContentType.CONTENT

    def test_javascript_file_gets_code_content_type(self, parser, tmp_path):
        """
        Purpose: Verify JavaScript files are classified as CODE.
        Quality Contribution: All programming languages get CODE type.
        Acceptance Criteria: JavaScript file node has content_type=CODE.
        """
        from fs2.core.models.content_type import ContentType

        js_file = tmp_path / "app.js"
        js_file.write_text("function hello() { return 42; }")

        nodes = parser.parse(js_file)

        assert len(nodes) >= 1
        assert nodes[0].content_type == ContentType.CODE

    def test_child_nodes_inherit_content_type(self, parser, tmp_path):
        """
        Purpose: Verify child nodes (functions) inherit parent content_type.
        Quality Contribution: Consistent classification throughout tree.
        Acceptance Criteria: Function nodes in Python file have CODE type.
        """
        from fs2.core.models.content_type import ContentType

        py_file = tmp_path / "module.py"
        py_file.write_text("def foo():\n    pass\n\ndef bar():\n    pass")

        nodes = parser.parse(py_file)
        callable_nodes = [n for n in nodes if n.category == "callable"]

        assert len(callable_nodes) >= 2
        for node in callable_nodes:
            assert node.content_type == ContentType.CODE
