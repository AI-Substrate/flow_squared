# Embeddings Guide

Embeddings convert code into dense vector representations, enabling semantic search that finds code by meaning rather than exact text matches.

## Overview

An embedding is a list of floating-point numbers (typically 1024 dimensions) that captures the semantic meaning of text. Similar code produces similar embeddings, allowing searches like "authentication flow" to find auth-related code even without exact keyword matches.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Scan Pipeline                                                   │
│                                                                  │
│  DiscoveryStage → ParsingStage → SmartContentStage              │
│                                        ↓                         │
│                                  EmbeddingStage                  │
│                                        ↓                         │
│                                   StorageStage                   │
└─────────────────────────────────────────────────────────────────┘
                                        ↓
┌─────────────────────────────────────────────────────────────────┐
│  EmbeddingService                                                │
│                                                                  │
│  1. Content-type classification (CODE vs CONTENT)               │
│  2. Chunking (400/800/8000 tokens based on type)                │
│  3. Batch API calls via EmbeddingAdapter                        │
│  4. Reassemble chunks → CodeNode.embedding                      │
└─────────────────────────────────────────────────────────────────┘
                                        ↓
┌─────────────────────────────────────────────────────────────────┐
│  EmbeddingAdapter (ABC)                                          │
│                                                                  │
│  ├── AzureEmbeddingAdapter (Azure OpenAI)                       │
│  ├── OpenAICompatibleEmbeddingAdapter (Generic)                 │
│  └── FakeEmbeddingAdapter (Testing)                             │
└─────────────────────────────────────────────────────────────────┘
```

### Content-Type Aware Chunking

Different content types use different chunk sizes for optimal search quality:

| Content Type | Max Tokens | Overlap | Rationale |
|--------------|------------|---------|-----------|
| **Code** | 400 | 50 | Small chunks for precise function/method matching |
| **Documentation** | 800 | 120 | Larger chunks to preserve narrative context |
| **Smart Content** | 8000 | 0 | AI descriptions rarely need chunking |

Code files (Python, Go, TypeScript, etc.) are classified as CODE. Documentation files (Markdown, RST) are classified as CONTENT.

### Dual Embedding Strategy

Each code node can have two embeddings:

1. **`embedding`**: Vector representation of the raw source code
2. **`smart_content_embedding`**: Vector representation of the AI-generated description

This enables hybrid search strategies:
- Search by code similarity (find similar implementations)
- Search by semantic meaning (find code matching a description)

### Incremental Updates

Embeddings are preserved across scans for unchanged content:

1. On first scan, all nodes get embeddings
2. On subsequent scans, only changed nodes are re-embedded
3. Hash-based detection: `embedding_hash` vs `content_hash`

This minimizes API calls and speeds up incremental scans.

---

## Configuration

### Quick Start

```yaml
# .fs2/config.yaml
embedding:
  mode: azure
  dimensions: 1024
  azure:
    endpoint: "${FS2_AZURE__EMBEDDING__ENDPOINT}"
    api_key: "${FS2_AZURE__EMBEDDING__API_KEY}"
    deployment_name: "text-embedding-3-small"
```

```bash
# Scan with embeddings
fs2 scan

# Skip embeddings (faster)
fs2 scan --no-embeddings
```

### Full Configuration Schema

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

### Environment Variables

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

### Dimensions

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

### CLI Options

```bash
# Default: embeddings enabled (when config exists)
fs2 scan

# Disable embeddings (faster, no API calls)
fs2 scan --no-embeddings

# Verbose mode shows embedding progress
fs2 scan --verbose
```

---

## Providers

### Azure OpenAI

The recommended provider for production use.

**Prerequisites**:
1. Azure OpenAI resource created
2. `text-embedding-3-small` model deployed
3. Endpoint URL and API key available

**Configuration**:

```yaml
# .fs2/config.yaml
embedding:
  mode: azure
  dimensions: 1024
  azure:
    endpoint: "${FS2_AZURE__EMBEDDING__ENDPOINT}"
    api_key: "${FS2_AZURE__EMBEDDING__API_KEY}"
    deployment_name: "text-embedding-3-small"
    api_version: "2024-02-01"
