"""Tests for CodeNode embedding fields.

Phase 1: Core Infrastructure - CodeNode embedding field tests.
Purpose: Verify CodeNode dual embedding fields work correctly.

Per DYK-1: embedding field is tuple[tuple[float, ...], ...] | None (chunk-level storage)
Per DYK-2: smart_content_embedding field added for dual embedding architecture
Per spec AC11: Embeddings stored as tuple-of-tuples for chunk-level search precision
"""

import pickle
from dataclasses import replace

import pytest

from fs2.core.utils.hash import compute_content_hash


@pytest.fixture
def sample_node():
    """Create a sample CodeNode for testing."""
    from fs2.core.models.code_node import CodeNode
    from fs2.core.models.content_type import ContentType

    return CodeNode(
        node_id="callable:src/calc.py:Calculator.add",
        category="callable",
        ts_kind="function_definition",
        name="add",
        qualified_name="Calculator.add",
        start_line=10,
        end_line=15,
        start_column=4,
        end_column=20,
        start_byte=200,
        end_byte=350,
        content="def add(self, a, b):\n    return a + b",
        content_hash=compute_content_hash("def add(self, a, b):\n    return a + b"),
        signature="def add(self, a, b):",
        language="python",
        content_type=ContentType.CODE,
        is_named=True,
        field_name="body",
    )


@pytest.fixture
def single_chunk_embedding() -> tuple[tuple[float, ...], ...]:
    """Create a single-chunk embedding (1 chunk of 1024 dimensions)."""
    return ((0.1, 0.2, 0.3) + (0.0,) * 1021,)


@pytest.fixture
def multi_chunk_embedding() -> tuple[tuple[float, ...], ...]:
    """Create a multi-chunk embedding (3 chunks of 1024 dimensions)."""
    return (
        (0.1, 0.2, 0.3) + (0.0,) * 1021,
        (0.4, 0.5, 0.6) + (0.0,) * 1021,
        (0.7, 0.8, 0.9) + (0.0,) * 1021,
    )


@pytest.mark.unit
class TestCodeNodeEmbeddingType:
    """T009: Tests for CodeNode embedding field type."""

    def test_given_embedding_when_set_then_is_tuple_of_tuples(
        self, sample_node, single_chunk_embedding
    ):
        """
        Purpose: Per spec AC11: Proves embedding is tuple[tuple[float, ...], ...]
        Quality Contribution: Ensures chunk-level storage for search precision.
        Acceptance Criteria: embedding is tuple of tuples of floats.

        Task: T009
        """
        # Arrange (fixtures provide sample_node and single_chunk_embedding)

        # Act
        updated = replace(sample_node, embedding=single_chunk_embedding)

        # Assert
        assert isinstance(updated.embedding, tuple)
        assert len(updated.embedding) == 1
        assert isinstance(updated.embedding[0], tuple)
        assert all(isinstance(f, float) for f in updated.embedding[0])

    def test_given_smart_content_embedding_when_set_then_is_tuple_of_tuples(
        self, sample_node, single_chunk_embedding
    ):
        """
        Purpose: Per DYK-2: Proves smart_content_embedding is tuple[tuple[float, ...], ...]
        Quality Contribution: Enables dual embedding architecture.
        Acceptance Criteria: smart_content_embedding is tuple of tuples of floats.

        Task: T009
        """
        # Arrange (fixtures provide sample_node and single_chunk_embedding)

        # Act
        updated = replace(sample_node, smart_content_embedding=single_chunk_embedding)

        # Assert
        assert isinstance(updated.smart_content_embedding, tuple)
        assert len(updated.smart_content_embedding) == 1
        assert isinstance(updated.smart_content_embedding[0], tuple)
        assert all(isinstance(f, float) for f in updated.smart_content_embedding[0])


