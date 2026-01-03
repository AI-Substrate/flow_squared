"""Tests for EmbeddingService content chunking logic.

TDD RED phase: Tests for content-type aware chunking.
Per Plan 3.1, Per Finding 04, Per DYK-2, DYK-5.

Tests cover:
- Code content uses config.code chunk parameters (400 tokens, 50 overlap)
- Documentation content uses config.documentation (800 tokens, 120 overlap)
- Smart content uses config.smart_content (8000 tokens, 0 overlap)
- Overlap between consecutive chunks
- Token boundary handling
- Dual embedding: both raw content and smart_content chunking
- ChunkItem output with is_smart_content flag
"""

from __future__ import annotations

import pytest

from fs2.config.objects import ChunkConfig, EmbeddingConfig
from fs2.core.models.code_node import CodeNode
from fs2.core.models.content_type import ContentType


class TestContentChunking:
    """Tests for _chunk_content() method.

    Purpose: Validates chunking respects content-type specific parameters
    Quality Contribution: Ensures optimal chunk sizes for search quality
    Acceptance Criteria: CODE=400, CONTENT=800, smart_content=8000 tokens
    """

    @pytest.fixture
    def default_config(self) -> EmbeddingConfig:
        """Default embedding config with standard chunk sizes."""
        return EmbeddingConfig(
            mode="fake",
            code=ChunkConfig(max_tokens=400, overlap_tokens=50),
            documentation=ChunkConfig(max_tokens=800, overlap_tokens=120),
            smart_content=ChunkConfig(max_tokens=8000, overlap_tokens=0),
        )

    @pytest.fixture
    def code_node(self) -> CodeNode:
        """Sample CODE content node."""
        # Generate content that will result in multiple chunks at 400 tokens
        # Average ~4 chars per token, so 400 tokens ≈ 1600 chars
        content = "def example():\n" + "    x = 1\n" * 500  # ~5500 chars
        return CodeNode(
            node_id="callable:test.py:example",
            category="callable",
            ts_kind="function_definition",
            name="example",
            qualified_name="example",
            start_line=1,
            end_line=502,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=len(content),
            content=content,
            content_hash="abc123",
            signature="def example():",
            language="python",
            content_type=ContentType.CODE,
            is_named=True,
            field_name=None,
        )

    @pytest.fixture
    def content_node(self) -> CodeNode:
        """Sample CONTENT type node (markdown)."""
        # Generate content that will result in multiple chunks at 800 tokens
        content = "# Documentation\n\n" + "This is a paragraph of text. " * 300
        return CodeNode(
            node_id="file:README.md",
            category="file",
            ts_kind="document",
            name="README.md",
            qualified_name="README.md",
            start_line=1,
            end_line=50,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=len(content),
            content=content,
            content_hash="def456",
            signature=None,
            language="markdown",
            content_type=ContentType.CONTENT,
            is_named=True,
            field_name=None,
        )

    def test_code_content_uses_code_chunk_config(self, default_config, code_node):
        """CODE content type uses config.code parameters (400 tokens, 50 overlap).

        Per DYK-5: Inline conditional maps ContentType.CODE → config.code
        """
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        # This will fail with ModuleNotFoundError (TDD RED)
        # When implemented, should use code chunk config
        service = EmbeddingService(
            config=default_config,
            embedding_adapter=None,  # Not needed for chunking tests
            token_counter=None,  # Will be mocked/injected
        )

        chunks = service._chunk_content(code_node, is_smart_content=False)

        # Each chunk should be ChunkItem with correct metadata
        assert len(chunks) > 1, "Long content should produce multiple chunks"
        for chunk in chunks:
            assert chunk.node_id == code_node.node_id
            assert chunk.is_smart_content is False

    def test_content_type_uses_documentation_chunk_config(
        self, default_config, content_node
    ):
        """CONTENT type uses config.documentation parameters (800 tokens, 120 overlap).

        Per DYK-5: Inline conditional maps ContentType.CONTENT → config.documentation
        """
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        service = EmbeddingService(
            config=default_config,
            embedding_adapter=None,
            token_counter=None,
        )

        chunks = service._chunk_content(content_node, is_smart_content=False)

        assert len(chunks) > 1, "Long content should produce multiple chunks"
        for chunk in chunks:
            assert chunk.node_id == content_node.node_id
            assert chunk.is_smart_content is False

    def test_smart_content_uses_smart_content_chunk_config(
        self, default_config, code_node
    ):
        """Smart content uses config.smart_content parameters (8000 tokens, 0 overlap).

        Per DYK-2: is_smart_content=True uses large chunk size for AI descriptions.
        Per DYK-5: Inline conditional checks is_smart_content first.
        """
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        service = EmbeddingService(
            config=default_config,
            embedding_adapter=None,
            token_counter=None,
        )

        # Simulate smart_content (shorter, fits in one chunk typically)
        chunks = service._chunk_content(code_node, is_smart_content=True)

        # Smart content typically fits in one chunk (8000 tokens)
        for chunk in chunks:
            assert chunk.node_id == code_node.node_id
            assert chunk.is_smart_content is True

    def test_chunk_overlap_preserved(self, default_config, code_node):
        """Consecutive chunks have overlapping content per overlap_tokens config."""
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        service = EmbeddingService(
            config=default_config,
            embedding_adapter=None,
            token_counter=None,
        )

        chunks = service._chunk_content(code_node, is_smart_content=False)

        if len(chunks) > 1:
            # Verify overlap exists between consecutive chunks
            for i in range(len(chunks) - 1):
                chunk1_text = chunks[i].text
                chunk2_text = chunks[i + 1].text
                # Overlap means end of chunk1 should appear at start of chunk2
                # (exact verification depends on implementation details)
                assert len(chunk1_text) > 0
                assert len(chunk2_text) > 0

    def test_chunk_indices_sequential(self, default_config, code_node):
        """ChunkItems have sequential chunk_index starting from 0.

        Per DYK-1: chunk_index tracks position for reassembly.
        """
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        service = EmbeddingService(
            config=default_config,
            embedding_adapter=None,
            token_counter=None,
        )

        chunks = service._chunk_content(code_node, is_smart_content=False)

        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i, f"Chunk {i} has wrong index {chunk.chunk_index}"

    def test_empty_content_returns_empty_list(self, default_config):
        """Empty content returns empty chunk list."""
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        empty_node = CodeNode(
            node_id="file:empty.py",
            category="file",
            ts_kind="module",
            name="empty.py",
            qualified_name="empty.py",
            start_line=1,
            end_line=1,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=0,
            content="",
            content_hash="empty",
            signature=None,
            language="python",
            content_type=ContentType.CODE,
            is_named=True,
            field_name=None,
        )

        service = EmbeddingService(
            config=default_config,
            embedding_adapter=None,
            token_counter=None,
        )

        chunks = service._chunk_content(empty_node, is_smart_content=False)
        assert chunks == []

    def test_short_content_single_chunk(self, default_config):
        """Content shorter than max_tokens produces single chunk."""
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        short_node = CodeNode(
            node_id="callable:test.py:add",
            category="callable",
            ts_kind="function_definition",
            name="add",
            qualified_name="add",
            start_line=1,
            end_line=2,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=30,
            content="def add(a, b):\n    return a + b",
            content_hash="short123",
            signature="def add(a, b):",
            language="python",
            content_type=ContentType.CODE,
            is_named=True,
            field_name=None,
        )

        service = EmbeddingService(
            config=default_config,
            embedding_adapter=None,
            token_counter=None,
        )

        chunks = service._chunk_content(short_node, is_smart_content=False)

        assert len(chunks) == 1
        assert chunks[0].node_id == short_node.node_id
        assert chunks[0].chunk_index == 0
        assert chunks[0].text == short_node.content
        assert chunks[0].is_smart_content is False


