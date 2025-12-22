"""Tests for EmbeddingService process_batch() method.

TDD RED phase: Tests for the main batch processing workflow.
Per Finding 02, Per DYK-1, DYK-2, DYK-4.

Tests cover:
- API-level batching (embed_batch called once per batch)
- ChunkItem reassembly back to nodes
- Dual embedding (embedding + smart_content_embedding)
- Tuple conversion (list → tuple)
- Stateless processing (CD10)
- Progress callback
- Statistics collection
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from fs2.config.objects import ChunkConfig, EmbeddingConfig
from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter
from fs2.core.models.code_node import CodeNode
from fs2.core.models.content_type import ContentType
from fs2.core.services.embedding.embedding_service import EmbeddingService


class TestProcessBatch:
    """Tests for process_batch() orchestration method.

    Purpose: Validates end-to-end batch processing workflow
    Quality Contribution: Ensures correct embedding generation and reassembly
    """

    @pytest.fixture
    def config(self) -> EmbeddingConfig:
        """Config with small batch size for testing."""
        return EmbeddingConfig(
            mode="fake",
            batch_size=5,
            code=ChunkConfig(max_tokens=400, overlap_tokens=50),
            documentation=ChunkConfig(max_tokens=800, overlap_tokens=120),
            smart_content=ChunkConfig(max_tokens=8000, overlap_tokens=0),
        )

    @pytest.fixture
    def fake_adapter(self) -> FakeEmbeddingAdapter:
        """Fake embedding adapter for testing."""
        adapter = FakeEmbeddingAdapter(dimensions=1024)
        # Set a fixed response for predictable tests
        adapter.set_response([0.1] * 1024)
        return adapter

    @pytest.fixture
    def sample_nodes(self) -> list[CodeNode]:
        """Sample nodes for testing."""
        return [
            CodeNode(
                node_id="callable:test.py:func1",
                category="callable",
                ts_kind="function_definition",
                name="func1",
                qualified_name="func1",
                start_line=1,
                end_line=3,
                start_column=0,
                end_column=0,
                start_byte=0,
                end_byte=50,
                content="def func1(): pass",
                content_hash="hash1",
                signature="def func1():",
                language="python",
                content_type=ContentType.CODE,
                is_named=True,
                field_name=None,
                embedding=None,
                smart_content_embedding=None,
            ),
            CodeNode(
                node_id="callable:test.py:func2",
                category="callable",
                ts_kind="function_definition",
                name="func2",
                qualified_name="func2",
                start_line=5,
                end_line=7,
                start_column=0,
                end_column=0,
                start_byte=60,
                end_byte=110,
                content="def func2(): return 1",
                content_hash="hash2",
                signature="def func2():",
                language="python",
                content_type=ContentType.CODE,
                is_named=True,
                field_name=None,
                embedding=None,
                smart_content_embedding=None,
            ),
        ]

    @pytest.mark.asyncio
    async def test_process_batch_returns_updated_nodes(
        self, config, fake_adapter, sample_nodes
    ):
        """process_batch returns nodes with embedding field populated."""
        service = EmbeddingService(
            config=config,
            embedding_adapter=fake_adapter,
            token_counter=None,
        )

        result = await service.process_batch(sample_nodes)

        assert "results" in result
        assert len(result["results"]) == 2

        # Each node should have embedding populated
        for node_id, node in result["results"].items():
            assert node.embedding is not None
            assert len(node.embedding) > 0
            # Embedding should be tuple of tuples (per DYK-4)
            assert isinstance(node.embedding, tuple)
            assert isinstance(node.embedding[0], tuple)

    @pytest.mark.asyncio
    async def test_embed_batch_called_correct_number_of_times(
        self, config, fake_adapter, sample_nodes
    ):
        """embed_batch is called once per batch, not per item."""
        service = EmbeddingService(
            config=config,
            embedding_adapter=fake_adapter,
            token_counter=None,
        )

        await service.process_batch(sample_nodes)

        # With 2 nodes and batch_size=5, should be 1 batch call
        batch_calls = [c for c in fake_adapter.call_history if "texts" in c]
        assert len(batch_calls) == 1

    @pytest.mark.asyncio
    async def test_process_batch_skips_nodes_with_embeddings(
        self, config, fake_adapter
    ):
        """Nodes that already have embeddings are skipped."""
        node_with_embedding = CodeNode(
            node_id="callable:test.py:done",
            category="callable",
            ts_kind="function_definition",
            name="done",
            qualified_name="done",
            start_line=1,
            end_line=1,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=20,
            content="def done(): pass",
            content_hash="done_hash",
            signature="def done():",
            language="python",
            content_type=ContentType.CODE,
            is_named=True,
            field_name=None,
            embedding=((0.5,) * 1024,),  # Already has embedding
            embedding_hash="done_hash",  # Matches content_hash - embedding is fresh
            smart_content_embedding=None,
            smart_content=None,
        )

        service = EmbeddingService(
            config=config,
            embedding_adapter=fake_adapter,
            token_counter=None,
        )

        result = await service.process_batch([node_with_embedding])

        assert result["skipped"] == 1
        assert result["processed"] == 0
        assert len(fake_adapter.call_history) == 0  # No API calls

    @pytest.mark.asyncio
    async def test_process_batch_returns_stats(
        self, config, fake_adapter, sample_nodes
    ):
        """process_batch returns statistics dict."""
        service = EmbeddingService(
            config=config,
            embedding_adapter=fake_adapter,
            token_counter=None,
        )

        result = await service.process_batch(sample_nodes)

        assert "processed" in result
        assert "skipped" in result
        assert "errors" in result
        assert "total" in result
        assert "results" in result

        assert result["total"] == 2
        assert result["processed"] == 2
        assert result["skipped"] == 0

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty_result(self, config, fake_adapter):
        """Empty node list returns empty result with zero stats."""
        service = EmbeddingService(
            config=config,
            embedding_adapter=fake_adapter,
            token_counter=None,
        )

        result = await service.process_batch([])

        assert result["total"] == 0
        assert result["processed"] == 0
        assert result["skipped"] == 0
        assert result["results"] == {}


class TestDualEmbedding:
    """Tests for dual embedding (raw content + smart_content).

    Per DYK-2: Both embedding and smart_content_embedding fields populated.
    """

    @pytest.fixture
    def config(self) -> EmbeddingConfig:
        return EmbeddingConfig(
            mode="fake",
            batch_size=10,
            code=ChunkConfig(max_tokens=400, overlap_tokens=50),
            smart_content=ChunkConfig(max_tokens=8000, overlap_tokens=0),
        )

    @pytest.fixture
    def fake_adapter(self) -> FakeEmbeddingAdapter:
        adapter = FakeEmbeddingAdapter(dimensions=1024)
        adapter.set_response([0.2] * 1024)
        return adapter

    @pytest.mark.asyncio
    async def test_node_with_smart_content_gets_both_embeddings(
        self, config, fake_adapter
    ):
        """Node with smart_content gets both embedding fields populated."""
        node = CodeNode(
            node_id="callable:test.py:smart_func",
            category="callable",
            ts_kind="function_definition",
            name="smart_func",
            qualified_name="smart_func",
            start_line=1,
            end_line=5,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=100,
            content="def smart_func():\n    return 42",
            content_hash="smart_hash",
            signature="def smart_func():",
            language="python",
            content_type=ContentType.CODE,
            is_named=True,
            field_name=None,
            embedding=None,
            smart_content="A function that returns the answer to life.",
            smart_content_embedding=None,
        )

        service = EmbeddingService(
            config=config,
            embedding_adapter=fake_adapter,
            token_counter=None,
        )

        result = await service.process_batch([node])

        updated_node = result["results"]["callable:test.py:smart_func"]

        # Both embedding fields should be populated
        assert updated_node.embedding is not None
        assert updated_node.smart_content_embedding is not None

        # Both should be tuple of tuples
        assert isinstance(updated_node.embedding, tuple)
        assert isinstance(updated_node.smart_content_embedding, tuple)

    @pytest.mark.asyncio
    async def test_node_without_smart_content_gets_only_raw_embedding(
        self, config, fake_adapter
    ):
        """Node without smart_content only gets raw embedding."""
        node = CodeNode(
            node_id="callable:test.py:simple",
            category="callable",
            ts_kind="function_definition",
            name="simple",
            qualified_name="simple",
            start_line=1,
            end_line=1,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=20,
            content="def simple(): pass",
            content_hash="simple_hash",
            signature="def simple():",
            language="python",
            content_type=ContentType.CODE,
            is_named=True,
            field_name=None,
            embedding=None,
            smart_content=None,  # No smart content
            smart_content_embedding=None,
        )

        service = EmbeddingService(
            config=config,
            embedding_adapter=fake_adapter,
            token_counter=None,
        )

        result = await service.process_batch([node])

        updated_node = result["results"]["callable:test.py:simple"]

        assert updated_node.embedding is not None
        assert updated_node.smart_content_embedding is None  # Not populated


class TestTupleConversion:
    """Tests for DYK-4: list → tuple conversion.

    API returns list[list[float]], CodeNode stores tuple[tuple[float, ...], ...].
    """

    @pytest.fixture
    def config(self) -> EmbeddingConfig:
        return EmbeddingConfig(mode="fake", batch_size=5)

    @pytest.fixture
    def fake_adapter(self) -> FakeEmbeddingAdapter:
        adapter = FakeEmbeddingAdapter(dimensions=4)
        adapter.set_response([0.1, 0.2, 0.3, 0.4])
        return adapter

    @pytest.mark.asyncio
    async def test_embedding_stored_as_nested_tuple(self, config, fake_adapter):
        """Embeddings are stored as tuple[tuple[float, ...], ...]."""
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
            content_hash="tuple_test",
            signature=None,
            language="python",
            content_type=ContentType.CODE,
            is_named=True,
            field_name=None,
            embedding=None,
            smart_content_embedding=None,
        )

        service = EmbeddingService(
            config=config,
            embedding_adapter=fake_adapter,
            token_counter=None,
        )

        result = await service.process_batch([node])
        updated_node = result["results"]["file:test.py"]

        # Type check
        assert isinstance(updated_node.embedding, tuple)
        assert isinstance(updated_node.embedding[0], tuple)
        assert isinstance(updated_node.embedding[0][0], float)

        # Values check
        assert updated_node.embedding[0] == (0.1, 0.2, 0.3, 0.4)


class TestStatelessProcessing:
    """Tests for CD10: Stateless service design.

    Batch processing uses local variables, no instance mutation.
    """

    @pytest.fixture
    def config(self) -> EmbeddingConfig:
        return EmbeddingConfig(mode="fake", batch_size=5)

    @pytest.fixture
    def fake_adapter(self) -> FakeEmbeddingAdapter:
        adapter = FakeEmbeddingAdapter(dimensions=4)
        adapter.set_response([0.1, 0.2, 0.3, 0.4])
        return adapter

    @pytest.mark.asyncio
    async def test_concurrent_batches_dont_interfere(self, config, fake_adapter):
        """Multiple concurrent process_batch calls don't interfere."""
        import asyncio

        nodes1 = [
            CodeNode(
                node_id=f"file:batch1_{i}.py",
                category="file",
                ts_kind="module",
                name=f"batch1_{i}.py",
                qualified_name=f"batch1_{i}.py",
                start_line=1,
                end_line=1,
                start_column=0,
                end_column=0,
                start_byte=0,
                end_byte=10,
                content=f"x_{i} = 1",
                content_hash=f"hash1_{i}",
                signature=None,
                language="python",
                content_type=ContentType.CODE,
                is_named=True,
                field_name=None,
            )
            for i in range(3)
        ]

        nodes2 = [
            CodeNode(
                node_id=f"file:batch2_{i}.py",
                category="file",
                ts_kind="module",
                name=f"batch2_{i}.py",
                qualified_name=f"batch2_{i}.py",
                start_line=1,
                end_line=1,
                start_column=0,
                end_column=0,
                start_byte=0,
                end_byte=10,
                content=f"y_{i} = 2",
                content_hash=f"hash2_{i}",
                signature=None,
                language="python",
                content_type=ContentType.CODE,
                is_named=True,
                field_name=None,
            )
            for i in range(3)
        ]

        service = EmbeddingService(
            config=config,
            embedding_adapter=fake_adapter,
            token_counter=None,
        )

        # Run concurrently
        result1, result2 = await asyncio.gather(
            service.process_batch(nodes1),
            service.process_batch(nodes2),
        )

        # Both should succeed with correct counts
        assert result1["processed"] == 3
        assert result2["processed"] == 3

        # Results should not cross-contaminate
        for node_id in result1["results"]:
            assert "batch1" in node_id
        for node_id in result2["results"]:
            assert "batch2" in node_id


