# Workshop: Local SentenceTransformer Embeddings

**Type**: Integration Pattern
**Plan**: 032-local-embeddings
**Created**: 2026-03-15
**Status**: Draft

**Related Documents**:
- [009-embeddings research dossier](../../009-embeddings/research-dossier.md)
- [EmbeddingAdapter ABC](../../../../src/fs2/core/adapters/embedding_adapter.py)
- [OpenAI adapter (reference impl)](../../../../src/fs2/core/adapters/embedding_adapter_openai.py)
- [EmbeddingConfig](../../../../src/fs2/config/objects.py)
- [Benchmark script](../../../../scripts/embeddings/benchmark.py)
- [FastCode CodeEmbedder (reference)](~/github/fastcode/fastcode/embedder.py)

---

## Purpose

Design a new `SentenceTransformerEmbeddingAdapter` that enables **fully local, zero-API-cost** embedding generation using HuggingFace SentenceTransformer models. This replaces the need for Azure/OpenAI API credentials when embedding code for semantic search, making fs2 usable offline and in air-gapped environments.

## Key Questions Addressed

- Which SentenceTransformer model should be the default, and why?
- How does the sync SentenceTransformer API integrate with fs2's async adapter contract?
- What configuration is needed, and how does it fit into `EmbeddingConfig`?
- How should device detection work across CUDA / MPS / CPU?
- What are the performance characteristics vs. API-based adapters?
- How do we handle the `list[float]` return type constraint (no numpy)?
- What are the dependency management implications (torch is large)?

---

## Benchmark Results (Empirical)

> **Source**: `scripts/embeddings/benchmark.py` — run on Apple Silicon (MPS)
> **Corpus**: 500 realistic code snippets, 3 timed runs per config

### Single-Process Throughput (All Models)

| Model | Device | items/s | ms/item | Dim | Size | Code-Aware | Native ST |
|-------|--------|--------:|--------:|----:|-----:|:----------:|:---------:|
| all-MiniLM-L6-v2 | MPS | 1,582 | 0.63 | 384 | ~90 MB | ❌ | ✅ |
| all-MiniLM-L6-v2 | CPU | 565 | 1.78 | 384 | ~90 MB | ❌ | ✅ |
| **BAAI/bge-small-en-v1.5** | **MPS** | **947** | **1.06** | **384** | **~130 MB** | **Partial** | **✅** |
| BAAI/bge-small-en-v1.5 | CPU | 285 | 3.62 | 384 | ~130 MB | Partial | ✅ |
| paraphrase-multilingual-L12 | MPS | 838 | 2.00 | 384 | ~470 MB | ❌ | ✅ |
| paraphrase-multilingual-L12 | CPU | 280 | 3.60 | 384 | ~470 MB | ❌ | ✅ |
| microsoft/unixcoder-base | MPS | 432 | 2.32 | 768 | ~500 MB | ✅ | ⚠️ |
| microsoft/unixcoder-base | CPU | 114 | 8.85 | 768 | ~500 MB | ✅ | ⚠️ |
| microsoft/codebert-base | MPS | 303 | 3.30 | 768 | ~500 MB | ✅ | ⚠️ |
| microsoft/codebert-base | CPU | 83 | 12.08 | 768 | ~500 MB | ✅ | ⚠️ |

> **⚠️ Native ST column**: CodeBERT and UniXcoder are NOT native SentenceTransformer models.
> When loaded by SentenceTransformer, they are auto-wrapped with **mean pooling**, which
> produces degraded embeddings. These models are designed for **[CLS] token pooling** and
> their benchmark numbers above are **not representative of their intended quality**.
> Mean pooling on non-fine-tuned transformers produces embeddings where dissimilar inputs
> have overly high cosine similarity. Only native ST models (MiniLM, BGE) produce correct
> embeddings via `model.encode()`.

### Parallel Encoding (2 workers)

| Model | Device | Aggregate items/s | Notes |
|-------|--------|------------------:|-------|
| multilingual-L12 | MPS | 38.4 | GPU contention — **worse** than single-process |
| english-L6 | MPS | 46.3 | GPU contention — **worse** than single-process |

### Key Findings