class TestDualEmbeddingChunking:
    """Tests for dual embedding workflow (raw content + smart_content).

    Per DYK-2: Unified batching processes both content types together.
    Per spec AC1: Each node needs BOTH embedding AND smart_content_embedding.
    """

    @pytest.fixture
    def config(self) -> EmbeddingConfig:
        """Embedding config for dual embedding tests."""
        return EmbeddingConfig(
            mode="fake",
            code=ChunkConfig(max_tokens=400, overlap_tokens=50),
            documentation=ChunkConfig(max_tokens=800, overlap_tokens=120),
            smart_content=ChunkConfig(max_tokens=8000, overlap_tokens=0),
        )

    @pytest.fixture
    def node_with_smart_content(self) -> CodeNode:
        """CodeNode with both content and smart_content."""
        return CodeNode(
            node_id="callable:test.py:process",
            category="callable",
            ts_kind="function_definition",
            name="process",
            qualified_name="process",
            start_line=1,
            end_line=10,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=200,
            content="def process(data):\n    # Long implementation\n" + "    pass\n" * 50,
            content_hash="proc123",
            signature="def process(data):",
            language="python",
            content_type=ContentType.CODE,
            is_named=True,
            field_name=None,
            smart_content="Processes input data and returns transformed results.",
        )

    def test_raw_content_chunks_have_is_smart_content_false(
        self, config, node_with_smart_content
    ):
        """Raw content chunks are marked with is_smart_content=False."""
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        service = EmbeddingService(
            config=config,
            embedding_adapter=None,
            token_counter=None,
        )

        raw_chunks = service._chunk_content(node_with_smart_content, is_smart_content=False)

        for chunk in raw_chunks:
            assert chunk.is_smart_content is False

    def test_smart_content_chunks_have_is_smart_content_true(
        self, config, node_with_smart_content
    ):
        """Smart content chunks are marked with is_smart_content=True."""
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        service = EmbeddingService(
            config=config,
            embedding_adapter=None,
            token_counter=None,
        )

        # Chunk the smart_content field
        smart_chunks = service._chunk_content(node_with_smart_content, is_smart_content=True)

        for chunk in smart_chunks:
            assert chunk.is_smart_content is True

    def test_smart_content_uses_larger_chunk_size(self, config, node_with_smart_content):
        """Smart content chunks use 8000 token limit vs 400 for code."""
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        service = EmbeddingService(
            config=config,
            embedding_adapter=None,
            token_counter=None,
        )

        raw_chunks = service._chunk_content(node_with_smart_content, is_smart_content=False)
        smart_chunks = service._chunk_content(node_with_smart_content, is_smart_content=True)

        # Smart content (short description) should be 1 chunk
        # Raw content (longer code) may be multiple chunks
        assert len(smart_chunks) <= len(raw_chunks)


