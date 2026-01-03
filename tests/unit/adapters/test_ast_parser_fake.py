"""Tests for FakeASTParser test double.

Tasks: T005-T008
Purpose: Verify FakeASTParser implements ASTParser ABC correctly.
Per CF02: Adapter ABC with Dual Implementation Pattern.
"""

from pathlib import Path

import pytest


@pytest.mark.unit
class TestFakeASTParser:
    """Tests for FakeASTParser test double (T005-T008)."""

    def test_fake_ast_parser_accepts_configuration_service(self):
        """
        Purpose: Verifies FakeASTParser follows ConfigurationService pattern.
        Quality Contribution: Ensures consistent DI across all adapters.
        Acceptance Criteria: Construction with ConfigurationService succeeds.

        Task: T005
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_fake import FakeASTParser

        config = FakeConfigurationService(ScanConfig())
        parser = FakeASTParser(config)

        assert parser is not None

    def test_fake_ast_parser_returns_configured_results(self):
        """
        Purpose: Verifies FakeASTParser returns pre-configured CodeNode list.
        Quality Contribution: Enables deterministic testing of dependent code.
        Acceptance Criteria: parse() returns exactly the configured CodeNodes.

        Task: T005
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_fake import FakeASTParser
        from fs2.core.models import CodeNode
        from fs2.core.models.content_type import ContentType

        config = FakeConfigurationService(ScanConfig())
        parser = FakeASTParser(config)

        expected_nodes = [
            CodeNode.create_file(
                file_path="src/main.py",
                language="python",
                content_type=ContentType.CODE,
                ts_kind="module",
                start_byte=0,
                end_byte=100,
                start_line=1,
                end_line=10,
                content="# Python file",
            ),
        ]
        parser.set_results(Path("src/main.py"), expected_nodes)

        result = parser.parse(Path("src/main.py"))

        assert result == expected_nodes

    def test_fake_ast_parser_returns_empty_list_by_default(self):
        """
        Purpose: Verifies FakeASTParser returns empty list when not configured.
        Quality Contribution: Safe default behavior.
        Acceptance Criteria: parse() returns empty list without set_results().

        Task: T005 (supplementary)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_fake import FakeASTParser

        config = FakeConfigurationService(ScanConfig())
        parser = FakeASTParser(config)

        result = parser.parse(Path("unknown.py"))

        assert result == []

    def test_fake_ast_parser_records_call_history(self):
        """
        Purpose: Verifies FakeASTParser tracks method calls for verification.
        Quality Contribution: Enables assertions on adapter usage in tests.
        Acceptance Criteria: call_history contains parse call after parse().

        Task: T006
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_fake import FakeASTParser

        config = FakeConfigurationService(ScanConfig())
        parser = FakeASTParser(config)

        parser.parse(Path("test.py"))

        assert len(parser.call_history) == 1
        assert parser.call_history[0]["method"] == "parse"
        assert parser.call_history[0]["args"]["file_path"] == Path("test.py")

    def test_fake_ast_parser_records_multiple_calls(self):
        """
        Purpose: Verifies call_history tracks all method calls.
        Quality Contribution: Enables complex interaction assertions.
        Acceptance Criteria: Multiple calls appear in call_history.

        Task: T006 (supplementary)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_fake import FakeASTParser

        config = FakeConfigurationService(ScanConfig())
        parser = FakeASTParser(config)

        parser.parse(Path("test.py"))
        parser.detect_language(Path("test.py"))
        parser.parse(Path("other.py"))

        assert len(parser.call_history) == 3
        assert parser.call_history[0]["method"] == "parse"
        assert parser.call_history[1]["method"] == "detect_language"
        assert parser.call_history[2]["method"] == "parse"

    def test_fake_ast_parser_error_simulation(self):
        """
        Purpose: Verifies FakeASTParser can simulate parse errors.
        Quality Contribution: Enables testing of error handling code paths.
        Acceptance Criteria: simulate_error_for causes ASTParserError on configured paths.

        Task: T007
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_fake import FakeASTParser
        from fs2.core.adapters.exceptions import ASTParserError

        config = FakeConfigurationService(ScanConfig())
        parser = FakeASTParser(config)

        parser.simulate_error_for = {Path("bad_file.py")}

        with pytest.raises(ASTParserError):
            parser.parse(Path("bad_file.py"))

        # Non-error paths should work
        result = parser.parse(Path("good_file.py"))
        assert result == []

    def test_fake_ast_parser_detect_language_returns_configured_result(self):
        """
        Purpose: Verifies detect_language() returns pre-configured language.
        Quality Contribution: Enables deterministic testing of language detection.
        Acceptance Criteria: detect_language() returns configured value.

        Task: T007 (supplementary)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_fake import FakeASTParser

        config = FakeConfigurationService(ScanConfig())
        parser = FakeASTParser(config)

        parser.set_language(Path("test.py"), "python")
        parser.set_language(Path("test.ts"), "typescript")

        assert parser.detect_language(Path("test.py")) == "python"
        assert parser.detect_language(Path("test.ts")) == "typescript"

    def test_fake_ast_parser_detect_language_defaults_to_none(self):
        """
        Purpose: Verifies detect_language() returns None by default.
        Quality Contribution: Safe default - unknown languages.
        Acceptance Criteria: detect_language() returns None without configuration.

        Task: T007 (supplementary)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser_fake import FakeASTParser

        config = FakeConfigurationService(ScanConfig())
        parser = FakeASTParser(config)

        assert parser.detect_language(Path("unknown.xyz")) is None

    def test_fake_ast_parser_inherits_from_ast_parser(self):
        """
        Purpose: Verifies FakeASTParser is a proper ASTParser implementation.
        Quality Contribution: Ensures polymorphism works correctly.
        Acceptance Criteria: FakeASTParser is instance of ASTParser.

        Task: T008
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.ast_parser import ASTParser
        from fs2.core.adapters.ast_parser_fake import FakeASTParser

        config = FakeConfigurationService(ScanConfig())
        parser = FakeASTParser(config)

        assert isinstance(parser, ASTParser)
