"""Tests for ScanResult domain model.

Task: T000a
Purpose: Verify ScanResult frozen dataclass with path and size_bytes fields.
"""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest


@pytest.mark.unit
class TestScanResult:
    """Tests for ScanResult domain model (T000a)."""

    def test_scan_result_is_frozen_dataclass(self):
        """
        Purpose: Verifies ScanResult is immutable.
        Quality Contribution: Ensures domain model consistency.
        Acceptance Criteria: Modification raises error.

        Task: T000a
        """
        from fs2.core.models import ScanResult

        result = ScanResult(path=Path("src/main.py"), size_bytes=1024)

        with pytest.raises((AttributeError, FrozenInstanceError)):
            result.size_bytes = 2048

    def test_scan_result_has_path_and_size_bytes(self):
        """
        Purpose: Verifies ScanResult has required fields.
        Quality Contribution: Ensures API contract.
        Acceptance Criteria: Both fields accessible.

        Task: T000a
        """
        from fs2.core.models import ScanResult

        result = ScanResult(path=Path("src/main.py"), size_bytes=1024)

        assert result.path == Path("src/main.py")
        assert result.size_bytes == 1024

    def test_scan_result_path_is_pathlib_path(self):
        """
        Purpose: Verifies path field uses pathlib.Path type.
        Quality Contribution: Ensures type consistency across codebase.
        Acceptance Criteria: path is instance of Path.

        Task: T000a
        """
        from fs2.core.models import ScanResult

        result = ScanResult(path=Path("lib/utils.py"), size_bytes=512)

        assert isinstance(result.path, Path)

    def test_scan_result_size_bytes_is_int(self):
        """
        Purpose: Verifies size_bytes field is integer.
        Quality Contribution: Ensures type consistency for Phase 3 truncation logic.
        Acceptance Criteria: size_bytes is instance of int.

        Task: T000a
        """
        from fs2.core.models import ScanResult

        result = ScanResult(path=Path("test.py"), size_bytes=0)

        assert isinstance(result.size_bytes, int)

    def test_scan_result_equality(self):
        """
        Purpose: Verifies ScanResult equality comparison works.
        Quality Contribution: Enables list comparison in tests.
        Acceptance Criteria: Two ScanResults with same values are equal.

        Task: T000a
        """
        from fs2.core.models import ScanResult

        result1 = ScanResult(path=Path("src/main.py"), size_bytes=1024)
        result2 = ScanResult(path=Path("src/main.py"), size_bytes=1024)
        result3 = ScanResult(path=Path("src/other.py"), size_bytes=1024)

        assert result1 == result2
        assert result1 != result3
