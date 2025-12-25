"""Tests for ChunkItem line offset fields (Phase 0: Chunk Offset Tracking).

Purpose: Verify ChunkItem supports optional start_line/end_line fields for
tracking which lines each chunk spans during semantic search.

Per Discovery 01: Fields must be optional with None defaults for backward compatibility.
Per DYK-02: These offsets are populated by _chunk_by_tokens() return type change.
"""

import pytest

from fs2.core.services.embedding.embedding_service import ChunkItem


class TestChunkItemLineOffsets:
    """Tests for ChunkItem with start_line/end_line fields."""

    def test_chunk_item_accepts_line_offsets(self):
        """
        Purpose: Proves ChunkItem can store line offset metadata
        Quality Contribution: Enables semantic search detail mode
        Acceptance Criteria: ChunkItem with line offsets serializes correctly
        """
        chunk = ChunkItem(
            node_id="test:node",
            chunk_index=0,
            text="line 1\nline 2\nline 3",
            is_smart_content=False,
            start_line=10,
            end_line=12,
        )
        assert chunk.start_line == 10
        assert chunk.end_line == 12

    def test_chunk_item_backward_compatible(self):
        """
        Purpose: Proves existing ChunkItem usage still works (Discovery 01)
        Quality Contribution: Prevents breaking changes
        Acceptance Criteria: ChunkItem without line offsets has None defaults
        """
        chunk = ChunkItem(
            node_id="test:node",
            chunk_index=0,
            text="content",
            is_smart_content=False,
        )
        assert chunk.start_line is None
        assert chunk.end_line is None

    def test_chunk_item_with_only_start_line(self):
        """
        Purpose: Proves partial offset specification works
        Quality Contribution: Flexibility for edge cases
        Acceptance Criteria: Only start_line specified, end_line is None
        """
        chunk = ChunkItem(
            node_id="test:node",
            chunk_index=0,
            text="content",
            is_smart_content=False,
            start_line=5,
        )
        assert chunk.start_line == 5
        assert chunk.end_line is None

    def test_chunk_item_with_only_end_line(self):
        """
        Purpose: Proves partial offset specification works
        Quality Contribution: Flexibility for edge cases
        Acceptance Criteria: Only end_line specified, start_line is None
        """
        chunk = ChunkItem(
            node_id="test:node",
            chunk_index=0,
            text="content",
            is_smart_content=False,
            end_line=10,
        )
        assert chunk.start_line is None
        assert chunk.end_line == 10

    def test_chunk_item_frozen_with_offsets(self):
        """
        Purpose: Proves frozen dataclass constraint still holds with new fields
        Quality Contribution: Immutability guarantee
        Acceptance Criteria: Cannot modify start_line/end_line after creation
        """
        chunk = ChunkItem(
            node_id="test:node",
            chunk_index=0,
            text="content",
            is_smart_content=False,
            start_line=1,
            end_line=5,
        )
        with pytest.raises(AttributeError):
            chunk.start_line = 10  # type: ignore

    def test_chunk_item_equality_with_offsets(self):
        """
        Purpose: Proves equality comparison includes line offsets
        Quality Contribution: Correct behavior in sets/dicts
        Acceptance Criteria: Same offsets → equal, different offsets → not equal
        """
        chunk1 = ChunkItem(
            node_id="test:node",
            chunk_index=0,
            text="content",
            is_smart_content=False,
            start_line=1,
            end_line=5,
        )
        chunk2 = ChunkItem(
            node_id="test:node",
            chunk_index=0,
            text="content",
            is_smart_content=False,
            start_line=1,
            end_line=5,
        )
        chunk3 = ChunkItem(
            node_id="test:node",
            chunk_index=0,
            text="content",
            is_smart_content=False,
            start_line=1,
            end_line=10,  # Different end_line
        )
        assert chunk1 == chunk2
        assert chunk1 != chunk3

    def test_chunk_item_hashable_with_offsets(self):
        """
        Purpose: Proves ChunkItem can be used in sets/as dict keys with offsets
        Quality Contribution: Usable in collections
        Acceptance Criteria: Can add to set without error
        """
        chunk = ChunkItem(
            node_id="test:node",
            chunk_index=0,
            text="content",
            is_smart_content=False,
            start_line=1,
            end_line=5,
        )
        chunk_set = {chunk}
        assert len(chunk_set) == 1

    def test_chunk_item_single_line(self):
        """
        Purpose: Proves single-line content has same start/end (DYK-04)
        Quality Contribution: Edge case for long lines that get character-split
        Acceptance Criteria: start_line == end_line is valid
        """
        chunk = ChunkItem(
            node_id="test:node",
            chunk_index=0,
            text="a very long single line of content",
            is_smart_content=False,
            start_line=42,
            end_line=42,
        )
        assert chunk.start_line == chunk.end_line == 42


class TestChunkItemSmartContentOffsets:
    """Tests for ChunkItem with smart_content and offsets."""

    def test_smart_content_chunk_can_have_none_offsets(self):
        """
        Purpose: Proves smart_content chunks don't need offsets (DYK-05)
        Quality Contribution: Documents asymmetry by design
        Acceptance Criteria: is_smart_content=True with None offsets is valid
        """
        chunk = ChunkItem(
            node_id="test:node",
            chunk_index=0,
            text="AI-generated summary of the code",
            is_smart_content=True,
            # No start_line/end_line - smart content doesn't have meaningful line offsets
        )
        assert chunk.is_smart_content is True
        assert chunk.start_line is None
        assert chunk.end_line is None