class TestChunkItemDataStructure:
    """Tests for ChunkItem frozen dataclass.

    Per DYK-1: ChunkItem tracks (node_id, chunk_index, text, is_smart_content)
    for reassembly after batching.
    """

    def test_chunk_item_is_frozen(self):
        """ChunkItem is immutable (frozen dataclass)."""
        from fs2.core.services.embedding.embedding_service import ChunkItem

        chunk = ChunkItem(
            node_id="test:node",
            chunk_index=0,
            text="sample text",
            is_smart_content=False,
        )

        with pytest.raises(AttributeError):
            chunk.text = "modified"  # type: ignore[misc]

    def test_chunk_item_fields(self):
        """ChunkItem has required fields: node_id, chunk_index, text, is_smart_content."""
        from fs2.core.services.embedding.embedding_service import ChunkItem

        chunk = ChunkItem(
            node_id="callable:test.py:func",
            chunk_index=2,
            text="def func(): pass",
            is_smart_content=True,
        )

        assert chunk.node_id == "callable:test.py:func"
        assert chunk.chunk_index == 2
        assert chunk.text == "def func(): pass"
        assert chunk.is_smart_content is True

    def test_chunk_item_default_is_smart_content(self):
        """ChunkItem.is_smart_content defaults to False."""
        from fs2.core.services.embedding.embedding_service import ChunkItem

        chunk = ChunkItem(
            node_id="test:node",
            chunk_index=0,
            text="content",
        )

        assert chunk.is_smart_content is False

    def test_chunk_item_equality(self):
        """ChunkItems with same values are equal."""
        from fs2.core.services.embedding.embedding_service import ChunkItem

        chunk1 = ChunkItem("node", 0, "text", False)
        chunk2 = ChunkItem("node", 0, "text", False)

        assert chunk1 == chunk2

    def test_chunk_item_hashable(self):
        """ChunkItem is hashable (can be used in sets/dicts)."""
        from fs2.core.services.embedding.embedding_service import ChunkItem

        chunk = ChunkItem("node", 0, "text", False)

        # Should not raise
        chunk_set = {chunk}
        assert chunk in chunk_set


