"""Tests for ChunkMatch semantic chunk match tracking model.

Purpose: Verify ChunkMatch validation and EmbeddingField enum behavior
Quality Contribution: Ensures semantic search can track which chunk matched
Acceptance Criteria: Per Discovery 05 (chunked embeddings), DYK-03 (EmbeddingField enum)

Per Phase 1 tasks.md: TDD approach - write tests FIRST, then implement
"""

from dataclasses import FrozenInstanceError

import pytest


class TestEmbeddingFieldEnum:
    """Tests for EmbeddingField enum values."""

    def test_embedding_field_has_embedding_value(self):
        """
        Purpose: Proves EMBEDDING value exists
        Quality Contribution: Type safety for raw content embeddings
        Acceptance Criteria: EMBEDDING is a valid enum value
        """
        from fs2.core.models.search import EmbeddingField

        assert EmbeddingField.EMBEDDING.value == "embedding"

    def test_embedding_field_has_smart_content_value(self):
        """
        Purpose: Proves SMART_CONTENT value exists
        Quality Contribution: Type safety for AI-generated content embeddings
        Acceptance Criteria: SMART_CONTENT is a valid enum value
        """
        from fs2.core.models.search import EmbeddingField

        assert EmbeddingField.SMART_CONTENT.value == "smart_content"

    def test_embedding_field_has_exactly_two_values(self):
        """
        Purpose: Proves enum is limited to expected values
        Quality Contribution: Prevents invalid field types
        Acceptance Criteria: Exactly 2 enum members
        """
        from fs2.core.models.search import EmbeddingField

        assert len(list(EmbeddingField)) == 2


class TestChunkMatchCreation:
    """Tests for ChunkMatch creation and field values."""

    def test_chunk_match_with_embedding_field(self):
        """
        Purpose: Proves ChunkMatch accepts EMBEDDING field
        Quality Contribution: Validates raw content matching
        Acceptance Criteria: ChunkMatch created successfully
        """
        from fs2.core.models.search import ChunkMatch, EmbeddingField

        match = ChunkMatch(
            field=EmbeddingField.EMBEDDING,
            chunk_index=0,
            score=0.85,
        )
        assert match.field == EmbeddingField.EMBEDDING
        assert match.chunk_index == 0
        assert match.score == 0.85

    def test_chunk_match_with_smart_content_field(self):
        """
        Purpose: Proves ChunkMatch accepts SMART_CONTENT field
        Quality Contribution: Validates AI summary matching
        Acceptance Criteria: ChunkMatch created successfully
        """
        from fs2.core.models.search import ChunkMatch, EmbeddingField

        match = ChunkMatch(
            field=EmbeddingField.SMART_CONTENT,
            chunk_index=1,
            score=0.92,
        )
        assert match.field == EmbeddingField.SMART_CONTENT
        assert match.chunk_index == 1
        assert match.score == 0.92


class TestChunkMatchValidation:
    """Tests for ChunkMatch validation behavior."""

    def test_negative_chunk_index_raises_error(self):
        """
        Purpose: Proves negative chunk_index rejected
        Quality Contribution: Prevents invalid array indices
        Acceptance Criteria: ValueError raised
        """
        from fs2.core.models.search import ChunkMatch, EmbeddingField

        with pytest.raises(ValueError, match="chunk_index"):
            ChunkMatch(
                field=EmbeddingField.EMBEDDING,
                chunk_index=-1,
                score=0.85,
            )

    def test_score_below_zero_raises_error(self):
        """
        Purpose: Proves negative score rejected
        Quality Contribution: Ensures valid similarity range
        Acceptance Criteria: ValueError raised
        """
        from fs2.core.models.search import ChunkMatch, EmbeddingField

        with pytest.raises(ValueError, match="score"):
            ChunkMatch(
                field=EmbeddingField.EMBEDDING,
                chunk_index=0,
                score=-0.1,
            )

    def test_score_above_one_raises_error(self):
        """
        Purpose: Proves score > 1.0 rejected
        Quality Contribution: Ensures valid similarity range
        Acceptance Criteria: ValueError raised
        """
        from fs2.core.models.search import ChunkMatch, EmbeddingField

        with pytest.raises(ValueError, match="score"):
            ChunkMatch(
                field=EmbeddingField.EMBEDDING,
                chunk_index=0,
                score=1.5,
            )

    def test_string_field_rejected(self):
        """
        Purpose: Proves string field rejected (must use enum)
        Quality Contribution: Type safety enforcement (DYK-03)
        Acceptance Criteria: TypeError raised
        """
        from fs2.core.models.search import ChunkMatch

        with pytest.raises((TypeError, ValueError)):
            ChunkMatch(
                field="embedding",  # type: ignore
                chunk_index=0,
                score=0.85,
            )


