"""Tests for SKIP_WHEN_ANONYMOUS behavior in TreeSitterParser.

Purpose: Verify that anonymous nodes for specific tree-sitter kinds
(arrow_function, interface_body, class_body, etc.) are skipped during
extraction while still recursing into their children to find named nodes.

Quality Contribution: Prevents regression of anonymous @line.column node
proliferation that wastes storage, LLM calls, and embedding API calls.

Task: T002 (030-better-node-parsing)
AC: AC1, AC2, AC3, AC4, AC7, AC8
"""

import re

import pytest


@pytest.mark.unit
class TestSkipWhenAnonymousCallbacks:
    """Tests for anonymous arrow_function/function_expression skipping."""

    def test_anonymous_arrow_function_callbacks_skipped(self, ast_samples_path):
        """
        Purpose: Anonymous arrow function callbacks should NOT produce @line.col nodes.
        AC: AC1
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        ts_file = ast_samples_path / "typescript" / "anonymous_callbacks.ts"
        nodes = parser.parse(ts_file)

        at_pat = re.compile(r"@\d+")
        anon_arrow = [
            n
            for n in nodes
            if n.ts_kind == "arrow_function" and n.name and at_pat.search(n.name)
        ]
        assert (
            len(anon_arrow) == 0
        ), f"Expected 0 anonymous arrow_function nodes, got {len(anon_arrow)}: {[n.name for n in anon_arrow]}"

    def test_anonymous_function_expression_skipped(self, ast_samples_path):
        """
        Purpose: Anonymous function expressions should NOT produce @line.col nodes.
        AC: AC1
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        ts_file = ast_samples_path / "typescript" / "anonymous_callbacks.ts"
        nodes = parser.parse(ts_file)

        at_pat = re.compile(r"@\d+")
        anon_fn_expr = [
            n
            for n in nodes
            if n.ts_kind == "function_expression"
            and n.name
            and at_pat.search(n.name)
        ]
        assert (
            len(anon_fn_expr) == 0
        ), f"Expected 0 anonymous function_expression nodes, got {len(anon_fn_expr)}"

    def test_named_function_inside_anonymous_callback_extracted(self, ast_samples_path):
        """
        Purpose: Named functions nested inside anonymous callbacks must still be extracted.
        Verifies recursion into skipped nodes works correctly.
        AC: AC3
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        ts_file = ast_samples_path / "typescript" / "anonymous_callbacks.ts"
        nodes = parser.parse(ts_file)

        # helperInsideCallback is a named function_declaration inside an anonymous describe() callback
        helper_nodes = [n for n in nodes if n.name == "helperInsideCallback"]
        assert (
            len(helper_nodes) == 1
        ), f"Expected helperInsideCallback to be extracted, got {len(helper_nodes)}"
        assert helper_nodes[0].category == "callable"
        assert helper_nodes[0].ts_kind == "function_declaration"

    def test_top_level_named_function_still_extracted(self, ast_samples_path):
        """
        Purpose: Named top-level functions must still be extracted normally.
        AC: AC1 (no regression on named extraction)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        ts_file = ast_samples_path / "typescript" / "anonymous_callbacks.ts"
        nodes = parser.parse(ts_file)

        top_level = [n for n in nodes if n.name == "topLevelFunction"]
        assert len(top_level) == 1
        assert top_level[0].category == "callable"
        assert top_level[0].ts_kind == "function_declaration"

    def test_no_anonymous_nodes_in_callbacks_fixture(self, ast_samples_path):
        """
        Purpose: The entire callbacks fixture should produce zero @line.col nodes.
        AC: AC1, AC7
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        ts_file = ast_samples_path / "typescript" / "anonymous_callbacks.ts"
        nodes = parser.parse(ts_file)

        at_pat = re.compile(r"@\d+")
        anon_nodes = [n for n in nodes if n.name and at_pat.search(n.name)]
        assert (
            len(anon_nodes) == 0
        ), f"Expected 0 anonymous nodes, got {len(anon_nodes)}: {[(n.ts_kind, n.name) for n in anon_nodes]}"


@pytest.mark.unit
class TestSkipWhenAnonymousBodies:
    """Tests for anonymous body/heritage/type skipping."""

    def test_interface_body_skipped(self, ast_samples_path):
        """
        Purpose: interface_body nodes should NOT produce @line.col nodes.
        AC: AC4
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        ts_file = ast_samples_path / "typescript" / "anonymous_bodies.ts"
        nodes = parser.parse(ts_file)

        at_pat = re.compile(r"@\d+")
        anon_iface_body = [
            n
            for n in nodes
            if n.ts_kind == "interface_body" and n.name and at_pat.search(n.name)
        ]
        assert (
            len(anon_iface_body) == 0
        ), f"Expected 0 anonymous interface_body nodes, got {len(anon_iface_body)}"

    def test_class_body_skipped(self, ast_samples_path):
        """
        Purpose: class_body nodes should NOT produce @line.col nodes.
        AC: AC4
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        ts_file = ast_samples_path / "typescript" / "anonymous_bodies.ts"
        nodes = parser.parse(ts_file)

        at_pat = re.compile(r"@\d+")
        anon_class_body = [
            n
            for n in nodes
            if n.ts_kind == "class_body" and n.name and at_pat.search(n.name)
        ]
        assert (
            len(anon_class_body) == 0
        ), f"Expected 0 anonymous class_body nodes, got {len(anon_class_body)}"

    def test_class_heritage_skipped(self, ast_samples_path):
        """
        Purpose: class_heritage nodes should NOT produce @line.col nodes.
        AC: AC4
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        ts_file = ast_samples_path / "typescript" / "anonymous_bodies.ts"
        nodes = parser.parse(ts_file)

        at_pat = re.compile(r"@\d+")
        anon_heritage = [
            n
            for n in nodes
            if n.ts_kind == "class_heritage" and n.name and at_pat.search(n.name)
        ]
        assert (
            len(anon_heritage) == 0
        ), f"Expected 0 anonymous class_heritage nodes, got {len(anon_heritage)}"

    def test_enum_body_skipped(self, ast_samples_path):
        """
        Purpose: enum_body nodes should NOT produce @line.col nodes.
        AC: AC4
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        ts_file = ast_samples_path / "typescript" / "anonymous_bodies.ts"
        nodes = parser.parse(ts_file)

        at_pat = re.compile(r"@\d+")
        anon_enum_body = [
            n
            for n in nodes
            if n.ts_kind == "enum_body" and n.name and at_pat.search(n.name)
        ]
        assert (
            len(anon_enum_body) == 0
        ), f"Expected 0 anonymous enum_body nodes, got {len(anon_enum_body)}"

    def test_function_type_skipped(self, ast_samples_path):
        """
        Purpose: function_type nodes should NOT produce @line.col nodes.
        AC: AC4
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        ts_file = ast_samples_path / "typescript" / "anonymous_bodies.ts"
        nodes = parser.parse(ts_file)

        at_pat = re.compile(r"@\d+")
        anon_fn_type = [
            n
            for n in nodes
            if n.ts_kind == "function_type" and n.name and at_pat.search(n.name)
        ]
        assert (
            len(anon_fn_type) == 0
        ), f"Expected 0 anonymous function_type nodes, got {len(anon_fn_type)}"

    def test_implements_clause_not_anonymous(self, ast_samples_path):
        """
        Purpose: implements_clause should not produce @line.col nodes.
        Note: Named implements_clause (e.g., 'UserService') should still be extracted.
        AC: AC4
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        ts_file = ast_samples_path / "typescript" / "anonymous_bodies.ts"
        nodes = parser.parse(ts_file)

        at_pat = re.compile(r"@\d+")
        anon_impl = [
            n
            for n in nodes
            if n.ts_kind == "implements_clause"
            and n.name
            and at_pat.search(n.name)
        ]
        assert (
            len(anon_impl) == 0
        ), f"Expected 0 anonymous implements_clause nodes, got {len(anon_impl)}"

    def test_named_types_still_extracted(self, ast_samples_path):
        """
        Purpose: Named interfaces, classes, enums should still be extracted.
        AC: AC4 (no regression)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        ts_file = ast_samples_path / "typescript" / "anonymous_bodies.ts"
        nodes = parser.parse(ts_file)

        names = {n.name for n in nodes if n.name}
        assert "UserService" in names, "UserService interface should be extracted"
        assert "EventHandler" in names, "EventHandler interface should be extracted"
        assert "UserRepository" in names, "UserRepository class should be extracted"
        assert "Status" in names, "Status enum should be extracted"
        assert "AdminService" in names, "AdminService class should be extracted"
        assert "AdminUser" in names, "AdminUser interface should be extracted"
        assert "User" in names, "User interface should be extracted"

    def test_methods_inside_classes_still_extracted(self, ast_samples_path):
        """
        Purpose: Methods inside classes (whose class_body is skipped) must still be extracted.
        AC: AC3, AC4
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        ts_file = ast_samples_path / "typescript" / "anonymous_bodies.ts"
        nodes = parser.parse(ts_file)

        method_names = {n.name for n in nodes if n.ts_kind == "method_definition"}
        assert "getUser" in method_names, "getUser method should be extracted"
        assert "saveUser" in method_names, "saveUser method should be extracted"

    def test_no_anonymous_nodes_in_bodies_fixture(self, ast_samples_path):
        """
        Purpose: The entire bodies fixture should produce zero @line.col nodes.
        AC: AC4, AC7
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_impl import TreeSitterParser

        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        ts_file = ast_samples_path / "typescript" / "anonymous_bodies.ts"
        nodes = parser.parse(ts_file)

        at_pat = re.compile(r"@\d+")
        anon_nodes = [n for n in nodes if n.name and at_pat.search(n.name)]
        assert (
            len(anon_nodes) == 0
        ), f"Expected 0 anonymous nodes, got {len(anon_nodes)}: {[(n.ts_kind, n.name) for n in anon_nodes]}"