@pytest.mark.unit
class TestCodeNodeEmbeddingReplace:
    """T009: Tests for CodeNode embedding field with dataclasses.replace()."""

    def test_given_node_when_replaced_with_embedding_then_original_unchanged(
        self, sample_node, single_chunk_embedding
    ):
        """
        Purpose: Proves frozen dataclass semantics - original is immutable.
        Quality Contribution: Prevents accidental mutation across async contexts.
        Acceptance Criteria: Original node still has embedding=None.

        Task: T009
        """
        # Arrange (fixtures provide sample_node and single_chunk_embedding)

        # Act
        updated = replace(sample_node, embedding=single_chunk_embedding)

        # Assert
        assert sample_node.embedding is None
        assert updated.embedding == single_chunk_embedding

    def test_given_node_when_replaced_with_smart_content_embedding_then_original_unchanged(
        self, sample_node, single_chunk_embedding
    ):
        """
        Purpose: Per DYK-2: Proves smart_content_embedding works with replace().
        Quality Contribution: Ensures immutability for dual embedding fields.
        Acceptance Criteria: Original node still has smart_content_embedding=None.

        Task: T009
        """
        # Arrange (fixtures provide sample_node and single_chunk_embedding)

        # Act
        updated = replace(sample_node, smart_content_embedding=single_chunk_embedding)

        # Assert
        assert sample_node.smart_content_embedding is None
        assert updated.smart_content_embedding == single_chunk_embedding

    def test_given_node_when_replaced_with_both_embeddings_then_both_updated(
        self, sample_node, single_chunk_embedding, multi_chunk_embedding
    ):
        """
        Purpose: Proves both embedding fields can be set together.
        Quality Contribution: Enables dual embedding architecture in one operation.
        Acceptance Criteria: Both fields have correct values.

        Task: T009
        """
        # Arrange (fixtures provide sample_node, single_chunk_embedding, multi_chunk_embedding)

        # Act
        updated = replace(
            sample_node,
            embedding=multi_chunk_embedding,
            smart_content_embedding=single_chunk_embedding,
        )

        # Assert
        assert updated.embedding == multi_chunk_embedding
        assert updated.smart_content_embedding == single_chunk_embedding


@pytest.mark.unit
class TestCodeNodeEmbeddingPickle:
    """T009: Tests for CodeNode embedding field with pickle serialization."""

    def test_given_node_with_embedding_when_pickled_then_roundtrips(
        self, sample_node, single_chunk_embedding
    ):
        """
        Purpose: Proves pickle serialization works with tuple-of-tuples.
        Quality Contribution: Enables graph persistence with embeddings.
        Acceptance Criteria: Deserialized node equals original.

        Task: T009
        """
        # Arrange
        updated = replace(sample_node, embedding=single_chunk_embedding)

        # Act
        pickled = pickle.dumps(updated)
        restored = pickle.loads(pickled)

        # Assert
        assert restored.embedding == updated.embedding
        assert restored == updated

    def test_given_node_with_both_embeddings_when_pickled_then_roundtrips(
        self, sample_node, single_chunk_embedding, multi_chunk_embedding
    ):
        """
        Purpose: Per DYK-2: Proves pickle works with dual embeddings.
        Quality Contribution: Ensures graph persistence for dual embedding architecture.
        Acceptance Criteria: Both embedding fields preserved after pickle.

        Task: T009
        """
        # Arrange
        updated = replace(
            sample_node,
            embedding=multi_chunk_embedding,
            smart_content_embedding=single_chunk_embedding,
        )

        # Act
        pickled = pickle.dumps(updated)
        restored = pickle.loads(pickled)

        # Assert
        assert restored.embedding == updated.embedding
        assert restored.smart_content_embedding == updated.smart_content_embedding
        assert restored == updated


