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

from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, Field, PrivateAttr, field_validator, model_validator


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
        ignore_patterns: Gitignore-syntax patterns to always exclude, regardless
                         of respect_gitignore setting (default: empty list).
                         Applied in addition to .gitignore patterns.
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
          ignore_patterns:
            - "node_modules"
            - "*.pyc"
          max_file_size_kb: 1000
          respect_gitignore: true
          follow_symlinks: false
          sample_lines_for_large_files: 2000
        ```
    """

    __config_path__: ClassVar[str] = "scan"

    scan_paths: list[str] = ["."]
    ignore_patterns: list[str] = []
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
        timeout: Request timeout in seconds (1-120, default: 30).
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
          timeout: 30
          max_retries: 3
        ```

    Security Notes:
        - API keys with 'sk-' prefix are rejected (literal OpenAI keys)
        - API keys longer than 64 characters are rejected (likely literals)
        - Use ${ENV_VAR} syntax for all secrets
    """

    __config_path__: ClassVar[str] = "llm"

    provider: Literal["azure", "openai", "fake", "local"]
    api_key: str | None = None
    base_url: str | None = None
    azure_deployment_name: str | None = None
    azure_api_version: str | None = None
    model: str | None = None
    temperature: float = 0.1
    max_tokens: int = 1024
    timeout: int = 30
    max_retries: int = 3

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str | None) -> str | None:
        """Validate API key is not empty when provided.

        Note: The sk-* literal check was removed because ${VAR} placeholders
        are expanded before config objects are created, so expanded keys
        (e.g., sk-proj-...) would be incorrectly rejected. The real protection
        is that YAML files use ${ENV_VAR} syntax and secrets.env is gitignored.
        """
        if v is None:
            return v

        if not v.strip():
            raise ValueError(
                "API key is empty. Check that the environment variable is set."
            )

        return v

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Validate timeout is in reasonable range.

        Basic range check. Provider-specific max is enforced in model_validator.
        """
        if v < 1:
            raise ValueError("Timeout must be at least 1 second")
        return v

    @model_validator(mode="after")
    def validate_provider_fields(self) -> "LLMConfig":
        """Validate provider-specific fields.

        - Azure: requires base_url, azure_deployment_name, azure_api_version
        - Local: requires base_url and model; allows timeout up to 300s
        - Cloud (azure/openai): timeout max 120s
        """
        errors = []

        if self.provider == "azure":
            if not self.base_url:
                errors.append("base_url is required when provider=azure")
            if not self.azure_deployment_name:
                errors.append("azure_deployment_name is required when provider=azure")
            if not self.azure_api_version:
                errors.append("azure_api_version is required when provider=azure")

        if self.provider == "local":
            if not self.base_url:
                errors.append(
                    "base_url is required when provider=local "
                    "(e.g., http://localhost:11434)"
                )
            if not self.model:
                errors.append(
                    "model is required when provider=local (e.g., qwen2.5-coder:7b)"
                )
            if self.timeout > 300:
                errors.append("Timeout must be 1-300 seconds for local provider")
        elif self.timeout > 120:
            errors.append("Timeout must be 1-120 seconds")

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

    enabled_categories: list[str] | None = Field(
        default=None,
        description="If set, only these node categories get smart content. "
        "None = all categories. Valid: file, callable, type, block, "
        "section, definition, statement, expression, other.",
    )

    _VALID_CATEGORIES: ClassVar[set[str]] = {
        "file",
        "callable",
        "type",
        "block",
        "section",
        "definition",
        "statement",
        "expression",
        "other",
    }

    @field_validator("enabled_categories")
    @classmethod
    def validate_enabled_categories(cls, v: list[str] | None) -> list[str] | None:
        """Validate enabled_categories contains only known category names."""
        if v is None:
            return v
        invalid = set(v) - cls._VALID_CATEGORIES
        if invalid:
            raise ValueError(
                f"Invalid categories: {sorted(invalid)}. "
                f"Valid: {sorted(cls._VALID_CATEGORIES)}"
            )
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
    api_key: str | None = None
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
    def validate_api_key(cls, v: str | None) -> str | None:
        """Validate api_key is not empty when provided."""
        if v is not None and not v.strip():
            raise ValueError("api_key must not be empty when provided")
        return v


