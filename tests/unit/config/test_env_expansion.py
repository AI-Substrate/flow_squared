"""Tests for placeholder expansion ${ENV_VAR}.

TDD Phase: RED - These tests should fail until T014 is implemented.

Tests cover:
- ${VAR} placeholder expansion in string fields
- Missing env var raises MissingConfigurationError
- Typed fields use env var override (not placeholder expansion) per Insight #1
- Multiple placeholders in single value
"""

import pytest


@pytest.mark.unit
def test_given_placeholder_in_yaml_when_env_set_then_expands(monkeypatch, tmp_path):
    """
    Purpose: Proves ${ENV_VAR} placeholders are expanded from environment
    Quality Contribution: Core config functionality
    Acceptance Criteria:
    - YAML has api_key: ${TEST_API_KEY}
    - Env has TEST_API_KEY=actual-key
    - Result: api_key='actual-key'
    """
    # Arrange
    yaml_content = """\
azure:
  openai:
    api_key: ${TEST_API_KEY}
"""
    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text(yaml_content)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TEST_API_KEY", "actual-key-value")

    # Act
    from fs2.config.models import FS2Settings

    config = FS2Settings()

    # Assert
    assert config.azure.openai.api_key == "actual-key-value"


@pytest.mark.unit
def test_given_placeholder_missing_env_when_loading_then_raises_error(
    monkeypatch, tmp_path
):
    """
    Purpose: Proves missing env var in placeholder raises actionable error
    Quality Contribution: Clear error messages for missing config
    Acceptance Criteria:
    - YAML has api_key: ${MISSING_VAR}
    - MISSING_VAR not set
    - Raises MissingConfigurationError with var name
    """
    # Arrange
    yaml_content = """\
azure:
  openai:
    api_key: ${MISSING_VAR}
"""
    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text(yaml_content)
    monkeypatch.chdir(tmp_path)
    # Ensure var is not set
    monkeypatch.delenv("MISSING_VAR", raising=False)

    # Act & Assert
    from fs2.config.exceptions import MissingConfigurationError
    from fs2.config.models import FS2Settings

    with pytest.raises(MissingConfigurationError) as exc_info:
        FS2Settings()

    assert "MISSING_VAR" in str(exc_info.value)


@pytest.mark.unit
def test_given_placeholder_with_embedded_text_when_expanding_then_preserves_text(
    monkeypatch, tmp_path
):
    """
    Purpose: Proves placeholders can be embedded in larger strings
    Quality Contribution: Supports URL patterns like https://${HOST}/api
    Acceptance Criteria:
    - YAML has endpoint: https://${HOST}/openai
    - Env has HOST=my.azure.com
    - Result: endpoint='https://my.azure.com/openai'
    """
    # Arrange
    yaml_content = """\
azure:
  openai:
    endpoint: https://${HOST}/openai
"""
    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text(yaml_content)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOST", "my.azure.com")

    # Act
    from fs2.config.models import FS2Settings

    config = FS2Settings()

    # Assert
    assert config.azure.openai.endpoint == "https://my.azure.com/openai"


@pytest.mark.unit
def test_given_multiple_placeholders_when_expanding_then_all_expand(
    monkeypatch, tmp_path
):
    """
    Purpose: Proves multiple placeholders in one value all expand
    Quality Contribution: Supports complex URL patterns
    Acceptance Criteria:
    - YAML has endpoint: https://${HOST}:${PORT}/api
    - Both vars set
    - Result: both expanded
    """
    # Arrange
    yaml_content = """\
azure:
  openai:
    endpoint: https://${HOST}:${PORT}/api
"""
    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text(yaml_content)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOST", "localhost")
    monkeypatch.setenv("PORT", "8080")

    # Act
    from fs2.config.models import FS2Settings

    config = FS2Settings()

    # Assert
    assert config.azure.openai.endpoint == "https://localhost:8080/api"


@pytest.mark.unit
def test_given_typed_field_when_env_var_set_then_no_placeholder_needed(monkeypatch):
    """
    Purpose: Proves typed fields (int, bool) use env var override directly
    Quality Contribution: Per Insight #1 - typed fields don't need ${} syntax
    Acceptance Criteria:
    - timeout is int field
    - FS2_AZURE__OPENAI__TIMEOUT=120 sets it directly
    - No placeholder expansion needed
    """
    # Arrange
    monkeypatch.setenv("FS2_AZURE__OPENAI__TIMEOUT", "120")

    # Act
    from fs2.config.models import FS2Settings

    config = FS2Settings()

    # Assert
    assert config.azure.openai.timeout == 120
    assert isinstance(config.azure.openai.timeout, int)


@pytest.mark.unit
def test_given_no_placeholder_when_loading_then_value_unchanged(monkeypatch, tmp_path):
    """
    Purpose: Proves non-placeholder values pass through unchanged
    Quality Contribution: Ensures expansion doesn't break literal values
    Acceptance Criteria:
    - YAML has api_version: 2024-02-01 (no placeholder)
    - Result: api_version='2024-02-01'
    """
    # Arrange
    yaml_content = """\
azure:
  openai:
    api_version: "2024-02-01"
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
    assert config.azure.openai.api_version == "2024-02-01"