class TestProgressCallback:
    """Tests for progress callback during batch processing."""

    @pytest.fixture
    def config(self) -> EmbeddingConfig:
        return EmbeddingConfig(mode="fake", batch_size=2)

    @pytest.fixture
    def fake_adapter(self) -> FakeEmbeddingAdapter:
        adapter = FakeEmbeddingAdapter(dimensions=4)
        adapter.set_response([0.1, 0.2, 0.3, 0.4])
        return adapter

    @pytest.mark.asyncio
    async def test_progress_callback_called(self, config, fake_adapter):
        """Progress callback is called during processing."""
        nodes = [
            CodeNode(
                node_id=f"file:prog_{i}.py",
                category="file",
                ts_kind="module",
                name=f"prog_{i}.py",
                qualified_name=f"prog_{i}.py",
                start_line=1,
                end_line=1,
                start_column=0,
                end_column=0,
                start_byte=0,
                end_byte=10,
                content=f"x_{i} = 1",
                content_hash=f"prog_hash_{i}",
                signature=None,
                language="python",
                content_type=ContentType.CODE,
                is_named=True,
                field_name=None,
            )
            for i in range(5)
        ]

        callback_calls = []

        def progress_callback(processed: int, total: int, skipped: int):
            callback_calls.append((processed, total, skipped))

        service = EmbeddingService(
            config=config,
            embedding_adapter=fake_adapter,
            token_counter=None,
        )

        await service.process_batch(nodes, progress_callback=progress_callback)

        # Callback should have been called at least once
        assert len(callback_calls) > 0


