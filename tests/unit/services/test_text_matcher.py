"""Tests for TextMatcher - case-insensitive substring search.

TDD tests for Phase 2: Text/Regex Matchers.

Per tasks.md:
- T006: Delegation to RegexMatcher tests
- T007: Special character escaping tests

Per Discovery 03: TextMatcher delegates to RegexMatcher after escaping.
Per R1-09: Avoid double escaping when delegating.
"""

import pytest

from fs2.core.models.code_node import CodeNode
from fs2.core.models.search import QuerySpec, SearchMode, SearchResult


# ============================================================================
# Test Fixtures - Helper functions to create test nodes
# ============================================================================


def create_node(
    node_id: str,
    content: str | None = None,
    smart_content: str | None = None,
    start_line: int = 1,
    end_line: int = 10,
) -> CodeNode:
    """Create a test CodeNode with minimal required fields."""
    return CodeNode(
        node_id=node_id,
        category=node_id.split(":")[0],
        ts_kind="function_definition",
        name=node_id.split(":")[-1] if ":" in node_id else node_id,
        qualified_name=node_id.split(":")[-1] if ":" in node_id else node_id,
        start_line=start_line,
        end_line=end_line,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=len(content) if content else 0,
        content=content or "",
        content_hash="test_hash",
        signature=None,
        language="python",
        is_named=True,
        field_name=None,
        smart_content=smart_content,
    )


# ============================================================================
# T006: Delegation Tests
# ============================================================================


class TestTextMatcherDelegation:
    """Tests for TextMatcher delegation to RegexMatcher (T006).

    Per Discovery 03: TextMatcher escapes pattern, then delegates.
    """

    def test_case_insensitive_substring_match(self) -> None:
        """Proves text mode is case-insensitive (AC01).

        Purpose: Case-insensitive substring search is core text mode behavior.
        Quality Contribution: Validates primary text mode use case.
        Acceptance Criteria: Lowercase pattern matches uppercase text.
        """
        from fs2.core.services.search.text_matcher import TextMatcher

        matcher = TextMatcher(timeout=2.0)
        nodes = [create_node("callable:test.py:SearchService")]

        results = matcher.match(
            QuerySpec(pattern="searchservice", mode=SearchMode.TEXT),
            nodes,
        )

        assert len(results) == 1
        assert results[0].node_id == "callable:test.py:SearchService"

    def test_case_insensitive_content_search(self) -> None:
        """Proves text mode is case-insensitive in content field.

        Purpose: Case-insensitivity applies to all fields.
        Quality Contribution: Consistent behavior across fields.
        Acceptance Criteria: Matches regardless of case.
        """
        from fs2.core.services.search.text_matcher import TextMatcher

        matcher = TextMatcher(timeout=2.0)
        nodes = [
            create_node(
                "callable:test.py:func",
                content="def ProcessData(): pass",
            )
        ]

        results = matcher.match(
            QuerySpec(pattern="processdata", mode=SearchMode.TEXT),
            nodes,
        )

        assert len(results) == 1

    def test_partial_match_in_node_id(self) -> None:
        """Proves text mode finds partial matches in node_id.

        Purpose: Substring matching, not exact matching.
        Quality Contribution: Flexible search behavior.
        Acceptance Criteria: Partial pattern matches.
        """
        from fs2.core.services.search.text_matcher import TextMatcher

        matcher = TextMatcher(timeout=2.0)
        nodes = [create_node("callable:src/services/authentication_service.py:login")]

        results = matcher.match(
            QuerySpec(pattern="auth", mode=SearchMode.TEXT),
            nodes,
        )

        assert len(results) == 1

    def test_returns_search_results(self) -> None:
        """Proves TextMatcher returns proper SearchResult objects.

        Purpose: Validates return type and structure.
        Quality Contribution: Contract verification.
        Acceptance Criteria: Returns list of SearchResult with required fields.
        """
        from fs2.core.services.search.text_matcher import TextMatcher

        matcher = TextMatcher(timeout=2.0)
        nodes = [create_node("callable:test.py:func")]

        results = matcher.match(
            QuerySpec(pattern="func", mode=SearchMode.TEXT),
            nodes,
        )

        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].node_id == "callable:test.py:func"
        assert 0.0 <= results[0].score <= 1.0
        assert results[0].match_field in ["node_id", "content", "smart_content"]


# ============================================================================
# T007: Special Character Escaping Tests
# ============================================================================


