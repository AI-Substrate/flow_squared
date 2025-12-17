"""Pydantic configuration models for fs2.

This module contains:
- FS2Settings: Root configuration with multi-source loading
- AzureConfig, OpenAIConfig: Nested configuration models
- YamlConfigSettingsSource: Custom YAML loader

Per Insight #6: Load .env at import with override=False for production behavior.
Per Finding 04: Use env_prefix='FS2_' and env_nested_delimiter='__'.
Per Finding 11: Config MUST NOT import from fs2.core.*.
Per Insight #3: CWD-relative path; future migration to ~/.config/fs2/
Per Insight #5: Two-stage validation with shared _is_literal_secret() function.
"""

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from fs2.config.exceptions import LiteralSecretError, MissingConfigurationError

# Regex to match ${VAR} or ${VAR} patterns
_PLACEHOLDER_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _is_literal_secret(value: str | None) -> bool:
    """Check if value looks like a literal secret (not a placeholder).

    Per Insight #5: Shared validation function for two-stage validation.
    Per Insight #4: Only applies to secret-bearing fields like api_key.

    Args:
        value: The value to check

    Returns:
        True if value appears to be a literal secret, False otherwise
    """
    if not value:
        return False
    # Allow placeholders through
    if value.startswith("${"):
        return False
    # Reject known secret patterns
    if value.startswith("sk-"):
        return True
    # Reject unusually long values (likely API keys)
    return len(value) > 64


class OpenAIConfig(BaseModel):
    """Azure OpenAI configuration.

    Fields:
    - endpoint: Azure OpenAI endpoint URL (optional)
    - api_version: API version string (default: 2024-02-01)
    - deployment_name: Deployment name (optional)
    - api_key: API key - use ${AZURE_OPENAI_API_KEY} placeholder (optional)
    - timeout: Request timeout in seconds (default: 30)

    Security: api_key field has literal secret detection.
    """

    endpoint: str | None = None
    api_version: str = "2024-02-01"
    deployment_name: str | None = None
    api_key: str | None = None
    timeout: int = 30

    @field_validator("api_key")
    @classmethod
    def validate_no_literal_secret(cls, v: str | None) -> str | None:
        """Reject literal secrets in config.

        Per Finding 02: field_validator runs BEFORE model_validator.
        Allow placeholders through; reject obvious literal secrets.
        """
        if _is_literal_secret(v):
            raise LiteralSecretError(field="api_key")
        return v


class AzureConfig(BaseModel):
    """Azure service configuration container.

    Contains nested configurations for Azure services.
    """

    openai: OpenAIConfig = OpenAIConfig()


class YamlConfigSettingsSource(PydanticBaseSettingsSource):
    """Custom settings source to load from .fs2/config.yaml.

    Per py_sample_repo pattern. Config file is optional - returns {}
    if file doesn't exist or is invalid YAML.

    NOTE: Current scaffold uses CWD-relative .fs2/config.yaml
    Future production will use ~/.config/fs2/config.yaml (XDG spec)
    Keep path resolution in this single location for easy migration.
    """

    # Path relative to CWD; TODO: migrate to ~/.config/fs2/
    CONFIG_PATH = Path(".fs2/config.yaml")

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        """Required by base class - not used for dict-based sources."""
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        """Load YAML config file if it exists.

        Returns:
            Config dict or {} if file missing/invalid.
        """
        config_path = self.CONFIG_PATH
        if not config_path.exists():
            return {}
        try:
            with open(config_path) as f:
                data = yaml.safe_load(f)
                return data if data else {}
        except yaml.YAMLError:
            # Graceful fallback on invalid YAML
            return {}


def _expand_string(value: str) -> str:
    """Expand ${ENV_VAR} placeholders in a string.

    Args:
        value: String potentially containing ${VAR} placeholders

    Returns:
        String with placeholders replaced by env var values

    Raises:
        MissingConfigurationError: If referenced env var is not set
    """

    def replace_placeholder(match: re.Match) -> str:
        var_name = match.group(1)
        env_value = os.environ.get(var_name)
        if env_value is None:
            raise MissingConfigurationError(
                key=var_name,
                sources=[f"Environment variable: {var_name}"],
            )
        return env_value

    return _PLACEHOLDER_PATTERN.sub(replace_placeholder, value)


def _expand_recursive(obj: Any) -> None:
    """Recursively expand ${ENV_VAR} placeholders in nested objects.

    Per Finding 10: Use object.__setattr__() and recurse into nested BaseModel.

    Args:
        obj: Object to process (BaseModel or other)
    """
    if not isinstance(obj, BaseModel):
        return

    for field_name in obj.__class__.model_fields:
        field_value = getattr(obj, field_name)
        if isinstance(field_value, str):
            expanded = _expand_string(field_value)
            object.__setattr__(obj, field_name, expanded)
        elif isinstance(field_value, BaseModel):
            _expand_recursive(field_value)


class FS2Settings(BaseSettings):
    """Root configuration for Flowspace2.

    Supports multi-source loading with precedence:
    1. Environment variables (FS2_* prefix)
    2. YAML config file (.fs2/config.yaml)
    3. .env file
    4. Default values

    Usage:
        # Production (singleton)
        from fs2.config import settings

        # Tests (fresh instance)
        from fs2.config.models import FS2Settings
        config = FS2Settings()
    """

    model_config = SettingsConfigDict(
        env_prefix="FS2_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",  # Allow extra fields in YAML (scan, graph, etc.)
    )

    azure: AzureConfig = AzureConfig()

    @model_validator(mode="after")
    def expand_env_vars(self) -> "FS2Settings":
        """Expand ${ENV_VAR} placeholders after all sources are loaded.

        Per Finding 02: model_validator runs AFTER field_validators.
        This is where we expand placeholders and do final validation.

        Per Insight #5: Re-validate after expansion to catch secrets
        that came from environment variables.
        """
        _expand_recursive(self.azure)

        # Post-expansion security check per Insight #5
        if _is_literal_secret(self.azure.openai.api_key):
            raise LiteralSecretError(field="api_key")

        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings source precedence.

        Order (highest to lowest priority):
        1. init_settings (programmatic)
        2. env_settings (FS2_* environment variables)
        3. YamlConfigSettingsSource (.fs2/config.yaml)
        4. dotenv_settings (.env file)
        5. Default values (from field definitions)

        Per AC6: env vars → YAML → .env → defaults
        """
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls),
            dotenv_settings,
        )