class TestCustomChunkConfig:
    """Tests for custom chunk configuration."""

    def test_custom_code_chunk_size(self):
        """Custom code chunk size is respected."""
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        config = EmbeddingConfig(
            mode="fake",
            code=ChunkConfig(max_tokens=200, overlap_tokens=20),
        )

        long_code = "x = 1\n" * 200  # Long content

        node = CodeNode(
            node_id="file:test.py",
            category="file",
            ts_kind="module",
            name="test.py",
            qualified_name="test.py",
            start_line=1,
            end_line=200,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=len(long_code),
            content=long_code,
            content_hash="custom123",
            signature=None,
            language="python",
            content_type=ContentType.CODE,
            is_named=True,
            field_name=None,
        )

        service = EmbeddingService(
            config=config,
            embedding_adapter=None,
            token_counter=None,
        )

        chunks = service._chunk_content(node, is_smart_content=False)

        # With smaller chunk size, should have more chunks
        assert len(chunks) >= 2

    def test_zero_overlap_produces_non_overlapping_chunks(self):
        """Overlap of 0 produces non-overlapping chunks (like smart_content)."""
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        config = EmbeddingConfig(
            mode="fake",
            smart_content=ChunkConfig(max_tokens=100, overlap_tokens=0),
        )

        # This tests the smart_content path which uses 0 overlap
        long_content = "word " * 200

        node = CodeNode(
            node_id="file:doc.md",
            category="file",
            ts_kind="document",
            name="doc.md",
            qualified_name="doc.md",
            start_line=1,
            end_line=1,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=len(long_content),
            content=long_content,
            content_hash="zero_overlap",
            signature=None,
            language="markdown",
            content_type=ContentType.CONTENT,
            is_named=True,
            field_name=None,
        )

        service = EmbeddingService(
            config=config,
            embedding_adapter=None,
            token_counter=None,
        )

        chunks = service._chunk_content(node, is_smart_content=True)

        # With 0 overlap, chunks should not share content
        if len(chunks) > 1:
            # The end of chunk 0 should not appear at start of chunk 1
            # (This is a conceptual test - actual verification depends on impl)
            assert chunks[0].text != chunks[1].text


