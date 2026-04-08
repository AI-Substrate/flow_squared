# Workshop: ONNX Runtime Embedding Inference

**Type**: Integration Pattern
**Plan**: 047-onnx-embedding-adapter
**Spec**: (pre-spec — findings to inform specification)
**Created**: 2026-04-08
**Status**: Approved

**Related Documents**:
- `docs/plans/047-onnx-embedding-adapter/research-dossier.md`
- `docs/plans/032-local-embeddings/workshops/001-local-sentence-transformer-embeddings.md`
- `C:\Users\Jordan.Knight\Downloads\torch-import-research.md` (external deep research)

---

## Purpose

Document the validated approach for replacing sentence-transformers/PyTorch with ONNX Runtime for local embedding inference. This workshop captures experimental results, the exact code needed, critical gotchas (especially pooling strategy), and performance data — so the implementation phase can proceed with confidence.

## Key Questions Addressed

- Can ONNX Runtime produce numerically identical embeddings to sentence-transformers? → **Yes** (L2 < 1e-6)
- What import time improvement is achievable? → **0.68s vs 93s** (137x faster)
- What pooling strategy does BGE use? → **CLS token, NOT mean pooling** (critical gotcha)
- Can we avoid importing `transformers` (which imports torch)? → **Yes**, use `tokenizers` library directly
- Does the HuggingFace Hub ONNX model work? → **Yes**, `onnx/model.onnx` is available and correct

---

## The Problem

On Windows, `import sentence_transformers` takes **93 seconds** because it imports PyTorch, which loads 150+ MB of DLLs. This makes MCP semantic search unusable for ~90 seconds after server startup.

```
=== Embedding Model Load Benchmark (Windows 11, Python 3.14) ===

Import sentence_transformers: 93.73s   ← THE BOTTLENECK
Load model from cache:         1.78s
Encode single text:            2.70s
Total:                         98.23s
```

On macOS/Linux, the same import takes 3-8 seconds. The Windows penalty is caused by:
1. PyTorch CPU wheel is ~150MB of DLLs that Windows must load/scan
2. Windows Defender real-time protection scans each DLL on access
3. Python 3.14 may have additional import system overhead

---

## Validated Solution: Pure ONNX Runtime

### Import Time Comparison

```
=== ONNX Import Stack (no torch) ===

huggingface_hub:  0.54s
tokenizers:       0.02s
onnxruntime:      0.13s
─────────────────────
TOTAL:            0.68s   ← 137x faster than torch's 93s
```

### End-to-End Timing

```
=== Full Pipeline ===

Import all deps:    0.68s
Download ONNX model: 0.63s  (from HF Hub cache)
Load tokenizer:     0.03s
Create ONNX session: 0.26s
Encode 5 texts:     0.03s
─────────────────────
TOTAL:              1.62s   (vs 98s with sentence-transformers)
```

### Numeric Equivalence — VERIFIED ✅

```
--- ONNX (CLS pool) vs SentenceTransformers ---
  Text 0: L2=0.00000068  cosine=1.00000000  PASS: "def add(a, b): return a + b"
  Text 1: L2=0.00000073  cosine=1.00000000  PASS: "class UserService: pass"
  Text 2: L2=0.00000062  cosine=0.99999994  PASS: "import asyncio"
  Text 3: L2=0.00000082  cosine=1.00000000  PASS: "The quick brown fox"
  Text 4: L2=0.00000087  cosine=1.00000000  PASS: "async def embed_text..."

Max L2: 0.00000087
Verdict: PASS - numerically equivalent
```

This means:
- Existing graph embeddings (from sentence-transformers) are **100% compatible** with ONNX-generated query embeddings
- Users can switch backends without re-embedding their codebase
- Cosine similarity search will produce **identical** results

---

## 🚨 Critical Gotcha: Pooling Strategy

### The Bug We Almost Shipped

The external deep research document and common examples recommend **mean pooling**:
```python
# WRONG for BGE models!
mask = np.expand_dims(attention_mask, -1)
sum_emb = np.sum(last_hidden * mask, axis=1)
sum_mask = np.sum(mask, axis=1)
embedding = sum_emb / sum_mask
```

This produces embeddings with **L2 distance ~0.36 and cosine ~0.93** from sentence-transformers — **completely wrong** for search compatibility.

### The Fix: CLS Token Pooling

BGE models (including `BAAI/bge-small-en-v1.5`) use **CLS token pooling**, meaning the embedding is just the first token's hidden state:

```python
# CORRECT for BGE models!
embedding = last_hidden_state[:, 0, :]  # CLS token = index 0
```

### How We Discovered This

