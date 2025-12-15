"""Tests for FakeFileScanner test double.

Tasks: T005-T008
Purpose: Verify FakeFileScanner implements FileScanner ABC correctly.
"""

import pytest
from pathlib import Path


@pytest.mark.unit
class TestFakeFileScanner:
    """Tests for FakeFileScanner test double (T005-T008)."""

    def test_fake_file_scanner_accepts_configuration_service(self):
        """
        Purpose: Verifies FakeFileScanner follows ConfigurationService pattern.
        Quality Contribution: Ensures consistent DI across all adapters.
        Acceptance Criteria: Construction with ConfigurationService succeeds.

        Task: T005
        """
        from fs2.config.service import FakeConfigurationService
        from fs2.config.objects import ScanConfig
        from fs2.core.adapters.file_scanner_fake import FakeFileScanner

        config = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config)

        assert scanner is not None

    def test_fake_file_scanner_returns_configured_results(self):
        """
        Purpose: Verifies FakeFileScanner returns pre-configured ScanResult list.
        Quality Contribution: Enables deterministic testing of dependent code.
        Acceptance Criteria: scan() returns exactly the configured ScanResults.

        Task: T006
        """
        from fs2.config.service import FakeConfigurationService
        from fs2.config.objects import ScanConfig
        from fs2.core.adapters.file_scanner_fake import FakeFileScanner
        from fs2.core.models import ScanResult

        config = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config)

        expected_results = [
            ScanResult(path=Path("src/main.py"), size_bytes=1024),
            ScanResult(path=Path("lib/utils.py"), size_bytes=512),
        ]
        scanner.set_results(expected_results)

        result = scanner.scan()

        assert result == expected_results

    def test_fake_file_scanner_returns_empty_list_by_default(self):
        """
        Purpose: Verifies FakeFileScanner returns empty list when not configured.
        Quality Contribution: Safe default behavior.
        Acceptance Criteria: scan() returns empty list without set_results().

        Task: T006 (supplementary)
        """
        from fs2.config.service import FakeConfigurationService
        from fs2.config.objects import ScanConfig
        from fs2.core.adapters.file_scanner_fake import FakeFileScanner

        config = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config)

        result = scanner.scan()

        assert result == []

    def test_fake_file_scanner_records_call_history(self):
        """
        Purpose: Verifies FakeFileScanner tracks method calls for verification.
        Quality Contribution: Enables assertions on adapter usage in tests.
        Acceptance Criteria: call_history contains scan call after scan().

        Task: T007
        """
        from fs2.config.service import FakeConfigurationService
        from fs2.config.objects import ScanConfig
        from fs2.core.adapters.file_scanner_fake import FakeFileScanner

        config = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config)

        scanner.scan()

        assert len(scanner.call_history) == 1
        assert scanner.call_history[0]["method"] == "scan"

    def test_fake_file_scanner_records_multiple_calls(self):
        """
        Purpose: Verifies call_history tracks all method calls.
        Quality Contribution: Enables complex interaction assertions.
        Acceptance Criteria: Multiple calls appear in call_history.

        Task: T007 (supplementary)
        """
        from fs2.config.service import FakeConfigurationService
        from fs2.config.objects import ScanConfig
        from fs2.core.adapters.file_scanner_fake import FakeFileScanner

        config = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config)

        scanner.scan()
        scanner.should_ignore(Path("test.py"))
        scanner.scan()

        assert len(scanner.call_history) == 3
        assert scanner.call_history[0]["method"] == "scan"
        assert scanner.call_history[1]["method"] == "should_ignore"
        assert scanner.call_history[2]["method"] == "scan"

    def test_fake_file_scanner_should_ignore_returns_configured_result(self):
        """
        Purpose: Verifies should_ignore() returns pre-configured boolean.
        Quality Contribution: Enables deterministic testing of gitignore behavior.
        Acceptance Criteria: should_ignore() returns configured value.

        Task: T008
        """
        from fs2.config.service import FakeConfigurationService
        from fs2.config.objects import ScanConfig
        from fs2.core.adapters.file_scanner_fake import FakeFileScanner

        config = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config)

        # Configure specific paths to be ignored
        scanner.set_ignored_paths({Path("node_modules/pkg.js"), Path("*.log")})

        assert scanner.should_ignore(Path("node_modules/pkg.js")) is True
        assert scanner.should_ignore(Path("src/main.py")) is False

    def test_fake_file_scanner_should_ignore_defaults_to_false(self):
        """
        Purpose: Verifies should_ignore() returns False by default.
        Quality Contribution: Safe default - no unexpected exclusions.
        Acceptance Criteria: should_ignore() returns False without configuration.

        Task: T008 (supplementary)
        """
        from fs2.config.service import FakeConfigurationService
        from fs2.config.objects import ScanConfig
        from fs2.core.adapters.file_scanner_fake import FakeFileScanner

        config = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config)

        assert scanner.should_ignore(Path("any/path.py")) is False

    def test_fake_file_scanner_inherits_from_file_scanner(self):
        """
        Purpose: Verifies FakeFileScanner is a proper FileScanner implementation.
        Quality Contribution: Ensures polymorphism works correctly.
        Acceptance Criteria: FakeFileScanner is instance of FileScanner.

        Task: T005 (supplementary)
        """
        from fs2.config.service import FakeConfigurationService
        from fs2.config.objects import ScanConfig
        from fs2.core.adapters.file_scanner import FileScanner
        from fs2.core.adapters.file_scanner_fake import FakeFileScanner

        config = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config)

        assert isinstance(scanner, FileScanner)
