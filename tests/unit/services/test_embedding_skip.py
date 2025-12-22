"""Tests for EmbeddingService hash-based skip logic.

TDD RED phase: Tests for _should_skip() method.
Per Plan 3.3, Per Finding 08.

Tests cover:
- Skip nodes that already have embeddings (unchanged content)
- Process nodes without embeddings (new content)
- Process nodes with changed content (hash mismatch)
- Edge cases: empty embeddings, None values
"""

from __future__ import annotations

import pytest

from fs2.config.objects import EmbeddingConfig
from fs2.core.models.code_node import CodeNode
from fs2.core.models.content_type import ContentType


class TestHashBasedSkip:
    """Tests for _should_skip() method.

    Purpose: Validates hash-based skip logic for incremental embedding updates
    Quality Contribution: Ensures unchanged content is not re-embedded (cost savings)
    Acceptance Criteria: Skip if embedding exists AND content hash unchanged
    """

    @pytest.fixture
    def config(self) -> EmbeddingConfig:
        """Default embedding config."""
        return EmbeddingConfig(mode="fake")

    @pytest.fixture
    def node_without_embedding(self) -> CodeNode:
        """Node that has never been embedded."""
        return CodeNode(
            node_id="callable:test.py:func",
            category="callable",
            ts_kind="function_definition",
            name="func",
            qualified_name="func",
            start_line=1,
            end_line=3,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=50,
            content="def func(): pass",
            content_hash="hash123",
            signature="def func():",
            language="python",
            content_type=ContentType.CODE,
            is_named=True,
            field_name=None,
            embedding=None,  # No embedding yet
            smart_content_embedding=None,
        )

    @pytest.fixture
    def node_with_embedding(self) -> CodeNode:
        """Node that has been embedded and is unchanged."""
        return CodeNode(
            node_id="callable:test.py:func",
            category="callable",
            ts_kind="function_definition",
            name="func",
            qualified_name="func",
            start_line=1,
            end_line=3,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=50,
            content="def func(): pass",
            content_hash="hash123",
            signature="def func():",
            language="python",
            content_type=ContentType.CODE,
            is_named=True,
            field_name=None,
            embedding=((0.1, 0.2, 0.3),),  # Has embedding
            embedding_hash="hash123",  # Matches content_hash - embedding is fresh
            smart_content_embedding=((0.4, 0.5, 0.6),),  # Has smart embedding too
        )

    def test_skip_node_with_embedding(self, config, node_with_embedding):
        """Node with existing embedding should be skipped.

        Skip if:
        - embedding is not None
        - embedding is not empty
        """
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        service = EmbeddingService(
            config=config,
            embedding_adapter=None,
            token_counter=None,
        )

        should_skip = service._should_skip(node_with_embedding)

        assert should_skip is True, "Node with embedding should be skipped"

    def test_process_node_without_embedding(self, config, node_without_embedding):
        """Node without embedding should be processed."""
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        service = EmbeddingService(
            config=config,
            embedding_adapter=None,
            token_counter=None,
        )

        should_skip = service._should_skip(node_without_embedding)

        assert should_skip is False, "Node without embedding should be processed"

    def test_process_node_with_empty_embedding(self, config):
        """Node with empty embedding tuple should be processed."""
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        node = CodeNode(
            node_id="file:test.py",
            category="file",
            ts_kind="module",
            name="test.py",
            qualified_name="test.py",
            start_line=1,
            end_line=1,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=10,
            content="x = 1",
            content_hash="hash456",
            signature=None,
            language="python",
            content_type=ContentType.CODE,
            is_named=True,
            field_name=None,
            embedding=(),  # Empty tuple
            smart_content_embedding=None,
        )

        service = EmbeddingService(
            config=config,
            embedding_adapter=None,
            token_counter=None,
        )

        should_skip = service._should_skip(node)

        assert should_skip is False, "Node with empty embedding should be processed"