class TestChunkMatchBoundaries:
    """Tests for ChunkMatch boundary values."""

    def test_chunk_index_zero_accepted(self):
        """
        Purpose: Proves zero chunk_index is valid (first chunk)
        Quality Contribution: Documents valid range
        Acceptance Criteria: ChunkMatch created successfully
        """
        from fs2.core.models.search import ChunkMatch, EmbeddingField

        match = ChunkMatch(
            field=EmbeddingField.EMBEDDING,
            chunk_index=0,
            score=0.85,
        )
        assert match.chunk_index == 0

    def test_high_chunk_index_accepted(self):
        """
        Purpose: Proves high chunk_index values are valid
        Quality Contribution: Supports large nodes with many chunks
        Acceptance Criteria: ChunkMatch created for high index
        """
        from fs2.core.models.search import ChunkMatch, EmbeddingField

        match = ChunkMatch(
            field=EmbeddingField.EMBEDDING,
            chunk_index=100,
            score=0.85,
        )
        assert match.chunk_index == 100

    def test_score_zero_accepted(self):
        """
        Purpose: Proves score=0.0 is valid
        Quality Contribution: Documents valid range
        Acceptance Criteria: ChunkMatch created successfully
        """
        from fs2.core.models.search import ChunkMatch, EmbeddingField

        match = ChunkMatch(
            field=EmbeddingField.EMBEDDING,
            chunk_index=0,
            score=0.0,
        )
        assert match.score == 0.0

    def test_score_one_accepted(self):
        """
        Purpose: Proves score=1.0 is valid (perfect match)
        Quality Contribution: Documents valid range
        Acceptance Criteria: ChunkMatch created successfully
        """
        from fs2.core.models.search import ChunkMatch, EmbeddingField

        match = ChunkMatch(
            field=EmbeddingField.EMBEDDING,
            chunk_index=0,
            score=1.0,
        )
        assert match.score == 1.0


class TestChunkMatchImmutability:
    """Tests for ChunkMatch frozen immutability."""

    def test_chunk_match_is_frozen(self):
        """
        Purpose: Proves ChunkMatch cannot be mutated
        Quality Contribution: Ensures thread safety
        Acceptance Criteria: FrozenInstanceError on modification
        """
        from fs2.core.models.search import ChunkMatch, EmbeddingField

        match = ChunkMatch(
            field=EmbeddingField.EMBEDDING,
            chunk_index=0,
            score=0.85,
        )
        with pytest.raises(FrozenInstanceError):
            match.score = 0.99  # type: ignore

    def test_chunk_match_field_cannot_be_modified(self):
        """
        Purpose: Proves field cannot be mutated
        Quality Contribution: Ensures immutability contract
        Acceptance Criteria: FrozenInstanceError on modification
        """
        from fs2.core.models.search import ChunkMatch, EmbeddingField

        match = ChunkMatch(
            field=EmbeddingField.EMBEDDING,
            chunk_index=0,
            score=0.85,
        )
        with pytest.raises(FrozenInstanceError):
            match.field = EmbeddingField.SMART_CONTENT  # type: ignore

    def test_chunk_match_chunk_index_cannot_be_modified(self):
        """
        Purpose: Proves chunk_index cannot be mutated
        Quality Contribution: Ensures immutability contract
        Acceptance Criteria: FrozenInstanceError on modification
        """
        from fs2.core.models.search import ChunkMatch, EmbeddingField

        match = ChunkMatch(
            field=EmbeddingField.EMBEDDING,
            chunk_index=0,
            score=0.85,
        )
        with pytest.raises(FrozenInstanceError):
            match.chunk_index = 5  # type: ignore
