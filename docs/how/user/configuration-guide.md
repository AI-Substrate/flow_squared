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
10. [Multi-Graph Configuration](#multi-graph-configuration)
11. [Complete Examples](#complete-examples)
12. [Troubleshooting](#troubleshooting)

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

| Provider | Description | Required Fields | API Key? |
|----------|-------------|-----------------|----------|
| `local` | **Local Ollama** (recommended) | `base_url`, `model` | No |
| `azure` | Azure OpenAI Service | `base_url`, `azure_deployment_name`, `azure_api_version` | Yes/AD |
| `openai` | OpenAI API | `api_key` | Yes |
| `fake` | Mock provider for testing | None | No |

### Local Ollama Configuration (Recommended)

Run a local LLM on your machine — no API keys, no network access, no cost.

**Setup:**
1. Install Ollama: https://ollama.com/download
2. Pull a model: `ollama pull qwen2.5-coder:7b`

```yaml
llm:
  provider: local
  base_url: http://localhost:11434
  model: qwen2.5-coder:7b
  temperature: 0.1                # Lower = more consistent summaries
  max_tokens: 1024
  timeout: 60                     # Up to 300s for CPU-only machines
```

**Recommended models:**
| Model | Size | Quality | Use Case |
|-------|------|---------|----------|
| `qwen2.5-coder:7b` | 4.7 GB | Best | Default — best code understanding |
| `qwen2.5-coder:3b` | 2.0 GB | Good | Limited RAM/VRAM |

Ollama auto-detects your GPU (Metal on Mac, CUDA on NVIDIA, CPU fallback).

See [Local LLM Guide](local-llm.md) for detailed setup and troubleshooting.

### Azure OpenAI Configuration (API Key)

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

### Azure OpenAI Configuration (Azure AD / `az login`)

If you don't want to manage API keys, you can authenticate using your Azure AD identity. Simply omit the `api_key` field and fs2 will use `DefaultAzureCredential` from the `azure-identity` package.

**Prerequisites:**
1. Install the Azure AD dependency: `pip install fs2[azure-ad]`
2. Sign in: `az login`
3. Ensure your Azure AD identity has the **Cognitive Services OpenAI User** role on the Azure OpenAI resource

```yaml
llm:
  provider: azure
  # No api_key — uses az login / DefaultAzureCredential
  base_url: https://your-instance.openai.azure.com/
  azure_deployment_name: gpt-4
  azure_api_version: 2024-12-01-preview
  model: gpt-4
  temperature: 0.1
  max_tokens: 1024
  timeout: 30
  max_retries: 3
```

**How it works:** When `api_key` is absent, the adapter lazily imports `azure.identity`, creates a `DefaultAzureCredential`, and obtains a bearer token for the `https://cognitiveservices.azure.com/.default` scope. The credential chain tries managed identity, Azure CLI (`az login`), and other sources automatically.

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

| Mode | Description | Required Fields | Install |
|------|-------------|-----------------|---------|
| `local` **(default)** | On-device SentenceTransformer | None (uses defaults) | `pip install fs2[local-embeddings]` |
| `azure` | Azure OpenAI Embeddings | `azure.endpoint` | Built-in (optional: `pip install fs2[azure-ad]`) |
| `openai_compatible` | OpenAI-compatible API | `openai.api_key` | Built-in |
| `fake` | Mock embeddings for testing | None | Built-in |

### Local Embedding Configuration (Default — No API Key Needed)

Local mode uses SentenceTransformer models to generate embeddings entirely on-device.
No API keys, no network access, no per-token costs.

**Prerequisites**:
```bash
# Install sentence-transformers and torch (adds ~2 GB)
pip install fs2[local-embeddings]

# Or if installed via uv tool:
uv tool install --force fs2 --with sentence-transformers --with torch
```

**Minimal config** (these are the defaults from `fs2 init`):
```yaml
embedding:
  mode: local
  dimensions: 384
```

**Full config with all options**:
```yaml
embedding:
  mode: local
  dimensions: 384                   # Fixed by model (384 for BGE-small/MiniLM)
  batch_size: 32                    # Texts per encode call

  local:
    model: BAAI/bge-small-en-v1.5   # Default — best retrieval quality per size
    device: auto                     # auto-detects: CUDA > MPS > CPU
    max_seq_length: 512              # Maximum token sequence length
```

**Device auto-detection**: The adapter picks the fastest available hardware:
1. **CUDA** — NVIDIA GPU (Linux/Windows)
2. **MPS** — Apple Silicon M1/M2/M3/M4 (macOS, ~3× faster than CPU)
3. **CPU** — Always available

**Model options**:

| Model | Dim | Size | Speed (MPS) | Best For |
|-------|----:|-----:|------------:|----------|
| `BAAI/bge-small-en-v1.5` | 384 | 130 MB | 947/s | **Default** — best retrieval quality per size |
| `sentence-transformers/all-MiniLM-L6-v2` | 384 | 90 MB | 1,582/s | Maximum throughput |
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | 384 | 470 MB | 838/s | Multilingual codebases |

> **Note**: The model downloads from HuggingFace Hub on first use (~130 MB for default).
> After the first download, it's cached locally and works fully offline.

### Azure Embedding Configuration (API Key)

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

### Azure Embedding Configuration (Azure AD / `az login`)

Same as above, but omit `api_key` to use Azure AD authentication:

**Prerequisites** (same as LLM):
1. Install: `pip install fs2[azure-ad]`
2. Sign in: `az login`
3. Ensure **Cognitive Services OpenAI User** role on the Azure OpenAI resource

```yaml
embedding:
  mode: azure
  dimensions: 1024
  batch_size: 16
  azure:
    endpoint: https://your-instance.openai.azure.com
    # No api_key — uses az login / DefaultAzureCredential
    deployment_name: text-embedding-3-small
    api_version: 2024-02-01
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

  # Category filter — limit which node types get AI summaries
  # Default (absent or null): all categories processed
  # enabled_categories: ["file"]          # Files only (~85% faster)
  # enabled_categories: ["file", "type"]  # Files + classes (~67% faster)

  # Per-category output token limits
  token_limits:
    file: 200
    type: 200          # Classes, interfaces
    callable: 150      # Functions, methods
    section: 150
    block: 150
    definition: 150
    statement: 100
    expression: 100
    other: 100
```

### Category Filter

Use `enabled_categories` to reduce scan time by limiting smart content to high-value node types:

| Setting | Nodes Processed | Time Savings |
|---------|----------------|-------------|
| `null` (default) | All | None |
| `["file"]` | Files only | ~85% |
| `["file", "type"]` | Files + classes | ~67% |
| `["file", "type", "callable"]` | Files + classes + functions | ~3% |

Valid categories: `file`, `callable`, `type`, `block`, `section`, `definition`, `statement`, `expression`, `other`.

> **Note**: Filtered nodes still exist in the graph with full source code, embeddings, and relationships — only the `smart_content` AI summary field is skipped.

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

## Multi-Graph Configuration

The `other_graphs` section lets you query external codebases alongside your local project.

```yaml
other_graphs:
  graphs:
    - name: shared-lib
      path: ~/projects/shared/.fs2/graph.pickle
      description: Shared utility library
      source_url: https://github.com/org/shared

    - name: vendor-sdk
      path: .fs2/graphs/vendor-sdk.pickle
      description: Vendor SDK (scanned locally)
```

### Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Identifier for CLI (`--graph-name`) and MCP (`graph_name`). Cannot be "default". |
| `path` | Yes | Path to graph file. Supports absolute, tilde (~), or relative paths. |
| `description` | No | Human-readable description shown in `list_graphs()` |
| `source_url` | No | URL to source repository (informational) |

### Prerequisites

Before adding an external graph, you must first scan that repository:

```bash
# Option A: Initialize fs2 in the external repo
cd /path/to/shared-library
fs2 init && fs2 scan

# Option B: Scan from your project
fs2 scan --scan-path /path/to/shared-library --graph-file .fs2/graphs/shared-lib.pickle
```

For comprehensive documentation including CLI and MCP usage examples, see the [Multi-Graph Configuration Guide](multi-graphs.md).

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
| "azure-identity package is required..." | Missing Azure AD dependency | Run `pip install fs2[azure-ad]` |
| `DefaultAzureCredential` / token errors | Azure AD session expired or wrong identity | Run `az login` to refresh, check RBAC role |
| 401 Unauthorized (with Azure AD) | Missing RBAC role | Assign **Cognitive Services OpenAI User** role to your identity on the Azure OpenAI resource |

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
4. **Missing Azure fields** — `base_url`, `azure_deployment_name`, and `azure_api_version` are required when `provider: azure`
5. **Wrong embedding dimensions** — Must match your model (1024 for text-embedding-3-small)
6. **Using Azure AD without the package** — Run `pip install fs2[azure-ad]` before omitting `api_key`
7. **Expired `az login` session** — Run `az login` to refresh your credentials
8. **Missing RBAC role for Azure AD** — Your identity needs **Cognitive Services OpenAI User** on the Azure OpenAI resource (not just Contributor)
