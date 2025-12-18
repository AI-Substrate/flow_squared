"""Tests for CodeNode frozen dataclass and classify_node function.

Tests verify:
- CodeNode immutability (frozen dataclass)
- Dual classification (ts_kind + category)
- Node ID format for named and anonymous nodes
- Position fields (byte offsets + line/column)
- Content and signature fields
- Naming fields (name, qualified_name)
- Metadata fields (language, is_named, field_name)
- Error flag (is_error)
- Truncation fields
- Placeholder fields for future features
- Factory methods for different node categories
- classify_node() pattern matching

Per Critical Findings: 09 (frozen dataclass), 11 (node ID), 12 (truncation)
Per Alignment Brief: Dual classification, language-agnostic patterns
"""

from dataclasses import FrozenInstanceError

import pytest

from fs2.core.utils.hash import compute_content_hash

@pytest.mark.unit
class TestCodeNodeStructure:
    """Tests for CodeNode dataclass structure and immutability (T003-T011, T013)."""

    def test_code_node_is_frozen_dataclass(self):
        """
        Purpose: Proves CodeNode immutability per Constitution P5.
        Quality Contribution: Prevents accidental mutation across async contexts.
        Acceptance Criteria: Mutation raises FrozenInstanceError/AttributeError.

        Task: T003
        """
        from fs2.core.models.code_node import CodeNode

        node = CodeNode(
            node_id="callable:src/calc.py:Calculator.add",
            category="callable",
            ts_kind="function_definition",
            name="add",
            qualified_name="Calculator.add",
            start_line=10,
            end_line=15,
            start_column=4,
            end_column=20,
            start_byte=200,
            end_byte=350,
            content="def add(self, a, b):\n    return a + b",
            content_hash=compute_content_hash(
                "def add(self, a, b):\n    return a + b"
            ),
            signature="def add(self, a, b):",
            language="python",
            is_named=True,
            field_name="body",
        )

        with pytest.raises((FrozenInstanceError, AttributeError)):
            node.name = "changed"

    def test_code_node_has_dual_classification(self):
        """
        Purpose: Verifies both ts_kind (grammar-specific) and category (universal) stored.
        Quality Contribution: Enables language-agnostic queries while preserving grammar detail.
        Acceptance Criteria: Both fields accessible with different values.

        Task: T004
        """
        from fs2.core.models.code_node import CodeNode

        node = CodeNode(
            node_id="type:src/models.py:User",
            category="type",
            ts_kind="class_definition",
            name="User",
            qualified_name="User",
            start_line=1,
            end_line=20,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=400,
            content="class User:\n    pass",
            content_hash=compute_content_hash("class User:\n    pass"),
            signature="class User:",
            language="python",
            is_named=True,
            field_name=None,
        )

        assert node.category == "type"
        assert node.ts_kind == "class_definition"
        assert node.category != node.ts_kind

    def test_code_node_node_id_format_named(self):
        """
        Purpose: Verifies node_id format for named nodes: {category}:{path}:{qualified_name}.
        Quality Contribution: Ensures consistent ID scheme for graph queries.
        Acceptance Criteria: ID follows format specification.

        Task: T005 (named nodes)
        """
        from fs2.core.models.code_node import CodeNode

        node = CodeNode(
            node_id="callable:src/calc.py:Calculator.add",
            category="callable",
            ts_kind="function_definition",
            name="add",
            qualified_name="Calculator.add",
            start_line=10,
            end_line=15,
            start_column=4,
            end_column=20,
            start_byte=200,
            end_byte=350,
            content="def add(self, a, b): return a + b",
            content_hash=compute_content_hash("def add(self, a, b): return a + b"),
            signature="def add(self, a, b):",
            language="python",
            is_named=True,
            field_name=None,
        )

        assert node.node_id == "callable:src/calc.py:Calculator.add"
        # Verify format: {category}:{path}:{qualified_name}
        parts = node.node_id.split(":")
        assert len(parts) == 3
        assert parts[0] == node.category
        assert parts[1] == "src/calc.py"
        assert parts[2] == node.qualified_name

    def test_code_node_node_id_format_anonymous(self):
        """
        Purpose: Verifies node_id format for anonymous nodes: {category}:{path}:{name}@{line}.
        Quality Contribution: Ensures idempotent IDs without counter state.
        Acceptance Criteria: ID uses @line suffix for anonymous nodes.

        Task: T005 (anonymous nodes)
        """
        from fs2.core.models.code_node import CodeNode

        node = CodeNode(
            node_id="expression:main.py:lambda@42",
            category="expression",
            ts_kind="lambda",
            name=None,
            qualified_name="lambda@42",
            start_line=42,
            end_line=42,
            start_column=10,
            end_column=30,
            start_byte=800,
            end_byte=820,
            content="lambda x: x + 1",
            content_hash=compute_content_hash("lambda x: x + 1"),
            signature="lambda x: x + 1",
            language="python",
            is_named=True,
            field_name=None,
        )

        assert node.node_id == "expression:main.py:lambda@42"
        assert "@42" in node.node_id
        assert node.name is None

    def test_code_node_has_byte_and_line_positions(self):
        """
        Purpose: Verifies both byte offsets (for slicing) and line/col (for UI) available.
        Quality Contribution: Supports both programmatic access and human display.
        Acceptance Criteria: All 6 position fields set and accessible.

        Task: T006
        """
        from fs2.core.models.code_node import CodeNode

        node = CodeNode(
            node_id="callable:src/main.py:process",
            category="callable",
            ts_kind="function_definition",
            name="process",
            qualified_name="process",
            start_line=42,
            end_line=50,
            start_column=0,
            end_column=15,
            start_byte=1200,
            end_byte=1500,
            content="def process(): ...",
            content_hash=compute_content_hash("def process(): ..."),
            signature="def process():",
            language="python",
            is_named=True,
            field_name=None,
        )

        # Line positions (1-indexed for humans)
        assert node.start_line == 42
        assert node.end_line == 50
        assert node.start_column == 0
        assert node.end_column == 15

        # Byte positions (0-indexed for slicing)
        assert node.start_byte == 1200
        assert node.end_byte == 1500

    def test_code_node_content_and_signature(self):
        """
        Purpose: Verifies content (full source) and signature (first line) fields.
        Quality Contribution: Enables embeddings from content, quick display from signature.
        Acceptance Criteria: Content has full source, signature has declaration line.

        Task: T007
        """
        from fs2.core.models.code_node import CodeNode

        full_content = """def calculate(x, y):
    result = x + y
    return result"""

        node = CodeNode(
            node_id="callable:src/math.py:calculate",
            category="callable",
            ts_kind="function_definition",
            name="calculate",
            qualified_name="calculate",
            start_line=1,
            end_line=3,
            start_column=0,
            end_column=17,
            start_byte=0,
            end_byte=len(full_content),
            content=full_content,
            content_hash=compute_content_hash(full_content),
            signature="def calculate(x, y):",
            language="python",
            is_named=True,
            field_name=None,
        )

        assert node.content == full_content
        assert node.signature == "def calculate(x, y):"
        assert node.signature in node.content

    def test_code_node_name_and_qualified_name(self):
        """
        Purpose: Verifies name (simple) and qualified_name (hierarchical) fields.
        Quality Contribution: Enables both display name and unique identification.
        Acceptance Criteria: name="add", qualified_name="Calculator.add".

        Task: T008
        """
        from fs2.core.models.code_node import CodeNode

        node = CodeNode(
            node_id="callable:src/calc.py:Calculator.add",
            category="callable",
            ts_kind="method_definition",
            name="add",
            qualified_name="Calculator.add",
            start_line=5,
            end_line=7,
            start_column=4,
            end_column=20,
            start_byte=100,
            end_byte=200,
            content="def add(self, a, b): return a + b",
            content_hash=compute_content_hash("def add(self, a, b): return a + b"),
            signature="def add(self, a, b):",
            language="python",
            is_named=True,
            field_name="body",
        )

        assert node.name == "add"
        assert node.qualified_name == "Calculator.add"
        assert node.name in node.qualified_name

    def test_code_node_metadata_fields(self):
        """
        Purpose: Verifies metadata fields: language, is_named, field_name.
        Quality Contribution: Preserves tree-sitter context for downstream processing.
        Acceptance Criteria: All metadata fields accessible.

        Task: T009
        """
        from fs2.core.models.code_node import CodeNode

        node = CodeNode(
            node_id="callable:src/app.py:main",
            category="callable",
            ts_kind="function_definition",
            name="main",
            qualified_name="main",
            start_line=1,
            end_line=5,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=100,
            content="def main(): pass",
            content_hash=compute_content_hash("def main(): pass"),
            signature="def main():",
            language="python",
            is_named=True,
            field_name="body",
        )

        assert node.language == "python"
        assert node.is_named is True
        assert node.field_name == "body"

    def test_code_node_is_error_flag(self):
        """
        Purpose: Verifies is_error flag for ERROR nodes (unparseable chunks).
        Quality Contribution: Enables error-tolerant parsing results.
        Acceptance Criteria: is_error defaults to False, can be set True.

        Task: T010
        """
        from fs2.core.models.code_node import CodeNode

        # Normal node - is_error defaults to False
        normal_node = CodeNode(
            node_id="callable:src/good.py:func",
            category="callable",
            ts_kind="function_definition",
            name="func",
            qualified_name="func",
            start_line=1,
            end_line=2,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=50,
            content="def func(): pass",
            content_hash=compute_content_hash("def func(): pass"),
            signature="def func():",
            language="python",
            is_named=True,
            field_name=None,
        )
        assert normal_node.is_error is False

        # Error node
        error_node = CodeNode(
            node_id="other:src/bad.py:ERROR@5",
            category="other",
            ts_kind="ERROR",
            name=None,
            qualified_name="ERROR@5",
            start_line=5,
            end_line=5,
            start_column=0,
            end_column=10,
            start_byte=100,
            end_byte=110,
            content="def broken(",
            content_hash=compute_content_hash("def broken("),
            signature="def broken(",
            language="python",
            is_named=False,
            field_name=None,
            is_error=True,
        )
        assert error_node.is_error is True

    def test_code_node_truncation_fields(self):
        """
        Purpose: Verifies truncation fields for large file handling.
        Quality Contribution: Enables sampling of large files per AC6.
        Acceptance Criteria: truncated and truncated_at_line fields accessible.

        Task: T011
        """
        from fs2.core.models.code_node import CodeNode

        # Normal node - not truncated
        normal_node = CodeNode(
            node_id="file:src/small.py",
            category="file",
            ts_kind="module",
            name="small.py",
            qualified_name="small.py",
            start_line=1,
            end_line=100,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=5000,
            content="# small file content",
            content_hash=compute_content_hash("# small file content"),
            signature=None,
            language="python",
            is_named=True,
            field_name=None,
        )
        assert normal_node.truncated is False
        assert normal_node.truncated_at_line is None

        # Truncated node
        truncated_node = CodeNode(
            node_id="file:src/large.py",
            category="file",
            ts_kind="module",
            name="large.py",
            qualified_name="large.py",
            start_line=1,
            end_line=10000,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=1000000,
            content="# first 1000 lines only...",
            content_hash=compute_content_hash("# first 1000 lines only..."),
            signature=None,
            language="python",
            is_named=True,
            field_name=None,
            truncated=True,
            truncated_at_line=1000,
        )
        assert truncated_node.truncated is True
        assert truncated_node.truncated_at_line == 1000

    def test_code_node_placeholder_fields(self):
        """
        Purpose: Verifies placeholder fields for future features.
        Quality Contribution: Future-proofs schema for AI summaries and embeddings.
        Acceptance Criteria: smart_content and embedding default to None.

        Task: T013
        """
        from fs2.core.models.code_node import CodeNode

        node = CodeNode(
            node_id="callable:src/app.py:main",
            category="callable",
            ts_kind="function_definition",
            name="main",
            qualified_name="main",
            start_line=1,
            end_line=5,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=100,
            content="def main(): pass",
            content_hash=compute_content_hash("def main(): pass"),
            signature="def main():",
            language="python",
            is_named=True,
            field_name=None,
        )

        assert node.smart_content is None
        assert node.embedding is None

        # Can also be explicitly set
        node_with_extras = CodeNode(
            node_id="callable:src/app.py:main",
            category="callable",
            ts_kind="function_definition",
            name="main",
            qualified_name="main",
            start_line=1,
            end_line=5,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=100,
            content="def main(): pass",
            content_hash=compute_content_hash("def main(): pass"),
            signature="def main():",
            language="python",
            is_named=True,
            field_name=None,
            smart_content="Entry point for the application",
            embedding=[0.1, 0.2, 0.3],
        )

        assert node_with_extras.smart_content == "Entry point for the application"
        assert node_with_extras.embedding == [0.1, 0.2, 0.3]


