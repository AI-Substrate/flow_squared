"""Configuration system using Pydantic-settings.

This module provides the configuration system for Flowspace2.

Usage:
    # Production (singleton - validates at import time):
    from fs2.config import settings
    print(settings.azure.openai.endpoint)

    # Tests (fresh instance - for test isolation):
    from fs2.config.models import FS2Settings
    config = FS2Settings()  # Creates new instance

Per Finding 01: Dual import paths enable fail-fast production
behavior while maintaining test isolation.

Per Insight #2: If you accidentally import settings in tests,
you'll see a warning from pytest_configure.
"""

from fs2.config.exceptions import (
    ConfigurationError,
    LiteralSecretError,
    MissingConfigurationError,
)
from fs2.config.models import FS2Settings

# Module-level singleton - instantiated at import time
# This enables fail-fast validation in production
settings: FS2Settings = FS2Settings()

__all__ = [
    "settings",
    "FS2Settings",
    "ConfigurationError",
    "MissingConfigurationError",
    "LiteralSecretError",
]
