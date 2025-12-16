"""Unit tests for ScanSummary frozen dataclass.

Purpose: Verifies ScanSummary captures pipeline execution results.
Quality Contribution: Ensures pipeline returns consistent, immutable results.

Per Phase 5 Tasks:
- T012: Tests for ScanSummary frozen dataclass

Per Alignment Brief:
- ScanSummary is frozen (immutable like other domain models)
- Contains success, files_scanned, nodes_created, errors, metrics
"""

import pytest


class TestScanSummaryFields:
    """Tests for ScanSummary field definitions."""

    def test_given_scan_summary_when_created_then_has_success_field(self):
        """
        Purpose: Verifies ScanSummary has success boolean.
        Quality Contribution: Enables binary success determination.
        Acceptance Criteria: success field accessible.
        """
        from fs2.core.models.scan_summary import ScanSummary

        summary = ScanSummary(
            success=True,
            files_scanned=10,
            nodes_created=50,
            errors=[],
            metrics={},
        )

        assert summary.success is True

    def test_given_scan_summary_when_created_then_has_files_scanned_field(self):
        """
        Purpose: Verifies ScanSummary has files_scanned count.
        Quality Contribution: Tracks discovery stage output.
        Acceptance Criteria: files_scanned field accessible.
        """
        from fs2.core.models.scan_summary import ScanSummary

        summary = ScanSummary(
            success=True,
            files_scanned=25,
            nodes_created=100,
            errors=[],
            metrics={},
        )

        assert summary.files_scanned == 25

    def test_given_scan_summary_when_created_then_has_nodes_created_field(self):
        """
        Purpose: Verifies ScanSummary has nodes_created count.
        Quality Contribution: Tracks parsing stage output.
        Acceptance Criteria: nodes_created field accessible.
        """
        from fs2.core.models.scan_summary import ScanSummary

        summary = ScanSummary(
            success=True,
            files_scanned=10,
            nodes_created=75,
            errors=[],
            metrics={},
        )

        assert summary.nodes_created == 75

    def test_given_scan_summary_when_created_then_has_errors_field(self):
        """
        Purpose: Verifies ScanSummary has errors list.
        Quality Contribution: Surfaces all pipeline errors.
        Acceptance Criteria: errors field accessible.
        """
        from fs2.core.models.scan_summary import ScanSummary

        summary = ScanSummary(
            success=False,
            files_scanned=5,
            nodes_created=20,
            errors=["Failed to parse bad.py", "Encoding error in weird.py"],
            metrics={},
        )

        assert len(summary.errors) == 2
        assert "bad.py" in summary.errors[0]

    def test_given_scan_summary_when_created_then_has_metrics_field(self):
        """
        Purpose: Verifies ScanSummary has metrics dict.
        Quality Contribution: Enables observability.
        Acceptance Criteria: metrics field accessible.
        """
        from fs2.core.models.scan_summary import ScanSummary

        summary = ScanSummary(
            success=True,
            files_scanned=10,
            nodes_created=50,
            errors=[],
            metrics={
                "discovery_files": 10,
                "parsing_nodes": 50,
                "storage_edges": 30,
            },
        )

        assert summary.metrics["discovery_files"] == 10
        assert summary.metrics["parsing_nodes"] == 50


class TestScanSummaryFrozen:
    """Tests for ScanSummary immutability."""

    def test_given_scan_summary_when_mutating_success_then_raises_error(self):
        """
        Purpose: Verifies ScanSummary is frozen.
        Quality Contribution: Prevents accidental mutation.
        Acceptance Criteria: AttributeError on mutation.
        """
        from fs2.core.models.scan_summary import ScanSummary

        summary = ScanSummary(
            success=True,
            files_scanned=10,
            nodes_created=50,
            errors=[],
            metrics={},
        )

        with pytest.raises(AttributeError):
            summary.success = False  # type: ignore

    def test_given_scan_summary_when_mutating_files_scanned_then_raises_error(self):
        """
        Purpose: Verifies files_scanned is immutable.
        Quality Contribution: Prevents accidental mutation.
        Acceptance Criteria: AttributeError on mutation.
        """
        from fs2.core.models.scan_summary import ScanSummary

        summary = ScanSummary(
            success=True,
            files_scanned=10,
            nodes_created=50,
            errors=[],
            metrics={},
        )

        with pytest.raises(AttributeError):
            summary.files_scanned = 999  # type: ignore


class TestScanSummarySuccessSemantics:
    """Tests for success flag semantics."""

    def test_given_no_errors_when_checking_success_then_true(self):
        """
        Purpose: Verifies success=True when no errors.
        Quality Contribution: Correct success determination.
        Acceptance Criteria: Empty errors means success.
        """
        from fs2.core.models.scan_summary import ScanSummary

        summary = ScanSummary(
            success=True,
            files_scanned=10,
            nodes_created=50,
            errors=[],
            metrics={},
        )

        assert summary.success is True

    def test_given_errors_when_checking_success_then_false(self):
        """
        Purpose: Verifies success=False when errors present.
        Quality Contribution: Correct failure determination.
        Acceptance Criteria: Any error means failure.
        """
        from fs2.core.models.scan_summary import ScanSummary

        summary = ScanSummary(
            success=False,
            files_scanned=10,
            nodes_created=45,  # Some parsed despite error
            errors=["One file failed"],
            metrics={},
        )

        assert summary.success is False


class TestScanSummaryDocumentation:
    """Tests for ScanSummary documentation."""

    def test_given_scan_summary_when_inspected_then_has_docstring(self):
        """
        Purpose: Verifies ScanSummary has documentation.
        Quality Contribution: Developers understand the model.
        Acceptance Criteria: Non-empty docstring.
        """
        from fs2.core.models.scan_summary import ScanSummary

        assert ScanSummary.__doc__ is not None
        assert len(ScanSummary.__doc__) > 0
