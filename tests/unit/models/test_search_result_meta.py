"""Tests for SearchResultMeta domain model.

Full TDD tests for the SearchResultMeta frozen dataclass covering:
- ST001: Meta structure fields (total, showing, pagination, folders)
- ST001: to_dict() serialization with optional filter fields
- ST003: Folder extraction from various node_id formats
- ST003: Threshold-based folder drilling
- ST003: Root file handling

Per Subtask 003 dossier: Full TDD approach - tests written before implementation.
Per DYK-003-05: meta.include/exclude are always arrays, omitted when empty.
"""

import pytest

# ============================================================================
# ST001: SearchResultMeta Structure Tests
# ============================================================================


@pytest.mark.unit
class TestSearchResultMetaStructure:
    """ST001: Tests for SearchResultMeta field structure."""

    def test_given_required_fields_when_creating_meta_then_succeeds(self):
        """
        Purpose: Proves SearchResultMeta can be created with required fields.
        Quality Contribution: Validates model structure.
        Acceptance Criteria: Meta with total, showing, pagination, folders succeeds.

        Task: ST001
        """
        from fs2.core.models.search.search_result_meta import SearchResultMeta

        meta = SearchResultMeta(
            total=47,
            showing={"from": 0, "to": 20, "count": 20},
            pagination={"limit": 20, "offset": 0},
            folders={"tests/": 36, "src/": 11},
        )

        assert meta.total == 47
        assert meta.showing == {"from": 0, "to": 20, "count": 20}
        assert meta.pagination == {"limit": 20, "offset": 0}
        assert meta.folders == {"tests/": 36, "src/": 11}

    def test_given_meta_when_frozen_then_immutable(self):
        """
        Purpose: Proves SearchResultMeta is immutable (frozen dataclass).
        Quality Contribution: Enforces value object pattern.
        Acceptance Criteria: Attribute assignment raises FrozenInstanceError.

        Task: ST001
        """
        from dataclasses import FrozenInstanceError

        from fs2.core.models.search.search_result_meta import SearchResultMeta

        meta = SearchResultMeta(
            total=10,
            showing={"from": 0, "to": 10, "count": 10},
            pagination={"limit": 10, "offset": 0},
            folders={"src/": 10},
        )

        with pytest.raises(FrozenInstanceError):
            meta.total = 20

    def test_given_optional_include_when_creating_meta_then_stored(self):
        """
        Purpose: Proves include patterns are stored as array.
        Quality Contribution: Validates filter field storage.
        Acceptance Criteria: meta.include is list.

        Task: ST001, DYK-003-05
        """
        from fs2.core.models.search.search_result_meta import SearchResultMeta

        meta = SearchResultMeta(
            total=47,
            showing={"from": 0, "to": 11, "count": 11},
            pagination={"limit": 20, "offset": 0},
            folders={"src/": 11},
            include=["src/"],
            filtered=11,
        )

        assert meta.include == ["src/"]
        assert meta.filtered == 11

    def test_given_optional_exclude_when_creating_meta_then_stored(self):
        """
        Purpose: Proves exclude patterns are stored as array.
        Quality Contribution: Validates filter field storage.
        Acceptance Criteria: meta.exclude is list.

        Task: ST001, DYK-003-05
        """
        from fs2.core.models.search.search_result_meta import SearchResultMeta

        meta = SearchResultMeta(
            total=47,
            showing={"from": 0, "to": 11, "count": 11},
            pagination={"limit": 20, "offset": 0},
            folders={"src/": 11},
            exclude=["tests/"],
            filtered=11,
        )

        assert meta.exclude == ["tests/"]
        assert meta.filtered == 11

    def test_given_multiple_patterns_when_creating_meta_then_stored_as_array(self):
        """
        Purpose: Proves multiple patterns stored in array.
        Quality Contribution: Validates OR logic field storage.
        Acceptance Criteria: meta.include with multiple patterns is list.

        Task: ST001, DYK-003-04
        """
        from fs2.core.models.search.search_result_meta import SearchResultMeta

        meta = SearchResultMeta(
            total=47,
            showing={"from": 0, "to": 15, "count": 15},
            pagination={"limit": 20, "offset": 0},
            folders={"src/": 12, "lib/": 3},
            include=["src/", "lib/"],
            exclude=["test", "fixture"],
            filtered=15,
        )

        assert meta.include == ["src/", "lib/"]
        assert meta.exclude == ["test", "fixture"]


# ============================================================================
# ST001: SearchResultMeta to_dict() Tests
# ============================================================================


