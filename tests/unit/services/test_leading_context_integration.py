"""Integration tests for leading_context in search, embedding hash, and output (Plan 037).

Tests T011: search matching, content_hash stability, embedding_hash changes,
and get_node/MCP output inclusion.
"""

import regex

import pytest

from fs2.core.models.code_node import CodeNode
from fs2.core.models.content_type import ContentType
from fs2.core.utils.hash import compute_content_hash


def _make_node(
    content: str = "def foo(): pass",
    leading_context: str | None = None,
    name: str = "foo",
) -> CodeNode:
    """Helper to create a CodeNode with optional leading_context."""
    return CodeNode.create_callable(
        file_path="test.py",
        language="python",
        ts_kind="function_definition",
        name=name,
        qualified_name=name,
        start_line=1,
        end_line=1,
        start_column=0,
        end_column=len(content),
        start_byte=0,
        end_byte=len(content),
        content=content,
        signature="def foo():",
        leading_context=leading_context,
    )


class TestLeadingContextSearch:
    """AC07: Text/regex search matches in leading_context with score 0.6."""

    def test_regex_matcher_finds_leading_context(self):
        """Search for text in leading_context returns match with score 0.6."""
        from fs2.core.services.search.regex_matcher import FieldMatch, RegexMatcher

        matcher = RegexMatcher()
        node = _make_node(leading_context="# cross-border transactions handler")

        compiled = regex.compile("cross-border", regex.IGNORECASE)
        result = matcher._find_best_field_match(compiled, node)

        assert result is not None
        assert result.field_name == "leading_context"
        assert result.score == 0.6

    def test_leading_context_scores_higher_than_content(self):
        """Leading context (0.6) beats content (0.5) when both match."""
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher()
        node = _make_node(
            content="def handler(): pass",
            leading_context="# handler for special cases",
        )

        compiled = regex.compile("handler", regex.IGNORECASE)
        result = matcher._find_best_field_match(compiled, node)

        assert result is not None
        assert result.field_name == "leading_context"
        assert result.score == 0.6

    def test_node_id_still_scores_highest(self):
        """Node ID (0.8+) still beats leading_context (0.6)."""
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher()
        node = _make_node(
            name="handler",
            leading_context="# handler function",
        )

        compiled = regex.compile("handler", regex.IGNORECASE)
        result = matcher._find_best_field_match(compiled, node)

        assert result is not None
        assert result.score >= 0.8  # node_id match


class TestEmbeddingHashWithLeadingContext:
    """AC11 + AC12: content_hash stable, embedding_hash changes."""

    def test_content_hash_unchanged_by_leading_context(self):
        """AC11: Same code produces same content_hash regardless of leading_context."""
        node_with = _make_node(
            content="def foo(): pass",
            leading_context="# important comment",
        )
        node_without = _make_node(
            content="def foo(): pass",
            leading_context=None,
        )
        assert node_with.content_hash == node_without.content_hash

    def test_embedding_hash_differs_with_leading_context(self):
        """AC12: embedding_hash factors in leading_context."""
        content = "def foo(): pass"
        lc = "# important comment"

        hash_with = compute_content_hash(content + lc)
        hash_without = compute_content_hash(content)

        # Different — leading_context changes the embedding hash
        assert hash_with != hash_without

    def test_embedding_hash_matches_content_hash_when_no_context(self):
        """Backward compat: no leading_context → embedding_hash = content_hash."""
        node = _make_node(content="def foo(): pass", leading_context=None)
        # The EmbeddingService sets embedding_hash = content_hash when no leading_context
        assert node.content_hash == compute_content_hash("def foo(): pass")


class TestGetNodeOutput:
    """AC: leading_context appears as separate field in get_node output."""

    def test_cli_dict_includes_leading_context(self):
        """get_node CLI output includes leading_context field."""
        from fs2.cli.get_node import _code_node_to_cli_dict

        node = _make_node(leading_context="# test comment")
        result = _code_node_to_cli_dict(node)

        assert "leading_context" in result
        assert result["leading_context"] == "# test comment"

    def test_cli_dict_includes_none_leading_context(self):
        """get_node output shows None when no leading_context."""
        from fs2.cli.get_node import _code_node_to_cli_dict

        node = _make_node(leading_context=None)
        result = _code_node_to_cli_dict(node)

        assert "leading_context" in result
        assert result["leading_context"] is None
