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

from typing import ClassVar, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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


class GraphConfig(BaseModel):
    """Configuration for graph access.

    Loaded from YAML or environment variables.
    Path: graph (e.g., FS2_GRAPH__GRAPH_PATH)

    Used by any service that needs to load/access the code graph.

    Attributes:
        graph_path: Path to the graph pickle file (default: .fs2/graph.pickle).

    YAML example:
        ```yaml
        # .fs2/config.yaml
        graph:
          graph_path: ".fs2/graph.pickle"
        ```
    """

    __config_path__: ClassVar[str] = "graph"

    graph_path: str = ".fs2/graph.pickle"


# Backward compatibility alias - DEPRECATED, use GraphConfig
TreeConfig = GraphConfig


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


class LLMConfig(BaseModel):
    """Configuration for LLM service adapters.

    Loaded from YAML or environment variables.
    Path: llm (e.g., FS2_LLM__PROVIDER)

    Provides unified configuration for all LLM providers (OpenAI, Azure, Fake).
    API keys must use ${ENV_VAR} placeholder syntax for security.

    Attributes:
        provider: LLM provider - "azure", "openai", or "fake" (required).
        api_key: API key - MUST use ${ENV_VAR} placeholder (optional).
        base_url: Provider endpoint URL (optional for OpenAI, required for Azure).
        azure_deployment_name: Azure deployment name (required when provider=azure).
        azure_api_version: Azure API version (required when provider=azure).
        model: Model name for logging/display (optional).
        temperature: Generation temperature (default: 0.1).
        max_tokens: Maximum tokens to generate (default: 1024).
        timeout: Request timeout in seconds (1-600, default: 120).
        max_retries: Retry count for transient errors (default: 3).

    YAML example:
        ```yaml
        # .fs2/config.yaml
        llm:
          provider: azure
          api_key: ${AZURE_OPENAI_API_KEY}
          base_url: https://myinstance.openai.azure.com/
          azure_deployment_name: gpt-4
          azure_api_version: 2024-12-01-preview
          model: gpt-4
          temperature: 0.1
          max_tokens: 1024
          timeout: 120
          max_retries: 3
        ```

    Security Notes:
        - API keys with 'sk-' prefix are rejected (literal OpenAI keys)
        - API keys longer than 64 characters are rejected (likely literals)
        - Use ${ENV_VAR} syntax for all secrets
    """

    __config_path__: ClassVar[str] = "llm"

    provider: Literal["azure", "openai", "fake"]
    api_key: str | None = None
    base_url: str | None = None
    azure_deployment_name: str | None = None
    azure_api_version: str | None = None
    model: str | None = None
    temperature: float = 0.1
    max_tokens: int = 1024
    timeout: int = 120
    max_retries: int = 3

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str | None) -> str | None:
        """Validate API key is not a literal secret.

        Rejects:
        - Keys starting with 'sk-' (OpenAI format) - these are always literal

        Allows:
        - ${ENV_VAR} placeholder syntax (will be expanded at runtime)
        - Azure keys (can be 64+ chars, that's legitimate)
        - Short tokens
        - None (optional field)

        Note: The 64+ char check was removed because Azure keys are legitimately
        long and after ${VAR} expansion they would fail validation. The sk-*
        check is sufficient to catch accidentally committed OpenAI keys.
        """
        if v is None:
            return v

        # Check for sk- prefix (OpenAI literal key)
        if v.startswith("sk-"):
            raise ValueError(
                "API key appears to be a literal secret (sk-* prefix). "
                "Use ${ENV_VAR} placeholder syntax instead, e.g., ${OPENAI_API_KEY}"
            )

        return v

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Validate timeout is in reasonable range (1-600 seconds)."""
        if v < 1 or v > 600:
            raise ValueError("Timeout must be 1-600 seconds")
        return v

    @model_validator(mode="after")
    def validate_azure_fields(self) -> "LLMConfig":
        """Validate Azure-specific fields when provider is 'azure'.

        When provider=azure, the following fields are required:
        - base_url (Azure endpoint)
        - azure_deployment_name
        - azure_api_version
        """
        if self.provider != "azure":
            return self

        errors = []
        if not self.base_url:
            errors.append("base_url is required when provider=azure")
        if not self.azure_deployment_name:
            errors.append("azure_deployment_name is required when provider=azure")
        if not self.azure_api_version:
            errors.append("azure_api_version is required when provider=azure")

        if errors:
            raise ValueError("; ".join(errors))

        return self


class SmartContentConfig(BaseModel):
    """Configuration for Smart Content generation.

    Loaded from YAML or environment variables.
    Path: smart_content (e.g., FS2_SMART_CONTENT__MAX_WORKERS)

    Attributes:
        max_workers: Number of parallel workers for batch processing (default: 50).
        max_input_tokens: Token limit for prompt input truncation (default: 50000).
        token_limits: Per-category output token limits for smart content generation.

    YAML example:
        ```yaml
        # .fs2/config.yaml
        smart_content:
          max_workers: 50
          max_input_tokens: 50000
          token_limits:
            file: 200
            type: 200
            callable: 150
        ```
    """

    __config_path__: ClassVar[str] = "smart_content"

    max_workers: int = 50
    max_input_tokens: int = 50000
    token_limits: dict[str, int] = Field(
        default_factory=lambda: {
            "file": 200,
            "type": 200,
            "callable": 150,
            "section": 150,
            "block": 150,
            "definition": 150,
            "statement": 100,
            "expression": 100,
            "other": 100,
        }
    )

    @field_validator("max_workers")
    @classmethod
    def validate_max_workers(cls, v: int) -> int:
        """Validate max_workers is positive."""
        if v < 1:
            raise ValueError("max_workers must be >= 1")
        return v

    @field_validator("max_input_tokens")
    @classmethod
    def validate_max_input_tokens(cls, v: int) -> int:
        """Validate max_input_tokens is positive."""
        if v < 1:
            raise ValueError("max_input_tokens must be >= 1")
        return v


class AzureEmbeddingConfig(BaseModel):
    """Azure OpenAI embedding configuration.

    Nested configuration for Azure-specific embedding settings.
    Per DYK-1: Missing connection config - this provides endpoint, api_key,
    deployment_name, and api_version for Azure embedding adapter.

    Attributes:
        endpoint: Azure OpenAI endpoint URL.
        api_key: Azure OpenAI API key.
        deployment_name: Model deployment name (default: text-embedding-3-small).
        api_version: Azure API version (default: 2024-02-01).

    YAML example:
        ```yaml
        embedding:
          mode: azure
          azure:
            endpoint: https://my-resource.openai.azure.com
            api_key: ${FS2_AZURE_EMBEDDING_API_KEY}
            deployment_name: text-embedding-3-small
            api_version: 2024-02-01
        ```
    """

    endpoint: str
    api_key: str
    deployment_name: str = "text-embedding-3-small"
    api_version: str = "2024-02-01"

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        """Validate endpoint is not empty."""
        if not v or not v.strip():
            raise ValueError("endpoint must not be empty")
        return v

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate api_key is not empty."""
        if not v or not v.strip():
            raise ValueError("api_key must not be empty")
        return v


