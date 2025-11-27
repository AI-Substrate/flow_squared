"""Typed configuration objects for fs2.

This module contains Pydantic config models with:
- __config_path__: Where to find this config in YAML/env hierarchy
- Validation via @field_validator

Config Types:
- AzureOpenAIConfig: Azure OpenAI settings (from YAML/env)
- SearchQueryConfig: Search query settings (CLI-only)

Per Architecture Decision: Typed object registry pattern.
Per Insight #6: Pydantic validation on construction.
"""

from typing import ClassVar

from pydantic import BaseModel, field_validator


class AzureOpenAIConfig(BaseModel):
    """Azure OpenAI configuration.

    Loaded from YAML or environment variables.
    Path: azure.openai (e.g., FS2_AZURE__OPENAI__TIMEOUT)

    Attributes:
        endpoint: Azure OpenAI endpoint URL (optional).
        api_key: API key - use ${AZURE_OPENAI_API_KEY} placeholder (optional).
        api_version: API version string (default: 2024-02-01).
        deployment_name: Deployment name (optional).
        timeout: Request timeout in seconds (1-300, default: 30).
    """

    __config_path__: ClassVar[str] = "azure.openai"

    endpoint: str | None = None
    api_key: str | None = None
    api_version: str = "2024-02-01"
    deployment_name: str | None = None
    timeout: int = 30

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Validate timeout is in reasonable range."""
        if v < 1 or v > 300:
            raise ValueError("Timeout must be 1-300 seconds")
        return v


class SearchQueryConfig(BaseModel):
    """Search query configuration.

    Set by CLI commands, not loaded from YAML.
    Path: None (CLI-only)

    Attributes:
        mode: Search mode - "slim", "normal", or "detailed" (default: normal).
        text: Search text (optional).
        limit: Maximum results (default: 10).
    """

    __config_path__: ClassVar[str | None] = None

    mode: str = "normal"
    text: str | None = None
    limit: int = 10

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Validate mode is one of the allowed values."""
        allowed = ("slim", "normal", "detailed")
        if v not in allowed:
            raise ValueError(f"Mode must be one of: {', '.join(allowed)}")
        return v


# Registry of config types to auto-load from YAML/env
# Only configs with __config_path__ != None should be in this list
YAML_CONFIG_TYPES: list[type[BaseModel]] = [
    AzureOpenAIConfig,
]
