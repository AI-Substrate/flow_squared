"""Tests for CodeEdge frozen dataclass for cross-file relationship representation.

Phase 1: T003 - CodeEdge model unit tests.
Purpose: Verify CodeEdge validation, immutability, and serialization.
Quality Contribution: Ensures relationship edges have valid confidence and type.
Acceptance Criteria: AC2 - CodeEdge raises ValueError for confidence outside 0.0-1.0.

Per Plan: Full TDD - write tests FIRST, then implement.
Per Plan Critical Discovery 02: Must follow ChunkMatch pattern with frozen dataclass.
"""

import pickle
from dataclasses import FrozenInstanceError

import pytest


@pytest.mark.unit
class TestCodeEdgeCreation:
    """Tests for CodeEdge creation and field values."""

    def test_code_edge_with_valid_confidence(self):
        """
        Purpose: Proves CodeEdge can be created with valid confidence.
        Quality Contribution: Documents happy path for edge creation.
        Acceptance Criteria: CodeEdge created successfully.
        """
        from fs2.core.models.code_edge import CodeEdge
        from fs2.core.models.edge_type import EdgeType

        edge = CodeEdge(
            source_node_id="file:src/app.py",
            target_node_id="file:src/auth.py",
            edge_type=EdgeType.IMPORTS,
            confidence=0.9,
        )
        assert edge.source_node_id == "file:src/app.py"
        assert edge.target_node_id == "file:src/auth.py"
        assert edge.edge_type == EdgeType.IMPORTS
        assert edge.confidence == 0.9

    def test_code_edge_with_source_line(self):
        """
        Purpose: Proves CodeEdge accepts optional source_line.
        Quality Contribution: Enables documentation discovery use case.
        Acceptance Criteria: source_line is preserved.
        """
        from fs2.core.models.code_edge import CodeEdge
        from fs2.core.models.edge_type import EdgeType

        edge = CodeEdge(
            source_node_id="file:docs/plan.md",
            target_node_id="method:src/auth.py:AuthHandler.validate",
            edge_type=EdgeType.REFERENCES,
            confidence=1.0,
            source_line=156,
        )
        assert edge.source_line == 156

    def test_code_edge_source_line_default_none(self):
        """
        Purpose: Proves source_line defaults to None.
        Quality Contribution: Backward compatibility for edges without line info.
        Acceptance Criteria: source_line is None when not provided.
        """
        from fs2.core.models.code_edge import CodeEdge
        from fs2.core.models.edge_type import EdgeType

        edge = CodeEdge(
            source_node_id="file:src/app.py",
            target_node_id="file:src/auth.py",
            edge_type=EdgeType.IMPORTS,
            confidence=0.9,
        )
        assert edge.source_line is None

    def test_code_edge_with_resolution_rule(self):
        """
        Purpose: Proves CodeEdge accepts optional resolution_rule.
        Quality Contribution: Enables debugging of how edge was resolved.
        Acceptance Criteria: resolution_rule is preserved.
        """
        from fs2.core.models.code_edge import CodeEdge
        from fs2.core.models.edge_type import EdgeType

        edge = CodeEdge(
            source_node_id="file:src/app.py",
            target_node_id="file:src/auth.py",
            edge_type=EdgeType.IMPORTS,
            confidence=0.9,
            resolution_rule="import_statement",
        )
        assert edge.resolution_rule == "import_statement"


@pytest.mark.unit
class TestCodeEdgeConfidenceValidation:
    """Tests for CodeEdge confidence validation (0.0-1.0 bounds)."""

    def test_confidence_above_1_raises_error(self):
        """
        Purpose: Proves confidence > 1.0 is rejected (AC2).
        Quality Contribution: Prevents invalid confidence scores.
        Acceptance Criteria: ValueError raised with message.
        """
        from fs2.core.models.code_edge import CodeEdge
        from fs2.core.models.edge_type import EdgeType

        with pytest.raises(ValueError, match="confidence"):
            CodeEdge(
                source_node_id="file:a.py",
                target_node_id="file:b.py",
                edge_type=EdgeType.IMPORTS,
                confidence=1.5,
            )

    def test_confidence_below_0_raises_error(self):
        """
        Purpose: Proves confidence < 0.0 is rejected (AC2).
        Quality Contribution: Prevents invalid confidence scores.
        Acceptance Criteria: ValueError raised with message.
        """
        from fs2.core.models.code_edge import CodeEdge
        from fs2.core.models.edge_type import EdgeType

        with pytest.raises(ValueError, match="confidence"):
            CodeEdge(
                source_node_id="file:a.py",
                target_node_id="file:b.py",
                edge_type=EdgeType.IMPORTS,
                confidence=-0.1,
            )

    def test_confidence_exactly_0_accepted(self):
        """
        Purpose: Proves confidence=0.0 is valid boundary value.
        Quality Contribution: Documents valid range.
        Acceptance Criteria: CodeEdge created successfully.
        """
        from fs2.core.models.code_edge import CodeEdge
        from fs2.core.models.edge_type import EdgeType

        edge = CodeEdge(
            source_node_id="file:a.py",
            target_node_id="file:b.py",
            edge_type=EdgeType.IMPORTS,
            confidence=0.0,
        )
        assert edge.confidence == 0.0

    def test_confidence_exactly_1_accepted(self):
        """
        Purpose: Proves confidence=1.0 is valid boundary value.
        Quality Contribution: Documents valid range.
        Acceptance Criteria: CodeEdge created successfully.
        """
        from fs2.core.models.code_edge import CodeEdge
        from fs2.core.models.edge_type import EdgeType

        edge = CodeEdge(
            source_node_id="file:a.py",
            target_node_id="file:b.py",
            edge_type=EdgeType.REFERENCES,
            confidence=1.0,
        )
        assert edge.confidence == 1.0