class ChunkConfig(BaseModel):
    """Chunking parameters for a specific content type.

    Used by EmbeddingConfig to define per-content-type chunking behavior.
    Per Critical Finding 04: Content-type aware configuration pattern.
    Per DYK-3: overlap_tokens >= 0 (0 is valid for smart_content).

    Attributes:
        max_tokens: Maximum tokens per chunk. Must be > 0.
        overlap_tokens: Overlap between consecutive chunks. Must be >= 0 and < max_tokens.

    Example:
        ```python
        # Code: smaller chunks for better search precision
        code_config = ChunkConfig(max_tokens=400, overlap_tokens=50)

        # Documentation: larger chunks for context
        docs_config = ChunkConfig(max_tokens=800, overlap_tokens=120)

        # Smart content: single large chunk (no overlap needed)
        smart_config = ChunkConfig(max_tokens=8000, overlap_tokens=0)
        ```
    """

    max_tokens: int
    overlap_tokens: int

    @field_validator("max_tokens")
    @classmethod
    def validate_max_tokens(cls, v: int) -> int:
        """Validate max_tokens is positive."""
        if v <= 0:
            raise ValueError("max_tokens must be positive")
        return v

    @field_validator("overlap_tokens")
    @classmethod
    def validate_overlap_tokens(cls, v: int) -> int:
        """Validate overlap_tokens is non-negative (per DYK-3: 0 is valid)."""
        if v < 0:
            raise ValueError("overlap_tokens must be >= 0")
        return v

    @model_validator(mode="after")
    def validate_overlap_less_than_max(self) -> "ChunkConfig":
        """Validate overlap is strictly less than max_tokens."""
        if self.overlap_tokens >= self.max_tokens:
            raise ValueError(
                f"overlap_tokens ({self.overlap_tokens}) must be less than "
                f"max_tokens ({self.max_tokens})"
            )
        return self


