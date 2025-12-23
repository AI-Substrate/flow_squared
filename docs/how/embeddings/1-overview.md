# Embeddings Overview

Embeddings convert code into dense vector representations, enabling semantic search that finds code by meaning rather than exact text matches.

## What Are Embeddings?

An embedding is a list of floating-point numbers (typically 1024 dimensions) that captures the semantic meaning of text. Similar code produces similar embeddings, allowing searches like "authentication flow" to find auth-related code even without exact keyword matches.

## Architecture

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

## Content-Type Aware Chunking

Different content types use different chunk sizes for optimal search quality:

| Content Type | Max Tokens | Overlap | Rationale |
|--------------|------------|---------|-----------|
| **Code** | 400 | 50 | Small chunks for precise function/method matching |
| **Documentation** | 800 | 120 | Larger chunks to preserve narrative context |
| **Smart Content** | 8000 | 0 | AI descriptions rarely need chunking |

Code files (Python, Go, TypeScript, etc.) are classified as CODE. Documentation files (Markdown, RST) are classified as CONTENT.

## Dual Embedding Strategy

Each code node can have two embeddings:

1. **`embedding`**: Vector representation of the raw source code
2. **`smart_content_embedding`**: Vector representation of the AI-generated description

This enables hybrid search strategies:
- Search by code similarity (find similar implementations)
- Search by semantic meaning (find code matching a description)

## Incremental Updates

Embeddings are preserved across scans for unchanged content:

1. On first scan, all nodes get embeddings
2. On subsequent scans, only changed nodes are re-embedded
3. Hash-based detection: `embedding_hash` vs `content_hash`

This minimizes API calls and speeds up incremental scans.

## Quick Start

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

## Next Steps

- [Configuration](2-configuration.md) - Full config options and environment variables
- [Providers](3-providers.md) - Azure, OpenAI, and Fake adapter setup
