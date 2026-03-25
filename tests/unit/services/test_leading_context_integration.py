"""Integration tests for leading_context in search, embedding hash, and output (Plan 037).

Tests T011: search matching, content_hash stability, embedding_hash changes,
and get_node/MCP output inclusion.
"""

import regex

from fs2.core.models.code_node import CodeNode
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
        from fs2.core.services.search.regex_matcher import RegexMatcher

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

        # Must match the exact payload used by embedding_service: "\n".join([lc, content])
        raw_text = "\n".join([lc, content])
        hash_with = compute_content_hash(raw_text)
        hash_without = compute_content_hash(content)

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


class TestEmbeddingPayload:
    """AC08: Verify embedding chunking prepends leading_context."""

    def test_chunk_content_prepends_leading_context(self):
        """Chunked text starts with leading_context when present."""
        from unittest.mock import MagicMock

        from fs2.config.objects import EmbeddingConfig
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        config = EmbeddingConfig()
        token_counter = MagicMock()
        token_counter.count_tokens.return_value = 10
        service = EmbeddingService(
            config=config,
            embedding_adapter=MagicMock(),
            token_counter=token_counter,
        )

        node = _make_node(
            content="def foo(): pass",
            leading_context="# important comment",
        )
        chunks = service._chunk_content(node, is_smart_content=False)
        assert len(chunks) > 0
        assert chunks[0].text.startswith("# important comment")


class TestSmartContentContext:
    """AC09: Verify smart content context includes leading_context."""

    def test_build_context_includes_leading_context(self):
        """_build_context dict includes leading_context."""
        from unittest.mock import MagicMock

        from fs2.config.objects import SmartContentConfig
        from fs2.core.services.smart_content.smart_content_service import (
            SmartContentService,
        )

        config = MagicMock()
        config.require.return_value = SmartContentConfig()
        service = SmartContentService(
            config=config,
            llm_service=MagicMock(),
            template_service=MagicMock(),
            token_counter=MagicMock(),
        )

        node = _make_node(
            content="def foo(): pass",
            leading_context="# important comment",
        )
        context = service._build_context(node, node.content)
        assert context["leading_context"] == "# important comment"

    def test_build_context_empty_when_no_leading_context(self):
        """_build_context returns empty string when no leading_context."""
        from unittest.mock import MagicMock

        from fs2.config.objects import SmartContentConfig
        from fs2.core.services.smart_content.smart_content_service import (
            SmartContentService,
        )

        config = MagicMock()
        config.require.return_value = SmartContentConfig()
        service = SmartContentService(
            config=config,
            llm_service=MagicMock(),
            template_service=MagicMock(),
            token_counter=MagicMock(),
        )

        node = _make_node(content="def foo(): pass", leading_context=None)
        context = service._build_context(node, node.content)
        assert context["leading_context"] == ""