class EmbeddingConfig(BaseModel):
    """Configuration for embedding generation service.

    Loaded from YAML or environment variables.
    Path: embedding (e.g., FS2_EMBEDDING__BATCH_SIZE)

    Per Critical Finding 04: Content-type aware chunking configuration.
    Per DYK-4: Retry configuration following Flowspace pattern.
    Per Alignment Finding 10: Default dimensions=1024 for text-embedding-3-small.

    Batching Architecture (per FlowSpace pattern):
        The embedding API supports batch input - multiple texts in ONE API call.
        This is much more efficient than parallel individual calls.

        - batch_size: Number of texts per API call (default: 16, max: 2048 for Azure)
        - Service collects items, splits into fixed batches, processes sequentially
        - Optional: max_concurrent_batches for parallel batch processing

    Attributes:
        mode: Embedding provider - "azure", "openai_compatible", or "fake".
        dimensions: Embedding vector dimensions (default: 1024).
        batch_size: Number of texts per API call (default: 16). Azure max is 2048.
        max_concurrent_batches: Number of batches to process concurrently (default: 1).
            Set higher for faster processing if rate limits allow.
        code: ChunkConfig for code content (default: 400/50).
        documentation: ChunkConfig for documentation (default: 800/120).
        smart_content: ChunkConfig for smart content (default: 8000/0).
        max_retries: Max retry attempts for 429/5xx errors (default: 3).
        base_delay: Base delay in seconds for exponential backoff (default: 2.0).
        max_delay: Maximum delay cap in seconds (default: 60.0).

    YAML example:
        ```yaml
        # .fs2/config.yaml
        embedding:
          mode: azure
          batch_size: 16           # Texts per API call (max 2048 for Azure)
          max_concurrent_batches: 1  # Concurrent batch processing (optional)
          # Retry configuration (per Flowspace pattern)
          max_retries: 3
          base_delay: 2.0
          max_delay: 60.0
          # Chunking configuration
          code:
            max_tokens: 400
            overlap_tokens: 50
          documentation:
            max_tokens: 800
            overlap_tokens: 120
          smart_content:
            max_tokens: 8000
            overlap_tokens: 0
        ```
    """

    __config_path__: ClassVar[str] = "embedding"

    mode: Literal["azure", "openai_compatible", "fake"] = "azure"
    dimensions: int = 1024
    batch_size: int = 16  # Texts per API call (FlowSpace pattern)
    max_concurrent_batches: int = 1  # Concurrent batch processing

    # Azure-specific configuration (per DYK-1)
    azure: AzureEmbeddingConfig | None = None

    # Per-content-type chunking configuration (Finding 04)
    code: ChunkConfig = Field(
        default_factory=lambda: ChunkConfig(max_tokens=400, overlap_tokens=50)
    )
    documentation: ChunkConfig = Field(
        default_factory=lambda: ChunkConfig(max_tokens=800, overlap_tokens=120)
    )
    smart_content: ChunkConfig = Field(
        default_factory=lambda: ChunkConfig(max_tokens=8000, overlap_tokens=0)
    )

    # Retry configuration (DYK-4: Flowspace pattern)
    max_retries: int = 3
    base_delay: float = 2.0
    max_delay: float = 60.0

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, v: int) -> int:
        """Validate dimensions is positive (per Alignment Finding 10)."""
        if v <= 0:
            raise ValueError("dimensions must be > 0")
        return v

    @field_validator("batch_size")
    @classmethod
    def validate_batch_size(cls, v: int) -> int:
        """Validate batch_size is between 1 and 2048 (Azure API limit)."""
        if v < 1:
            raise ValueError("batch_size must be >= 1")
        if v > 2048:
            raise ValueError("batch_size must be <= 2048 (Azure API limit)")
        return v

    @field_validator("max_concurrent_batches")
    @classmethod
    def validate_max_concurrent_batches(cls, v: int) -> int:
        """Validate max_concurrent_batches is positive."""
        if v < 1:
            raise ValueError("max_concurrent_batches must be >= 1")
        return v

    @field_validator("max_retries")
    @classmethod
    def validate_max_retries(cls, v: int) -> int:
        """Validate max_retries is non-negative."""
        if v < 0:
            raise ValueError("max_retries must be >= 0")
        return v

    @field_validator("base_delay")
    @classmethod
    def validate_base_delay(cls, v: float) -> float:
        """Validate base_delay is positive."""
        if v <= 0:
            raise ValueError("base_delay must be > 0")
        return v

    @model_validator(mode="after")
    def validate_max_delay_gte_base(self) -> "EmbeddingConfig":
        """Validate max_delay is at least as large as base_delay."""
        if self.max_delay < self.base_delay:
            raise ValueError(
                f"max_delay ({self.max_delay}) must be >= base_delay ({self.base_delay})"
            )
        return self