@pytest.mark.unit
class TestSearchResultMetaToDict:
    """ST001: Tests for SearchResultMeta.to_dict() serialization."""

    def test_given_meta_when_to_dict_then_includes_required_fields(self):
        """
        Purpose: Proves to_dict() includes all required fields.
        Quality Contribution: Validates serialization completeness.
        Acceptance Criteria: Dict has total, showing, pagination, folders.

        Task: ST001
        """
        from fs2.core.models.search.search_result_meta import SearchResultMeta

        meta = SearchResultMeta(
            total=47,
            showing={"from": 0, "to": 20, "count": 20},
            pagination={"limit": 20, "offset": 0},
            folders={"tests/": 36, "src/": 11},
        )

        d = meta.to_dict()

        assert d["total"] == 47
        assert d["showing"] == {"from": 0, "to": 20, "count": 20}
        assert d["pagination"] == {"limit": 20, "offset": 0}
        assert d["folders"] == {"tests/": 36, "src/": 11}

    def test_given_meta_with_include_when_to_dict_then_includes_array(self):
        """
        Purpose: Proves to_dict() includes include as array.
        Quality Contribution: Validates BC-18 (always arrays).
        Acceptance Criteria: Dict has include as list.

        Task: ST001, BC-18
        """
        from fs2.core.models.search.search_result_meta import SearchResultMeta

        meta = SearchResultMeta(
            total=47,
            showing={"from": 0, "to": 11, "count": 11},
            pagination={"limit": 20, "offset": 0},
            folders={"src/": 11},
            include=["src/"],
            filtered=11,
        )

        d = meta.to_dict()

        assert d["include"] == ["src/"]
        assert isinstance(d["include"], list)
        assert d["filtered"] == 11

    def test_given_meta_without_filters_when_to_dict_then_omits_filter_keys(self):
        """
        Purpose: Proves to_dict() omits include/exclude when None.
        Quality Contribution: Validates BC-18 (omit when empty).
        Acceptance Criteria: Dict does not have include/exclude keys.

        Task: ST001, BC-18
        """
        from fs2.core.models.search.search_result_meta import SearchResultMeta

        meta = SearchResultMeta(
            total=47,
            showing={"from": 0, "to": 20, "count": 20},
            pagination={"limit": 20, "offset": 0},
            folders={"tests/": 36, "src/": 11},
        )

        d = meta.to_dict()

        assert "include" not in d
        assert "exclude" not in d
        assert "filtered" not in d

    def test_given_meta_with_empty_lists_when_to_dict_then_omits_filter_keys(self):
        """
        Purpose: Proves to_dict() omits include/exclude when empty lists.
        Quality Contribution: Validates clean output for no filters.
        Acceptance Criteria: Dict does not have include/exclude keys.

        Task: ST001, BC-18
        """
        from fs2.core.models.search.search_result_meta import SearchResultMeta

        meta = SearchResultMeta(
            total=47,
            showing={"from": 0, "to": 20, "count": 20},
            pagination={"limit": 20, "offset": 0},
            folders={"tests/": 36, "src/": 11},
            include=[],
            exclude=[],
        )

        d = meta.to_dict()

        assert "include" not in d
        assert "exclude" not in d

    def test_given_meta_with_filters_when_to_dict_then_includes_filtered_count(self):
        """
        Purpose: Proves to_dict() includes filtered count when filters applied.
        Quality Contribution: Validates BC-19.
        Acceptance Criteria: Dict has filtered key with count.

        Task: ST001, BC-19
        """
        from fs2.core.models.search.search_result_meta import SearchResultMeta

        meta = SearchResultMeta(
            total=47,
            showing={"from": 0, "to": 30, "count": 30},
            pagination={"limit": 30, "offset": 0},
            folders={"src/": 25, "lib/": 5},
            include=["src/", "lib/"],
            filtered=30,
        )

        d = meta.to_dict()

        assert d["filtered"] == 30


# ============================================================================
# ST003: Folder Extraction Tests
# ============================================================================