class TestTextMatcherEscaping:
    """Tests for special character escaping (T007).

    Per Discovery 03: Text patterns are escaped before delegation.
    Per R1-09: Avoid double escaping - escape once only.
    """

    def test_dot_in_pattern_is_literal(self) -> None:
        """Proves dot in text pattern matches literal dot (Discovery 03).

        Purpose: Special regex chars are escaped for text mode.
        Quality Contribution: Prevents surprise regex behavior.
        Acceptance Criteria: "file.py" matches literal dot, not any char.
        """
        from fs2.core.services.search.text_matcher import TextMatcher

        matcher = TextMatcher(timeout=2.0)
        nodes = [
            create_node("file:src/config.py"),  # Should match
            create_node("file:src/configXpy"),  # Should NOT match
        ]

        results = matcher.match(
            QuerySpec(pattern="config.py", mode=SearchMode.TEXT),
            nodes,
        )

        assert len(results) == 1
        assert "config.py" in results[0].node_id

    def test_asterisk_in_pattern_is_literal(self) -> None:
        """Proves asterisk in text pattern matches literal asterisk.

        Purpose: Regex quantifier * is escaped.
        Quality Contribution: Predictable text matching.
        Acceptance Criteria: "*" matches literal star character.
        """
        from fs2.core.services.search.text_matcher import TextMatcher

        matcher = TextMatcher(timeout=2.0)
        nodes = [
            create_node(
                "callable:test.py:func",
                content="pattern = 'a*b'",
            ),
            create_node(
                "callable:test.py:other",
                content="pattern = 'aaaaab'",  # Would match regex a*b
            ),
        ]

        results = matcher.match(
            QuerySpec(pattern="a*b", mode=SearchMode.TEXT),
            nodes,
        )

        # Only the first node has literal "a*b"
        assert len(results) == 1
        assert "func" in results[0].node_id

    def test_question_mark_in_pattern_is_literal(self) -> None:
        """Proves question mark in text pattern matches literal question mark.

        Purpose: Regex quantifier ? is escaped.
        Quality Contribution: Predictable text matching.
        Acceptance Criteria: "?" matches literal question mark.
        """
        from fs2.core.services.search.text_matcher import TextMatcher

        matcher = TextMatcher(timeout=2.0)
        nodes = [
            create_node(
                "callable:test.py:func",
                content="# TODO: what should this do?",
            ),
        ]

        results = matcher.match(
            QuerySpec(pattern="do?", mode=SearchMode.TEXT),
            nodes,
        )

        assert len(results) == 1

    def test_brackets_in_pattern_are_literal(self) -> None:
        """Proves square brackets in text pattern match literally.

        Purpose: Regex character class [...] is escaped.
        Quality Contribution: Predictable text matching.
        Acceptance Criteria: "[0]" matches literal bracket notation.
        """
        from fs2.core.services.search.text_matcher import TextMatcher

        matcher = TextMatcher(timeout=2.0)
        nodes = [
            create_node(
                "callable:test.py:func",
                content="items[0] = value",
            ),
        ]

        results = matcher.match(
            QuerySpec(pattern="[0]", mode=SearchMode.TEXT),
            nodes,
        )

        assert len(results) == 1

    def test_caret_and_dollar_are_literal(self) -> None:
        """Proves ^ and $ in text pattern match literally.

        Purpose: Regex anchors are escaped.
        Quality Contribution: Predictable text matching.
        Acceptance Criteria: "^" and "$" match literally.
        """
        from fs2.core.services.search.text_matcher import TextMatcher

        matcher = TextMatcher(timeout=2.0)
        nodes = [
            create_node(
                "callable:test.py:func",
                content="# Price: $100",
            ),
            create_node(
                "callable:test.py:other",
                content="# regex: ^start",
            ),
        ]

        results = matcher.match(
            QuerySpec(pattern="$100", mode=SearchMode.TEXT),
            nodes,
        )

        assert len(results) == 1
        assert "func" in results[0].node_id

    def test_backslash_in_pattern_is_literal(self) -> None:
        """Proves backslash in text pattern matches literally.

        Purpose: Regex escape character \\ is escaped.
        Quality Contribution: Windows paths work correctly.
        Acceptance Criteria: "\\n" matches literal backslash-n.
        """
        from fs2.core.services.search.text_matcher import TextMatcher

        matcher = TextMatcher(timeout=2.0)
        nodes = [
            create_node(
                "callable:test.py:func",
                content="path = 'C:\\\\Users\\\\name'",
            ),
        ]

        results = matcher.match(
            QuerySpec(pattern="\\Users\\", mode=SearchMode.TEXT),
            nodes,
        )

        assert len(results) == 1

    def test_no_double_escaping(self) -> None:
        """Proves pattern is escaped only once (Discovery 03, R1-09).

        Purpose: Avoids double-escape bugs from delegation.
        Quality Contribution: Correct escaping behavior.
        Acceptance Criteria: "\\." searches for literal backslash-dot.
        """
        from fs2.core.services.search.text_matcher import TextMatcher

        matcher = TextMatcher(timeout=2.0)
        nodes = [
            create_node(
                "callable:test.py:func",
                content="pattern = r'\\.'",  # Contains literal \\.
            ),
        ]

        # User searches for literal backslash-dot
        results = matcher.match(
            QuerySpec(pattern="\\.", mode=SearchMode.TEXT),
            nodes,
        )

        assert len(results) == 1

    def test_parens_in_pattern_are_literal(self) -> None:
        """Proves parentheses in text pattern match literally.

        Purpose: Regex groups () are escaped.
        Quality Contribution: Function signatures searchable.
        Acceptance Criteria: "()" matches literal parentheses.
        """
        from fs2.core.services.search.text_matcher import TextMatcher

        matcher = TextMatcher(timeout=2.0)
        nodes = [
            create_node(
                "callable:test.py:main",
                content="def main(): pass",
            ),
        ]

        results = matcher.match(
            QuerySpec(pattern="main()", mode=SearchMode.TEXT),
            nodes,
        )

        assert len(results) == 1

    def test_pipe_in_pattern_is_literal(self) -> None:
        """Proves pipe character in text pattern matches literally.

        Purpose: Regex alternation | is escaped.
        Quality Contribution: Bitwise OR expressions searchable.
        Acceptance Criteria: "|" matches literal pipe.
        """
        from fs2.core.services.search.text_matcher import TextMatcher

        matcher = TextMatcher(timeout=2.0)
        nodes = [
            create_node(
                "callable:test.py:func",
                content="result = a | b",
            ),
        ]

        results = matcher.match(
            QuerySpec(pattern="a | b", mode=SearchMode.TEXT),
            nodes,
        )

        assert len(results) == 1
