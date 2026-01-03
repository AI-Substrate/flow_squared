"""Tests for SearchResult search result model.

Purpose: Verify SearchResult to_dict(detail) behavior for min/max modes
Quality Contribution: Ensures consistent JSON output for downstream tools
Acceptance Criteria: AC19 (min: 9 fields), AC20 (max: 13 fields)

Per Phase 1 tasks.md DYK-01: Always include all 13 fields in max mode;
use null for mode-irrelevant fields.

Per Phase 1 tasks.md DYK-02: Normative field reference table.
"""

from dataclasses import FrozenInstanceError

import pytest

# Constants for expected fields per DYK-02
MIN_FIELDS = {
    "node_id",
    "start_line",
    "end_line",
    "match_start_line",
    "match_end_line",
    "smart_content",
    "snippet",
    "score",
    "match_field",
}

MAX_ONLY_FIELDS = {
    "content",
    "matched_lines",
    "chunk_offset",
    "embedding_chunk_index",
}

ALL_FIELDS = MIN_FIELDS | MAX_ONLY_FIELDS


class TestSearchResultMinDetail:
    """Tests for SearchResult.to_dict(detail="min") behavior."""

    def test_min_detail_returns_exactly_9_fields(self):
        """
        Purpose: Proves min detail level returns exactly 9 fields (AC19)
        Quality Contribution: Ensures compact output for scanning
        Acceptance Criteria: Dict has exactly 9 keys
        """
        from fs2.core.models.search import SearchResult

        result = SearchResult(
            node_id="callable:test.py:func",
            start_line=10,
            end_line=20,
            match_start_line=12,
            match_end_line=12,
            smart_content="A test function",
            snippet="def func():",
            score=0.85,
            match_field="content",
            content="def func():\n    pass",
            matched_lines=[12],
            chunk_offset=None,
            embedding_chunk_index=None,
        )
        d = result.to_dict(detail="min")
        assert len(d) == 9

    def test_min_detail_contains_required_fields(self):
        """
        Purpose: Proves min detail includes all 9 required fields
        Quality Contribution: Documents expected minimal output
        Acceptance Criteria: All MIN_FIELDS present
        """
        from fs2.core.models.search import SearchResult

        result = SearchResult(
            node_id="callable:test.py:func",
            start_line=10,
            end_line=20,
            match_start_line=12,
            match_end_line=12,
            smart_content="A test function",
            snippet="def func():",
            score=0.85,
            match_field="content",
            content="def func():\n    pass",
        )
        d = result.to_dict(detail="min")
        for field in MIN_FIELDS:
            assert field in d, f"Missing min field: {field}"

    def test_min_detail_excludes_content(self):
        """
        Purpose: Proves content is excluded in min mode
        Quality Contribution: Keeps min output compact
        Acceptance Criteria: content key absent
        """
        from fs2.core.models.search import SearchResult

        result = SearchResult(
            node_id="callable:test.py:func",
            start_line=10,
            end_line=20,
            match_start_line=12,
            match_end_line=12,
            smart_content="A test function",
            snippet="def func():",
            score=0.85,
            match_field="content",
            content="def func():\n    pass",
        )
        d = result.to_dict(detail="min")
        assert "content" not in d

    def test_min_detail_excludes_matched_lines(self):
        """
        Purpose: Proves matched_lines excluded in min mode
        Quality Contribution: Keeps min output compact
        Acceptance Criteria: matched_lines key absent
        """
        from fs2.core.models.search import SearchResult

        result = SearchResult(
            node_id="callable:test.py:func",
            start_line=10,
            end_line=20,
            match_start_line=12,
            match_end_line=12,
            smart_content="A test function",
            snippet="def func():",
            score=0.85,
            match_field="content",
            matched_lines=[12, 13],
        )
        d = result.to_dict(detail="min")
        assert "matched_lines" not in d

    def test_min_detail_excludes_chunk_offset(self):
        """
        Purpose: Proves chunk_offset excluded in min mode
        Quality Contribution: Keeps min output compact
        Acceptance Criteria: chunk_offset key absent
        """
        from fs2.core.models.search import SearchResult

        result = SearchResult(
            node_id="callable:test.py:func",
            start_line=10,
            end_line=20,
            match_start_line=12,
            match_end_line=12,
            smart_content="A test function",
            snippet="def func():",
            score=0.85,
            match_field="embedding",
            chunk_offset=(12, 15),
        )
        d = result.to_dict(detail="min")
        assert "chunk_offset" not in d

    def test_min_detail_excludes_embedding_chunk_index(self):
        """
        Purpose: Proves embedding_chunk_index excluded in min mode
        Quality Contribution: Keeps min output compact
        Acceptance Criteria: embedding_chunk_index key absent
        """
        from fs2.core.models.search import SearchResult

        result = SearchResult(
            node_id="callable:test.py:func",
            start_line=10,
            end_line=20,
            match_start_line=12,
            match_end_line=12,
            smart_content="A test function",
            snippet="def func():",
            score=0.85,
            match_field="embedding",
            embedding_chunk_index=2,
        )
        d = result.to_dict(detail="min")
        assert "embedding_chunk_index" not in d


