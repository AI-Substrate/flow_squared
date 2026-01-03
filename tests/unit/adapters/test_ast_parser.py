"""Tests for ASTParser ABC contract.

Tasks: T001-T003
Purpose: Verify ASTParser ABC defines correct interface.
Per CF02: Adapter ABC with Dual Implementation Pattern.
"""

from abc import ABC

import pytest


@pytest.mark.unit
class TestASTParserABC:
    """Tests for ASTParser ABC contract (T001-T003)."""

    def test_ast_parser_abc_cannot_be_instantiated(self):
        """
        Purpose: Proves ABC cannot be directly instantiated.
        Quality Contribution: Enforces interface-only contract.
        Acceptance Criteria: TypeError raised on instantiation.

        Task: T001
        """
        from fs2.core.adapters.ast_parser import ASTParser

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            ASTParser()

    def test_ast_parser_abc_defines_parse_method(self):
        """
        Purpose: Verifies parse() is an abstract method.
        Quality Contribution: Ensures implementations provide parsing capability.
        Acceptance Criteria: parse in __abstractmethods__.

        Task: T002
        """
        from fs2.core.adapters.ast_parser import ASTParser

        assert "parse" in ASTParser.__abstractmethods__

    def test_ast_parser_abc_defines_detect_language_method(self):
        """
        Purpose: Verifies detect_language() is an abstract method.
        Quality Contribution: Ensures implementations provide language detection.
        Acceptance Criteria: detect_language in __abstractmethods__.

        Task: T003
        """
        from fs2.core.adapters.ast_parser import ASTParser

        assert "detect_language" in ASTParser.__abstractmethods__

    def test_ast_parser_abc_inherits_from_abc(self):
        """
        Purpose: Verifies ASTParser is a proper ABC.
        Quality Contribution: Ensures abc.ABC pattern followed correctly.
        Acceptance Criteria: ASTParser is subclass of ABC.

        Task: T001 (supplementary)
        """
        from fs2.core.adapters.ast_parser import ASTParser

        assert issubclass(ASTParser, ABC)
