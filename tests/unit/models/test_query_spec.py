"""Tests for QuerySpec search query specification model.

Purpose: Verify QuerySpec validation and immutability behavior
Quality Contribution: Ensures search queries are well-formed before execution
Acceptance Criteria: AC10 (empty pattern rejection), frozen immutability

Per Phase 1 tasks.md: TDD approach - write tests FIRST, then implement
"""

from dataclasses import FrozenInstanceError

import pytest


class TestQuerySpecValidation:
    """Tests for QuerySpec validation behavior."""

    def test_empty_pattern_raises_validation_error(self):
        """
        Purpose: Proves empty patterns are rejected (AC10)
        Quality Contribution: Prevents meaningless searches
        Acceptance Criteria: ValueError with clear message
        """
        from fs2.core.models.search import QuerySpec, SearchMode

        with pytest.raises(ValueError, match="[Pp]attern cannot be empty"):
            QuerySpec(pattern="", mode=SearchMode.TEXT)

    def test_whitespace_pattern_raises_validation_error(self):
        """
        Purpose: Proves whitespace-only patterns rejected
        Quality Contribution: Prevents meaningless searches
        Acceptance Criteria: ValueError raised
        """
        from fs2.core.models.search import QuerySpec, SearchMode

        with pytest.raises(ValueError, match="[Pp]attern cannot be empty"):
            QuerySpec(pattern="   ", mode=SearchMode.TEXT)

    def test_tab_only_pattern_raises_validation_error(self):
        """
        Purpose: Proves tab-only patterns rejected
        Quality Contribution: Handles edge case whitespace
        Acceptance Criteria: ValueError raised
        """
        from fs2.core.models.search import QuerySpec, SearchMode

        with pytest.raises(ValueError, match="[Pp]attern cannot be empty"):
            QuerySpec(pattern="\t\t", mode=SearchMode.TEXT)

    def test_newline_only_pattern_raises_validation_error(self):
        """
        Purpose: Proves newline-only patterns rejected
        Quality Contribution: Handles edge case whitespace
        Acceptance Criteria: ValueError raised
        """
        from fs2.core.models.search import QuerySpec, SearchMode

        with pytest.raises(ValueError, match="[Pp]attern cannot be empty"):
            QuerySpec(pattern="\n\n", mode=SearchMode.TEXT)


class TestQuerySpecDefaults:
    """Tests for QuerySpec default values."""

    def test_valid_spec_with_defaults(self):
        """
        Purpose: Proves default values applied correctly
        Quality Contribution: Documents expected defaults
        Acceptance Criteria: limit=20, min_similarity=0.25 (per DYK-P3-04)
        """
        from fs2.core.models.search import QuerySpec, SearchMode

        spec = QuerySpec(pattern="test", mode=SearchMode.TEXT)
        assert spec.limit == 20
        assert spec.min_similarity == 0.25

    def test_pattern_preserved_exactly(self):
        """
        Purpose: Proves pattern stored without modification
        Quality Contribution: Ensures search precision
        Acceptance Criteria: Pattern identical to input
        """
        from fs2.core.models.search import QuerySpec, SearchMode

        pattern = "class.*Service"
        spec = QuerySpec(pattern=pattern, mode=SearchMode.REGEX)
        assert spec.pattern == pattern

    def test_mode_preserved(self):
        """
        Purpose: Proves mode stored correctly
        Quality Contribution: Ensures mode routing works
        Acceptance Criteria: Mode matches input
        """
        from fs2.core.models.search import QuerySpec, SearchMode

        for mode in SearchMode:
            spec = QuerySpec(pattern="test", mode=mode)
            assert spec.mode == mode