@pytest.mark.unit
class TestCodeNodeEmbeddingChunks:
    """T009: Tests for CodeNode embedding chunk storage."""

    def test_given_single_chunk_when_stored_then_has_one_element(
        self, sample_node, single_chunk_embedding
    ):
        """
        Purpose: Proves single-chunk content stored as 1-element tuple.
        Quality Contribution: Documents single-chunk storage format.
        Acceptance Criteria: len(embedding) == 1.

        Task: T009
        """
        # Arrange (fixtures provide sample_node and single_chunk_embedding)

        # Act
        updated = replace(sample_node, embedding=single_chunk_embedding)

        # Assert
        assert len(updated.embedding) == 1
        assert isinstance(updated.embedding[0], tuple)

    def test_given_multi_chunk_when_stored_then_has_n_elements(
        self, sample_node, multi_chunk_embedding
    ):
        """
        Purpose: Proves multi-chunk content stored as n-element tuple.
        Quality Contribution: Documents multi-chunk storage format.
        Acceptance Criteria: len(embedding) == n chunks.

        Task: T009
        """
        # Arrange (fixtures provide sample_node and multi_chunk_embedding)

        # Act
        updated = replace(sample_node, embedding=multi_chunk_embedding)

        # Assert
        assert len(updated.embedding) == 3
        for chunk_embedding in updated.embedding:
            assert isinstance(chunk_embedding, tuple)
            assert len(chunk_embedding) == 1024


@pytest.mark.unit
class TestCodeNodeEmbeddingIndependence:
    """T009: Tests for independent embedding fields."""

    def test_given_only_embedding_when_set_then_smart_content_embedding_is_none(
        self, sample_node, single_chunk_embedding
    ):
        """
        Purpose: Per DYK-2: Proves embedding fields are independent.
        Quality Contribution: Enables partial embedding (code only, or smart only).
        Acceptance Criteria: Can have embedding without smart_content_embedding.

        Task: T009
        """
        # Arrange (fixtures provide sample_node and single_chunk_embedding)

        # Act
        updated = replace(sample_node, embedding=single_chunk_embedding)

        # Assert
        assert updated.embedding is not None
        assert updated.smart_content_embedding is None

    def test_given_only_smart_content_embedding_when_set_then_embedding_is_none(
        self, sample_node, single_chunk_embedding
    ):
        """
        Purpose: Per DYK-2: Proves embedding fields are independent.
        Quality Contribution: Enables partial embedding (smart only).
        Acceptance Criteria: Can have smart_content_embedding without embedding.

        Task: T009
        """
        # Arrange (fixtures provide sample_node and single_chunk_embedding)

        # Act
        updated = replace(sample_node, smart_content_embedding=single_chunk_embedding)

        # Assert
        assert updated.embedding is None
        assert updated.smart_content_embedding is not None


