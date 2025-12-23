# Embeddings Configuration

Complete reference for embedding configuration options.

## Full Configuration Schema

```yaml
# .fs2/config.yaml
embedding:
  # Provider selection
  mode: azure  # azure | openai_compatible | fake

  # Embedding dimensions (model-dependent)
  dimensions: 1024  # text-embedding-3-small default

  # Batch processing
  batch_size: 16              # Texts per API call (max 2048 for Azure)
  max_concurrent_batches: 1   # Parallel batch limit

  # Retry configuration
  max_retries: 3      # Retry attempts for 429/5xx errors
  base_delay: 2.0     # Base delay in seconds
  max_delay: 60.0     # Maximum delay cap in seconds

  # Content-type specific chunking
  code:
    max_tokens: 400       # Code chunk size
    overlap_tokens: 50    # Overlap between chunks
  documentation:
    max_tokens: 800       # Documentation chunk size
    overlap_tokens: 120   # Overlap between chunks
  smart_content:
    max_tokens: 8000      # AI description chunk size
    overlap_tokens: 0     # No overlap needed

  # Azure configuration (when mode: azure)
  azure:
    endpoint: "${FS2_AZURE__EMBEDDING__ENDPOINT}"
    api_key: "${FS2_AZURE__EMBEDDING__API_KEY}"
    deployment_name: "text-embedding-3-small"
    api_version: "2024-02-01"
```

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `FS2_EMBEDDING__MODE` | Provider selection | `azure` |
| `FS2_EMBEDDING__DIMENSIONS` | Vector dimensions | `1024` |
| `FS2_EMBEDDING__BATCH_SIZE` | Texts per API call | `16` |
| `FS2_EMBEDDING__MAX_RETRIES` | Retry attempts | `3` |
| `FS2_AZURE__EMBEDDING__ENDPOINT` | Azure endpoint URL | `https://myresource.openai.azure.com/` |
| `FS2_AZURE__EMBEDDING__API_KEY` | Azure API key | `sk-...` |
| `FS2_AZURE__EMBEDDING__DEPLOYMENT_NAME` | Azure deployment | `text-embedding-3-small` |
| `FS2_AZURE__EMBEDDING__API_VERSION` | Azure API version | `2024-06-01` |

**Format rules**:
- Prefix: `FS2_` (uppercase)
- Nesting: `__` (double underscore) = `.` in YAML
- Case: UPPERCASE in env, lowercase in config path

## Chunk Configuration

### Code Chunks (400 tokens)

Code uses small chunks to maximize search precision:

```yaml
code:
  max_tokens: 400     # ~300-400 tokens per function/method
  overlap_tokens: 50  # Context overlap for boundary code
```

**Rationale**: Smaller chunks ensure individual functions and methods get distinct embeddings, improving precision when searching for specific implementations.

### Documentation Chunks (800 tokens)

Documentation uses larger chunks to preserve narrative context:

```yaml
documentation:
  max_tokens: 800      # ~600-800 tokens per section
  overlap_tokens: 120  # More overlap for context continuity
```

**Rationale**: Larger chunks keep related paragraphs together, improving coherence when searching documentation.

### Smart Content Chunks (8000 tokens)

AI-generated descriptions rarely need chunking:

```yaml
smart_content:
  max_tokens: 8000    # Near model limit
  overlap_tokens: 0   # No overlap needed
```

**Rationale**: Smart content descriptions are typically short (100-500 tokens), so chunking is rarely triggered.

## Dimensions

The `dimensions` setting controls embedding vector size:

| Model | Default Dimensions | Configurable |
|-------|-------------------|--------------|
| text-embedding-3-small | 1536 | Yes (1024 recommended) |
| text-embedding-3-large | 3072 | Yes |
| text-embedding-ada-002 | 1536 | No |

**Memory Implications**:
- 1024 dims × 10,000 nodes = ~40MB
- 1536 dims × 10,000 nodes = ~60MB
- 3072 dims × 10,000 nodes = ~120MB

Use 1024 dimensions for a good balance of quality and memory.

## Graph Metadata

Embedding configuration is stored in the graph for model validation:

```python
{
    "embedding_model": "text-embedding-3-small",
    "embedding_dimensions": 1024,
    "chunk_params": {
        "code": {"max_tokens": 400, "overlap_tokens": 50},
        "documentation": {"max_tokens": 800, "overlap_tokens": 120},
        "smart_content": {"max_tokens": 8000, "overlap_tokens": 0}
    }
}
```

If the embedding model changes between scans, a warning is logged. Re-embed all content when switching models for consistent search results.

## CLI Options

```bash
# Default: embeddings enabled (when config exists)
fs2 scan

# Disable embeddings (faster, no API calls)
fs2 scan --no-embeddings

# Verbose mode shows embedding progress
fs2 scan --verbose
```

## Validation

Configuration is validated on load:

- `max_tokens` must be > 0
- `overlap_tokens` must be >= 0
- `overlap_tokens` must be < `max_tokens`
- `dimensions` must be > 0
- `mode` must be one of: `azure`, `openai_compatible`, `fake`

Invalid configuration raises a clear error with fix instructions.

## Next Steps

- [Providers](3-providers.md) - Azure, OpenAI, and Fake adapter setup
- [Overview](1-overview.md) - Architecture and concepts