class TestQuerySpecCustomValues:
    """Tests for QuerySpec with custom values."""

    def test_custom_limit_accepted(self):
        """
        Purpose: Proves custom limit is accepted
        Quality Contribution: Enables result count control
        Acceptance Criteria: limit matches input
        """
        from fs2.core.models.search import QuerySpec, SearchMode

        spec = QuerySpec(pattern="test", mode=SearchMode.TEXT, limit=50)
        assert spec.limit == 50

    def test_custom_min_similarity_accepted(self):
        """
        Purpose: Proves custom min_similarity is accepted
        Quality Contribution: Enables threshold tuning for semantic search
        Acceptance Criteria: min_similarity matches input
        """
        from fs2.core.models.search import QuerySpec, SearchMode

        spec = QuerySpec(pattern="test", mode=SearchMode.SEMANTIC, min_similarity=0.8)
        assert spec.min_similarity == 0.8

    def test_limit_zero_raises_error(self):
        """
        Purpose: Proves zero limit is rejected
        Quality Contribution: Prevents useless queries
        Acceptance Criteria: ValueError raised
        """
        from fs2.core.models.search import QuerySpec, SearchMode

        with pytest.raises(ValueError, match="[Ll]imit must be"):
            QuerySpec(pattern="test", mode=SearchMode.TEXT, limit=0)

    def test_negative_limit_raises_error(self):
        """
        Purpose: Proves negative limit is rejected
        Quality Contribution: Prevents invalid queries
        Acceptance Criteria: ValueError raised
        """
        from fs2.core.models.search import QuerySpec, SearchMode

        with pytest.raises(ValueError, match="[Ll]imit must be"):
            QuerySpec(pattern="test", mode=SearchMode.TEXT, limit=-5)

    def test_min_similarity_below_zero_raises_error(self):
        """
        Purpose: Proves negative similarity rejected
        Quality Contribution: Enforces valid range
        Acceptance Criteria: ValueError raised
        """
        from fs2.core.models.search import QuerySpec, SearchMode

        with pytest.raises(ValueError, match="min_similarity"):
            QuerySpec(pattern="test", mode=SearchMode.SEMANTIC, min_similarity=-0.1)

    def test_min_similarity_above_one_raises_error(self):
        """
        Purpose: Proves similarity > 1.0 rejected
        Quality Contribution: Enforces valid range
        Acceptance Criteria: ValueError raised
        """
        from fs2.core.models.search import QuerySpec, SearchMode

        with pytest.raises(ValueError, match="min_similarity"):
            QuerySpec(pattern="test", mode=SearchMode.SEMANTIC, min_similarity=1.5)


class TestQuerySpecImmutability:
    """Tests for QuerySpec frozen immutability."""

    def test_query_spec_is_frozen(self):
        """
        Purpose: Proves QuerySpec cannot be mutated
        Quality Contribution: Ensures thread safety and predictable behavior
        Acceptance Criteria: FrozenInstanceError on attribute assignment
        """
        from fs2.core.models.search import QuerySpec, SearchMode

        spec = QuerySpec(pattern="test", mode=SearchMode.TEXT)
        with pytest.raises(FrozenInstanceError):
            spec.pattern = "modified"  # type: ignore

    def test_query_spec_limit_cannot_be_modified(self):
        """
        Purpose: Proves limit cannot be mutated after creation
        Quality Contribution: Ensures immutability contract
        Acceptance Criteria: FrozenInstanceError on limit modification
        """
        from fs2.core.models.search import QuerySpec, SearchMode

        spec = QuerySpec(pattern="test", mode=SearchMode.TEXT)
        with pytest.raises(FrozenInstanceError):
            spec.limit = 100  # type: ignore

    def test_query_spec_mode_cannot_be_modified(self):
        """
        Purpose: Proves mode cannot be mutated after creation
        Quality Contribution: Ensures immutability contract
        Acceptance Criteria: FrozenInstanceError on mode modification
        """
        from fs2.core.models.search import QuerySpec, SearchMode

        spec = QuerySpec(pattern="test", mode=SearchMode.TEXT)
        with pytest.raises(FrozenInstanceError):
            spec.mode = SearchMode.REGEX  # type: ignore