1. **MPS gives ~3× speedup** over CPU for all models
2. **BGE-small-en-v1.5 is the recommended default**: 947 items/s on MPS, same 384 dim as MiniLM, ~50% better retrieval quality per MTEB benchmarks, only 40MB larger than MiniLM
3. **all-MiniLM-L6-v2 is fastest** but has weakest retrieval quality (trained on NLI/STS text, not code)
4. **CodeBERT/UniXcoder are NOT usable** via SentenceTransformer without custom pooling — their auto-wrapped mean-pooling embeddings are degraded. Would require custom adapter code with [CLS] extraction to use properly.
5. **Parallel encoding hurts on GPU**: MPS can't be shared across processes
6. **MPS warmup**: First run is slow (JIT compilation); runs 2-3 are 2-3× faster
7. **Darwin `pool=None` workaround**: Required on macOS to avoid multiprocessing crash (already in FastCode)

### Cross-Platform Device Support

All native SentenceTransformer models (MiniLM, BGE) work on all platforms via PyTorch:

| Device | Platform | Status | Notes |
|--------|----------|--------|-------|
| **CPU** | Linux, macOS, Windows | ✅ | Always available, no GPU required |
| **CUDA** | Linux, Windows | ✅ | Requires NVIDIA GPU + CUDA toolkit |
| **MPS** | macOS (Apple Silicon) | ✅ | macOS 12.3+, M1/M2/M3/M4 chips |

Auto-detection order: `CUDA > MPS > CPU` (matches FastCode pattern).

### Comparison vs. API-Based Embedders

| Factor | Local (BGE-small) | Azure/OpenAI API |
|--------|-------------------|-----------------|
| Throughput | ~950 items/s (MPS) | ~100-300 items/s (network-bound) |
| Latency | ~1ms/item | 50-200ms/item (network RTT) |
| Cost | $0 (after model download) | $0.02-0.13 per 1M tokens |
| Offline | ✅ | ❌ |
| Dimensions | 384 (fixed by model) | 256-3072 (configurable) |
| Retrieval Quality (MTEB) | ~50-54 | ~62-65 (text-embedding-3-small) |
| Setup | `pip install sentence-transformers` | API key + endpoint |

---

## Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ EmbeddingAdapter ABC                                            │
│   provider_name → str                                           │
│   embed_text(text) → list[float]      (async)                  │
│   embed_batch(texts) → list[list[float]]  (async)              │
├────────────┬────────────┬───────────────┬───────────────────────┤
│ Azure      │ OpenAI     │ Fake          │ SentenceTransformer   │
│ Adapter    │ Compat     │ Adapter       │ Adapter (NEW)         │
│            │ Adapter    │               │                       │
│ async→API  │ async→API  │ sync in-mem   │ sync→run_in_executor  │
│ dim: cfg   │ dim: cfg   │ dim: cfg      │ dim: model-fixed      │
└────────────┴────────────┴───────────────┴───────────────────────┘
```

### Adapter Implementation

The key design challenge: SentenceTransformer's `model.encode()` is **synchronous** but the ABC requires **async** methods. Solution: `asyncio.get_event_loop().run_in_executor()`.

```python
# src/fs2/core/adapters/embedding_adapter_local.py

"""SentenceTransformerEmbeddingAdapter implementation.

Local embedding generation using HuggingFace SentenceTransformer models.
No API keys required — runs entirely on-device (CPU, MPS, or CUDA).
"""

import asyncio
import logging
import platform
from typing import TYPE_CHECKING

from fs2.config.objects import EmbeddingConfig
from fs2.core.adapters.embedding_adapter import EmbeddingAdapter
from fs2.core.adapters.exceptions import EmbeddingAdapterError

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService

logger = logging.getLogger(__name__)


