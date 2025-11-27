"""ConfigurationService ABC and implementations for fs2.

This module provides:
- ConfigurationService: Abstract base class defining the config interface
- FS2ConfigurationService: Production implementation with multi-source loading
- FakeConfigurationService: Test double for DI in tests

Per Architecture Decision: Typed object registry pattern.
Per Insight #1: No singleton, explicit construction via DI.
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)
from typing import TypeVar

from pydantic import BaseModel

from fs2.config.exceptions import MissingConfigurationError
from fs2.config.loaders import (
    deep_merge,
    expand_placeholders,
    load_secrets_to_env,
    load_yaml_config,
    parse_env_vars,
)
from fs2.config.objects import YAML_CONFIG_TYPES
from fs2.config.paths import get_project_config_dir, get_user_config_dir

T = TypeVar("T", bound=BaseModel)


class ConfigurationService(ABC):
    """Abstract base class for configuration services.

    Provides a typed object registry pattern where config objects
    are stored and retrieved by type.

    Methods:
        set: Store a typed config object.
        get: Retrieve a config object by type (returns None if not set).
        require: Retrieve a config object by type (raises if not set).
    """

    @abstractmethod
    def set(self, config: T) -> None:
        """Store a typed configuration object.

        Args:
            config: Pydantic BaseModel instance to store.
        """

    @abstractmethod
    def get(self, config_type: type[T]) -> T | None:
        """Retrieve a configuration object by type.

        Args:
            config_type: The type of config to retrieve.

        Returns:
            The config object if set, None otherwise.
        """

    @abstractmethod
    def require(self, config_type: type[T]) -> T:
        """Retrieve a configuration object by type, raising if not set.

        Args:
            config_type: The type of config to retrieve.

        Returns:
            The config object.

        Raises:
            MissingConfigurationError: If config type is not set.
        """


class FS2ConfigurationService(ConfigurationService):
    """Production configuration service with multi-source loading.

    Loading pipeline (executed in __init__):
    1. Load secrets into os.environ (user → project → .env)
    2. Build raw config dict (user YAML → project YAML → env vars)
    3. Expand ${VAR} placeholders
    4. Create typed config objects from YAML_CONFIG_TYPES

    Precedence (lowest → highest):
    - Config object defaults
    - User YAML (~/.config/fs2/config.yaml)
    - Project YAML (./.fs2/config.yaml)
    - Environment vars (FS2_*)
    """

    def __init__(self) -> None:
        """Initialize the service, loading all config sources."""
        self._configs: dict[type, BaseModel] = {}

        # Phase 1: Load secrets into os.environ
        load_secrets_to_env()

        # Phase 2: Build raw config dict
        raw_config: dict = {}

        # User config (lowest priority)
        user_config_file = get_user_config_dir() / "config.yaml"
        raw_config = deep_merge(raw_config, load_yaml_config(user_config_file))

        # Project config (overrides user)
        project_config_file = get_project_config_dir() / "config.yaml"
        raw_config = deep_merge(raw_config, load_yaml_config(project_config_file))

        # Env vars (highest priority)
        raw_config = deep_merge(raw_config, parse_env_vars())

        # Phase 3: Expand ${VAR} placeholders
        expand_placeholders(raw_config)

        # Phase 4: Create typed config objects
        self._create_config_objects(raw_config)

    def _create_config_objects(self, raw_config: dict) -> None:
        """Create typed config objects from raw config dict.

        For each config type in YAML_CONFIG_TYPES, extracts data from
        raw_config using __config_path__ and creates the typed object.
        """
        for config_type in YAML_CONFIG_TYPES:
            config_path = getattr(config_type, "__config_path__", None)
            if config_path is None:
                continue

            # Navigate to the config data using path (e.g., "azure.openai")
            data = raw_config
            for part in config_path.split("."):
                if not isinstance(data, dict) or part not in data:
                    data = None
                    break
                data = data[part]

            # Create typed object if data was found
            if data and isinstance(data, dict):
                try:
                    config_obj = config_type(**data)
                    self.set(config_obj)
                except Exception as e:
                    # Skip invalid configs - validation error will surface
                    # when consumer tries to require() it
                    logger.debug(
                        "Failed to create %s from config path '%s': %s",
                        config_type.__name__,
                        config_path,
                        e,
                    )

    def set(self, config: T) -> None:
        """Store a typed configuration object."""
        self._configs[type(config)] = config

    def get(self, config_type: type[T]) -> T | None:
        """Retrieve a configuration object by type."""
        return self._configs.get(config_type)  # type: ignore

    def require(self, config_type: type[T]) -> T:
        """Retrieve a configuration object by type, raising if not set."""
        config = self.get(config_type)
        if config is None:
            raise MissingConfigurationError(
                key=config_type.__name__,
                sources=[
                    f"Set via: config.set({config_type.__name__}(...))",
                    f"Or in YAML at: {getattr(config_type, '__config_path__', 'N/A')}",
                ],
            )
        return config


class FakeConfigurationService(ConfigurationService):
    """Test double for ConfigurationService.

    Accepts config objects in constructor for easy test setup.

    Usage:
        config = FakeConfigurationService(
            AzureOpenAIConfig(endpoint="..."),
            SearchQueryConfig(mode="slim"),
        )
        service = MyService(config=config)
    """

    def __init__(self, *configs: BaseModel) -> None:
        """Initialize with optional pre-set configs.

        Args:
            *configs: Typed config objects to pre-load.
        """
        self._configs: dict[type, BaseModel] = {}
        for config in configs:
            self.set(config)

    def set(self, config: T) -> None:
        """Store a typed configuration object."""
        self._configs[type(config)] = config

    def get(self, config_type: type[T]) -> T | None:
        """Retrieve a configuration object by type."""
        return self._configs.get(config_type)  # type: ignore

    def require(self, config_type: type[T]) -> T:
        """Retrieve a configuration object by type, raising if not set."""
        config = self.get(config_type)
        if config is None:
            raise MissingConfigurationError(
                key=config_type.__name__,
                sources=[
                    f"Set via: config.set({config_type.__name__}(...))",
                ],
            )
        return config