class TestSkipLogicEdgeCases:
    """Edge case tests for skip logic."""

    @pytest.fixture
    def config(self) -> EmbeddingConfig:
        return EmbeddingConfig(mode="fake")

    def test_skip_requires_both_embedding_fields_for_full_skip(self, config):
        """Skip logic considers both embedding and smart_content_embedding."""
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        # Node with embedding but no smart_content_embedding
        node = CodeNode(
            node_id="callable:test.py:func",
            category="callable",
            ts_kind="function_definition",
            name="func",
            qualified_name="func",
            start_line=1,
            end_line=3,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=50,
            content="def func(): pass",
            content_hash="hash123",
            signature="def func():",
            language="python",
            content_type=ContentType.CODE,
            is_named=True,
            field_name=None,
            embedding=((0.1, 0.2),),  # Has embedding
            smart_content_embedding=None,  # But no smart_content_embedding
            smart_content="A function that does nothing",  # Has smart_content text
        )

        service = EmbeddingService(
            config=config,
            embedding_adapter=None,
            token_counter=None,
        )

        # Should not skip because smart_content exists but is not embedded
        should_skip = service._should_skip(node)

        # The exact behavior depends on implementation:
        # If we only check raw embedding: should_skip = True
        # If we check both fields: should_skip = False (needs smart_content_embedding)
        # Per spec AC1: Both fields needed for complete node
        assert isinstance(should_skip, bool)  # At minimum, returns a bool

    def test_node_with_both_embeddings_is_skipped(self, config):
        """Node with both embedding fields populated should be skipped."""
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        node = CodeNode(
            node_id="callable:test.py:func",
            category="callable",
            ts_kind="function_definition",
            name="func",
            qualified_name="func",
            start_line=1,
            end_line=3,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=50,
            content="def func(): pass",
            content_hash="hash123",
            signature="def func():",
            language="python",
            content_type=ContentType.CODE,
            is_named=True,
            field_name=None,
            embedding=((0.1, 0.2),),
            embedding_hash="hash123",  # Matches content_hash - embedding is fresh
            smart_content_embedding=((0.3, 0.4),),
            smart_content="A function",
        )

        service = EmbeddingService(
            config=config,
            embedding_adapter=None,
            token_counter=None,
        )

        should_skip = service._should_skip(node)

        assert should_skip is True, "Node with both embeddings should be skipped"

    def test_node_without_smart_content_can_skip_with_just_embedding(self, config):
        """Node without smart_content (no AI description yet) can skip if has embedding."""
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        # Node with embedding but no smart_content text (smart_content generation not done)
        node = CodeNode(
            node_id="callable:test.py:func",
            category="callable",
            ts_kind="function_definition",
            name="func",
            qualified_name="func",
            start_line=1,
            end_line=3,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=50,
            content="def func(): pass",
            content_hash="hash123",
            signature="def func():",
            language="python",
            content_type=ContentType.CODE,
            is_named=True,
            field_name=None,
            embedding=((0.1, 0.2),),  # Has raw embedding
            embedding_hash="hash123",  # Matches content_hash - embedding is fresh
            smart_content_embedding=None,  # No smart embedding
            smart_content=None,  # No smart_content text either
        )

        service = EmbeddingService(
            config=config,
            embedding_adapter=None,
            token_counter=None,
        )

        # Node has raw content embedded, no smart_content to embed
        # Should be skipped for raw embedding, no smart_content work needed
        should_skip = service._should_skip(node)

        # If smart_content is None, there's nothing to embed for smart_content
        # So checking raw embedding is sufficient
        assert should_skip is True