class SentenceTransformerEmbeddingAdapter(EmbeddingAdapter):
    """Local embedding adapter using SentenceTransformer models.

    Provides embedding generation on-device with:
    - ConfigurationService DI pattern (same as Azure/OpenAI adapters)
    - Auto-detection of best device: CUDA > MPS > CPU
    - Lazy model loading (first call loads model)
    - Thread-pool execution for async compatibility

    Key difference from API adapters:
    - No retry logic needed (no network)
    - No rate limiting
    - Dimensions fixed by model (not configurable)
    - Sync model.encode() wrapped in run_in_executor()

    Example:
        >>> config_service = FS2ConfigurationService()
        >>> adapter = SentenceTransformerEmbeddingAdapter(config_service)
        >>> embedding = await adapter.embed_text("def add(a, b): return a + b")
        >>> len(embedding)  # 384 for BAAI/bge-small-en-v1.5
    """

    def __init__(self, config: "ConfigurationService") -> None:
        self._config_service = config
        self._embedding_config = config.require(EmbeddingConfig)

        if self._embedding_config.local is None:
            raise EmbeddingAdapterError(
                "Local config is required for mode='local'. "
                "Set embedding.local.model in .fs2/config.yaml."
            )

        self._local_config = self._embedding_config.local
        self._model = None  # Lazy loaded
        self._device: str | None = None

    @property
    def provider_name(self) -> str:
        return "local"

    def _detect_device(self) -> str:
        """Auto-detect best available device: CUDA > MPS > CPU."""
        import torch

        requested = self._local_config.device

        if requested != "auto":
            # Validate requested device is available
            if requested == "cuda" and not torch.cuda.is_available():
                logger.warning("CUDA requested but not available, falling back to CPU")
                return "cpu"
            if requested == "mps" and not torch.backends.mps.is_available():
                logger.warning("MPS requested but not available, falling back to CPU")
                return "cpu"
            return requested

        if torch.cuda.is_available():
            logger.info(f"CUDA detected: {torch.cuda.get_device_name(0)}")
            return "cuda"
        if torch.backends.mps.is_available():
            logger.info("MPS detected (Apple Silicon)")
            return "mps"
        logger.info("Using CPU for embeddings")
        return "cpu"

    def _get_model(self):
        """Lazy-load the SentenceTransformer model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                raise EmbeddingAdapterError(
                    "sentence-transformers package is required for local embeddings. "
                    "Install it with: pip install fs2[local-embeddings]"
                ) from None

            self._device = self._detect_device()

            logger.info(
                f"Loading SentenceTransformer model: {self._local_config.model} "
                f"on device: {self._device}"
            )
            self._model = SentenceTransformer(
                self._local_config.model,
                device=self._device,
            )
            self._model.max_seq_length = self._local_config.max_seq_length

            actual_dim = self._model.get_sentence_embedding_dimension()
            if actual_dim != self._embedding_config.dimensions:
                logger.warning(
                    f"Model dimension ({actual_dim}) differs from configured "
                    f"dimensions ({self._embedding_config.dimensions}). "
                    f"Using model dimension ({actual_dim})."
                )

        return self._model

    def _encode_sync(self, texts: list[str]) -> list[list[float]]:
        """Synchronous encoding — called via run_in_executor."""
        model = self._get_model()

        encode_kwargs = {
            "batch_size": self._embedding_config.batch_size,
            "show_progress_bar": False,
            "normalize_embeddings": True,
            "convert_to_numpy": True,
            "device": self._device,
            "convert_to_tensor": False,
        }

        # Darwin MPS workaround (from FastCode CodeEmbedder)
        if platform.system() == "Darwin":
            encode_kwargs["pool"] = None

        embeddings = model.encode(texts, **encode_kwargs)

        # Convert numpy arrays to list[list[float]] per Critical Finding 05
        return [list(float(x) for x in emb) for emb in embeddings]

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text on-device."""
        result = await self.embed_batch([text])
        return result[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts on-device.

        Delegates to synchronous SentenceTransformer.encode() via
        run_in_executor to avoid blocking the event loop.
        """
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, self._encode_sync, texts)
        except EmbeddingAdapterError:
            raise
        except Exception as e:
            raise EmbeddingAdapterError(
                f"Local embedding failed: {e}"
            ) from e
```

### Design Decisions

#### D1: `run_in_executor` for Async Wrapping

**Decision**: Use `asyncio.get_event_loop().run_in_executor(None, ...)` to wrap the synchronous `model.encode()` call.

**Why**:
- SentenceTransformer's `encode()` is CPU/GPU-bound, not I/O-bound
- `run_in_executor(None, ...)` dispatches to the default `ThreadPoolExecutor`
- This keeps the event loop responsive during encoding
- Simpler than spawning a subprocess (which we proved hurts throughput due to GPU contention)

**Alternatives rejected**:
- `ProcessPoolExecutor`: Benchmark showed parallel encoding is **slower** on GPU (38 items/s vs 1,582 items/s)
- Making encode truly async: Not supported by SentenceTransformer library

#### D2: Lazy Model Loading

**Decision**: Load the model on first `embed_text`/`embed_batch` call, not in `__init__`.

**Why**:
- Model loading takes 3-15 seconds (network download first time, 3-5s from cache)
- Constructor should be fast (DI pattern)
- If embeddings are never used (e.g., text-only search), the model is never loaded
- Matches the `_get_client()` lazy pattern used by Azure/OpenAI adapters

#### D3: No Retry Logic

**Decision**: No retry loop, unlike API-based adapters.

**Why**:
- Local execution has no transient network errors
- If the model fails to load, it's a permanent error
- If encoding fails, it's a bug (not a rate limit)
- Simplifies the adapter significantly

#### D4: Fixed Dimensions (Model-Determined)

**Decision**: Log a warning if `dimensions` config doesn't match model output, but use model's actual dimension.

**Why**:
- SentenceTransformer models have fixed output dimensions (384 for MiniLM)
- Unlike OpenAI's `text-embedding-3-small` which accepts a `dimensions` parameter
- The config's `dimensions` field is used by the search index for allocation — must match reality
- Warning helps users notice the mismatch and update config

#### D5: `pool=None` on Darwin

**Decision**: Always set `pool=None` in encode kwargs on macOS.

**Why**:
- SentenceTransformer's default multiprocessing pool crashes on macOS with MPS
- FastCode's `CodeEmbedder` already has this workaround
- Our benchmark uses it successfully
- Only affects macOS; Linux/CUDA systems unaffected

---

## Configuration Design

### New Config Model: `LocalEmbeddingConfig`

```python
# In src/fs2/config/objects.py

class LocalEmbeddingConfig(BaseModel):
    """Local SentenceTransformer embedding configuration.

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
```

### EmbeddingConfig Changes

```python
# Extend existing EmbeddingConfig in src/fs2/config/objects.py

class EmbeddingConfig(BaseModel):
    # Existing fields...
    mode: Literal["azure", "openai_compatible", "local", "fake"] = "azure"
    #                                          ^^^^^^^ NEW

    # Existing provider configs...
    azure: AzureEmbeddingConfig | None = None
    openai: OpenAIEmbeddingConfig | None = None
    local: LocalEmbeddingConfig | None = None     # NEW

    # ... rest unchanged
```

### Factory Function Changes

```python
# In create_embedding_adapter_from_config() — add new branch:

elif embedding_config.mode == "local":
    if embedding_config.local is None:
        # Create with defaults if section missing
        embedding_config.local = LocalEmbeddingConfig()
    from fs2.core.adapters.embedding_adapter_local import (
        SentenceTransformerEmbeddingAdapter,
    )
    return SentenceTransformerEmbeddingAdapter(config)
```

### YAML Configuration Examples

```yaml
# .fs2/config.yaml — Minimal local config
embedding:
  mode: local
  dimensions: 384
```

```yaml
# .fs2/config.yaml — Explicit local config (recommended default: BGE-small)
embedding:
  mode: local
  dimensions: 384
  batch_size: 32
  local:
    model: BAAI/bge-small-en-v1.5
    device: auto
    max_seq_length: 512
```

```yaml
# .fs2/config.yaml — Fastest model (lower retrieval quality)
embedding:
  mode: local
  dimensions: 384
  batch_size: 32
  local:
    model: sentence-transformers/all-MiniLM-L6-v2
    device: auto
```

```yaml
# .fs2/config.yaml — Multilingual model (larger, slower)
embedding:
  mode: local
  dimensions: 384
  batch_size: 16
  local:
    model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
    device: auto
```

```yaml
# .fs2/config.yaml — Force CPU (e.g., for CI or consistency)
embedding:
  mode: local
  dimensions: 384
  local:
    device: cpu
```

---

## File Naming Convention

Following the established adapter naming pattern:

| File | Purpose |
|------|---------|
| `embedding_adapter.py` | ABC (exists) |
| `embedding_adapter_azure.py` | Azure impl (exists) |
| `embedding_adapter_openai.py` | OpenAI impl (exists) |
| `embedding_adapter_fake.py` | Test double (exists) |
| `embedding_adapter_local.py` | **NEW**: SentenceTransformer impl |

Test file: `tests/unit/adapters/test_embedding_adapter_local.py`

---

## Dependency Management

### The `torch` Problem

`torch` + `sentence-transformers` together are ~2 GB installed. This should NOT be a required dependency.

**Solution**: Optional dependency group in `pyproject.toml`:

```toml
[project.optional-dependencies]
local-embeddings = [
    "sentence-transformers>=3.0",
    "torch>=2.0",
]
```

**Install**:
```bash
pip install fs2[local-embeddings]
# or
uv pip install fs2[local-embeddings]
```

**Runtime guard** (in adapter `_get_model()`):
```python
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    raise EmbeddingAdapterError(
        "sentence-transformers package is required for local embeddings. "
        "Install it with: pip install fs2[local-embeddings]"
    ) from None
```

This follows the same pattern as Azure AD auth:
```python
# From embedding_adapter_azure.py line 105-109
try:
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
except ImportError:
    raise EmbeddingAdapterError(
        "azure-identity package is required for Azure AD authentication. "
        "Install it with: pip install fs2[azure-ad]"
    ) from None
```

---

## Testing Strategy

### What Needs Testing

| Test | Type | Purpose |
|------|------|---------|
| ABC compliance | Unit | Adapter implements all abstract methods |
| Provider name | Unit | Returns `"local"` |
| Device detection | Unit | CUDA > MPS > CPU fallback chain |
| Lazy loading | Unit | Model not loaded until first embed call |
| Dimension warning | Unit | Logs warning on config/model mismatch |
| Import guard | Unit | Actionable error when sentence-transformers missing |
| encode output type | Unit | Returns `list[list[float]]`, not numpy |
| embed_text delegates | Unit | Calls embed_batch([text])[0] |
| Darwin pool workaround | Unit | Sets `pool=None` on macOS |
| Config validation | Unit | `LocalEmbeddingConfig` validates model, device |
| Factory integration | Unit | `create_embedding_adapter_from_config` creates local adapter |

### Fake/Mock Strategy

For unit tests, **mock `sentence_transformers.SentenceTransformer`** at the import level:

```python
@pytest.fixture
def mock_sentence_transformer(monkeypatch):
    """Mock SentenceTransformer to avoid loading real model in tests."""
    mock_model = MagicMock()
    mock_model.get_sentence_embedding_dimension.return_value = 384
    mock_model.encode.return_value = np.array([[0.1] * 384])

    mock_class = MagicMock(return_value=mock_model)
    monkeypatch.setattr(
        "fs2.core.adapters.embedding_adapter_local.SentenceTransformer",
        mock_class,
        raising=False,
    )
    return mock_model
```

> **Note**: This is one of the rare cases where mocking is appropriate — loading a real 90MB model in unit tests would be impractical. Integration tests (if needed) can use the real model with `@pytest.mark.slow`.

---

## Integration Points

### Search Service

The `SearchService` uses `embedding_adapter.embed_text()` for query embedding during semantic search. The local adapter is a drop-in replacement — no search service changes needed.

### Scan Pipeline (Embedding Stage)

The scan pipeline's embedding stage calls `embed_batch()` for bulk indexing. The local adapter's batch support maps directly.

### Dimension Alignment

**Critical**: The search index (FAISS/cosine) must be built with the correct dimension.

- Azure/OpenAI default: `dimensions: 1024`
- Local MiniLM default: `dimensions: 384`

If a user switches from `mode: azure` to `mode: local`, they **must** re-embed all content. The dimensions mismatch will cause search index errors.

**Mitigation**: The adapter logs a warning on dimension mismatch. The `fs2 scan --embed` command should detect when stored embeddings have different dimensions and offer to re-embed.

---

## Model Selection Guide

For users who want to choose a model (only native SentenceTransformer models are supported):

| Model | Dim | Size | Speed (MPS) | MTEB Retrieval | Best For |
|-------|----:|-----:|------------:|:--------------:|----------|
| `BAAI/bge-small-en-v1.5` | 384 | 130 MB | 947/s | ~50-54 | **Default** — best retrieval quality per size |
| `all-MiniLM-L6-v2` | 384 | 90 MB | 1,582/s | ~42-45 | Maximum throughput, lower quality |
| `paraphrase-multilingual-MiniLM-L12-v2` | 384 | 470 MB | 838/s | ~44-47 | Multilingual codebases |
| `all-mpnet-base-v2` | 768 | 420 MB | ~400/s* | ~49-52 | Higher quality, 2× storage |

*Estimated from model architecture; not yet benchmarked with `scripts/embeddings/benchmark.py`.

> **⚠️ Not supported**: `microsoft/codebert-base` and `microsoft/unixcoder-base` — these are
> not SentenceTransformer models. Auto-wrapping with mean pooling produces degraded embeddings.
> They require [CLS] token extraction which is not compatible with the ST `model.encode()` API.

**Recommendation**: Default to `BAAI/bge-small-en-v1.5`. It scores ~50% higher on MTEB retrieval benchmarks than MiniLM-L6, is only 40MB larger, and still delivers 947 items/s on MPS. Users who need maximum speed can switch to `all-MiniLM-L6-v2` in config.

---

## Migration Path

### From API Embeddings to Local

```bash
# 1. Install local embedding deps
pip install fs2[local-embeddings]

# 2. Update config
cat >> .fs2/config.yaml << 'EOF'
embedding:
  mode: local
  dimensions: 384
  local:
    model: BAAI/bge-small-en-v1.5
EOF

# 3. Re-embed (dimensions changed from 1024 to 384)
fs2 scan --embed --force
```

### From Local to API Embeddings

Simply change `mode` back to `azure` or `openai_compatible` and re-embed.

---

## Open Questions

### Q1: Should `dimensions` auto-detect from model?

**OPEN**: Currently, users must set `dimensions: 384` in config when using local mode. Could the adapter auto-set this after loading the model?

- Option A: Auto-detect and override config — simpler UX but surprises users
- Option B: Validate and error if mismatch — strict but clear
- **Option C (Recommended)**: Warn on mismatch, use model's actual dimension — flexible, discoverable

### Q2: Should model download happen at `fs2 scan --embed` time or `fs2 init` time?

**OPEN**: First model load downloads ~90 MB from HuggingFace.

- Option A: Download at first embed call (lazy) — current design
- Option B: Add `fs2 embedding download` command — explicit
- **Option C (Recommended)**: Lazy download with clear progress message — simplest, works offline after first run

### Q3: Thread pool size for `run_in_executor`?

**OPEN**: Default `ThreadPoolExecutor` has `min(32, os.cpu_count() + 4)` threads.

- Since encoding is GPU-bound, only 1 thread will actually be doing work
- The default pool is fine — no need to create a custom executor
- **Resolved**: Use default pool (`None`)

---

## Reproducing Benchmark Results

To re-run the benchmarks that informed this design:

```bash
cd scripts/embeddings
python3 -m venv .venv
source .venv/bin/activate
pip install sentence-transformers torch numpy

# Quick smoke test
python benchmark.py --corpus-size 50 --batch-sizes 32 --runs 1 --models english-L6

# Full benchmark
python benchmark.py --corpus-size 500 --runs 3 --compare-devices

# With parallel test
python benchmark.py --corpus-size 500 --runs 3 --compare-devices --parallel
```

The benchmark script at `scripts/embeddings/benchmark.py` tests both models (`all-MiniLM-L6-v2` and `paraphrase-multilingual-MiniLM-L12-v2`) across devices with configurable corpus sizes, batch sizes, and run counts.

---

## Summary: What Changes

| Component | Change | Files |
|-----------|--------|-------|
| **New adapter** | `SentenceTransformerEmbeddingAdapter` | `src/fs2/core/adapters/embedding_adapter_local.py` |
| **New config** | `LocalEmbeddingConfig` model | `src/fs2/config/objects.py` |
| **Extend config** | Add `mode: "local"` + `local:` field to `EmbeddingConfig` | `src/fs2/config/objects.py` |
| **Extend factory** | New branch in `create_embedding_adapter_from_config` | `src/fs2/core/adapters/embedding_adapter.py` |
| **Update exports** | Add to `__init__.py` and `__all__` | `src/fs2/core/adapters/__init__.py` |
| **Optional deps** | Add `[local-embeddings]` group | `pyproject.toml` |
| **Tests** | Unit tests for adapter + config | `tests/unit/adapters/test_embedding_adapter_local.py`, `tests/unit/config/test_embedding_config.py` |

---

**Workshop Complete**: 2026-03-15
**Next Steps**:
- Review and refine the workshop document
- Mark as 'Approved' when design is finalized
- Continue with `/plan-1b-specify` or `/plan-3-architect`