class TestSearchResultMaxDetail:
    """Tests for SearchResult.to_dict(detail="max") behavior."""

    def test_max_detail_returns_exactly_13_fields(self):
        """
        Purpose: Proves max detail level returns exactly 13 fields (AC20)
        Quality Contribution: Documents complete output format
        Acceptance Criteria: Dict has exactly 13 keys
        """
        from fs2.core.models.search import SearchResult

        result = SearchResult(
            node_id="callable:test.py:func",
            start_line=10,
            end_line=20,
            match_start_line=12,
            match_end_line=12,
            smart_content="A test function",
            snippet="def func():",
            score=0.85,
            match_field="content",
            content="def func():\n    pass",
            matched_lines=[12],
            chunk_offset=None,
            embedding_chunk_index=None,
        )
        d = result.to_dict(detail="max")
        assert len(d) == 13

    def test_max_detail_contains_all_fields(self):
        """
        Purpose: Proves max detail includes all 13 fields (AC20)
        Quality Contribution: Enables deep inspection
        Acceptance Criteria: All ALL_FIELDS present
        """
        from fs2.core.models.search import SearchResult

        result = SearchResult(
            node_id="callable:test.py:func",
            start_line=10,
            end_line=20,
            match_start_line=12,
            match_end_line=12,
            smart_content="A test function",
            snippet="def func():",
            score=0.85,
            match_field="content",
            content="def func():\n    pass",
            matched_lines=[12],
            chunk_offset=None,
            embedding_chunk_index=None,
        )
        d = result.to_dict(detail="max")
        for field in ALL_FIELDS:
            assert field in d, f"Missing max field: {field}"

    def test_max_detail_includes_content(self):
        """
        Purpose: Proves content included in max mode
        Quality Contribution: Enables full text inspection
        Acceptance Criteria: content key present with value
        """
        from fs2.core.models.search import SearchResult

        content = "def func():\n    pass"
        result = SearchResult(
            node_id="callable:test.py:func",
            start_line=10,
            end_line=20,
            match_start_line=12,
            match_end_line=12,
            smart_content="A test function",
            snippet="def func():",
            score=0.85,
            match_field="content",
            content=content,
        )
        d = result.to_dict(detail="max")
        assert "content" in d
        assert d["content"] == content

    def test_max_detail_includes_matched_lines_for_text_search(self):
        """
        Purpose: Proves matched_lines included for text/regex results
        Quality Contribution: Enables highlighting in UI
        Acceptance Criteria: matched_lines present with lines
        """
        from fs2.core.models.search import SearchResult

        result = SearchResult(
            node_id="callable:test.py:func",
            start_line=10,
            end_line=20,
            match_start_line=12,
            match_end_line=13,
            smart_content="A test function",
            snippet="def func():",
            score=0.85,
            match_field="content",
            matched_lines=[12, 13],
        )
        d = result.to_dict(detail="max")
        assert "matched_lines" in d
        assert d["matched_lines"] == [12, 13]

    def test_max_detail_includes_chunk_offset_for_semantic_search(self):
        """
        Purpose: Proves chunk_offset included for semantic results
        Quality Contribution: Enables chunk-level navigation
        Acceptance Criteria: chunk_offset present with tuple
        """
        from fs2.core.models.search import SearchResult

        result = SearchResult(
            node_id="callable:test.py:func",
            start_line=10,
            end_line=20,
            match_start_line=12,
            match_end_line=15,
            smart_content="A test function",
            snippet="def func():",
            score=0.92,
            match_field="embedding",
            chunk_offset=(12, 15),
            embedding_chunk_index=2,
        )
        d = result.to_dict(detail="max")
        assert "chunk_offset" in d
        assert d["chunk_offset"] == (12, 15)

    def test_max_detail_includes_embedding_chunk_index(self):
        """
        Purpose: Proves embedding_chunk_index included for semantic results
        Quality Contribution: Enables chunk tracing
        Acceptance Criteria: embedding_chunk_index present
        """
        from fs2.core.models.search import SearchResult

        result = SearchResult(
            node_id="callable:test.py:func",
            start_line=10,
            end_line=20,
            match_start_line=12,
            match_end_line=15,
            smart_content="A test function",
            snippet="def func():",
            score=0.92,
            match_field="embedding",
            chunk_offset=(12, 15),
            embedding_chunk_index=2,
        )
        d = result.to_dict(detail="max")
        assert "embedding_chunk_index" in d
        assert d["embedding_chunk_index"] == 2