@pytest.mark.unit
class TestCodeNodeFactories:
    """Tests for CodeNode factory methods (T014-T018)."""

    def test_create_file_sets_category_and_node_id(self):
        """
        Purpose: Verifies create_file() sets category="file" and formats node_id.
        Quality Contribution: Encapsulates ID formatting logic in factory.
        Acceptance Criteria: node_id = "file:{path}", category = "file".

        Task: T014
        """
        from fs2.core.models.code_node import CodeNode

        node = CodeNode.create_file(
            file_path="src/main.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=1000,
            start_line=1,
            end_line=50,
            content="# Main module\nimport os\n...",
        )

        assert node.category == "file"
        assert node.node_id == "file:src/main.py"

    def test_create_file_when_called_then_populates_content_hash(self):
        """
        Purpose: Proves CodeNode factories compute content_hash from content.
        Quality Contribution: Enables hash-based regeneration without mutating frozen nodes.
        Acceptance Criteria: content_hash equals SHA-256 hexdigest of content.

        Task: T008
        """
        from fs2.core.models.code_node import CodeNode
        from fs2.core.utils.hash import compute_content_hash

        content = "# Main module\nimport os\n..."

        node = CodeNode.create_file(
            file_path="src/main.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=len(content),
            start_line=1,
            end_line=3,
            content=content,
        )

        assert node.content_hash == compute_content_hash(content)
        assert node.ts_kind == "module"
        assert node.language == "python"
        assert node.name == "main.py"
        assert node.qualified_name == "main.py"

    def test_create_type_for_class_struct_interface(self):
        """
        Purpose: Verifies create_type() handles classes, structs, interfaces.
        Quality Contribution: Universal type creation regardless of ts_kind.
        Acceptance Criteria: category = "type", node_id formatted correctly.

        Task: T015
        """
        from fs2.core.models.code_node import CodeNode

        node = CodeNode.create_type(
            file_path="src/models.py",
            language="python",
            ts_kind="class_definition",
            name="User",
            qualified_name="User",
            start_line=1,
            end_line=20,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=500,
            content="class User:\n    pass",
            signature="class User:",
        )

        assert node.category == "type"
        assert node.node_id == "type:src/models.py:User"
        assert node.ts_kind == "class_definition"
        assert node.name == "User"

    def test_create_callable_for_function_method(self):
        """
        Purpose: Verifies create_callable() handles functions, methods, lambdas.
        Quality Contribution: Universal callable creation regardless of ts_kind.
        Acceptance Criteria: category = "callable", node_id formatted correctly.

        Task: T016
        """
        from fs2.core.models.code_node import CodeNode

        node = CodeNode.create_callable(
            file_path="src/utils.py",
            language="python",
            ts_kind="function_definition",
            name="helper",
            qualified_name="helper",
            start_line=10,
            end_line=15,
            start_column=0,
            end_column=0,
            start_byte=200,
            end_byte=350,
            content="def helper(): pass",
            signature="def helper():",
        )

        assert node.category == "callable"
        assert node.node_id == "callable:src/utils.py:helper"

    def test_create_section_for_markdown_heading(self):
        """
        Purpose: Verifies create_section() handles markdown headings.
        Quality Contribution: Supports markup documentation parsing.
        Acceptance Criteria: category = "section" for heading nodes.

        Task: T017
        """
        from fs2.core.models.code_node import CodeNode

        node = CodeNode.create_section(
            file_path="docs/README.md",
            language="markdown",
            ts_kind="atx_heading",
            name="Installation",
            qualified_name="Installation",
            start_line=5,
            end_line=5,
            start_column=0,
            end_column=15,
            start_byte=50,
            end_byte=65,
            content="## Installation",
            signature="## Installation",
        )

        assert node.category == "section"
        assert node.node_id == "section:docs/README.md:Installation"

    def test_create_block_for_terraform_dockerfile(self):
        """
        Purpose: Verifies create_block() handles IaC blocks.
        Quality Contribution: Supports Terraform, Dockerfile parsing.
        Acceptance Criteria: category = "block" for block nodes.

        Task: T018
        """
        from fs2.core.models.code_node import CodeNode

        node = CodeNode.create_block(
            file_path="infra/main.tf",
            language="hcl",
            ts_kind="block",
            name="aws_instance.web",
            qualified_name="aws_instance.web",
            start_line=1,
            end_line=10,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=200,
            content='resource "aws_instance" "web" { }',
            signature='resource "aws_instance" "web" {',
        )

        assert node.category == "block"
        assert node.node_id == "block:infra/main.tf:aws_instance.web"


