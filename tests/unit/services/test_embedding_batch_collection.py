"""Tests for EmbeddingService batch collection logic.

TDD RED phase: Tests for _collect_batches() method.
Per FlowSpace pattern, Per DYK-1.

Tests cover:
- Fixed-size batch splitting (100 items / batch_size=16 → 7 batches)
- ChunkItem metadata preservation
- Edge cases: empty list, fewer items than batch_size
- Last batch may be smaller than batch_size
"""

from __future__ import annotations

import pytest

from fs2.config.objects import EmbeddingConfig
from fs2.core.services.embedding.embedding_service import ChunkItem, EmbeddingService


class TestBatchCollection:
    """Tests for _collect_batches() method.

    Purpose: Validates batch splitting for API-level batching
    Quality Contribution: Ensures efficient batch sizes per API limits
    Acceptance Criteria: 100 items / batch_size=16 → 7 batches, metadata preserved
    """

    @pytest.fixture
    def config_batch_16(self) -> EmbeddingConfig:
        """Config with batch_size=16."""
        return EmbeddingConfig(mode="fake", batch_size=16)

    @pytest.fixture
    def config_batch_10(self) -> EmbeddingConfig:
        """Config with batch_size=10."""
        return EmbeddingConfig(mode="fake", batch_size=10)

    def test_100_items_batch_16_produces_7_batches(self, config_batch_16):
        """100 items with batch_size=16 → ceil(100/16) = 7 batches."""
        # Create 100 ChunkItems
        chunks = [
            ChunkItem(
                node_id=f"node:{i}",
                chunk_index=i,
                text=f"content {i}",
            )
            for i in range(100)
        ]

        service = EmbeddingService(
            config=config_batch_16,
            embedding_adapter=None,
            token_counter=None,
        )

        batches = service._collect_batches(chunks)

        assert len(batches) == 7  # ceil(100/16) = 7
        # First 6 batches should be full (16 items each)
        for i in range(6):
            assert len(batches[i]) == 16, f"Batch {i} should have 16 items"
        # Last batch should have remainder (100 - 6*16 = 4)
        assert len(batches[6]) == 4

    def test_chunk_items_preserved_in_batches(self, config_batch_16):
        """ChunkItem instances are not modified during batching."""
        chunks = [
            ChunkItem(
                node_id="node:0", chunk_index=0, text="hello", is_smart_content=False
            ),
            ChunkItem(
                node_id="node:0", chunk_index=1, text="world", is_smart_content=False
            ),
            ChunkItem(
                node_id="node:1", chunk_index=0, text="smart", is_smart_content=True
            ),
        ]

        service = EmbeddingService(
            config=config_batch_16,
            embedding_adapter=None,
            token_counter=None,
        )

        batches = service._collect_batches(chunks)

        # All items should be in one batch (3 < 16)
        assert len(batches) == 1
        assert batches[0] == chunks  # Same ChunkItem instances

    def test_empty_list_returns_empty_batches(self, config_batch_16):
        """Empty input returns empty list of batches."""
        service = EmbeddingService(
            config=config_batch_16,
            embedding_adapter=None,
            token_counter=None,
        )

        batches = service._collect_batches([])

        assert batches == []

    def test_fewer_items_than_batch_size_single_batch(self, config_batch_16):
        """Fewer items than batch_size → single batch."""
        chunks = [
            ChunkItem(node_id=f"node:{i}", chunk_index=i, text=f"text {i}")
            for i in range(5)
        ]

        service = EmbeddingService(
            config=config_batch_16,
            embedding_adapter=None,
            token_counter=None,
        )

        batches = service._collect_batches(chunks)

        assert len(batches) == 1
        assert len(batches[0]) == 5

    def test_exact_batch_size_multiple_no_remainder(self, config_batch_10):
        """Exact multiple of batch_size → no partial batch."""
        chunks = [
            ChunkItem(node_id=f"node:{i}", chunk_index=i, text=f"text {i}")
            for i in range(30)  # 3 * 10
        ]

        service = EmbeddingService(
            config=config_batch_10,
            embedding_adapter=None,
            token_counter=None,
        )

        batches = service._collect_batches(chunks)

        assert len(batches) == 3
        assert all(len(batch) == 10 for batch in batches)

    def test_mixed_smart_content_chunks_in_batches(self, config_batch_10):
        """Both regular and smart_content ChunkItems can be in same batch."""
        chunks = [
            ChunkItem(
                node_id="node:0", chunk_index=0, text="regular", is_smart_content=False
            ),
            ChunkItem(
                node_id="node:0", chunk_index=0, text="smart", is_smart_content=True
            ),
            ChunkItem(
                node_id="node:1", chunk_index=0, text="regular2", is_smart_content=False
            ),
            ChunkItem(
                node_id="node:1", chunk_index=0, text="smart2", is_smart_content=True
            ),
        ]

        service = EmbeddingService(
            config=config_batch_10,
            embedding_adapter=None,
            token_counter=None,
        )

        batches = service._collect_batches(chunks)

        assert len(batches) == 1
        # Check both types present
        is_smart_flags = [chunk.is_smart_content for chunk in batches[0]]
        assert False in is_smart_flags
        assert True in is_smart_flags


