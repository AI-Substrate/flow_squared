"""Tests for FileScanner ABC contract.

Tasks: T001-T003
Purpose: Verify FileScanner ABC defines correct interface.
"""

import pytest
from abc import ABC


@pytest.mark.unit
class TestFileScannerABC:
    """Tests for FileScanner ABC contract (T001-T003)."""

    def test_file_scanner_abc_cannot_be_instantiated(self):
        """
        Purpose: Proves ABC cannot be directly instantiated.
        Quality Contribution: Enforces interface-only contract.
        Acceptance Criteria: TypeError raised on instantiation.

        Task: T001
        """
        from fs2.core.adapters.file_scanner import FileScanner

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            FileScanner()

    def test_file_scanner_abc_defines_scan_method(self):
        """
        Purpose: Verifies scan() is an abstract method.
        Quality Contribution: Ensures implementations provide scan().
        Acceptance Criteria: scan in __abstractmethods__.

        Task: T002
        """
        from fs2.core.adapters.file_scanner import FileScanner

        assert "scan" in FileScanner.__abstractmethods__

    def test_file_scanner_abc_defines_should_ignore_method(self):
        """
        Purpose: Verifies should_ignore() is an abstract method.
        Quality Contribution: Ensures implementations provide pattern checking.
        Acceptance Criteria: should_ignore in __abstractmethods__.

        Task: T003
        """
        from fs2.core.adapters.file_scanner import FileScanner

        assert "should_ignore" in FileScanner.__abstractmethods__

    def test_file_scanner_abc_inherits_from_abc(self):
        """
        Purpose: Verifies FileScanner is a proper ABC.
        Quality Contribution: Ensures abc.ABC pattern followed correctly.
        Acceptance Criteria: FileScanner is subclass of ABC.

        Task: T001 (supplementary)
        """
        from fs2.core.adapters.file_scanner import FileScanner

        assert issubclass(FileScanner, ABC)