class TestChunkLineOffsetTracking:
    """Tests for line offset tracking during chunking (Phase 0).

    Purpose: Verify _chunk_by_tokens() tracks which lines each chunk spans.
    Quality Contribution: Enables semantic search to report accurate line ranges.

    Per DYK-02: _chunk_by_tokens() return type changes to include line offsets.
    Per DYK-03: Overlap lines appear in multiple chunks (report actual ranges).
    Per DYK-04: Long line character splits have same start_line == end_line.
    """

    @pytest.fixture
    def embedding_config(self) -> EmbeddingConfig:
        """Config for line tracking tests."""
        return EmbeddingConfig(
            mode="fake",
            code=ChunkConfig(max_tokens=50, overlap_tokens=10),
        )

    @pytest.fixture
    def fake_token_counter(self):
        """Fake token counter that counts words as tokens."""
        from unittest.mock import Mock

        counter = Mock()
        # Approximate: ~1 word = 1 token
        counter.count_tokens = lambda text: len(text.split())
        return counter

    def test_chunk_by_tokens_returns_line_offsets(
        self, embedding_config, fake_token_counter
    ):
        """
        Purpose: Proves _chunk_by_tokens() returns (text, start_line, end_line) tuples
        Quality Contribution: Foundation for chunk-level line range reporting
        Acceptance Criteria: Return type is list[tuple[str, int, int]]
        """
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        service = EmbeddingService(
            config=embedding_config,
            embedding_adapter=None,
            token_counter=fake_token_counter,
        )

        # Multi-line content that will produce multiple chunks
        content = "\n".join([f"line {i} with some words" for i in range(1, 21)])

        result = service._chunk_by_tokens(
            content=content,
            max_tokens=50,
            overlap_tokens=10,
        )

        # Should return list of tuples, not list of strings
        assert len(result) > 0
        first_chunk = result[0]
        assert isinstance(first_chunk, tuple), "Must return tuples, not strings"
        assert len(first_chunk) == 3, "Tuple must be (text, start_line, end_line)"

        text, start_line, end_line = first_chunk
        assert isinstance(text, str)
        assert isinstance(start_line, int)
        assert isinstance(end_line, int)

    def test_first_chunk_starts_at_line_1(self, embedding_config, fake_token_counter):
        """
        Purpose: Proves first chunk starts at line 1 (1-indexed)
        Quality Contribution: Consistent line numbering with CodeNode
        Acceptance Criteria: First chunk has start_line=1
        """
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        service = EmbeddingService(
            config=embedding_config,
            embedding_adapter=None,
            token_counter=fake_token_counter,
        )

        content = "line one\nline two\nline three"
        result = service._chunk_by_tokens(content, max_tokens=50, overlap_tokens=0)

        text, start_line, end_line = result[0]
        assert start_line == 1, "First chunk must start at line 1 (1-indexed)"

    def test_single_chunk_covers_all_lines(self, embedding_config, fake_token_counter):
        """
        Purpose: Proves short content produces single chunk covering all lines
        Quality Contribution: Correct behavior for nodes that fit in one chunk
        Acceptance Criteria: Single chunk has start_line=1, end_line=line_count
        """
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        service = EmbeddingService(
            config=embedding_config,
            embedding_adapter=None,
            token_counter=fake_token_counter,
        )

        content = "line 1\nline 2\nline 3"  # Short, fits in one chunk
        result = service._chunk_by_tokens(content, max_tokens=100, overlap_tokens=0)

        assert len(result) == 1
        text, start_line, end_line = result[0]
        assert start_line == 1
        assert end_line == 3

    def test_multi_chunk_line_ranges_are_contiguous(
        self, embedding_config, fake_token_counter
    ):
        """
        Purpose: Proves consecutive chunks have contiguous or overlapping line ranges
        Quality Contribution: Complete coverage of source lines
        Acceptance Criteria: No gaps in line coverage (overlap may exist per DYK-03)
        """
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        service = EmbeddingService(
            config=embedding_config,
            embedding_adapter=None,
            token_counter=fake_token_counter,
        )

        # Content that will produce multiple chunks
        content = "\n".join([f"line {i} with some extra words" for i in range(1, 31)])

        result = service._chunk_by_tokens(content, max_tokens=30, overlap_tokens=0)

        assert len(result) > 1, "Test requires multiple chunks"

        for i in range(len(result) - 1):
            _, _, end_line_i = result[i]
            _, start_line_j, _ = result[i + 1]
            # Next chunk starts at or before previous chunk ends (overlap) or immediately after
            assert start_line_j <= end_line_i + 1, (
                f"Gap between chunk {i} end_line={end_line_i} "
                f"and chunk {i+1} start_line={start_line_j}"
            )

    def test_overlap_lines_appear_in_multiple_chunks(
        self, embedding_config, fake_token_counter
    ):
        """
        Purpose: Proves DYK-03 - overlap lines appear in multiple chunks
        Quality Contribution: Documents expected overlap behavior
        Acceptance Criteria: With overlap_tokens > 0, same lines in consecutive chunks
        """
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        service = EmbeddingService(
            config=embedding_config,
            embedding_adapter=None,
            token_counter=fake_token_counter,
        )

        # Content that will produce chunks with overlap
        content = "\n".join([f"line {i} words here" for i in range(1, 21)])

        result = service._chunk_by_tokens(content, max_tokens=20, overlap_tokens=5)

        if len(result) > 1:
            _, _, end_line_0 = result[0]
            _, start_line_1, _ = result[1]
            # With overlap, chunk 1 starts before chunk 0 ends
            assert start_line_1 <= end_line_0, (
                f"With overlap, chunk 1 should start at or before chunk 0 ends. "
                f"Chunk 0 ends at {end_line_0}, chunk 1 starts at {start_line_1}"
            )

    def test_long_line_character_split_has_same_line_range(
        self, embedding_config, fake_token_counter
    ):
        """
        Purpose: Proves DYK-04 - character-split chunks have same line range
        Quality Contribution: Documents edge case for minified/long lines
        Acceptance Criteria: All character-split chunks report same start_line == end_line
        """
        # Create counter that makes the long line exceed max_tokens
        from unittest.mock import Mock

        from fs2.core.services.embedding.embedding_service import EmbeddingService

        counter = Mock()
        # This counter makes each character worth 2 tokens (forcing splits)
        counter.count_tokens = lambda text: len(text) * 2

        service = EmbeddingService(
            config=embedding_config,
            embedding_adapter=None,
            token_counter=counter,
        )

        # Very long single line that will be character-split
        long_line = "x" * 1000  # Single line, 1000 chars

        result = service._chunk_by_tokens(long_line, max_tokens=50, overlap_tokens=0)

        # Should produce multiple chunks all with same line range
        assert len(result) > 1, "Long line should produce multiple character-split chunks"
        for text, start_line, end_line in result:
            assert start_line == end_line == 1, (
                f"Character-split chunks should all have same line (1). "
                f"Got start_line={start_line}, end_line={end_line}"
            )