class TestBatchCollectionEdgeCases:
    """Edge case tests for batch collection."""

    @pytest.fixture
    def config(self) -> EmbeddingConfig:
        return EmbeddingConfig(mode="fake", batch_size=5)

    def test_single_item_single_batch(self, config):
        """Single item produces single batch with one item."""
        chunks = [ChunkItem(node_id="node:0", chunk_index=0, text="only")]

        service = EmbeddingService(
            config=config,
            embedding_adapter=None,
            token_counter=None,
        )

        batches = service._collect_batches(chunks)

        assert len(batches) == 1
        assert len(batches[0]) == 1

    def test_batch_size_1_produces_many_batches(self):
        """batch_size=1 produces one batch per item."""
        config = EmbeddingConfig(mode="fake", batch_size=1)
        chunks = [
            ChunkItem(node_id=f"node:{i}", chunk_index=i, text=f"text {i}")
            for i in range(5)
        ]

        service = EmbeddingService(
            config=config,
            embedding_adapter=None,
            token_counter=None,
        )

        batches = service._collect_batches(chunks)

        assert len(batches) == 5
        assert all(len(batch) == 1 for batch in batches)

    def test_order_preserved_within_batches(self, config):
        """Chunk order is preserved within each batch."""
        chunks = [
            ChunkItem(node_id="node:A", chunk_index=0, text="A0"),
            ChunkItem(node_id="node:A", chunk_index=1, text="A1"),
            ChunkItem(node_id="node:B", chunk_index=0, text="B0"),
            ChunkItem(node_id="node:B", chunk_index=1, text="B1"),
            ChunkItem(node_id="node:C", chunk_index=0, text="C0"),  # Batch boundary
            ChunkItem(node_id="node:C", chunk_index=1, text="C1"),
        ]

        service = EmbeddingService(
            config=config,
            embedding_adapter=None,
            token_counter=None,
        )

        batches = service._collect_batches(chunks)

        assert len(batches) == 2
        # First batch: A0, A1, B0, B1, C0
        assert batches[0][0].text == "A0"
        assert batches[0][4].text == "C0"
        # Second batch: C1
        assert batches[1][0].text == "C1"


class TestBatchCollectionReturnType:
    """Tests for return type of _collect_batches."""

    @pytest.fixture
    def config(self) -> EmbeddingConfig:
        return EmbeddingConfig(mode="fake", batch_size=10)

    def test_returns_list_of_lists(self, config):
        """_collect_batches returns List[List[ChunkItem]]."""
        chunks = [ChunkItem(node_id="node:0", chunk_index=0, text="test")]

        service = EmbeddingService(
            config=config,
            embedding_adapter=None,
            token_counter=None,
        )

        batches = service._collect_batches(chunks)

        assert isinstance(batches, list)
        assert all(isinstance(batch, list) for batch in batches)
        assert all(isinstance(item, ChunkItem) for batch in batches for item in batch)

    def test_batches_can_be_iterated(self, config):
        """Batches can be iterated for processing."""
        chunks = [
            ChunkItem(node_id=f"node:{i}", chunk_index=0, text=f"text {i}")
            for i in range(25)
        ]

        service = EmbeddingService(
            config=config,
            embedding_adapter=None,
            token_counter=None,
        )

        batches = service._collect_batches(chunks)

        # Should be able to iterate and extract texts for embed_batch
        for batch in batches:
            texts = [chunk.text for chunk in batch]
            assert len(texts) > 0
            assert all(isinstance(t, str) for t in texts)