```

**Environment Variables**:

```bash
# .fs2/secrets.env (gitignored)
FS2_AZURE__EMBEDDING__ENDPOINT=https://your-resource.openai.azure.com/
FS2_AZURE__EMBEDDING__API_KEY=your-api-key-here
```

**Deployment Name**: Use your Azure deployment name, not the model name. Check Azure Portal > Azure OpenAI > Deployments.

**API Version**: Quote the API version in YAML to prevent date parsing:

```yaml
# Correct - quoted string
api_version: "2024-06-01"

# Wrong - parsed as date
api_version: 2024-06-01
```

**Rate Limiting**: Azure has rate limits (tokens per minute). The adapter handles this automatically with exponential backoff (2s, 4s, 8s... up to 60s).

### OpenAI Compatible

For OpenAI API or compatible providers (LocalAI, Ollama, etc.).

```yaml
# .fs2/config.yaml
embedding:
  mode: openai_compatible
  dimensions: 1024
```

**Note**: Connection parameters (api_key, base_url, model) must be provided programmatically:

```python
from fs2.core.adapters.embedding_adapter_openai import OpenAICompatibleEmbeddingAdapter

adapter = OpenAICompatibleEmbeddingAdapter(
    config=config_service,
    api_key="sk-your-openai-key",
    base_url="https://api.openai.com/v1",
    model="text-embedding-3-small",
)
```

For local providers (Ollama, LocalAI):

```python
adapter = OpenAICompatibleEmbeddingAdapter(
    config=config_service,
    api_key="not-needed",
    base_url="http://localhost:11434/v1",  # Ollama
    model="nomic-embed-text",
)
```

### Fake (Testing)

For testing without API calls.

```yaml
# .fs2/config.yaml
embedding:
  mode: fake
  dimensions: 1024
```

The `FakeEmbeddingAdapter` returns deterministic embeddings:
1. **Fixture lookup**: If content matches `fixture_graph.pkl`, returns real embeddings
2. **Hash fallback**: For unknown content, generates deterministic vectors from content hash

To regenerate fixture embeddings:

```bash
export FS2_AZURE__EMBEDDING__ENDPOINT=...
export FS2_AZURE__EMBEDDING__API_KEY=...
just generate-fixtures
```

---

## Error Handling

All adapters raise domain-specific exceptions:

```python
from fs2.core.adapters import (
    EmbeddingAdapterError,
    EmbeddingAuthenticationError,
    EmbeddingRateLimitError,
)

try:
    embedding = await adapter.embed_text(content)
except EmbeddingAuthenticationError:
    print("Check your API credentials")
except EmbeddingRateLimitError as e:
    print(f"Rate limited. Retry after: {e.retry_after}s")
except EmbeddingAdapterError as e:
    print(f"Embedding failed: {e}")
```

---

## Troubleshooting

### "API key contains unexpanded placeholder"

The `${VAR}` wasn't expanded. Check:
1. Environment variable is set: `echo $FS2_AZURE__EMBEDDING__API_KEY`
2. secrets.env file exists and is sourced
3. Variable name matches exactly

### "endpoint required when mode=azure"

Azure mode requires the endpoint URL:
```yaml
azure:
  endpoint: "https://your-resource.openai.azure.com/"
```

### "Embedding dimension mismatch"

The model returned different dimensions than configured. Either:
1. Pass `dimensions` parameter to API (text-embedding-3-* only)
2. Update config to match model's native dimensions

### Rate Limit Errors After Retries

The adapter retries automatically. If still failing:
1. Increase `max_retries` in config
2. Reduce `batch_size` to lower tokens per call
3. Check your Azure/OpenAI quota
