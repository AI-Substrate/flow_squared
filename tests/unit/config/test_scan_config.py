"""Tests for ScanConfig Pydantic model.

Tests verify:
- ScanConfig loads from YAML with scan_paths (AC1)
- Sensible defaults for all fields
- follow_symlinks defaults to False (Critical Finding 06)
- sample_lines_for_large_files field (Critical Finding 12)
- Validation for invalid values

Per Plan: Full TDD approach, no mocks
Per Spec: AC1 - configuration loading
"""

import pytest
from pydantic import ValidationError


@pytest.mark.unit
class TestScanConfigLoading:
    """Tests for ScanConfig YAML loading and paths (T022)."""

    def test_scan_config_has_config_path_for_yaml(self):
        """
        Purpose: Verifies ScanConfig has __config_path__ for YAML loading.
        Quality Contribution: Enables registry-based config loading per pattern.
        Acceptance Criteria: __config_path__ = "scan".

        Task: T022
        """
        from fs2.config.objects import ScanConfig

        assert hasattr(ScanConfig, "__config_path__")
        assert ScanConfig.__config_path__ == "scan"

    def test_scan_config_can_be_constructed_with_scan_paths(self):
        """
        Purpose: Verifies scan_paths field exists and is a list.
        Quality Contribution: Enables AC1 - scan path configuration.
        Acceptance Criteria: scan_paths accepts list of paths.

        Task: T022
        """
        from fs2.config.objects import ScanConfig

        config = ScanConfig(scan_paths=["./src", "./lib"])

        assert config.scan_paths == ["./src", "./lib"]

    def test_scan_config_in_yaml_config_types_registry(self):
        """
        Purpose: Verifies ScanConfig is registered for auto-loading.
        Quality Contribution: Enables automatic loading from YAML/env.
        Acceptance Criteria: ScanConfig in YAML_CONFIG_TYPES.

        Task: T022
        """
        from fs2.config.objects import YAML_CONFIG_TYPES, ScanConfig

        assert ScanConfig in YAML_CONFIG_TYPES


@pytest.mark.unit
class TestScanConfigDefaults:
    """Tests for ScanConfig default values (T023-T025)."""

    def test_scan_config_scan_paths_defaults_to_current_dir(self):
        """
        Purpose: Verifies scan_paths has sensible default.
        Quality Contribution: Users can run with minimal config.
        Acceptance Criteria: Default scan_paths is ["."]).

        Task: T023
        """
        from fs2.config.objects import ScanConfig

        config = ScanConfig()

        assert config.scan_paths == ["."]

    def test_scan_config_max_file_size_kb_defaults_to_500(self):
        """
        Purpose: Verifies max_file_size_kb default is reasonable.
        Quality Contribution: Prevents scanning giant files by default.
        Acceptance Criteria: Default is 500 KB.

        Task: T023
        """
        from fs2.config.objects import ScanConfig

        config = ScanConfig()

        assert config.max_file_size_kb == 500

    def test_scan_config_respect_gitignore_defaults_to_true(self):
        """
        Purpose: Verifies respect_gitignore default is True.
        Quality Contribution: Honors developer intent by default (AC2, AC3).
        Acceptance Criteria: Default is True.

        Task: T023
        """
        from fs2.config.objects import ScanConfig

        config = ScanConfig()

        assert config.respect_gitignore is True

    def test_scan_config_follow_symlinks_defaults_to_false(self):
        """
        Purpose: Verifies follow_symlinks defaults to False.
        Quality Contribution: Prevents infinite loops from circular symlinks (Finding 06).
        Acceptance Criteria: Default is False.

        Task: T024
        """
        from fs2.config.objects import ScanConfig

        config = ScanConfig()

        assert config.follow_symlinks is False

    def test_scan_config_sample_lines_for_large_files_field(self):
        """
        Purpose: Verifies sample_lines_for_large_files field exists.
        Quality Contribution: Enables large file sampling (Finding 12, AC6).
        Acceptance Criteria: Field exists with default value.

        Task: T025
        """
        from fs2.config.objects import ScanConfig

        config = ScanConfig()

        assert hasattr(config, "sample_lines_for_large_files")
        assert config.sample_lines_for_large_files == 1000  # Default 1000 lines


@pytest.mark.unit
class TestScanConfigValidation:
    """Tests for ScanConfig validation (T026)."""

    def test_scan_config_validates_scan_paths_is_list(self):
        """
        Purpose: Verifies scan_paths must be a list.
        Quality Contribution: Catches misconfiguration early.
        Acceptance Criteria: ValidationError for non-list value.

        Task: T026
        """
        from fs2.config.objects import ScanConfig

        # String instead of list should fail
        with pytest.raises(ValidationError):
            ScanConfig(scan_paths="./src")  # type: ignore

    def test_scan_config_validates_max_file_size_kb_positive(self):
        """
        Purpose: Verifies max_file_size_kb must be positive.
        Quality Contribution: Prevents invalid configuration.
        Acceptance Criteria: ValidationError for zero or negative.

        Task: T026
        """
        from fs2.config.objects import ScanConfig

        with pytest.raises(ValidationError):
            ScanConfig(max_file_size_kb=0)

        with pytest.raises(ValidationError):
            ScanConfig(max_file_size_kb=-100)

    def test_scan_config_validates_sample_lines_positive(self):
        """
        Purpose: Verifies sample_lines_for_large_files must be positive.
        Quality Contribution: Prevents invalid configuration.
        Acceptance Criteria: ValidationError for zero or negative.

        Task: T026
        """
        from fs2.config.objects import ScanConfig

        with pytest.raises(ValidationError):
            ScanConfig(sample_lines_for_large_files=0)

        with pytest.raises(ValidationError):
            ScanConfig(sample_lines_for_large_files=-10)

    def test_scan_config_accepts_valid_configuration(self):
        """
        Purpose: Verifies valid configuration is accepted.
        Quality Contribution: Confirms happy path works.
        Acceptance Criteria: No error for valid values.

        Task: T026
        """
        from fs2.config.objects import ScanConfig

        config = ScanConfig(
            scan_paths=["./src", "./tests"],
            max_file_size_kb=1000,
            respect_gitignore=False,
            follow_symlinks=True,
            sample_lines_for_large_files=500,
        )

        assert config.scan_paths == ["./src", "./tests"]
        assert config.max_file_size_kb == 1000
        assert config.respect_gitignore is False
        assert config.follow_symlinks is True
        assert config.sample_lines_for_large_files == 500
