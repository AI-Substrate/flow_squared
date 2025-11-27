"""Tests for FS2Settings basic loading with defaults.

TDD Phase: RED - These tests should fail until T002 is implemented.

Tests cover:
- FS2Settings instantiation
- Default values
- BaseSettings inheritance verification
"""

import pytest


@pytest.mark.unit
def test_given_no_config_when_creating_settings_then_instance_created():
    """
    Purpose: Proves FS2Settings can be instantiated with defaults
    Quality Contribution: Foundation for all config tests
    Acceptance Criteria:
    - FS2Settings() returns an instance
    - No exceptions raised with empty environment
    """
    # Arrange
    from fs2.config.models import FS2Settings

    # Act
    config = FS2Settings()

    # Assert
    assert config is not None


@pytest.mark.unit
def test_given_settings_class_when_checking_inheritance_then_is_base_settings():
    """
    Purpose: Proves FS2Settings inherits from pydantic_settings.BaseSettings
    Quality Contribution: Ensures multi-source loading capability
    Acceptance Criteria:
    - FS2Settings is subclass of BaseSettings
    """
    # Arrange
    from pydantic_settings import BaseSettings

    from fs2.config.models import FS2Settings

    # Act & Assert
    assert issubclass(FS2Settings, BaseSettings)


@pytest.mark.unit
def test_given_settings_instance_when_checking_type_then_is_base_settings_instance():
    """
    Purpose: Proves instances are BaseSettings instances
    Quality Contribution: Confirms runtime type compatibility
    Acceptance Criteria:
    - isinstance(config, BaseSettings) returns True
    """
    # Arrange
    from pydantic_settings import BaseSettings

    from fs2.config.models import FS2Settings

    # Act
    config = FS2Settings()

    # Assert
    assert isinstance(config, BaseSettings)


@pytest.mark.unit
def test_given_settings_when_accessing_model_config_then_has_env_prefix():
    """
    Purpose: Proves model_config has FS2_ env_prefix per Finding 04
    Quality Contribution: Prevents env var namespace collisions
    Acceptance Criteria:
    - model_config.env_prefix == 'FS2_'
    """
    # Arrange
    from fs2.config.models import FS2Settings

    # Act
    config = FS2Settings()

    # Assert
    assert config.model_config.get("env_prefix") == "FS2_"


@pytest.mark.unit
def test_given_settings_when_accessing_model_config_then_has_double_underscore_delimiter():
    """
    Purpose: Proves model_config uses __ delimiter per Finding 04
    Quality Contribution: Prevents field name splitting issues (deployment_name)
    Acceptance Criteria:
    - model_config.env_nested_delimiter == '__'
    """
    # Arrange
    from fs2.config.models import FS2Settings

    # Act
    config = FS2Settings()

    # Assert
    assert config.model_config.get("env_nested_delimiter") == "__"
