"""Tests for configuration precedence.

TDD Phase: RED then GREEN as features are implemented.

Tests cover:
- T005-T006: Env var precedence over defaults
- T009-T010: Full precedence order (env > YAML > .env > defaults)
- T011-T012: Leaf-level override behavior
"""

import pytest


@pytest.mark.unit
def test_given_env_var_when_loading_config_then_env_overrides_default(monkeypatch):
    """
    Purpose: Proves environment variables take precedence over defaults
    Quality Contribution: Prevents production misconfigurations
    Acceptance Criteria:
    - Default timeout is 30
    - FS2_AZURE__OPENAI__TIMEOUT=60 overrides to 60
    """
    # Arrange
    monkeypatch.setenv("FS2_AZURE__OPENAI__TIMEOUT", "60")

    # Act
    from fs2.config.models import FS2Settings

    config = FS2Settings()

    # Assert
    assert config.azure.openai.timeout == 60


@pytest.mark.unit
def test_given_env_var_for_string_field_when_loading_then_overrides_default(
    monkeypatch,
):
    """
    Purpose: Proves string fields can be overridden by env vars
    Quality Contribution: Validates basic env var functionality
    Acceptance Criteria:
    - Default api_version is '2024-02-01'
    - FS2_AZURE__OPENAI__API_VERSION overrides it
    """
    # Arrange
    monkeypatch.setenv("FS2_AZURE__OPENAI__API_VERSION", "2024-06-01")

    # Act
    from fs2.config.models import FS2Settings

    config = FS2Settings()

    # Assert
    assert config.azure.openai.api_version == "2024-06-01"


@pytest.mark.unit
def test_given_env_var_for_optional_field_when_loading_then_sets_value(monkeypatch):
    """
    Purpose: Proves optional (None default) fields can be set via env vars
    Quality Contribution: Validates production deployment pattern
    Acceptance Criteria:
    - Default endpoint is None
    - FS2_AZURE__OPENAI__ENDPOINT sets the value
    """
    # Arrange
    monkeypatch.setenv("FS2_AZURE__OPENAI__ENDPOINT", "https://my.openai.azure.com")

    # Act
    from fs2.config.models import FS2Settings

    config = FS2Settings()

    # Assert
    assert config.azure.openai.endpoint == "https://my.openai.azure.com"


@pytest.mark.unit
def test_given_env_var_with_type_coercion_when_loading_then_coerces_correctly(
    monkeypatch,
):
    """
    Purpose: Proves Pydantic handles string-to-int type coercion
    Quality Contribution: Validates env var usability
    Acceptance Criteria:
    - FS2_AZURE__OPENAI__TIMEOUT='120' (string) becomes timeout=120 (int)
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
def test_given_no_env_vars_when_loading_then_uses_defaults():
    """
    Purpose: Proves defaults are used when no env vars are set
    Quality Contribution: Validates graceful fallback
    Acceptance Criteria:
    - Without env vars, defaults are preserved
    """
    # Arrange - ensure clean environment (no FS2_ vars)
    # Note: This test may be affected by actual env; proper isolation in conftest

    # Act
    from fs2.config.models import FS2Settings

    config = FS2Settings()

    # Assert
    assert config.azure.openai.timeout == 30
    assert config.azure.openai.api_version == "2024-02-01"


# =============================================================================
# T009-T010: Full precedence order (env > YAML > .env > defaults)
# =============================================================================


@pytest.mark.unit
def test_given_yaml_and_env_when_loading_then_env_wins(monkeypatch, tmp_path):
    """
    Purpose: Proves env vars have higher precedence than YAML
    Quality Contribution: Validates precedence order per AC6
    Acceptance Criteria:
    - YAML has timeout=60
    - ENV has FS2_AZURE__OPENAI__TIMEOUT=90
    - Result: timeout=90 (env wins)
    """
    # Arrange
    yaml_content = """\
azure:
  openai:
    timeout: 60
"""
    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text(yaml_content)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FS2_AZURE__OPENAI__TIMEOUT", "90")

    # Act
    from fs2.config.models import FS2Settings

    config = FS2Settings()

    # Assert
    assert config.azure.openai.timeout == 90  # Env wins over YAML


@pytest.mark.unit
def test_given_yaml_only_when_loading_then_yaml_used(monkeypatch, tmp_path):
    """
    Purpose: Proves YAML values are used when no env vars set
    Quality Contribution: Validates YAML as second precedence source
    Acceptance Criteria:
    - YAML has timeout=45
    - No env var set
    - Result: timeout=45
    """
    # Arrange
    yaml_content = """\
azure:
  openai:
    timeout: 45
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
    assert config.azure.openai.timeout == 45  # YAML value used


# =============================================================================
# T011-T012: Leaf-level override behavior (Finding 08)
# =============================================================================


@pytest.mark.unit
def test_given_yaml_and_env_when_loading_then_env_wins_leaf_level(
    monkeypatch, tmp_path
):
    """
    Purpose: Proves leaf-level override (not atomic section replacement)
    Quality Contribution: Catches precedence bugs early (Finding 08)
    Acceptance Criteria:
    - YAML has endpoint=yaml-ep, timeout=30
    - ENV has endpoint=env-override
    - Result: endpoint=env-override, timeout=30 (not lost!)
    """
    # Arrange
    yaml_content = """\
azure:
  openai:
    endpoint: yaml-endpoint
    timeout: 45
"""
    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text(yaml_content)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FS2_AZURE__OPENAI__ENDPOINT", "env-override")

    # Act
    from fs2.config.models import FS2Settings

    config = FS2Settings()

    # Assert
    assert config.azure.openai.endpoint == "env-override"  # Env wins
    assert config.azure.openai.timeout == 45  # YAML preserved (leaf-level!)


@pytest.mark.unit
def test_given_multiple_yaml_fields_when_env_overrides_one_then_others_preserved(
    monkeypatch, tmp_path
):
    """
    Purpose: Proves partial env override preserves sibling fields from YAML
    Quality Contribution: Validates leaf-level merge behavior
    Acceptance Criteria:
    - YAML sets multiple fields
    - Env overrides only one
    - All non-overridden fields preserved from YAML
    """
    # Arrange
    yaml_content = """\
azure:
  openai:
    endpoint: yaml-endpoint
    api_version: "2024-05-01"
    timeout: 60
    deployment_name: yaml-deployment
"""
    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text(yaml_content)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FS2_AZURE__OPENAI__API_VERSION", "2024-07-01")

    # Act
    from fs2.config.models import FS2Settings

    config = FS2Settings()

    # Assert
    assert config.azure.openai.api_version == "2024-07-01"  # Env override
    assert config.azure.openai.endpoint == "yaml-endpoint"  # YAML preserved
    assert config.azure.openai.timeout == 60  # YAML preserved
    assert config.azure.openai.deployment_name == "yaml-deployment"  # YAML preserved
