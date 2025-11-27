"""Tests for ConfigurationService instance patterns.

Updated for new architecture: No singleton - explicit construction via DI.

Tests cover:
- ConfigurationService creates fresh instances
- FakeConfigurationService for test isolation
- Legacy FS2Settings still creates fresh instances

Per Architecture Decision: No singleton, ConfigurationService owns loading pipeline.
Per Insight #1: Eliminated singletons to avoid race conditions.
"""

import pytest


@pytest.mark.unit
def test_given_configuration_service_when_created_twice_then_different_instances(
    monkeypatch, tmp_path
):
    """
    Purpose: Proves FS2ConfigurationService creates fresh instances
    Quality Contribution: Validates DI pattern - no singleton pollution
    """
    # Arrange
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.chdir(tmp_path)

    # Act
    from fs2.config import FS2ConfigurationService

    config1 = FS2ConfigurationService()
    config2 = FS2ConfigurationService()

    # Assert: Different instances
    assert config1 is not config2


@pytest.mark.unit
def test_given_fresh_import_when_created_twice_then_different_instances():
    """
    Purpose: Proves FS2Settings creates fresh instances (legacy pattern)
    Quality Contribution: Validates test isolation pattern
    Acceptance Criteria:
    - `FS2Settings()` creates new instance each time
    """
    # Arrange
    from fs2.config.models import FS2Settings

    # Act
    config1 = FS2Settings()
    config2 = FS2Settings()

    # Assert
    assert config1 is not config2


@pytest.mark.unit
def test_given_fake_service_when_created_then_isolated_from_files():
    """
    Purpose: Proves FakeConfigurationService works without file access
    Quality Contribution: Validates test double pattern
    """
    # Arrange & Act
    from fs2.config import FakeConfigurationService, AzureOpenAIConfig

    config = FakeConfigurationService(
        AzureOpenAIConfig(endpoint="https://test.com")
    )

    # Assert: Works without any file system setup
    azure = config.get(AzureOpenAIConfig)
    assert azure is not None
    assert azure.endpoint == "https://test.com"


@pytest.mark.unit
def test_given_env_var_when_fresh_instance_created_then_picks_up_change(monkeypatch):
    """
    Purpose: Proves fresh instances pick up env var changes
    Quality Contribution: Validates test isolation with env var changes
    Acceptance Criteria:
    - Set env var, create fresh instance, see new value
    """
    # Arrange
    monkeypatch.setenv("FS2_AZURE__OPENAI__TIMEOUT", "99")

    # Act - fresh instance (legacy pattern)
    from fs2.config.models import FS2Settings

    config = FS2Settings()

    # Assert
    assert config.azure.openai.timeout == 99