class TestQuerySpecModeEnum:
    """Tests for SearchMode enum integration with QuerySpec."""

    def test_all_search_modes_valid(self):
        """
        Purpose: Proves all SearchMode values create valid specs
        Quality Contribution: Ensures complete mode coverage
        Acceptance Criteria: All four modes work
        """
        from fs2.core.models.search import QuerySpec, SearchMode

        modes = [SearchMode.TEXT, SearchMode.REGEX, SearchMode.SEMANTIC, SearchMode.AUTO]
        for mode in modes:
            spec = QuerySpec(pattern="test", mode=mode)
            assert spec.mode == mode

    def test_invalid_mode_string_raises_error(self):
        """
        Purpose: Proves string modes rejected (must use enum)
        Quality Contribution: Type safety enforcement
        Acceptance Criteria: TypeError or ValueError raised
        """
        from fs2.core.models.search import QuerySpec

        # When using @dataclass, passing wrong type should fail validation
        # The exact error depends on implementation, but it should fail
        with pytest.raises((TypeError, ValueError)):
            QuerySpec(pattern="test", mode="text")  # type: ignore


# ============================================================================
# Phase 5 T000: Offset Field Tests (Pagination Support)
# ============================================================================


class TestQuerySpecOffset:
    """Tests for QuerySpec offset field (pagination support).

    Per Phase 5 tasks.md T000: TDD tests for offset field.
    BC-04: --offset flag for pagination with default 0.
    """

    def test_offset_default_0(self):
        """
        Purpose: Proves offset defaults to 0 for no pagination
        Quality Contribution: Documents expected default
        Acceptance Criteria: QuerySpec.offset == 0 when not specified
        """
        from fs2.core.models.search import QuerySpec, SearchMode

        spec = QuerySpec(pattern="test", mode=SearchMode.TEXT)
        assert spec.offset == 0

    def test_offset_custom_value(self):
        """
        Purpose: Proves custom offset values are accepted
        Quality Contribution: Enables pagination (skip first N results)
        Acceptance Criteria: offset matches input value
        """
        from fs2.core.models.search import QuerySpec, SearchMode

        spec = QuerySpec(pattern="test", mode=SearchMode.TEXT, offset=10)
        assert spec.offset == 10

    def test_offset_large_value(self):
        """
        Purpose: Proves large offset values are accepted
        Quality Contribution: Handles deep pagination
        Acceptance Criteria: Large offset accepted without error
        """
        from fs2.core.models.search import QuerySpec, SearchMode

        spec = QuerySpec(pattern="test", mode=SearchMode.TEXT, offset=1000)
        assert spec.offset == 1000

    def test_offset_negative_rejected(self):
        """
        Purpose: Proves negative offset values are rejected
        Quality Contribution: Prevents invalid pagination
        Acceptance Criteria: ValueError raised for negative offset
        """
        from fs2.core.models.search import QuerySpec, SearchMode

        with pytest.raises(ValueError, match="[Oo]ffset"):
            QuerySpec(pattern="test", mode=SearchMode.TEXT, offset=-1)

    def test_offset_zero_accepted(self):
        """
        Purpose: Proves zero is a valid offset (no skip)
        Quality Contribution: Boundary condition validation
        Acceptance Criteria: offset=0 accepted without error
        """
        from fs2.core.models.search import QuerySpec, SearchMode

        spec = QuerySpec(pattern="test", mode=SearchMode.TEXT, offset=0)
        assert spec.offset == 0

    def test_offset_immutable(self):
        """
        Purpose: Proves offset cannot be modified after creation
        Quality Contribution: Ensures immutability contract
        Acceptance Criteria: FrozenInstanceError on offset modification
        """
        from fs2.core.models.search import QuerySpec, SearchMode

        spec = QuerySpec(pattern="test", mode=SearchMode.TEXT, offset=5)
        with pytest.raises(FrozenInstanceError):
            spec.offset = 10  # type: ignore