class TestSearchResultModeIrrelevantFields:
    """Tests for DYK-01: null for mode-irrelevant fields in max mode."""

    def test_max_detail_null_for_semantic_only_fields_in_text_search(self):
        """
        Purpose: Proves DYK-01 - semantic fields null for text search
        Quality Contribution: Consistent JSON schema across modes
        Acceptance Criteria: chunk_offset and embedding_chunk_index are null
        """
        from fs2.core.models.search import SearchResult

        result = SearchResult(
            node_id="callable:test.py:func",
            start_line=10,
            end_line=20,
            match_start_line=12,
            match_end_line=12,
            smart_content="A test function",
            snippet="def func():",
            score=0.85,
            match_field="content",
            content="def func():\n    pass",
            matched_lines=[12],
            chunk_offset=None,  # Not applicable for text search
            embedding_chunk_index=None,  # Not applicable for text search
        )
        d = result.to_dict(detail="max")
        assert d["chunk_offset"] is None
        assert d["embedding_chunk_index"] is None

    def test_max_detail_null_for_text_only_fields_in_semantic_search(self):
        """
        Purpose: Proves DYK-01 - text fields null for semantic search
        Quality Contribution: Consistent JSON schema across modes
        Acceptance Criteria: matched_lines is null for semantic
        """
        from fs2.core.models.search import SearchResult

        result = SearchResult(
            node_id="callable:test.py:func",
            start_line=10,
            end_line=20,
            match_start_line=12,
            match_end_line=15,
            smart_content="A test function",
            snippet="def func():",
            score=0.92,
            match_field="embedding",
            content="def func():\n    pass",
            matched_lines=None,  # Not applicable for semantic search
            chunk_offset=(12, 15),
            embedding_chunk_index=2,
        )
        d = result.to_dict(detail="max")
        assert d["matched_lines"] is None