```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("BAAI/bge-small-en-v1.5")

# Inspect the pipeline modules
for i, m in enumerate(model):
    print(f"[{i}] {type(m).__name__}")
    if hasattr(m, 'pooling_mode_mean_tokens'):
        print(f"    mean: {m.pooling_mode_mean_tokens}")
    if hasattr(m, 'pooling_mode_cls_token'):
        print(f"    cls: {m.pooling_mode_cls_token}")
```

Output:
```
[0] Transformer
[1] Pooling
    mean: False       ← NOT mean pooling!
    cls: True         ← CLS token pooling!
[2] Normalize
```

### Implication for ONNX Adapter

The ONNX adapter **MUST** read the model's `1_Pooling/config.json` to determine pooling strategy. Different models use different pooling:

| Model | Pooling | Normalization |
|-------|---------|---------------|
| `BAAI/bge-small-en-v1.5` | CLS | L2 |
| `BAAI/bge-base-en-v1.5` | CLS | L2 |
| `all-MiniLM-L6-v2` | Mean | L2 |
| `all-mpnet-base-v2` | Mean | L2 |
| `nomic-embed-text-v1.5` | Mean | None (pre-normalized) |

**Recommendation**: Read `1_Pooling/config.json` from the HF Hub model repo to detect pooling mode automatically. Fall back to CLS if config not found (most common for BGE).

```python
# Pooling config detection
pooling_config_path = hf_hub_download(model_name, "1_Pooling/config.json")
with open(pooling_config_path) as f:
    pooling_config = json.load(f)

if pooling_config.get("pooling_mode_cls_token"):
    embedding = last_hidden[:, 0, :]  # CLS
elif pooling_config.get("pooling_mode_mean_tokens"):
    mask = np.expand_dims(attention_mask, -1).astype(np.float32)
    embedding = np.sum(last_hidden * mask, axis=1) / np.maximum(np.sum(mask, axis=1), 1e-9)
```

---

## Complete Working Implementation

### Minimal ONNX Embedding Function

```python
import numpy as np
from huggingface_hub import hf_hub_download
from onnxruntime import InferenceSession
from tokenizers import Tokenizer

def create_onnx_embedder(model_name: str = "BAAI/bge-small-en-v1.5", max_seq_length: int = 512):
    """Create an ONNX-based embedding function. No torch needed."""
    
    # Download model files from HuggingFace Hub
    onnx_path = hf_hub_download(model_name, "onnx/model.onnx")
    tok_path = hf_hub_download(model_name, "tokenizer.json")
    
    # Load tokenizer (from tokenizers lib — NOT transformers)
    tokenizer = Tokenizer.from_file(tok_path)
    tokenizer.enable_truncation(max_length=max_seq_length)
    tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
    
    # Create ONNX session
    session = InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    model_input_names = [inp.name for inp in session.get_inputs()]
    
    # Detect pooling strategy
    try:
        import json
        pooling_path = hf_hub_download(model_name, "1_Pooling/config.json")
        with open(pooling_path) as f:
            pooling_config = json.load(f)
        use_cls = pooling_config.get("pooling_mode_cls_token", False)
    except Exception:
        use_cls = True  # Default for BGE models
    
    def encode(texts: list[str]) -> list[list[float]]:
        """Encode texts to normalized embeddings."""
        encoded_batch = tokenizer.encode_batch(texts)
        input_ids = np.array([e.ids for e in encoded_batch], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in encoded_batch], dtype=np.int64)
        token_type_ids = np.zeros_like(input_ids, dtype=np.int64)
        
        # Build input feed (only pass what the model expects)
        input_feed = {}
        if "input_ids" in model_input_names:
            input_feed["input_ids"] = input_ids
        if "attention_mask" in model_input_names:
            input_feed["attention_mask"] = attention_mask
        if "token_type_ids" in model_input_names:
            input_feed["token_type_ids"] = token_type_ids
        
        # Run inference
        outputs = session.run(None, input_feed)
        last_hidden = outputs[0]  # (batch, seq_len, hidden_dim)
        
        # Apply pooling
        if use_cls:
            embeddings = last_hidden[:, 0, :]  # CLS token
        else:
            # Mean pooling
            mask_expanded = np.expand_dims(attention_mask, -1).astype(np.float32)
            sum_emb = np.sum(last_hidden * mask_expanded, axis=1)
            sum_mask = np.maximum(np.sum(mask_expanded, axis=1), 1e-9)
            embeddings = sum_emb / sum_mask
        
        # L2 normalize
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / norms
        
        # Convert to list[list[float]] per Critical Finding 05
        return [list(float(x) for x in emb) for emb in embeddings]
    
    return encode
```

### Usage

