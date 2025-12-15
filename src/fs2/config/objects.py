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


class SampleServiceConfig(BaseModel):
    """Configuration for SampleService.

    Loaded from YAML or environment variables.
    Path: sample.service (e.g., FS2_SAMPLE__SERVICE__RETRY_COUNT)

    This is a canonical example demonstrating service configuration.
    The service behavior is controlled by config, not hardcoded.

    Attributes:
        retry_count: Number of times to retry on failure (0 = no retry).
        validate_before_process: Whether to validate input before processing.
        include_timing: Whether to include timing metadata in results.

    YAML example:
        ```yaml
        # .fs2/config.yaml
        sample:
          service:
            retry_count: 3
            validate_before_process: true
            include_timing: false
        ```
    """

    __config_path__: ClassVar[str] = "sample.service"

    retry_count: int = 0
    validate_before_process: bool = True
    include_timing: bool = False


class SampleAdapterConfig(BaseModel):
    """Configuration for SampleAdapter implementations.

    Loaded from YAML or environment variables.
    Path: sample.adapter (e.g., FS2_SAMPLE__ADAPTER__PREFIX)

    This is a canonical example demonstrating adapter configuration.
    The adapter behavior is controlled by config, not hardcoded.

    Attributes:
        prefix: String to prepend to processed output.
        max_length: Maximum allowed input length (0 = unlimited).
        fail_on_empty: Whether to fail when input is empty.
        simulate_error: If set, process() returns this error message (testing only).

    YAML example:
        ```yaml
        # .fs2/config.yaml
        sample:
          adapter:
            prefix: "processed"
            max_length: 0
            fail_on_empty: true
        ```
    """

    __config_path__: ClassVar[str] = "sample.adapter"

    prefix: str = "processed"
    max_length: int = 0
    fail_on_empty: bool = True
    simulate_error: str | None = None


class LogAdapterConfig(BaseModel):
    """Configuration for LogAdapter implementations.

    Loaded from YAML or environment variables.
    Path: log.adapter (e.g., FS2_LOG__ADAPTER__MIN_LEVEL)

    Controls logging behavior for ConsoleLogAdapter and FakeLogAdapter.

    Attributes:
        min_level: Minimum log level to output (DEBUG, INFO, WARNING, ERROR).
                   Messages below this level are filtered out.
                   Default: DEBUG (all messages shown).

    YAML example:
        ```yaml
        # .fs2/config.yaml
        log:
          adapter:
            min_level: INFO  # Filters out DEBUG messages
        ```

    Note:
        min_level is stored as string for YAML compatibility.
        Use LogLevel enum values: DEBUG, INFO, WARNING, ERROR.
    """

    __config_path__: ClassVar[str] = "log.adapter"

    min_level: str = "DEBUG"


class ScanConfig(BaseModel):
    """Configuration for file scanning operations.

    Loaded from YAML or environment variables.
    Path: scan (e.g., FS2_SCAN__MAX_FILE_SIZE_KB)

    Controls how fs2 scans directories for source files.
    Per spec AC1: Configuration loading for scan paths.
    Per Critical Finding 06: follow_symlinks defaults to False.
    Per Critical Finding 12: sample_lines_for_large_files for large file handling.

    Attributes:
        scan_paths: List of paths to scan (relative or absolute).
        max_file_size_kb: Maximum file size in KB to fully parse (default: 500).
                          Files larger than this are sampled.
        respect_gitignore: Whether to respect .gitignore patterns (default: True).
        follow_symlinks: Whether to follow symbolic links (default: False).
                         False prevents infinite loops from circular symlinks.
        sample_lines_for_large_files: Number of lines to sample from large files
                                      (default: 1000). Per AC6.

    YAML example:
        ```yaml
        # .fs2/config.yaml
        scan:
          scan_paths:
            - "./src"
            - "./lib"
          max_file_size_kb: 1000
          respect_gitignore: true
          follow_symlinks: false
          sample_lines_for_large_files: 2000
        ```
    """

    __config_path__: ClassVar[str] = "scan"

    scan_paths: list[str] = ["."]
    max_file_size_kb: int = 500
    respect_gitignore: bool = True
    follow_symlinks: bool = False
    sample_lines_for_large_files: int = 1000

    @field_validator("max_file_size_kb")
    @classmethod
    def validate_max_file_size_kb(cls, v: int) -> int:
        """Validate max_file_size_kb is positive."""
        if v <= 0:
            raise ValueError("max_file_size_kb must be positive")
        return v

    @field_validator("sample_lines_for_large_files")
    @classmethod
    def validate_sample_lines(cls, v: int) -> int:
        """Validate sample_lines_for_large_files is positive."""
        if v <= 0:
            raise ValueError("sample_lines_for_large_files must be positive")
        return v


# Registry of config types to auto-load from YAML/env
# Only configs with __config_path__ != None should be in this list
YAML_CONFIG_TYPES: list[type[BaseModel]] = [
    AzureOpenAIConfig,
    SampleServiceConfig,
    SampleAdapterConfig,
    LogAdapterConfig,
    ScanConfig,
]