class SearchConfig(BaseModel):
    """Configuration for search operations.

    Loaded from YAML or environment variables.
    Path: search (e.g., FS2_SEARCH__DEFAULT_LIMIT)

    Controls search behavior for the fs2 search command.
    Per Phase 1 Core Models specification.
    Per DYK-P3-04: min_similarity lowered from 0.5 to 0.25 to capture weakly-related code.

    Attributes:
        default_limit: Maximum number of search results (default: 20, must be >= 1).
        min_similarity: Minimum similarity score for semantic matches (default: 0.25, range 0.0-1.0).
        regex_timeout: Maximum time in seconds for regex operations (default: 2.0, must be > 0).

    YAML example:
        ```yaml
        # .fs2/config.yaml
        search:
          default_limit: 20
          min_similarity: 0.25
          regex_timeout: 2.0
        ```
    """

    __config_path__: ClassVar[str] = "search"

    default_limit: int = 20
    min_similarity: float = 0.25
    regex_timeout: float = 2.0

    @field_validator("default_limit")
    @classmethod
    def validate_default_limit(cls, v: int) -> int:
        """Validate default_limit is positive."""
        if v < 1:
            raise ValueError("default_limit must be >= 1")
        return v

    @field_validator("min_similarity")
    @classmethod
    def validate_min_similarity(cls, v: float) -> float:
        """Validate min_similarity is in 0.0-1.0 range."""
        if v < 0.0 or v > 1.0:
            raise ValueError("min_similarity must be between 0.0 and 1.0")
        return v

    @field_validator("regex_timeout")
    @classmethod
    def validate_regex_timeout(cls, v: float) -> float:
        """Validate regex_timeout is positive."""
        if v <= 0:
            raise ValueError("regex_timeout must be > 0")
        return v


# Registry of config types to auto-load from YAML/env
# Only configs with __config_path__ != None should be in this list
YAML_CONFIG_TYPES: list[type[BaseModel]] = [
    AzureOpenAIConfig,
    SampleServiceConfig,
    SampleAdapterConfig,
    LogAdapterConfig,
    ScanConfig,
    GraphConfig,
    LLMConfig,
    SmartContentConfig,
    EmbeddingConfig,
    SearchConfig,
]