class TestSearchResultImmutability:
    """Tests for SearchResult frozen immutability."""

    def test_search_result_is_frozen(self):
        """
        Purpose: Proves SearchResult cannot be mutated
        Quality Contribution: Ensures thread safety
        Acceptance Criteria: FrozenInstanceError on modification
        """
        from fs2.core.models.search import SearchResult

        result = SearchResult(
            node_id="callable:test.py:func",
            start_line=10,
            end_line=20,
            match_start_line=12,
            match_end_line=12,
            smart_content="A test function",
            snippet="def func():",
            score=0.85,
            match_field="content",
        )
        with pytest.raises(FrozenInstanceError):
            result.score = 0.99  # type: ignore

    def test_search_result_node_id_cannot_be_modified(self):
        """
        Purpose: Proves node_id cannot be mutated
        Quality Contribution: Ensures result integrity
        Acceptance Criteria: FrozenInstanceError on modification
        """
        from fs2.core.models.search import SearchResult

        result = SearchResult(
            node_id="callable:test.py:func",
            start_line=10,
            end_line=20,
            match_start_line=12,
            match_end_line=12,
            smart_content="A test function",
            snippet="def func():",
            score=0.85,
            match_field="content",
        )
        with pytest.raises(FrozenInstanceError):
            result.node_id = "modified"  # type: ignore


class TestSearchResultDefaultDetail:
    """Tests for SearchResult.to_dict() default detail level."""

    def test_default_detail_is_min(self):
        """
        Purpose: Proves default detail level is "min"
        Quality Contribution: Documents expected default
        Acceptance Criteria: No arg returns same as detail="min"
        """
        from fs2.core.models.search import SearchResult

        result = SearchResult(
            node_id="callable:test.py:func",
            start_line=10,
            end_line=20,
            match_start_line=12,
            match_end_line=12,
            smart_content="A test function",
            snippet="def func():",
            score=0.85,
            match_field="content",
            content="def func():\n    pass",
        )
        d_default = result.to_dict()
        d_min = result.to_dict(detail="min")
        assert d_default == d_min


class TestSearchResultFieldValues:
    """Tests for correct field value preservation."""

    def test_all_field_values_preserved_in_max_mode(self):
        """
        Purpose: Proves all values are correctly serialized
        Quality Contribution: Ensures data integrity
        Acceptance Criteria: All values match input
        """
        from fs2.core.models.search import SearchResult

        result = SearchResult(
            node_id="callable:test.py:MyClass.my_method",
            start_line=100,
            end_line=150,
            match_start_line=120,
            match_end_line=125,
            smart_content="A method that processes data",
            snippet="def my_method(self, data):",
            score=0.95,
            match_field="smart_content",
            content="def my_method(self, data):\n    return process(data)",
            matched_lines=[120, 121, 122],
            chunk_offset=(120, 125),
            embedding_chunk_index=3,
        )
        d = result.to_dict(detail="max")

        assert d["node_id"] == "callable:test.py:MyClass.my_method"
        assert d["start_line"] == 100
        assert d["end_line"] == 150
        assert d["match_start_line"] == 120
        assert d["match_end_line"] == 125
        assert d["smart_content"] == "A method that processes data"
        assert d["snippet"] == "def my_method(self, data):"
        assert d["score"] == 0.95
        assert d["match_field"] == "smart_content"
        assert d["content"] == "def my_method(self, data):\n    return process(data)"
        assert d["matched_lines"] == [120, 121, 122]
        assert d["chunk_offset"] == (120, 125)
        assert d["embedding_chunk_index"] == 3

    def test_smart_content_none_preserved(self):
        """
        Purpose: Proves None smart_content is preserved
        Quality Contribution: Handles nodes without AI summary
        Acceptance Criteria: smart_content is None in output
        """
        from fs2.core.models.search import SearchResult

        result = SearchResult(
            node_id="callable:test.py:func",
            start_line=10,
            end_line=20,
            match_start_line=12,
            match_end_line=12,
            smart_content=None,
            snippet="def func():",
            score=0.85,
            match_field="content",
        )
        d = result.to_dict(detail="min")
        assert d["smart_content"] is None