@pytest.mark.unit
class TestClassifyNode:
    """Tests for classify_node() pattern matching function (T019)."""

    def test_classify_root_containers(self):
        """
        Purpose: Verifies root container types map to "file" category.
        Quality Contribution: Consistent file-level classification across languages.

        Task: T019
        """
        from fs2.core.models.code_node import classify_node

        assert classify_node("module") == "file"
        assert classify_node("program") == "file"
        assert classify_node("source_file") == "file"
        assert classify_node("document") == "file"
        assert classify_node("compilation_unit") == "file"
        assert classify_node("translation_unit") == "file"
        assert classify_node("config_file") == "file"
        assert classify_node("stream") == "file"

    def test_classify_callables(self):
        """
        Purpose: Verifies function/method types map to "callable" category.
        Quality Contribution: Language-agnostic callable queries.

        Task: T019
        """
        from fs2.core.models.code_node import classify_node

        assert classify_node("function_definition") == "callable"
        assert classify_node("function_declaration") == "callable"
        assert classify_node("method_definition") == "callable"
        assert classify_node("method_declaration") == "callable"
        assert classify_node("lambda") == "callable"
        assert classify_node("arrow_function") == "callable"
        assert classify_node("procedure_declaration") == "callable"

    def test_classify_types(self):
        """
        Purpose: Verifies class/struct/interface types map to "type" category.
        Quality Contribution: Language-agnostic type queries.

        Task: T019
        """
        from fs2.core.models.code_node import classify_node

        assert classify_node("class_definition") == "type"
        assert classify_node("class_declaration") == "type"
        assert classify_node("struct_item") == "type"
        assert classify_node("interface_declaration") == "type"
        assert classify_node("enum_declaration") == "type"
        assert classify_node("type_alias_declaration") == "type"

    def test_classify_sections(self):
        """
        Purpose: Verifies heading types map to "section" category.
        Quality Contribution: Markup document structure support.

        Task: T019
        """
        from fs2.core.models.code_node import classify_node

        assert classify_node("atx_heading") == "section"
        assert classify_node("setext_heading") == "section"

    def test_classify_statements(self):
        """
        Purpose: Verifies statement types map to "statement" category.
        Quality Contribution: Statement-level granularity when needed.

        Task: T019
        """
        from fs2.core.models.code_node import classify_node

        assert classify_node("if_statement") == "statement"
        assert classify_node("for_statement") == "statement"
        assert classify_node("return_statement") == "statement"
        assert classify_node("import_statement") == "statement"

    def test_classify_expressions(self):
        """
        Purpose: Verifies expression types map to "expression" category.
        Quality Contribution: Expression-level granularity when needed.

        Task: T019
        """
        from fs2.core.models.code_node import classify_node

        assert classify_node("call_expression") == "expression"
        assert classify_node("binary_expression") == "expression"
        assert classify_node("assignment_expression") == "expression"

    def test_classify_blocks(self):
        """
        Purpose: Verifies block/instruction types map to "block" category.
        Quality Contribution: IaC (Terraform, Dockerfile) support.

        Task: T019
        """
        from fs2.core.models.code_node import classify_node

        assert classify_node("block") == "block"
        assert classify_node("FROM_instruction") == "block"
        assert classify_node("RUN_instruction") == "block"
        assert classify_node("if_block") == "block"

    def test_classify_definitions(self):
        """
        Purpose: Verifies definition types map to "definition" category.
        Quality Contribution: General definition support.

        Task: T019
        """
        from fs2.core.models.code_node import classify_node

        assert classify_node("variable_definition") == "definition"
        assert classify_node("constant_declaration") == "definition"
        assert classify_node("field_declaration") == "definition"
        assert classify_node("type_specifier") == "definition"

    def test_classify_fallback_to_other(self):
        """
        Purpose: Verifies unknown types return "other" category.
        Quality Contribution: Graceful handling of unrecognized node types.

        Task: T019
        """
        from fs2.core.models.code_node import classify_node

        assert classify_node("unknown_thing") == "other"
        assert classify_node("xyz123") == "other"
        assert classify_node("comment") == "other"
        assert classify_node("string") == "other"
