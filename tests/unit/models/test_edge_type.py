"""Tests for EdgeType enum for cross-file relationship classification.

Phase 1: T001 - EdgeType enum unit tests.
Purpose: Verify EdgeType enum values, serialization, and comparison.
Quality Contribution: Enables type-safe relationship edge classification.
Acceptance Criteria: AC1 - EdgeType enum is serializable, comparable, pickle-safe.

Per Plan: Full TDD - write tests FIRST, then implement.
"""

import pickle

import pytest


@pytest.mark.unit
class TestEdgeTypeValues:
    """Tests for EdgeType enum values."""

    def test_edge_type_has_imports_value(self):
        """
        Purpose: Verify IMPORTS enum member exists with correct value.
        Quality Contribution: Enables import relationship classification.
        Acceptance Criteria: EdgeType.IMPORTS.value == "imports"
        """
        from fs2.core.models.edge_type import EdgeType

        assert EdgeType.IMPORTS.value == "imports"

    def test_edge_type_has_calls_value(self):
        """
        Purpose: Verify CALLS enum member exists with correct value.
        Quality Contribution: Enables call relationship classification.
        Acceptance Criteria: EdgeType.CALLS.value == "calls"
        """
        from fs2.core.models.edge_type import EdgeType

        assert EdgeType.CALLS.value == "calls"

    def test_edge_type_has_references_value(self):
        """
        Purpose: Verify REFERENCES enum member exists with correct value.
        Quality Contribution: Enables node_id reference classification.
        Acceptance Criteria: EdgeType.REFERENCES.value == "references"
        """
        from fs2.core.models.edge_type import EdgeType

        assert EdgeType.REFERENCES.value == "references"

    def test_edge_type_has_documents_value(self):
        """
        Purpose: Verify DOCUMENTS enum member exists with correct value.
        Quality Contribution: Enables documentation link classification.
        Acceptance Criteria: EdgeType.DOCUMENTS.value == "documents"
        """
        from fs2.core.models.edge_type import EdgeType

        assert EdgeType.DOCUMENTS.value == "documents"

    def test_edge_type_has_exactly_four_values(self):
        """
        Purpose: Verify EdgeType has exactly 4 enum members.
        Quality Contribution: Ensures complete coverage of relationship types.
        Acceptance Criteria: len(list(EdgeType)) == 4
        """
        from fs2.core.models.edge_type import EdgeType

        assert len(list(EdgeType)) == 4


@pytest.mark.unit
class TestEdgeTypeSerialization:
    """Tests for EdgeType string serialization."""

    def test_edge_type_is_str_enum(self):
        """
        Purpose: Verify EdgeType is a string enum for JSON serialization.
        Quality Contribution: Ensures graph edge attributes are serializable.
        Acceptance Criteria: str(EdgeType.IMPORTS) == "imports"
        """
        from fs2.core.models.edge_type import EdgeType

        assert str(EdgeType.IMPORTS) == "imports"
        assert str(EdgeType.CALLS) == "calls"
        assert str(EdgeType.REFERENCES) == "references"
        assert str(EdgeType.DOCUMENTS) == "documents"

    def test_edge_type_equality_with_string(self):
        """
        Purpose: Verify EdgeType can be compared with strings.
        Quality Contribution: Enables flexible usage in conditionals.
        Acceptance Criteria: EdgeType.IMPORTS == "imports"
        """
        from fs2.core.models.edge_type import EdgeType

        assert EdgeType.IMPORTS == "imports"
        assert EdgeType.CALLS == "calls"
        assert EdgeType.REFERENCES == "references"
        assert EdgeType.DOCUMENTS == "documents"


@pytest.mark.unit
class TestEdgeTypeComparison:
    """Tests for EdgeType comparison behavior."""

    def test_edge_type_equality(self):
        """
        Purpose: Verify same enum values compare equal.
        Quality Contribution: Enables type-based edge filtering.
        Acceptance Criteria: EdgeType.IMPORTS == EdgeType.IMPORTS
        """
        from fs2.core.models.edge_type import EdgeType

        assert EdgeType.IMPORTS == EdgeType.IMPORTS
        assert EdgeType.CALLS == EdgeType.CALLS

    def test_edge_type_inequality(self):
        """
        Purpose: Verify different enum values compare unequal.
        Quality Contribution: Enables type-based edge filtering.
        Acceptance Criteria: EdgeType.IMPORTS != EdgeType.CALLS
        """
        from fs2.core.models.edge_type import EdgeType

        assert EdgeType.IMPORTS != EdgeType.CALLS
        assert EdgeType.REFERENCES != EdgeType.DOCUMENTS


@pytest.mark.unit
class TestEdgeTypeIteration:
    """Tests for EdgeType iteration behavior."""

    def test_edge_type_iteration(self):
        """
        Purpose: Verify EdgeType can be iterated to get all values.
        Quality Contribution: Enables enumeration of all relationship types.
        Acceptance Criteria: Can iterate all 4 values.
        """
        from fs2.core.models.edge_type import EdgeType

        edge_types = list(EdgeType)
        assert len(edge_types) == 4
        assert EdgeType.IMPORTS in edge_types
        assert EdgeType.CALLS in edge_types
        assert EdgeType.REFERENCES in edge_types
        assert EdgeType.DOCUMENTS in edge_types


@pytest.mark.unit
class TestEdgeTypePickle:
    """Tests for EdgeType pickle persistence."""

    def test_edge_type_pickle_roundtrip(self):
        """
        Purpose: Verify EdgeType survives pickle round-trip.
        Quality Contribution: Ensures graph persistence works (AC1).
        Acceptance Criteria: Pickle/unpickle preserves value.
        """
        from fs2.core.models.edge_type import EdgeType

        for edge_type in EdgeType:
            pickled = pickle.dumps(edge_type)
            unpickled = pickle.loads(pickled)
            assert unpickled == edge_type
            assert unpickled.value == edge_type.value

    def test_edge_type_pickle_preserves_type(self):
        """
        Purpose: Verify unpickled EdgeType is still EdgeType instance.
        Quality Contribution: Type safety after persistence.
        Acceptance Criteria: isinstance(unpickled, EdgeType)
        """
        from fs2.core.models.edge_type import EdgeType

        pickled = pickle.dumps(EdgeType.IMPORTS)
        unpickled = pickle.loads(pickled)
        assert isinstance(unpickled, EdgeType)
