# fs2 Configuration Guide

This document is a comprehensive reference for all fs2 configuration options. Read this when setting up fs2 for the first time, configuring LLM/embedding providers, or troubleshooting configuration issues.

## Table of Contents

1. [Configuration File Locations](#configuration-file-locations)
2. [Environment Files for Secrets](#environment-files-for-secrets)
3. [Configuration Merging and Precedence](#configuration-merging-and-precedence)
4. [Environment Variable Substitution](#environment-variable-substitution)
5. [LLM Configuration](#llm-configuration)
6. [Embedding Configuration](#embedding-configuration)
7. [Scan Configuration](#scan-configuration)
8. [Smart Content Configuration](#smart-content-configuration)
9. [Search Configuration](#search-configuration)
10. [Complete Examples](#complete-examples)
11. [Troubleshooting](#troubleshooting)

**Deep Dives**: LLM Service Usage, Embeddings Architecture, Content-Type Chunking, Error Handling

---

## Configuration File Locations

fs2 uses a layered configuration system with two main locations:

### User Configuration (Global)

```
~/.config/fs2/config.yaml     # User-level config (XDG spec)
~/.config/fs2/secrets.env     # User-level secrets
```

The user config directory follows the XDG Base Directory specification:
- If `$XDG_CONFIG_HOME` is set: `$XDG_CONFIG_HOME/fs2/`
- Otherwise: `~/.config/fs2/`

### Project Configuration (Local)

```
.fs2/config.yaml              # Project-specific config
.fs2/secrets.env              # Project-specific secrets
```

The project config directory is always `.fs2/` relative to the current working directory.

### Precedence

Project configuration **overrides** user configuration. This allows you to:
- Set global defaults in `~/.config/fs2/config.yaml`
- Override specific values per project in `.fs2/config.yaml`

---

## Environment Files for Secrets

**Never commit API keys or secrets to config.yaml files.** Instead, use environment files that are excluded from version control.

### Three Environment File Locations

Environment files are loaded in order (later overrides earlier):

| Priority | Location | Naming | Purpose |
|----------|----------|--------|---------|
| 1 (lowest) | `~/.config/fs2/secrets.env` | `secrets.env` | User-level API keys |
| 2 | `.fs2/secrets.env` | `secrets.env` | Project-specific API keys |
| 3 (highest) | `./.env` | `.env` | Working directory overrides |

### Naming Convention

- In `~/.config/fs2/` and `.fs2/` directories → use **`secrets.env`**
- In project root (working directory) → use **`.env`**

### Example secrets.env / .env Content

```bash
# Azure OpenAI API keys
AZURE_OPENAI_API_KEY=your-azure-openai-key-here
AZURE_EMBEDDING_API_KEY=your-azure-embedding-key-here

# OpenAI API key (alternative)
OPENAI_API_KEY=sk-your-openai-key-here

# Custom environment variables for your project
MY_CUSTOM_API_KEY=some-value
```

### How Environment Files Work

1. All env files are loaded into `os.environ` **before** config.yaml is parsed
2. This enables `${VAR}` placeholder expansion in config.yaml at runtime
3. Never put literal secrets in config.yaml — always use `${VAR}` placeholders

### Gitignore

Add these patterns to `.gitignore`:

```gitignore
# fs2 secrets
.fs2/secrets.env
.env
```

---

## Configuration Merging and Precedence

fs2 uses **deep merge** for configuration from multiple sources. This means nested objects are merged recursively, not replaced entirely.

### Full Precedence Order (Lowest to Highest)

1. **Default values** — Built into config objects
2. **User config.yaml** — `~/.config/fs2/config.yaml`
3. **Project config.yaml** — `.fs2/config.yaml`
4. **Environment variables** — `FS2_*` prefix (highest priority)

### Deep Merge Example

```yaml
# ~/.config/fs2/config.yaml (user)
llm:
  provider: azure
  timeout: 30
  max_retries: 3

# .fs2/config.yaml (project)
llm:
  timeout: 60  # Override just this field
```

**Result**: `provider: azure`, `timeout: 60`, `max_retries: 3`

### Environment Variable Overrides

Environment variables use the `FS2_` prefix and double underscore for nesting:

```bash
# Override llm.timeout
export FS2_LLM__TIMEOUT=120

# Override embedding.batch_size
export FS2_EMBEDDING__BATCH_SIZE=32

# Override scan.max_file_size_kb
export FS2_SCAN__MAX_FILE_SIZE_KB=1000
```

**Convention**:
- Prefix: `FS2_`
- Nesting: Double underscore `__` (e.g., `FS2_LLM__PROVIDER` → `llm.provider`)
- Case: Environment variables are UPPERCASE, config paths are lowercase

---

## Environment Variable Substitution

fs2 supports `${VAR}` placeholder syntax in config.yaml files. This is the **recommended** way to handle secrets.

### Syntax

```yaml
llm:
  api_key: ${AZURE_OPENAI_API_KEY}  # Placeholder, not literal
  base_url: ${AZURE_OPENAI_ENDPOINT}
```

### Expansion Process

1. Environment files are loaded first (secrets.env, .env)
2. Config.yaml files are parsed
3. `${VAR}` placeholders are expanded using `os.environ`
4. If a variable is not found, the placeholder is left unexpanded
5. The consumer (e.g., LLM adapter) validates that required values exist

### Complete Example

**`.env` file:**
```bash
AZURE_OPENAI_API_KEY=actual-key-here
AZURE_OPENAI_ENDPOINT=https://my-instance.openai.azure.com/
```

**`.fs2/config.yaml`:**
```yaml
llm:
  provider: azure
  api_key: ${AZURE_OPENAI_API_KEY}
  base_url: ${AZURE_OPENAI_ENDPOINT}
```

**At runtime**, `api_key` becomes `actual-key-here`.

### Security: Literal Secret Detection

fs2 rejects obvious literal secrets in config files:

- Keys starting with `sk-` (OpenAI API key format) are rejected
- This prevents accidentally committing secrets to config.yaml

If you see "API key appears to be a literal secret", use `${VAR}` placeholder syntax instead.

---

## LLM Configuration

The `llm` section configures the Large Language Model used for smart content generation.

### Provider Options

| Provider | Description | Required Fields |
|----------|-------------|-----------------|
| `azure` | Azure OpenAI Service | `base_url`, `azure_deployment_name`, `azure_api_version` |
| `openai` | OpenAI API | `api_key` |
| `fake` | Mock provider for testing | None |

### Azure OpenAI Configuration

```yaml
llm:
  provider: azure
  api_key: ${AZURE_OPENAI_API_KEY}
  base_url: https://your-instance.openai.azure.com/
  azure_deployment_name: gpt-4
  azure_api_version: 2024-12-01-preview
  model: gpt-4                    # For logging/display
  temperature: 0.1                # 0.0-2.0, lower = more deterministic
  max_tokens: 1024                # Max tokens to generate
  timeout: 30                     # Request timeout (1-120 seconds)
  max_retries: 3                  # Retry count for transient errors
```

### OpenAI Configuration

```yaml
llm:
  provider: openai
  api_key: ${OPENAI_API_KEY}
  model: gpt-4-turbo
  temperature: 0.1
  max_tokens: 1024
  timeout: 30
  max_retries: 3
```

### Fake Provider (Testing)

```yaml
llm:
  provider: fake
  # No other fields required
```

### LLM Service Usage

To use the LLM service programmatically:

```python
from fs2.core.services.llm_service import LLMService
from fs2.config import ConfigurationService

# Create service from configuration
config = ConfigurationService()
llm_service = LLMService.create(config)

# Generate content
result = await llm_service.generate("Summarize this function...")
print(result.content)
```

### Content Filter Handling

Azure OpenAI may filter content. Check the `was_filtered` flag:

```python
result = await llm_service.generate(prompt)
if result.was_filtered:
    print("Content was filtered by Azure content safety")
else:
    print(result.content)
```

### Testing with FakeLLMAdapter

For testing without API calls:

```python
from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter

# Create fake adapter
fake = FakeLLMAdapter()

# Set predetermined responses
fake.set_response("Expected response for testing")

# Use in tests
result = await fake.generate("Any prompt")
assert result.content == "Expected response for testing"

# Check call history
assert len(fake.call_history) == 1
assert fake.call_history[0]["prompt"] == "Any prompt"
```

---

## Embedding Configuration

The `embedding` section configures vector embeddings for semantic search.

### Mode Options

| Mode | Description | Required Fields |
|------|-------------|-----------------|
| `azure` | Azure OpenAI Embeddings | `azure.endpoint`, `azure.api_key` |
| `openai_compatible` | OpenAI-compatible API | Depends on provider |
| `fake` | Mock embeddings for testing | None |

### Azure Embedding Configuration

```yaml
embedding:
  mode: azure
  dimensions: 1024                # Vector dimensions (model-dependent)
  batch_size: 16                  # Texts per API call (max 2048)
  max_concurrent_batches: 1       # Parallel batch processing

  # Azure connection settings
  azure:
    endpoint: https://your-instance.openai.azure.com
    api_key: ${AZURE_EMBEDDING_API_KEY}
    deployment_name: text-embedding-3-small
    api_version: 2024-02-01

  # Retry configuration
  max_retries: 3
  base_delay: 2.0                 # Seconds (exponential backoff)
  max_delay: 60.0                 # Maximum delay cap

  # Chunking configuration (optional)
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

### Fake Embedding (Testing)

```yaml
embedding:
  mode: fake
  dimensions: 1024
```

### Embeddings Architecture

The embedding pipeline integrates into the scan process:

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

### Memory Implications

Vector dimensions affect memory usage:

| Dimensions | 10,000 nodes | 50,000 nodes |
|------------|--------------|--------------|
| 1024 | ~40MB | ~200MB |
| 1536 | ~60MB | ~300MB |
| 3072 | ~120MB | ~600MB |

Use 1024 dimensions for a good balance of quality and memory.

### Embedding Error Handling

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

## Scan Configuration

The `scan` section configures how fs2 discovers and processes source files.

```yaml
scan:
  # Paths to scan (relative or absolute)
  scan_paths:
    - "./src"
    - "./lib"
    - "./tests"

  # Maximum file size to fully parse (KB)
  max_file_size_kb: 500

  # Lines to sample from large files
  sample_lines_for_large_files: 1000

  # Respect .gitignore patterns
  respect_gitignore: true

  # Follow symbolic links (false prevents infinite loops)
  follow_symlinks: false
```

### Field Reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `scan_paths` | list | `["."]` | Directories to scan |
| `max_file_size_kb` | int | `500` | Files larger than this are sampled |
| `sample_lines_for_large_files` | int | `1000` | Lines to sample from large files |
| `respect_gitignore` | bool | `true` | Skip files matching .gitignore |
| `follow_symlinks` | bool | `false` | Follow symbolic links |

---

## Smart Content Configuration

The `smart_content` section configures AI-generated summaries for code elements.

```yaml
smart_content:
  # Parallel processing
  max_workers: 50

  # Token limit for prompt input
  max_input_tokens: 50000

  # Per-category output token limits
  token_limits:
    file: 1000
    type: 1000         # Classes, interfaces
    callable: 1000     # Functions, methods
    section: 1000
    block: 1000
    definition: 1000
    statement: 1000
    expression: 1000
    other: 1000
```

---

## Search Configuration

The `search` section configures search behavior.

```yaml
search:
  # Maximum results to return
  default_limit: 20

  # Minimum similarity score for semantic search (0.0-1.0)
  min_similarity: 0.25

  # Timeout for regex operations (seconds)
  regex_timeout: 2.0
```

---

## Complete Examples

### Minimal Testing Configuration

For local development without API calls:

```yaml
# .fs2/config.yaml
llm:
  provider: fake

embedding:
  mode: fake
  dimensions: 1024

scan:
  scan_paths:
    - "."
```

No `.env` file needed.

### Azure Production Configuration

**`.fs2/secrets.env`:**
```bash
AZURE_OPENAI_API_KEY=your-llm-api-key
AZURE_OPENAI_ENDPOINT=https://your-llm-instance.openai.azure.com/
AZURE_EMBEDDING_API_KEY=your-embedding-api-key
AZURE_EMBEDDING_ENDPOINT=https://your-embedding-instance.openai.azure.com
```

**`.fs2/config.yaml`:**
```yaml
llm:
  provider: azure
  api_key: ${AZURE_OPENAI_API_KEY}
  base_url: ${AZURE_OPENAI_ENDPOINT}
  azure_deployment_name: gpt-4
  azure_api_version: 2024-12-01-preview
  temperature: 0.1
  max_tokens: 1024
  timeout: 60

embedding:
  mode: azure
  dimensions: 1024
  batch_size: 16
  azure:
    endpoint: ${AZURE_EMBEDDING_ENDPOINT}
    api_key: ${AZURE_EMBEDDING_API_KEY}
    deployment_name: text-embedding-3-small
    api_version: 2024-02-01

scan:
  scan_paths:
    - "./src"
    - "./lib"
  max_file_size_kb: 1000
  respect_gitignore: true

smart_content:
  max_workers: 50
  max_input_tokens: 50000
```

### OpenAI Production Configuration

**`.fs2/secrets.env`:**
```bash
OPENAI_API_KEY=sk-your-openai-api-key
```

**`.fs2/config.yaml`:**
```yaml
llm:
  provider: openai
  api_key: ${OPENAI_API_KEY}
  model: gpt-4-turbo
  temperature: 0.1
  max_tokens: 1024
  timeout: 60

embedding:
  mode: openai_compatible
  dimensions: 1536  # OpenAI default

scan:
  scan_paths:
    - "./src"
  respect_gitignore: true
```

---

## Troubleshooting

### Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| "API key appears to be a literal secret" | Hardcoded key in config.yaml | Use `${VAR}` placeholder syntax |
| "Missing configuration: LLMConfig" | No llm section in config | Add llm configuration to config.yaml |
| "base_url is required when provider=azure" | Azure config incomplete | Add all required Azure fields |
| "Timeout must be 1-120 seconds" | Invalid timeout value | Use value between 1 and 120 |

### Validation Behavior

fs2 uses two-stage validation:

1. **Pre-expansion**: Validates config structure before `${VAR}` expansion
2. **Post-expansion**: Validates actual values after environment variables are substituted

If validation fails, you'll see a clear error message indicating which field is invalid.

### Checking Configuration

To verify your configuration is loaded correctly:

```bash
# Run scan with verbose output
fs2 scan --verbose

# Check if embedding is configured
fs2 scan --embed --verbose
```

### Environment Variable Debug

To see what environment variables are set:

```bash
# Check if your secret is loaded
echo $AZURE_OPENAI_API_KEY

# List all FS2_ environment variables
env | grep FS2_
```

### Common Mistakes

1. **Using `.env` in `.fs2/` directory** — Should be `secrets.env`
2. **Forgetting to add `.env` to `.gitignore`** — Secrets may be committed
3. **Using literal API keys** — Use `${VAR}` placeholders instead
4. **Missing Azure fields** — All three Azure fields are required when `provider: azure`
5. **Wrong embedding dimensions** — Must match your model (1024 for text-embedding-3-small)