@pytest.mark.unit
class TestCodeEdgeTypeValidation:
    """Tests for CodeEdge edge_type validation."""

    def test_string_edge_type_rejected(self):
        """
        Purpose: Proves string edge_type is rejected (must use enum).
        Quality Contribution: Type safety enforcement.
        Acceptance Criteria: TypeError raised.
        """
        from fs2.core.models.code_edge import CodeEdge

        with pytest.raises((TypeError, ValueError)):
            CodeEdge(
                source_node_id="file:a.py",
                target_node_id="file:b.py",
                edge_type="imports",  # type: ignore
                confidence=0.9,
            )

    def test_all_edge_types_accepted(self):
        """
        Purpose: Proves all EdgeType values can be used.
        Quality Contribution: Validates enum integration.
        Acceptance Criteria: All 4 types work.
        """
        from fs2.core.models.code_edge import CodeEdge
        from fs2.core.models.edge_type import EdgeType

        for edge_type in EdgeType:
            edge = CodeEdge(
                source_node_id="file:a.py",
                target_node_id="file:b.py",
                edge_type=edge_type,
                confidence=0.5,
            )
            assert edge.edge_type == edge_type


@pytest.mark.unit
class TestCodeEdgeImmutability:
    """Tests for CodeEdge frozen immutability."""

    def test_code_edge_is_frozen(self):
        """
        Purpose: Ensures CodeEdge cannot be mutated (CD-02).
        Quality Contribution: Thread safety for concurrent access.
        Acceptance Criteria: FrozenInstanceError on modification.
        """
        from fs2.core.models.code_edge import CodeEdge
        from fs2.core.models.edge_type import EdgeType

        edge = CodeEdge(
            source_node_id="file:a.py",
            target_node_id="file:b.py",
            edge_type=EdgeType.IMPORTS,
            confidence=0.9,
        )
        with pytest.raises(FrozenInstanceError):
            edge.confidence = 0.5  # type: ignore

    def test_code_edge_source_cannot_be_modified(self):
        """
        Purpose: Proves source_node_id cannot be mutated.
        Quality Contribution: Ensures immutability contract.
        Acceptance Criteria: FrozenInstanceError on modification.
        """
        from fs2.core.models.code_edge import CodeEdge
        from fs2.core.models.edge_type import EdgeType

        edge = CodeEdge(
            source_node_id="file:a.py",
            target_node_id="file:b.py",
            edge_type=EdgeType.IMPORTS,
            confidence=0.9,
        )
        with pytest.raises(FrozenInstanceError):
            edge.source_node_id = "file:c.py"  # type: ignore

    def test_code_edge_edge_type_cannot_be_modified(self):
        """
        Purpose: Proves edge_type cannot be mutated.
        Quality Contribution: Ensures immutability contract.
        Acceptance Criteria: FrozenInstanceError on modification.
        """
        from fs2.core.models.code_edge import CodeEdge
        from fs2.core.models.edge_type import EdgeType

        edge = CodeEdge(
            source_node_id="file:a.py",
            target_node_id="file:b.py",
            edge_type=EdgeType.IMPORTS,
            confidence=0.9,
        )
        with pytest.raises(FrozenInstanceError):
            edge.edge_type = EdgeType.CALLS  # type: ignore


@pytest.mark.unit
class TestCodeEdgePickle:
    """Tests for CodeEdge pickle persistence."""

    def test_code_edge_pickle_roundtrip(self):
        """
        Purpose: Proves CodeEdge survives pickle round-trip (AC1/AC2).
        Quality Contribution: Ensures graph persistence works.
        Acceptance Criteria: All fields preserved through pickle.
        """
        from fs2.core.models.code_edge import CodeEdge
        from fs2.core.models.edge_type import EdgeType

        original = CodeEdge(
            source_node_id="file:src/app.py",
            target_node_id="file:src/auth.py",
            edge_type=EdgeType.IMPORTS,
            confidence=0.9,
            source_line=42,
            resolution_rule="import_statement",
        )

        pickled = pickle.dumps(original)
        restored = pickle.loads(pickled)

        assert restored.source_node_id == original.source_node_id
        assert restored.target_node_id == original.target_node_id
        assert restored.edge_type == original.edge_type
        assert restored.confidence == original.confidence
        assert restored.source_line == original.source_line
        assert restored.resolution_rule == original.resolution_rule

    def test_code_edge_pickle_preserves_type(self):
        """
        Purpose: Proves unpickled CodeEdge is still CodeEdge instance.
        Quality Contribution: Type safety after persistence.
        Acceptance Criteria: isinstance(unpickled, CodeEdge)
        """
        from fs2.core.models.code_edge import CodeEdge
        from fs2.core.models.edge_type import EdgeType

        original = CodeEdge(
            source_node_id="file:a.py",
            target_node_id="file:b.py",
            edge_type=EdgeType.CALLS,
            confidence=0.7,
        )

        pickled = pickle.dumps(original)
        restored = pickle.loads(pickled)

        assert isinstance(restored, CodeEdge)
        assert isinstance(restored.edge_type, EdgeType)