```python
encode = create_onnx_embedder()
embeddings = encode(["def add(a, b): return a + b", "class UserService: pass"])
# embeddings[0] is list[float] with 384 dimensions
```

---

## Dependency Stack

### Required (ONNX path)

| Package | Import Time | Size | Purpose |
|---------|-------------|------|---------|
| `onnxruntime` | 0.13s | ~50MB | ONNX model inference |
| `tokenizers` | 0.02s | ~5MB | Fast tokenization (Rust) |
| `huggingface_hub` | 0.54s | ~2MB | Download model files |
| `numpy` | (already loaded) | — | Numeric operations |

**Total: ~57MB, 0.68s import**

### NOT Required (eliminated)

| Package | Import Time | Size | Why Eliminated |
|---------|-------------|------|----------------|
| `torch` | ~90s | ~150MB | ONNX Runtime replaces PyTorch |
| `sentence-transformers` | ~3s | ~5MB | Manual tokenize + pool replaces ST |
| `transformers` | ~38s* | ~50MB | `tokenizers` lib used directly |

*\* `transformers.AutoTokenizer` imports torch transitively — discovered during experiment*

### Key Discovery: `transformers.AutoTokenizer` Imports Torch!

```
[2] import AutoTokenizer:   38.38s   ← Still imports torch!
```

Using `from transformers import AutoTokenizer` defeats the purpose because `transformers` imports torch. The solution is to use the `tokenizers` library directly (which is what `transformers` wraps anyway):

```python
# BAD — still imports torch via transformers
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-small-en-v1.5")

# GOOD — pure Rust tokenizer, no torch
from tokenizers import Tokenizer
from huggingface_hub import hf_hub_download
tok_path = hf_hub_download("BAAI/bge-small-en-v1.5", "tokenizer.json")
tokenizer = Tokenizer.from_file(tok_path)
```

---

## Model File Availability

### HuggingFace Hub Structure for BAAI/bge-small-en-v1.5

```
BAAI/bge-small-en-v1.5/
├── config.json                 # Model architecture config
├── tokenizer.json              # Tokenizer definition (for tokenizers lib)
├── tokenizer_config.json       # Tokenizer settings
├── vocab.txt                   # BERT vocabulary
├── 1_Pooling/
│   └── config.json             # Pooling strategy (cls vs mean)
├── model.safetensors           # PyTorch weights (SafeTensors format)
├── pytorch_model.bin           # PyTorch weights (legacy format)
└── onnx/
    └── model.onnx              # ✅ ONNX export available!
```

### Files Needed by ONNX Adapter

Only 3 files from the Hub:
1. `onnx/model.onnx` — The ONNX model (~127MB)
2. `tokenizer.json` — Tokenizer definition (~700KB)
3. `1_Pooling/config.json` — Pooling strategy (~200B)

All cached locally by `huggingface_hub` after first download.

---

## ONNX Session Input/Output Contract

### Model Inputs

```python
session = InferenceSession("model.onnx", providers=["CPUExecutionProvider"])
for inp in session.get_inputs():
    print(f"{inp.name}: {inp.shape} ({inp.type})")
```

```
input_ids:      ['batch_size', 'sequence_length'] (tensor(int64))
attention_mask: ['batch_size', 'sequence_length'] (tensor(int64))
token_type_ids: ['batch_size', 'sequence_length'] (tensor(int64))
```

### Model Outputs

```
last_hidden_state: ['batch_size', 'sequence_length', 384] (tensor(float))
```

Single output: the full last hidden state. Pooling must be applied manually (CLS or mean depending on model).

---

## Adapter Architecture Mapping

### How ONNX Adapter Maps to Existing Patterns

```
SentenceTransformerEmbeddingAdapter          OnnxEmbeddingAdapter
─────────────────────────────────────        ─────────────────────────────────
__init__(config)                       →     __init__(config)
  config.require(EmbeddingConfig)              config.require(EmbeddingConfig)
  self._local_config                           self._onnx_config

provider_name → "local"                →     provider_name → "onnx"

_get_model()                           →     _get_session()
  threading.Lock                               threading.Lock
  import sentence_transformers                  import onnxruntime
  SentenceTransformer(model, device)           InferenceSession(onnx_path)
  lazy, double-checked locking                  lazy, double-checked locking

_encode_sync(texts)                    →     _encode_sync(texts)
  model.encode(texts, normalize=True)          tokenizer.encode_batch(texts)
  pool=None on Darwin                          session.run(None, input_feed)
                                               CLS/mean pool + L2 normalize

embed_text(text) → list[float]         →     embed_text(text) → list[float]
embed_batch(texts) → list[list[float]] →     embed_batch(texts) → list[list[float]]
  run_in_executor                              run_in_executor

warmup()                               →     warmup()
  _get_model() + catch errors                  _get_session() + catch errors
```