class TestFrozenNodeImmutability:
    """Tests for CD03: Frozen dataclass immutability.

    Original nodes are not modified; new instances are returned.
    """

    @pytest.fixture
    def config(self) -> EmbeddingConfig:
        return EmbeddingConfig(mode="fake", batch_size=5)

    @pytest.fixture
    def fake_adapter(self) -> FakeEmbeddingAdapter:
        adapter = FakeEmbeddingAdapter(dimensions=4)
        adapter.set_response([0.1, 0.2, 0.3, 0.4])
        return adapter

    @pytest.mark.asyncio
    async def test_original_nodes_unchanged(self, config, fake_adapter):
        """Original input nodes are not modified."""
        original_node = CodeNode(
            node_id="file:original.py",
            category="file",
            ts_kind="module",
            name="original.py",
            qualified_name="original.py",
            start_line=1,
            end_line=1,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=10,
            content="x = 1",
            content_hash="original_hash",
            signature=None,
            language="python",
            content_type=ContentType.CODE,
            is_named=True,
            field_name=None,
            embedding=None,
        )

        service = EmbeddingService(
            config=config,
            embedding_adapter=fake_adapter,
            token_counter=None,
        )

        await service.process_batch([original_node])

        # Original node should still have None embedding
        assert original_node.embedding is None
