"""Configuration system for Flowspace2.

This module provides the ConfigurationService pattern for configuration management.

Usage:
    # Production - create ConfigurationService in main():
    from fs2.config import FS2ConfigurationService
    config = FS2ConfigurationService()  # Loads YAML/env
    config.set(SearchQueryConfig(mode="slim", text="query"))

    # Get typed config:
    azure = config.get(AzureOpenAIConfig)  # Returns None if not set
    search = config.require(SearchQueryConfig)  # Raises if not set

    # Tests - use FakeConfigurationService:
    from fs2.config import FakeConfigurationService
    config = FakeConfigurationService(
        AzureOpenAIConfig(endpoint="https://test.com"),
        SearchQueryConfig(mode="slim"),
    )

Per Architecture Decision: Typed object registry pattern.
Per Insight #1: No singleton - explicit construction via DI.

Legacy Note:
    The old FS2Settings Pydantic model still exists in models.py for
    backward compatibility during migration. New code should use
    ConfigurationService.
"""

from fs2.config.exceptions import (ConfigurationError, LiteralSecretError,
                                   MissingConfigurationError)
# Legacy export for backward compatibility
from fs2.config.models import FS2Settings
from fs2.config.objects import (YAML_CONFIG_TYPES, AzureOpenAIConfig,
                                SearchQueryConfig)
from fs2.config.service import (ConfigurationService, FakeConfigurationService,
                                FS2ConfigurationService)

__all__ = [
    # Primary API - ConfigurationService pattern
    "ConfigurationService",
    "FS2ConfigurationService",
    "FakeConfigurationService",
    # Config objects
    "AzureOpenAIConfig",
    "SearchQueryConfig",
    "YAML_CONFIG_TYPES",
    # Exceptions
    "ConfigurationError",
    "MissingConfigurationError",
    "LiteralSecretError",
    # Legacy (for migration)
    "FS2Settings",
]