@pytest.mark.unit
class TestSkipWhenAnonymousConstant:
    """Tests for the SKIP_WHEN_ANONYMOUS constant itself."""

    def test_skip_when_anonymous_is_defined(self):
        """
        Purpose: SKIP_WHEN_ANONYMOUS must exist as a module-level constant.
        AC: AC8
        """
        from fs2.core.adapters.ast_parser_impl import SKIP_WHEN_ANONYMOUS

        assert isinstance(
            SKIP_WHEN_ANONYMOUS, (set, frozenset)
        ), "SKIP_WHEN_ANONYMOUS must be a set or frozenset"

    def test_skip_when_anonymous_contains_all_10_kinds(self):
        """
        Purpose: The constant must contain all 10 specified ts_kinds.
        AC: AC7, AC8
        """
        from fs2.core.adapters.ast_parser_impl import SKIP_WHEN_ANONYMOUS

        expected = {
            "arrow_function",
            "function",
            "function_expression",
            "generator_function",
            "interface_body",
            "class_body",
            "class_heritage",
            "enum_body",
            "function_type",
            "implements_clause",
        }
        assert expected == set(
            SKIP_WHEN_ANONYMOUS
        ), f"Missing kinds: {expected - set(SKIP_WHEN_ANONYMOUS)}, Extra kinds: {set(SKIP_WHEN_ANONYMOUS) - expected}"