@pytest.mark.unit
class TestCodeNodeFactoryMethods:
    """T009: Tests for factory methods accepting embedding parameters."""

    def test_given_create_file_when_called_with_embedding_then_sets_field(
        self, single_chunk_embedding
    ):
        """
        Purpose: Proves create_file accepts embedding parameter.
        Quality Contribution: Enables embedding during node construction.
        Acceptance Criteria: Factory method accepts embedding param.

        Task: T009
        """
        from fs2.core.models.code_node import CodeNode

        # Arrange (fixture provides single_chunk_embedding)

        # Act
        node = CodeNode.create_file(
            file_path="src/main.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# main.py",
            embedding=single_chunk_embedding,
        )

        # Assert
        assert node.embedding == single_chunk_embedding

    def test_given_create_file_when_called_with_smart_content_embedding_then_sets_field(
        self, single_chunk_embedding
    ):
        """
        Purpose: Per DYK-2: Proves create_file accepts smart_content_embedding.
        Quality Contribution: Enables dual embedding during construction.
        Acceptance Criteria: Factory method accepts smart_content_embedding param.

        Task: T009
        """
        from fs2.core.models.code_node import CodeNode

        # Arrange (fixture provides single_chunk_embedding)

        # Act
        node = CodeNode.create_file(
            file_path="src/main.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# main.py",
            smart_content_embedding=single_chunk_embedding,
        )

        # Assert
        assert node.smart_content_embedding == single_chunk_embedding

    def test_given_create_callable_when_called_with_both_embeddings_then_sets_both(
        self, single_chunk_embedding, multi_chunk_embedding
    ):
        """
        Purpose: Proves create_callable accepts both embedding parameters.
        Quality Contribution: Enables dual embedding during callable construction.
        Acceptance Criteria: Factory method accepts both embedding params.

        Task: T009
        """
        from fs2.core.models.code_node import CodeNode

        # Arrange (fixtures provide single_chunk_embedding and multi_chunk_embedding)

        # Act
        node = CodeNode.create_callable(
            file_path="src/calc.py",
            language="python",
            ts_kind="function_definition",
            name="add",
            qualified_name="Calculator.add",
            start_line=10,
            end_line=15,
            start_column=4,
            end_column=20,
            start_byte=200,
            end_byte=350,
            content="def add(a, b): return a + b",
            signature="def add(a, b):",
            embedding=multi_chunk_embedding,
            smart_content_embedding=single_chunk_embedding,
        )

        # Assert
        assert node.embedding == multi_chunk_embedding
        assert node.smart_content_embedding == single_chunk_embedding

    def test_given_create_type_when_called_with_embedding_then_sets_field(
        self, single_chunk_embedding
    ):
        """
        Purpose: Proves create_type accepts embedding parameter.
        Quality Contribution: Enables embedding during type construction.
        Acceptance Criteria: Factory method accepts embedding param.

        Task: T009
        """
        from fs2.core.models.code_node import CodeNode

        # Arrange (fixture provides single_chunk_embedding)

        # Act
        node = CodeNode.create_type(
            file_path="src/models.py",
            language="python",
            ts_kind="class_definition",
            name="User",
            qualified_name="User",
            start_line=1,
            end_line=20,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=500,
            content="class User: pass",
            signature="class User:",
            embedding=single_chunk_embedding,
            smart_content_embedding=single_chunk_embedding,
        )

        # Assert
        assert node.embedding == single_chunk_embedding
        assert node.smart_content_embedding == single_chunk_embedding


