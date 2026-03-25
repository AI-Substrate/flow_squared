# Local Embeddings

Enable semantic search in fs2 without API keys or network access using on-device SentenceTransformer models.

## Quick Start

```bash
# 1. Initialize (local embeddings are the default)
fs2 init

# 2. Scan with embeddings
fs2 scan

# 3. Search semantically
fs2 search "error handling" --mode semantic
```

No extra installation needed — `sentence-transformers` and `torch` are included with fs2.

## Configuration

Local embeddings are the **default mode** for new projects. Running `fs2 init` creates a config with:

```yaml
embedding:
  mode: local
  dimensions: 384
```

### Custom Model

Override the default model in `.fs2/config.yaml`:

```yaml
embedding:
  mode: local
  dimensions: 384
  local:
    model: BAAI/bge-small-en-v1.5       # default — best retrieval quality per size
    device: auto                          # auto-detects CUDA > MPS > CPU
    max_seq_length: 512
```

### Force CPU

```yaml
embedding:
  mode: local
  dimensions: 384
  local:
    device: cpu
```

## Model Selection

| Model | Dim | Size | Speed (MPS) | MTEB Retrieval | Best For |
|-------|----:|-----:|------------:|:--------------:|----------|
| `BAAI/bge-small-en-v1.5` | 384 | 130 MB | 947/s | ~50-54 | **Default** — best quality per size |
| `all-MiniLM-L6-v2` | 384 | 90 MB | 1,582/s | ~42-45 | Maximum throughput |
| `paraphrase-multilingual-MiniLM-L12-v2` | 384 | 470 MB | 838/s | ~44-47 | Multilingual codebases |

## Device Auto-Detection

The adapter auto-detects the best available device:

1. **CUDA** (NVIDIA GPU) — fastest, requires CUDA toolkit
2. **MPS** (Apple Silicon) — ~3× faster than CPU on M1/M2/M3/M4
3. **CPU** — always available, no GPU required

Override with `device: cpu`, `device: mps`, or `device: cuda` in config.

## Migrating from API Embeddings

If you're switching from `mode: azure` or `mode: openai_compatible`:

```bash
# 1. Update config to mode: local
# 2. Re-embed (dimensions change from 1024 → 384)
fs2 scan --embed --force
```

The `--force` flag is required because stored embeddings have different dimensions. Without it, the scan will error with a clear message explaining the mismatch.

## Air-Gapped / Offline Setup

The model downloads from HuggingFace Hub on first use (~130MB). To pre-download:

```bash
uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"
```

After the first download, the model is cached locally and no network access is needed.

## Troubleshooting

### "Dimension mismatch detected"

You've changed embedding modes. Re-embed with `--force`:
```bash
fs2 scan --embed --force
```

### Slow first run

The first embedding run downloads the model (~130MB) and compiles the MPS kernel (if on Mac). Subsequent runs are much faster.

## Benchmark

A benchmark script is included at `scripts/embeddings/benchmark.py`:

```bash
cd scripts/embeddings
uv run python benchmark.py --corpus-size 500 --runs 3 --compare-devices
```
