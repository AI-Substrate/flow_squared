"""Tests for YAML config source.

TDD Phase: RED - These tests should fail until T008 is implemented.

Tests cover:
- YAML file loading from .fs2/config.yaml
- Missing file graceful handling (returns {})
- Invalid YAML graceful handling
"""

import pytest


@pytest.mark.unit
def test_given_yaml_config_when_loading_then_values_applied(monkeypatch, tmp_path):
    """
    Purpose: Proves YAML config file is loaded and values applied
    Quality Contribution: Validates primary config file support
    Acceptance Criteria:
    - YAML file at .fs2/config.yaml is read
    - Values from YAML are applied to settings
    """
    # Arrange
    yaml_content = """\
azure:
  openai:
    endpoint: https://yaml-endpoint.openai.azure.com
    api_version: "2024-03-01"
"""
    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text(yaml_content)
    monkeypatch.chdir(tmp_path)

    # Act
    from fs2.config.models import FS2Settings

    config = FS2Settings()

    # Assert
    assert config.azure.openai.endpoint == "https://yaml-endpoint.openai.azure.com"
    assert config.azure.openai.api_version == "2024-03-01"


@pytest.mark.unit
def test_given_no_yaml_file_when_loading_then_uses_defaults(monkeypatch, tmp_path):
    """
    Purpose: Proves missing YAML file is handled gracefully
    Quality Contribution: Prevents crash when config file doesn't exist
    Acceptance Criteria:
    - No .fs2/config.yaml exists
    - Settings loads with defaults (no exception)
    """
    # Arrange - tmp_path has no .fs2/config.yaml
    monkeypatch.chdir(tmp_path)

    # Act
    from fs2.config.models import FS2Settings

    config = FS2Settings()

    # Assert - defaults are used
    assert config.azure.openai.timeout == 30
    assert config.azure.openai.api_version == "2024-02-01"


@pytest.mark.unit
def test_given_empty_yaml_file_when_loading_then_uses_defaults(monkeypatch, tmp_path):
    """
    Purpose: Proves empty YAML file is handled gracefully
    Quality Contribution: Handles edge case of empty config file
    Acceptance Criteria:
    - .fs2/config.yaml exists but is empty
    - Settings loads with defaults (no exception)
    """
    # Arrange
    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text("")  # Empty file
    monkeypatch.chdir(tmp_path)

    # Act
    from fs2.config.models import FS2Settings

    config = FS2Settings()

    # Assert - defaults are used
    assert config.azure.openai.timeout == 30


@pytest.mark.unit
def test_given_yaml_with_partial_config_when_loading_then_merges_with_defaults(
    monkeypatch, tmp_path
):
    """
    Purpose: Proves partial YAML config merges with defaults
    Quality Contribution: Validates incremental config approach
    Acceptance Criteria:
    - YAML sets only endpoint
    - Other fields retain defaults
    """
    # Arrange
    yaml_content = """\
azure:
  openai:
    endpoint: https://partial.openai.azure.com
"""
    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text(yaml_content)
    monkeypatch.chdir(tmp_path)

    # Act
    from fs2.config.models import FS2Settings

    config = FS2Settings()

    # Assert
    assert config.azure.openai.endpoint == "https://partial.openai.azure.com"
    assert config.azure.openai.timeout == 30  # Default preserved
    assert config.azure.openai.api_version == "2024-02-01"  # Default preserved