@pytest.mark.unit
class TestCodeNodeChunkOffsets:
    """Phase 0: Tests for CodeNode.embedding_chunk_offsets field.

    Per Discovery 01: Field must be optional with None default for backward compatibility.
    Per DYK-05: Only raw content has chunk offsets (smart_content uses node's full range).
    """

    def test_given_node_when_created_then_chunk_offsets_default_none(self, sample_node):
        """
        Purpose: Proves backward compatibility - default is None
        Quality Contribution: Prevents breaking changes
        Acceptance Criteria: CodeNode without chunk offsets has None default
        """
        assert sample_node.embedding_chunk_offsets is None

    def test_given_chunk_offsets_when_set_then_stored_correctly(self, sample_node):
        """
        Purpose: Proves CodeNode can store chunk offset metadata
        Quality Contribution: Enables semantic search detail mode
        Acceptance Criteria: CodeNode with chunk offsets serializes correctly
        """
        offsets = ((1, 25), (20, 50), (45, 75), (70, 100))
        updated = replace(sample_node, embedding_chunk_offsets=offsets)

        assert updated.embedding_chunk_offsets == offsets
        assert len(updated.embedding_chunk_offsets) == 4

    def test_given_chunk_offsets_when_set_then_are_tuples(self, sample_node):
        """
        Purpose: Proves chunk offsets use tuple type (immutable)
        Quality Contribution: Matches embedding field patterns
        Acceptance Criteria: Offsets are tuple of tuples
        """
        offsets = ((1, 10), (11, 20), (21, 30))
        updated = replace(sample_node, embedding_chunk_offsets=offsets)

        assert isinstance(updated.embedding_chunk_offsets, tuple)
        assert all(
            isinstance(offset, tuple) for offset in updated.embedding_chunk_offsets
        )

    def test_given_node_with_offsets_when_pickle_roundtrip_then_preserved(
        self, sample_node
    ):
        """
        Purpose: Proves CodeNode with offsets can be pickled/unpickled
        Quality Contribution: Required for fixture_graph.pkl serialization
        Acceptance Criteria: Pickle round-trip preserves offsets
        """
        offsets = ((1, 25), (26, 50))
        updated = replace(sample_node, embedding_chunk_offsets=offsets)

        pickled = pickle.dumps(updated)
        restored = pickle.loads(pickled)

        assert restored.embedding_chunk_offsets == offsets

    def test_given_both_embedding_and_offsets_when_set_then_counts_match(
        self, sample_node, multi_chunk_embedding
    ):
        """
        Purpose: Proves offsets count matches embedding chunk count
        Quality Contribution: Data consistency for search results
        Acceptance Criteria: len(offsets) == len(embedding) when both present
        """
        # 3 embedding chunks
        # 3 offset tuples (must match)
        offsets = ((1, 30), (25, 60), (55, 100))

        updated = replace(
            sample_node,
            embedding=multi_chunk_embedding,
            embedding_chunk_offsets=offsets,
        )

        assert len(updated.embedding) == len(updated.embedding_chunk_offsets)

    def test_given_empty_offsets_when_set_then_is_empty_tuple(self, sample_node):
        """
        Purpose: Proves empty content produces empty offsets
        Quality Contribution: Consistent handling of edge cases
        Acceptance Criteria: Empty tuple for nodes with no chunks
        """
        updated = replace(sample_node, embedding_chunk_offsets=())

        assert updated.embedding_chunk_offsets == ()
        assert len(updated.embedding_chunk_offsets) == 0


@pytest.mark.unit
class TestCodeNodeFactoryMethodsWithOffsets:
    """Phase 0: Tests for factory methods with embedding_chunk_offsets."""

    def test_given_create_callable_when_called_with_offsets_then_sets_field(self):
        """
        Purpose: Proves create_callable factory supports new field
        Quality Contribution: Factory method parity
        Acceptance Criteria: Factory method accepts and stores offsets
        """
        from fs2.core.models.code_node import CodeNode

        offsets = ((1, 10), (11, 20))

        node = CodeNode.create_callable(
            file_path="test.py",
            language="python",
            ts_kind="function_definition",
            name="my_func",
            qualified_name="my_func",
            start_line=1,
            end_line=20,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=500,
            content="def my_func():\n    pass",
            signature="def my_func():",
            embedding_chunk_offsets=offsets,
        )

        assert node.embedding_chunk_offsets == offsets

    def test_given_create_file_when_called_with_offsets_then_sets_field(self):
        """
        Purpose: Proves create_file factory supports new field
        Quality Contribution: Factory method parity
        Acceptance Criteria: Factory method accepts and stores offsets
        """
        from fs2.core.models.code_node import CodeNode

        offsets = ((1, 100),)

        node = CodeNode.create_file(
            file_path="test.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=1000,
            start_line=1,
            end_line=100,
            content="# Test file\nprint('hello')",
            embedding_chunk_offsets=offsets,
        )

        assert node.embedding_chunk_offsets == offsets

    def test_given_factory_when_omit_offsets_then_default_is_none(self):
        """
        Purpose: Proves factory methods default to None for offsets
        Quality Contribution: Backward compatibility
        Acceptance Criteria: Omitting offsets results in None
        """
        from fs2.core.models.code_node import CodeNode

        node = CodeNode.create_callable(
            file_path="test.py",
            language="python",
            ts_kind="function_definition",
            name="my_func",
            qualified_name="my_func",
            start_line=1,
            end_line=20,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=500,
            content="def my_func():\n    pass",
            signature="def my_func():",
            # No embedding_chunk_offsets specified
        )

        assert node.embedding_chunk_offsets is None