@pytest.mark.unit
class TestFolderExtraction:
    """ST003: Tests for extract_folder() from node_id."""

    def test_given_file_node_when_extract_folder_then_returns_first_segment(self):
        """
        Purpose: Proves file: prefix is handled correctly.
        Quality Contribution: Validates core parsing logic.
        Acceptance Criteria: file:src/foo.py → "src/"

        Task: ST003
        """
        from fs2.core.models.search.search_result_meta import extract_folder

        folder = extract_folder("file:src/foo.py")
        assert folder == "src/"

    def test_given_callable_node_when_extract_folder_then_returns_first_segment(self):
        """
        Purpose: Proves callable: prefix with :symbol suffix handled.
        Quality Contribution: Validates callable node parsing.
        Acceptance Criteria: callable:tests/x.py:f → "tests/"

        Task: ST003
        """
        from fs2.core.models.search.search_result_meta import extract_folder

        folder = extract_folder("callable:tests/unit/test_foo.py:test_bar")
        assert folder == "tests/"

    def test_given_class_node_when_extract_folder_then_returns_first_segment(self):
        """
        Purpose: Proves class: prefix with :Class suffix handled.
        Quality Contribution: Validates class node parsing.
        Acceptance Criteria: class:src/models/u.py:User → "src/"

        Task: ST003, DYK-003-03
        """
        from fs2.core.models.search.search_result_meta import extract_folder

        folder = extract_folder("class:src/models/user.py:User")
        assert folder == "src/"

    def test_given_chunk_node_when_extract_folder_then_returns_first_segment(self):
        """
        Purpose: Proves chunk: prefix with :line-range suffix handled.
        Quality Contribution: Validates chunk node parsing.
        Acceptance Criteria: chunk:docs/api.md:10-20 → "docs/"

        Task: ST003, DYK-003-03
        """
        from fs2.core.models.search.search_result_meta import extract_folder

        folder = extract_folder("chunk:docs/api.md:10-20")
        assert folder == "docs/"

    def test_given_content_node_when_extract_folder_then_returns_first_segment(self):
        """
        Purpose: Proves content: prefix handled.
        Quality Contribution: Validates content node parsing.
        Acceptance Criteria: content:docs/guide.md → "docs/"

        Task: ST003, DYK-003-03
        """
        from fs2.core.models.search.search_result_meta import extract_folder

        folder = extract_folder("content:docs/guide.md")
        assert folder == "docs/"

    def test_given_root_file_when_extract_folder_then_returns_root(self):
        """
        Purpose: Proves root files (no folder) return "(root)".
        Quality Contribution: Validates edge case for root-level files.
        Acceptance Criteria: file:README.md → "(root)"

        Task: ST003, DYK-003-03
        """
        from fs2.core.models.search.search_result_meta import extract_folder

        folder = extract_folder("file:README.md")
        assert folder == "(root)"

    def test_given_root_content_when_extract_folder_then_returns_root(self):
        """
        Purpose: Proves root content nodes return "(root)".
        Quality Contribution: Validates edge case for root-level content.
        Acceptance Criteria: content:CHANGELOG.md → "(root)"

        Task: ST003, DYK-003-03
        """
        from fs2.core.models.search.search_result_meta import extract_folder

        folder = extract_folder("content:CHANGELOG.md")
        assert folder == "(root)"

    def test_given_nested_path_when_extract_folder_then_returns_only_first_segment(
        self,
    ):
        """
        Purpose: Proves deeply nested paths return only first segment.
        Quality Contribution: Consistent folder grouping.
        Acceptance Criteria: file:src/core/models/x.py → "src/"

        Task: ST003
        """
        from fs2.core.models.search.search_result_meta import extract_folder

        folder = extract_folder("file:src/core/models/search/query.py")
        assert folder == "src/"


# ============================================================================
# ST003: Folder Distribution Tests
# ============================================================================


@pytest.mark.unit
class TestFolderDistribution:
    """ST003: Tests for compute_folder_distribution()."""

    def test_given_node_ids_when_compute_then_returns_folder_counts(self):
        """
        Purpose: Proves folder distribution counts correctly.
        Quality Contribution: Core distribution logic.
        Acceptance Criteria: Returns dict with folder→count mapping.

        Task: ST003
        """
        from fs2.core.models.search.search_result_meta import (
            compute_folder_distribution,
        )

        node_ids = [
            "file:src/foo.py",
            "file:src/bar.py",
            "file:tests/test_foo.py",
        ]

        dist = compute_folder_distribution(node_ids)

        assert dist["src/"] == 2
        assert dist["tests/"] == 1

    def test_given_empty_list_when_compute_then_returns_empty_dict(self):
        """
        Purpose: Proves empty input returns empty dict.
        Quality Contribution: Edge case handling.
        Acceptance Criteria: Returns {}.

        Task: ST003
        """
        from fs2.core.models.search.search_result_meta import (
            compute_folder_distribution,
        )

        dist = compute_folder_distribution([])
        assert dist == {}


# ============================================================================
# ST003: Threshold-Based Drilling Tests
# ============================================================================