### Key Differences

| Aspect | Local (ST) | ONNX |
|--------|------------|------|
| Device detection | CUDA > MPS > CPU via torch | ONNX Execution Providers |
| Pooling | Handled by ST internally | Manual CLS/mean + L2 normalize |
| Model format | PyTorch `.safetensors`/`.bin` | ONNX `.onnx` |
| Tokenizer | ST wraps transformers | `tokenizers` lib directly |
| macOS workaround | `pool=None` | Not needed (no MPS pool issue) |
| Import cost | 93s (torch + ST) | 0.68s (onnxruntime + tokenizers) |

---

## Configuration Design

### YAML Config

```yaml
# .fs2/config.yaml
embedding:
  mode: onnx                    # NEW mode alongside azure/openai_compatible/local/fake
  onnx:
    model: BAAI/bge-small-en-v1.5
    max_seq_length: 512
    provider: CPUExecutionProvider    # or CUDAExecutionProvider
```

### Config Model

```python
class OnnxEmbeddingConfig(BaseModel):
    """Configuration for ONNX Runtime embedding adapter."""
    model: str = "BAAI/bge-small-en-v1.5"
    max_seq_length: int = 512
    provider: str = "CPUExecutionProvider"
```

### Auto-Dimensions

Like local mode, ONNX should auto-detect dimensions from the model output shape:
```python
# After first inference, check output dim
output_dim = session.get_outputs()[0].shape[-1]  # e.g., 384
```

---

## Graph Metadata Compatibility

### Current Metadata Format

```python
{
    "embedding_model": "local",          # or "azure", deployment name, etc.
    "embedding_dimensions": 384,
    "chunk_params": { ... },
}
```

### ONNX Metadata

```python
{
    "embedding_model": "onnx",           # NEW value
    "embedding_dimensions": 384,         # Same as local for same model
    "chunk_params": { ... },
}
```

### Backend Switch Compatibility

Because ONNX produces numerically identical embeddings (verified L2 < 1e-6), **search across backends works correctly**. However, the graph metadata will show a different `embedding_model` value, which could trigger a "model mismatch" warning in `EmbeddingStage`.

**Recommendation**: When detecting mismatches, compare the actual model name (e.g., `BAAI/bge-small-en-v1.5`), not the backend identifier (`local` vs `onnx`). Or add a separate `embedding_backend` metadata field.

---

## Open Questions

### Q1: Should ONNX become the default for new projects on Windows?

**OPEN**: ONNX is objectively better on Windows (137x faster import). Options:
- A: Make `mode: "onnx"` the default on all platforms → simpler config, but requires onnxruntime installed
- B: Make `mode: "onnx"` the default only on Windows → platform-specific defaults are complex
- C: Keep `mode: "local"` as default, document ONNX as recommended for Windows → safest

### Q2: Should we support GPU via ONNX?

**RESOLVED**: Not in v1. ONNX supports `CUDAExecutionProvider` and `DmlExecutionProvider` (DirectML for Windows), but CPU is sufficient for the embedding workload. GPU support can be added later by changing the provider config.

### Q3: What happens if `onnx/model.onnx` doesn't exist for a model?

**OPEN**: Not all HuggingFace models have ONNX exports. Options:
- A: Fail with actionable error message → simplest
- B: Auto-export using `optimum` → adds dependency, torch needed at export time
- C: Check model repo before creating adapter, fall back to local → complex

**Recommendation**: Option A for v1. Error message: "Model {name} does not have an ONNX export. Use mode: 'local' or export with `optimum-cli export onnx`."

### Q4: How to handle `token_type_ids`?

**RESOLVED**: Some ONNX models expect `token_type_ids`, others don't. Check `session.get_inputs()` and only pass what the model expects. For BERT-based models like BGE, always pass zeros.

---

## Summary of Experimental Results

| Experiment | Result | Implication |
|------------|--------|-------------|
| ONNX import time | 0.68s | 137x faster than torch on Windows |
| Embedding L2 distance | < 1e-6 | Numerically identical to ST |
| CLS vs mean pooling | CLS required for BGE | Must read pooling config per model |
| `transformers.AutoTokenizer` | Imports torch (38s) | Must use `tokenizers` directly |
| HF repo `onnx/model.onnx` | Available and correct | No self-export needed |
| End-to-end pipeline | 1.62s total | Ready for production |

---

**Workshop Conclusion**: The ONNX Runtime approach is validated, fast, and produces identical embeddings. The critical gotcha (CLS pooling, not mean) was caught during experimentation. The implementation can proceed with high confidence.