class OpenAIEmbeddingConfig(BaseModel):
    """OpenAI embedding configuration.

    Nested configuration for OpenAI-compatible embedding settings.

    Attributes:
        api_key: OpenAI API key.
        base_url: API base URL (default: https://api.openai.com/v1).
        model: Embedding model name (default: text-embedding-3-small).

    YAML example:
        ```yaml
        embedding:
          mode: openai_compatible
          openai:
            api_key: ${OPENAI_API_KEY}
            model: text-embedding-3-small
        ```
    """

    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "text-embedding-3-small"

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate api_key is not empty."""
        if not v or not v.strip():
            raise ValueError("api_key must not be empty")
        return v


class OnnxEmbeddingConfig(BaseModel):
    """ONNX Runtime embedding configuration.

    Nested configuration for ONNX-based on-device embedding settings.
    No API keys required — runs entirely on-device using ONNX Runtime.
    Eliminates PyTorch dependency, reducing import time from ~93s to ~1s on Windows.

    Per 047: Uses HuggingFace Hub ONNX exports and tokenizers lib directly.

    Attributes:
        model: HuggingFace model name with ONNX export (default: BAAI/bge-small-en-v1.5).
        max_seq_length: Maximum token sequence length (default: 512).
        provider: ONNX Runtime execution provider (default: CPUExecutionProvider).

    YAML example:
        ```yaml
        embedding:
          mode: onnx
          dimensions: 384
          onnx:
            model: BAAI/bge-small-en-v1.5
            max_seq_length: 512
            provider: CPUExecutionProvider
        ```
    """

    model: str = "BAAI/bge-small-en-v1.5"
    max_seq_length: int = 512
    provider: str = "CPUExecutionProvider"

    @field_validator("max_seq_length")
    @classmethod
    def validate_max_seq_length(cls, v: int) -> int:
        """Validate max_seq_length is positive."""
        if v <= 0:
            raise ValueError("max_seq_length must be > 0")
        return v


class LocalEmbeddingConfig(BaseModel):
    """Local SentenceTransformer embedding configuration.

    Nested configuration for local on-device embedding settings.
    No API keys required — runs entirely on-device (CPU, MPS, or CUDA).

    Attributes:
        model: HuggingFace model name (default: BAAI/bge-small-en-v1.5).
        device: Compute device - "auto", "cpu", "mps", or "cuda" (default: auto).
        max_seq_length: Maximum token sequence length (default: 512).

    YAML example:
        ```yaml
        embedding:
          mode: local
          dimensions: 384
          local:
            model: BAAI/bge-small-en-v1.5
            device: auto
            max_seq_length: 512
        ```
    """

    model: str = "BAAI/bge-small-en-v1.5"
    device: Literal["auto", "cpu", "mps", "cuda"] = "auto"
    max_seq_length: int = 512

    @field_validator("max_seq_length")
    @classmethod
    def validate_max_seq_length(cls, v: int) -> int:
        """Validate max_seq_length is positive."""
        if v <= 0:
            raise ValueError("max_seq_length must be > 0")
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
        # Code: large chunks to keep functions together
        code_config = ChunkConfig(max_tokens=4000, overlap_tokens=50)

        # Documentation: large chunks for context
        docs_config = ChunkConfig(max_tokens=4000, overlap_tokens=120)

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
        mode: Embedding provider - "local", "azure", "openai_compatible", or "fake".
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
            max_tokens: 4000
            overlap_tokens: 50
          documentation:
            max_tokens: 4000
            overlap_tokens: 120
          smart_content:
            max_tokens: 8000
            overlap_tokens: 0
        ```
    """

    __config_path__: ClassVar[str] = "embedding"

    mode: Literal["azure", "openai_compatible", "local", "onnx", "fake"] = "local"
    dimensions: int = 1024
    batch_size: int = 16  # Texts per API call (FlowSpace pattern)
    max_concurrent_batches: int = 1  # Concurrent batch processing

    # Azure-specific configuration (per DYK-1)
    azure: AzureEmbeddingConfig | None = None

    # OpenAI-compatible configuration
    openai: OpenAIEmbeddingConfig | None = None

    # Local SentenceTransformer configuration
    local: LocalEmbeddingConfig | None = None

    # ONNX Runtime configuration (per 047)
    onnx: OnnxEmbeddingConfig | None = None

    # Per-content-type chunking configuration (Finding 04)
    code: ChunkConfig = Field(
        default_factory=lambda: ChunkConfig(max_tokens=4000, overlap_tokens=50)
    )
    documentation: ChunkConfig = Field(
        default_factory=lambda: ChunkConfig(max_tokens=4000, overlap_tokens=120)
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

    @model_validator(mode="after")
    def auto_default_dimensions_for_local(self) -> "EmbeddingConfig":
        """Auto-default dimensions to 384 for local/onnx mode when not explicitly set.

        Per DYK-3: Uses model_fields_set to distinguish between user-provided
        dimensions and Pydantic default. Only overrides if user didn't explicitly
        set dimensions.
        Per 047: ONNX uses the same default model (bge-small-en-v1.5, 384 dims).
        """
        if self.mode in ("local", "onnx") and "dimensions" not in self.model_fields_set:
            self.dimensions = 384
        return self


class WatchConfig(BaseModel):
    """Configuration for watch mode operations.

    Loaded from YAML or environment variables.
    Path: watch (e.g., FS2_WATCH__DEBOUNCE_MS)

    Controls the behavior of the `fs2 watch` command which monitors
    directories for file changes and automatically triggers scans.
    Per spec AC9: Configuration integration.

    Attributes:
        debounce_ms: Milliseconds to wait before triggering scan after changes
                     (default: 1600, range: 100-60000).
        watch_paths: List of paths to watch. If empty, uses scan_paths from ScanConfig.
        additional_ignores: Extra patterns to ignore beyond .gitignore (default: empty).
        scan_timeout_seconds: Timeout for change-triggered scans in seconds
                              (default: 300, range: 60-3600).
                              Note: Initial scan has no timeout (may take 40+ min with embeddings).

    YAML example:
        ```yaml
        # .fs2/config.yaml
        watch:
          debounce_ms: 1600
          watch_paths:
            - "./src"
            - "./tests"
          additional_ignores:
            - "*.tmp"
            - ".cache/"
          scan_timeout_seconds: 300
        ```

    Environment variables example:
        FS2_WATCH__DEBOUNCE_MS=2000
        FS2_WATCH__SCAN_TIMEOUT_SECONDS=600
    """

    __config_path__: ClassVar[str] = "watch"

    debounce_ms: int = 1600
    watch_paths: list[str] = Field(default_factory=list)
    additional_ignores: list[str] = Field(default_factory=list)
    scan_timeout_seconds: int = 300

    @field_validator("debounce_ms")
    @classmethod
    def validate_debounce_ms(cls, v: int) -> int:
        """Validate debounce_ms is in reasonable range (100-60000ms)."""
        if v < 100 or v > 60000:
            raise ValueError("debounce_ms must be between 100 and 60000")
        return v

    @field_validator("scan_timeout_seconds")
    @classmethod
    def validate_scan_timeout_seconds(cls, v: int) -> int:
        """Validate scan_timeout_seconds is in reasonable range (60-3600s)."""
        if v < 60 or v > 3600:
            raise ValueError("scan_timeout_seconds must be between 60 and 3600")
        return v


class OtherGraph(BaseModel):
    """Configuration for an external graph reference.

    Represents a single external code graph that can be queried alongside
    the default project graph. Part of multi-graph support.

    Per Critical Finding 04: "default" is reserved for the local graph.
    Per Phase 1 spec: name and path required, description and source_url optional.
    Per Phase 2 DYK-02: _source_dir tracks config file location for path resolution.

    Attributes:
        name: Unique identifier for this graph (required, cannot be "default").
        path: File path to the graph pickle file (required).
              Supports absolute, tilde (~), or relative paths.
              Path resolution happens at access time (Phase 2).
        description: Human-readable description of this graph (optional).
        source_url: URL of the source repository (optional, informational only).
        _source_dir: Directory of the config file this graph came from (internal).
                     Used for resolving relative paths from the config file location.
                     Set during config merge, not from YAML directly.

    YAML example:
        ```yaml
        # .fs2/config.yaml
        other_graphs:
          graphs:
            - name: "shared-lib"
              path: "~/projects/shared/.fs2/graph.pickle"
              description: "Shared utilities library"
              source_url: "https://github.com/org/shared"
        ```
    """

    name: str
    path: str
    description: str | None = None
    source_url: str | None = None
    _source_dir: Path | None = PrivateAttr(default=None)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate name is not empty, whitespace, or reserved.

        Per Critical Finding 04: 'default' is reserved for local graph.
        """
        if not v or not v.strip():
            raise ValueError("name must not be empty or whitespace")
        if v == "default":
            raise ValueError(
                "'default' is reserved for the local project graph. "
                "Choose a different name for this external graph."
            )
        return v

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Validate path is not empty or whitespace."""
        if not v or not v.strip():
            raise ValueError("path must not be empty or whitespace")
        return v


class OtherGraphsConfig(BaseModel):
    """Configuration for external graph references.

    Loaded from YAML at path "other_graphs".
    Path: other_graphs (e.g., in YAML: other_graphs.graphs)

    Container model for listing external graphs that can be queried
    alongside the default project graph. Supports multi-graph workflows.

    Per Critical Finding 01: User and project config graphs are concatenated
    (not replaced) via custom merge logic in ConfigurationService.

    Attributes:
        graphs: List of OtherGraph configurations (default: empty list).

    YAML example:
        ```yaml
        # .fs2/config.yaml
        other_graphs:
          graphs:
            - name: "team-lib"
              path: "/shared/team-lib/.fs2/graph.pickle"
              description: "Team shared components"
            - name: "personal-utils"
              path: "~/projects/utils/.fs2/graph.pickle"
        ```

    Note:
        The `graphs:` wrapper is required (not a direct list under other_graphs).
        This allows future extension of the config schema.
    """

    __config_path__: ClassVar[str] = "other_graphs"

    graphs: list[OtherGraph] = []


class SearchConfig(BaseModel):
    """Configuration for search operations.

    Loaded from YAML or environment variables.
    Path: search (e.g., FS2_SEARCH__DEFAULT_LIMIT)

    Controls search behavior for the fs2 search command.
    Per Phase 1 Core Models specification.
    Per DYK-P3-04: min_similarity lowered from 0.5 to 0.25 to capture weakly-related code.
    Per plan-018: parent_penalty reduces parent node scores when children also match.

    Attributes:
        default_limit: Maximum number of search results (default: 20, must be >= 1).
        min_similarity: Minimum similarity score for semantic matches (default: 0.25, range 0.0-1.0).
        regex_timeout: Maximum time in seconds for regex operations (default: 2.0, must be > 0).
        parent_penalty: Penalty factor for parent nodes when children match (default: 0.25, range 0.0-1.0).
            0.0 = no penalty (parents keep full score), 1.0 = maximum penalty (parents score → 0).
            Depth-weighted: parent score × (1 - penalty)^depth.

    YAML example:
        ```yaml
        # .fs2/config.yaml
        search:
          default_limit: 20
          min_similarity: 0.25
          regex_timeout: 2.0
          parent_penalty: 0.25
        ```
    """

    __config_path__: ClassVar[str] = "search"

    default_limit: int = 20
    min_similarity: float = 0.25
    regex_timeout: float = 2.0
    parent_penalty: float = 0.25

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

    @field_validator("parent_penalty")
    @classmethod
    def validate_parent_penalty(cls, v: float) -> float:
        """Validate parent_penalty is in 0.0-1.0 range."""
        if v < 0.0 or v > 1.0:
            raise ValueError("parent_penalty must be between 0.0 and 1.0")
        return v


# Canonical SCIP language names and their aliases.
# Kept as a local set — does NOT import from scip_adapter (dependency boundary).
_KNOWN_LANGUAGE_TYPES: set[str] = {
    "python",
    "typescript",
    "javascript",
    "go",
    "dotnet",
    "rust",
    "java",
}
_LANGUAGE_TYPE_ALIASES: dict[str, str] = {
    "ts": "typescript",
    "js": "javascript",
    "cs": "dotnet",
    "csharp": "dotnet",
    "c#": "dotnet",
}


class ProjectConfig(BaseModel):
    """Configuration for a single language project.

    Attributes:
        type: Language type (python, typescript, go, dotnet, etc.). Aliases accepted.
        path: Path to the project root, relative to the repository root.
        project_file: Override the marker file (e.g., tsconfig.json).
        enabled: Whether this project is indexed (default: True).
        options: Extra indexer-specific options (default: empty).

    YAML example:
        ```yaml
        - type: python
          path: .
        - type: typescript
          path: frontend
          project_file: tsconfig.json
        ```
    """

    type: str
    path: str = "."
    project_file: str | None = None
    enabled: bool = True
    options: dict[str, str] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def normalise_type(cls, v: str) -> str:
        """Normalise type aliases to canonical names."""
        v = v.strip().lower()
        v = _LANGUAGE_TYPE_ALIASES.get(v, v)
        if v not in _KNOWN_LANGUAGE_TYPES:
            raise ValueError(
                f"Unknown project type '{v}'. "
                f"Known types: {', '.join(sorted(_KNOWN_LANGUAGE_TYPES))}"
            )
        return v


class ProjectsConfig(BaseModel):
    """Configuration for SCIP-indexed language projects.

    Loaded from YAML or environment variables.
    Path: projects (e.g., FS2_PROJECTS__AUTO_DISCOVER)

    Attributes:
        entries: List of project configurations.
        auto_discover: Auto-discover projects from markers when entries is empty (default: True).
        scip_cache_dir: Directory for cached SCIP index files (default: .fs2/scip).

    YAML example:
        ```yaml
        # .fs2/config.yaml
        projects:
          entries:
            - type: python
              path: .
            - type: typescript
              path: frontend
          auto_discover: true
          scip_cache_dir: .fs2/scip
        ```
    """

    __config_path__: ClassVar[str] = "projects"

    entries: list[ProjectConfig] = Field(default_factory=list)
    auto_discover: bool = True
    scip_cache_dir: str = ".fs2/scip"


class CrossFileRelsConfig(BaseModel):
    """Configuration for cross-file relationship extraction.

    Loaded from YAML or environment variables.
    Path: cross_file_rels (e.g., FS2_CROSS_FILE_RELS__ENABLED)

    Controls whether cross-file reference resolution runs during scan.
    Uses SCIP indexers for offline analysis.

    Attributes:
        enabled: Whether cross-file relationship extraction is enabled (default: True).

    YAML example:
        ```yaml
        # .fs2/config.yaml
        cross_file_rels:
          enabled: true
        ```
    """

    __config_path__: ClassVar[str] = "cross_file_rels"

    enabled: bool = True


class ReportsConfig(BaseModel):
    """Configuration for report generation.

    Loaded from YAML or environment variables.
    Path: reports (e.g., FS2_REPORTS__OUTPUT_DIR)

    Controls report output location, content inclusion, and scale limits.

    Attributes:
        output_dir: Directory for generated reports (default: ".fs2/reports").
        include_smart_content: Include AI summaries in report data (default: True).
        max_nodes: Maximum nodes before clustering (default: 10000, range 100-500000).

    YAML example:
        ```yaml
        # .fs2/config.yaml
        reports:
          output_dir: .fs2/reports
          include_smart_content: true
          max_nodes: 10000
        ```
    """

    __config_path__: ClassVar[str] = "reports"

    output_dir: str = ".fs2/reports"
    include_smart_content: bool = True
    max_nodes: int = 10000

    @field_validator("max_nodes")
    @classmethod
    def validate_max_nodes(cls, v: int) -> int:
        """Validate max_nodes is in 100-500000 range."""
        if v < 100 or v > 500000:
            raise ValueError("max_nodes must be between 100 and 500000")
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
    WatchConfig,
    OtherGraphsConfig,
    CrossFileRelsConfig,
    ProjectsConfig,
    ReportsConfig,
]
