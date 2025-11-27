"""Tests for singleton vs fresh instance import paths.

TDD Phase: RED - Tests fail until T020 implements singleton in __init__.py

Tests cover:
- Production import: from fs2.config import settings (singleton)
- Test import: from fs2.config.models import FS2Settings (fresh instance)
- Singleton is same instance across imports
- Fresh instances are independent
"""

import pytest


@pytest.mark.unit
def test_given_singleton_import_when_accessed_twice_then_same_instance():
    """
    Purpose: Proves singleton is the same instance across imports
    Quality Contribution: Validates fail-fast singleton pattern
    Acceptance Criteria:
    - `from fs2.config import settings` returns same object
    """
    # Arrange & Act
    from fs2.config import settings as settings1
    from fs2.config import settings as settings2

    # Assert
    assert settings1 is settings2


@pytest.mark.unit
def test_given_fresh_import_when_created_twice_then_different_instances():
    """
    Purpose: Proves FS2Settings creates fresh instances
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
def test_given_singleton_when_imported_then_is_fs2settings_instance():
    """
    Purpose: Proves singleton is an FS2Settings instance
    Quality Contribution: Type safety validation
    """
    # Arrange & Act
    from fs2.config import settings
    from fs2.config.models import FS2Settings

    # Assert
    assert isinstance(settings, FS2Settings)


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

    # Act - fresh instance
    from fs2.config.models import FS2Settings

    config = FS2Settings()

    # Assert
    assert config.azure.openai.timeout == 99
