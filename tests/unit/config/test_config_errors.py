"""Tests for ConfigurationError actionable messages.

TDD Phase: Tests for error hierarchy and actionable messages.

Tests cover:
- MissingConfigurationError has key and sources
- LiteralSecretError has field name
- Error messages include fix instructions
"""

import pytest


@pytest.mark.unit
def test_given_missing_config_error_when_created_then_has_key():
    """
    Purpose: Proves MissingConfigurationError stores key
    Quality Contribution: Enables programmatic error handling
    """
    # Arrange
    from fs2.config.exceptions import MissingConfigurationError

    # Act
    error = MissingConfigurationError(key="MY_VAR", sources=["env: MY_VAR"])

    # Assert
    assert error.key == "MY_VAR"


@pytest.mark.unit
def test_given_missing_config_error_when_created_then_has_sources():
    """
    Purpose: Proves MissingConfigurationError stores sources
    Quality Contribution: Enables programmatic error handling
    """
    # Arrange
    from fs2.config.exceptions import MissingConfigurationError

    sources = ["Environment variable: MY_VAR", "YAML: azure.openai.api_key"]

    # Act
    error = MissingConfigurationError(key="MY_VAR", sources=sources)

    # Assert
    assert error.sources == sources


@pytest.mark.unit
def test_given_missing_config_error_when_to_string_then_actionable():
    """
    Purpose: Proves error message includes fix instructions
    Quality Contribution: Per Finding 05 - actionable error messages
    """
    # Arrange
    from fs2.config.exceptions import MissingConfigurationError

    # Act
    error = MissingConfigurationError(
        key="AZURE_OPENAI_API_KEY",
        sources=["Environment variable: AZURE_OPENAI_API_KEY"],
    )

    # Assert
    msg = str(error)
    assert "AZURE_OPENAI_API_KEY" in msg
    assert "Environment variable" in msg
    assert "Set one of" in msg


@pytest.mark.unit
def test_given_literal_secret_error_when_created_then_has_field():
    """
    Purpose: Proves LiteralSecretError stores field name
    Quality Contribution: Enables programmatic error handling
    """
    # Arrange
    from fs2.config.exceptions import LiteralSecretError

    # Act
    error = LiteralSecretError(field="api_key")

    # Assert
    assert error.field == "api_key"


@pytest.mark.unit
def test_given_literal_secret_error_when_to_string_then_suggests_placeholder():
    """
    Purpose: Proves error message suggests using placeholder
    Quality Contribution: Per Finding 05 - actionable error messages
    """
    # Arrange
    from fs2.config.exceptions import LiteralSecretError

    # Act
    error = LiteralSecretError(field="api_key")

    # Assert
    msg = str(error)
    assert "placeholder" in msg.lower()
    assert "${" in msg
    assert "api_key" in msg.lower()


@pytest.mark.unit
def test_given_configuration_error_when_raised_then_catchable():
    """
    Purpose: Proves ConfigurationError is catchable base class
    Quality Contribution: Enables broad exception handling
    """
    # Arrange
    from fs2.config.exceptions import (
        ConfigurationError,
        LiteralSecretError,
        MissingConfigurationError,
    )

    # Act & Assert
    # Both should be catchable as ConfigurationError
    with pytest.raises(ConfigurationError):
        raise MissingConfigurationError(key="test", sources=["test"])

    with pytest.raises(ConfigurationError):
        raise LiteralSecretError(field="test")


@pytest.mark.unit
def test_given_literal_secret_in_yaml_when_loading_then_actionable_error(
    monkeypatch, tmp_path
):
    """
    Purpose: Proves literal secret in YAML raises actionable error
    Quality Contribution: End-to-end validation of error path
    """
    # Arrange
    yaml_content = """\
azure:
  openai:
    api_key: sk-supersecretkey12345
"""
    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text(yaml_content)
    monkeypatch.chdir(tmp_path)

    # Act & Assert
    from fs2.config.exceptions import LiteralSecretError
    from fs2.config.models import FS2Settings

    with pytest.raises(LiteralSecretError) as exc_info:
        FS2Settings()

    assert "placeholder" in str(exc_info.value).lower()