@pytest.mark.unit
class TestThresholdDrilling:
    """ST003: Tests for threshold-based folder drilling (BC-14)."""

    def test_given_90_percent_threshold_when_folder_dominant_then_drills(self):
        """
        Purpose: Proves 90%+ threshold triggers drilling.
        Quality Contribution: Validates BC-14 threshold behavior.
        Acceptance Criteria: 90% tests/ → tests/unit/, tests/integration/ drilled.

        Task: ST003, BC-14, DYK-003-02
        """
        from fs2.core.models.search.search_result_meta import (
            compute_folder_distribution,
        )

        # 9 tests/ + 1 src/ = 90% tests/
        node_ids = [
            "file:tests/unit/test_a.py",
            "file:tests/unit/test_b.py",
            "file:tests/unit/test_c.py",
            "file:tests/integration/test_d.py",
            "file:tests/integration/test_e.py",
            "file:tests/unit/test_f.py",
            "file:tests/unit/test_g.py",
            "file:tests/unit/test_h.py",
            "file:tests/integration/test_i.py",
            "file:src/foo.py",  # 10% minority
        ]

        dist = compute_folder_distribution(node_ids)

        # Should drill into tests/ (90%) while keeping src/
        assert "tests/unit/" in dist
        assert "tests/integration/" in dist
        assert "src/" in dist
        assert "tests/" not in dist  # Drilled into second level

    def test_given_below_threshold_when_compute_then_no_drilling(self):
        """
        Purpose: Proves below-threshold folders are not drilled.
        Quality Contribution: Validates BC-14 threshold cutoff.
        Acceptance Criteria: 80% tests/ → tests/, src/ (no drill).

        Task: ST003, BC-14, DYK-003-02
        """
        from fs2.core.models.search.search_result_meta import (
            compute_folder_distribution,
        )

        # 8 tests/ + 2 src/ = 80% tests/
        node_ids = [
            "file:tests/unit/test_a.py",
            "file:tests/unit/test_b.py",
            "file:tests/unit/test_c.py",
            "file:tests/unit/test_d.py",
            "file:tests/unit/test_e.py",
            "file:tests/unit/test_f.py",
            "file:tests/unit/test_g.py",
            "file:tests/unit/test_h.py",
            "file:src/foo.py",
            "file:src/bar.py",
        ]

        dist = compute_folder_distribution(node_ids)

        # Should NOT drill (80% < 90%)
        assert "tests/" in dist
        assert "src/" in dist
        assert "tests/unit/" not in dist

    def test_given_threshold_constant_then_value_is_0_9(self):
        """
        Purpose: Proves FOLDER_DRILL_THRESHOLD is tunable constant at 0.9.
        Quality Contribution: Documents threshold value per DYK-003-02.
        Acceptance Criteria: Constant equals 0.9.

        Task: ST003, DYK-003-02
        """
        from fs2.core.models.search.search_result_meta import FOLDER_DRILL_THRESHOLD

        assert FOLDER_DRILL_THRESHOLD == 0.9

    def test_given_exactly_90_percent_when_compute_then_drills(self):
        """
        Purpose: Proves exactly 90% threshold triggers drilling.
        Quality Contribution: Boundary condition check.
        Acceptance Criteria: Exactly 90% triggers drilling.

        Task: ST003, BC-14
        """
        from fs2.core.models.search.search_result_meta import (
            compute_folder_distribution,
        )

        # 9 tests/ + 1 src/ = exactly 90%
        node_ids = [
            "file:tests/unit/test_a.py",
            "file:tests/unit/test_b.py",
            "file:tests/unit/test_c.py",
            "file:tests/unit/test_d.py",
            "file:tests/unit/test_e.py",
            "file:tests/unit/test_f.py",
            "file:tests/unit/test_g.py",
            "file:tests/unit/test_h.py",
            "file:tests/integration/test_i.py",
            "file:src/foo.py",
        ]

        dist = compute_folder_distribution(node_ids)

        # Exactly 90% should trigger drilling
        assert "tests/unit/" in dist or "tests/integration/" in dist

    def test_given_100_percent_single_folder_when_compute_then_drills(self):
        """
        Purpose: Proves 100% single folder drills.
        Quality Contribution: Full saturation case.
        Acceptance Criteria: 100% tests/ → tests/unit/, tests/integration/.

        Task: ST003, BC-14
        """
        from fs2.core.models.search.search_result_meta import (
            compute_folder_distribution,
        )

        node_ids = [
            "file:tests/unit/test_a.py",
            "file:tests/unit/test_b.py",
            "file:tests/integration/test_c.py",
        ]

        dist = compute_folder_distribution(node_ids)

        # Should drill into second level
        assert "tests/unit/" in dist
        assert "tests/integration/" in dist
        assert "tests/" not in dist
