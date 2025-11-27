"""Tests for nested config structure (azure.openai.*).

TDD Phase: RED - These tests should fail until T004 is implemented.

Tests cover:
- Nested attribute access (settings.azure.openai.*)
- Double-underscore parsing for env vars
- Default values in nested configs
"""

import pytest


@pytest.mark.unit
def test_given_settings_when_accessing_azure_then_returns_azure_config():
    """
    Purpose: Proves top-level nesting works (settings.azure)
    Quality Contribution: Foundation for hierarchical config
    Acceptance Criteria:
    - config.azure is not None
    - config.azure is an AzureConfig instance
    """
    # Arrange
    from fs2.config.models import AzureConfig, FS2Settings

    # Act
    config = FS2Settings()

    # Assert
    assert config.azure is not None
    assert isinstance(config.azure, AzureConfig)


@pytest.mark.unit
def test_given_settings_when_accessing_azure_openai_then_returns_openai_config():
    """
    Purpose: Proves second-level nesting works (settings.azure.openai)
    Quality Contribution: Validates deep nesting for complex configs
    Acceptance Criteria:
    - config.azure.openai is not None
    - config.azure.openai is an OpenAIConfig instance
    """
    # Arrange
    from fs2.config.models import FS2Settings, OpenAIConfig

    # Act
    config = FS2Settings()

    # Assert
    assert config.azure.openai is not None
    assert isinstance(config.azure.openai, OpenAIConfig)


@pytest.mark.unit
def test_given_settings_when_accessing_nested_defaults_then_returns_expected_values():
    """
    Purpose: Proves nested fields have sensible defaults
    Quality Contribution: Ensures fail-safe configuration
    Acceptance Criteria:
    - config.azure.openai.api_version has default '2024-02-01'
    - config.azure.openai.timeout has default 30
    """
    # Arrange
    from fs2.config.models import FS2Settings

    # Act
    config = FS2Settings()

    # Assert
    assert config.azure.openai.api_version == "2024-02-01"
    assert config.azure.openai.timeout == 30


@pytest.mark.unit
def test_given_settings_when_accessing_optional_fields_then_returns_none():
    """
    Purpose: Proves optional fields default to None
    Quality Contribution: Validates optional config pattern
    Acceptance Criteria:
    - config.azure.openai.endpoint defaults to None
    - config.azure.openai.api_key defaults to None
    - config.azure.openai.deployment_name defaults to None
    """
    # Arrange
    from fs2.config.models import FS2Settings

    # Act
    config = FS2Settings()

    # Assert
    assert config.azure.openai.endpoint is None
    assert config.azure.openai.api_key is None
    assert config.azure.openai.deployment_name is None