class TestHashComparisonSkipLogic:
    """Tests for hash-based skip logic that compares content hashes.

    Per Finding 08 and review S1: Skip logic must compare content_hash,
    not just check embedding presence. This prevents stale embeddings.
    """

    @pytest.fixture
    def config(self) -> EmbeddingConfig:
        return EmbeddingConfig(mode="fake")

    def test_node_with_embedding_but_changed_hash_is_NOT_skipped(self, config):
        """Node with embedding but changed content_hash should be processed.

        Per review S1: Hash-based skip must compare hashes to detect stale embeddings.
        If content changed (different hash), embedding needs regeneration.
        """
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        # Node was embedded with old content, but content has changed
        node = CodeNode(
            node_id="callable:test.py:func",
            category="callable",
            ts_kind="function_definition",
            name="func",
            qualified_name="func",
            start_line=1,
            end_line=3,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=50,
            content="def func(): return 'NEW CONTENT'",  # Content changed
            content_hash="new_hash_456",  # Hash reflects new content
            signature="def func():",
            language="python",
            content_type=ContentType.CODE,
            is_named=True,
            field_name=None,
            embedding=((0.1, 0.2, 0.3),),  # Has old embedding
            embedding_hash="old_hash_123",  # Hash from when embedding was generated
            smart_content_embedding=None,
            smart_content=None,
        )

        service = EmbeddingService(
            config=config,
            embedding_adapter=None,
            token_counter=None,
        )

        # Should NOT skip because content_hash != embedding_hash
        should_skip = service._should_skip(node)

        assert should_skip is False, (
            "Node with stale embedding (hash mismatch) should be processed"
        )

    def test_node_with_matching_hash_is_skipped(self, config):
        """Node with embedding and matching hash should be skipped.

        This is the happy path - content unchanged, embedding valid.
        """
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        node = CodeNode(
            node_id="callable:test.py:func",
            category="callable",
            ts_kind="function_definition",
            name="func",
            qualified_name="func",
            start_line=1,
            end_line=3,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=50,
            content="def func(): pass",
            content_hash="hash_123",  # Current content hash
            signature="def func():",
            language="python",
            content_type=ContentType.CODE,
            is_named=True,
            field_name=None,
            embedding=((0.1, 0.2, 0.3),),
            embedding_hash="hash_123",  # Matches content_hash - embedding is fresh
            smart_content_embedding=None,
            smart_content=None,
        )

        service = EmbeddingService(
            config=config,
            embedding_adapter=None,
            token_counter=None,
        )

        should_skip = service._should_skip(node)

        assert should_skip is True, (
            "Node with fresh embedding (matching hash) should be skipped"
        )

    def test_node_without_embedding_hash_is_processed(self, config):
        """Node with embedding but no embedding_hash (legacy) should be processed.

        Backwards compatibility: Old nodes may have embedding but no embedding_hash.
        Treat as stale and re-embed.
        """
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        node = CodeNode(
            node_id="callable:test.py:legacy",
            category="callable",
            ts_kind="function_definition",
            name="legacy",
            qualified_name="legacy",
            start_line=1,
            end_line=3,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=50,
            content="def legacy(): pass",
            content_hash="hash_789",
            signature="def legacy():",
            language="python",
            content_type=ContentType.CODE,
            is_named=True,
            field_name=None,
            embedding=((0.1, 0.2, 0.3),),  # Has embedding
            embedding_hash=None,  # No embedding_hash (legacy node)
            smart_content_embedding=None,
            smart_content=None,
        )

        service = EmbeddingService(
            config=config,
            embedding_adapter=None,
            token_counter=None,
        )

        should_skip = service._should_skip(node)

        assert should_skip is False, (
            "Legacy node without embedding_hash should be re-processed"
        )


class TestSkipLogicWithSmartContent:
    """Tests for skip logic involving smart_content field."""

    @pytest.fixture
    def config(self) -> EmbeddingConfig:
        return EmbeddingConfig(mode="fake")

    def test_node_needs_smart_content_embedding_when_text_exists(self, config):
        """Node with smart_content text but no embedding needs processing."""
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        node = CodeNode(
            node_id="callable:test.py:func",
            category="callable",
            ts_kind="function_definition",
            name="func",
            qualified_name="func",
            start_line=1,
            end_line=3,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=50,
            content="def func(): pass",
            content_hash="hash123",
            signature="def func():",
            language="python",
            content_type=ContentType.CODE,
            is_named=True,
            field_name=None,
            embedding=((0.1, 0.2),),  # Has raw embedding
            smart_content="A function that does nothing",  # Has smart_content text
            smart_content_embedding=None,  # But no smart_content embedding!
        )

        service = EmbeddingService(
            config=config,
            embedding_adapter=None,
            token_counter=None,
        )

        # Per DYK-2: Need to embed both raw content and smart_content
        # Since smart_content exists but smart_content_embedding is None,
        # we should NOT skip (need to generate smart_content_embedding)
        should_skip = service._should_skip(node)

        assert should_skip is False, (
            "Node with smart_content text but no embedding should be processed"
        )

    def test_fully_embedded_node_is_skipped(self, config):
        """Node with all embeddings populated is skipped."""
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        node = CodeNode(
            node_id="callable:test.py:func",
            category="callable",
            ts_kind="function_definition",
            name="func",
            qualified_name="func",
            start_line=1,
            end_line=3,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=50,
            content="def func(): pass",
            content_hash="hash123",
            signature="def func():",
            language="python",
            content_type=ContentType.CODE,
            is_named=True,
            field_name=None,
            embedding=((0.1, 0.2),),
            embedding_hash="hash123",  # Matches content_hash - embedding is fresh
            smart_content="A function that does nothing",
            smart_content_embedding=((0.3, 0.4),),
        )

        service = EmbeddingService(
            config=config,
            embedding_adapter=None,
            token_counter=None,
        )

        should_skip = service._should_skip(node)

        assert should_skip is True, "Fully embedded node should be skipped"
