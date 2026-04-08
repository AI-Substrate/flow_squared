# Research Report: ONNX Embedding Adapter

**Generated**: 2026-04-08T00:30:00Z
**Research Query**: "Plan for ONNX-based embedding adapter to eliminate 93-second PyTorch import on Windows"
**Mode**: Pre-Plan (Plan-Associated)
**Location**: `docs/plans/047-onnx-embedding-adapter/research-dossier.md`
**FlowSpace**: Available ✅
**Findings**: 73 across 8 subagents
**Harness**: Not found
**Domain Registry**: Not found

---

## Executive Summary

### What It Does
The fs2 embedding system generates vector embeddings for code search. Currently the local adapter uses `sentence-transformers` + PyTorch, which takes **93 seconds to import on Windows** due to PyTorch's massive DLL loading chain. An ONNX Runtime-based adapter would provide identical embeddings for the same model (BAAI/bge-small-en-v1.5) with import time under 2 seconds.

### Business Purpose
The 93-second import makes the MCP server's semantic search effectively unusable for the first ~90 seconds on Windows. Since this is a developer tool used via AI coding agents, this cold-start penalty is a show-stopper. ONNX Runtime eliminates PyTorch entirely, reducing the import to ~1-2 seconds while producing numerically equivalent embeddings.

### Key Insights
1. **The adapter ABC is clean and extensible** — adding `embedding_adapter_onnx.py` follows the exact same pattern as all other adapters (PS-01, PS-08). No architectural changes needed.
2. **ONNX must be a separate mode, not a transparent replacement** — graph metadata doesn't track backend, so silently switching could mix embedding spaces. Add `mode: "onnx"` alongside existing modes (DB-08).
3. **Three viable approaches exist**: (a) Pure ONNX Runtime with manual tokenizer + pooling (~1-2s import), (b) FastEmbed library (~0.5-1.5s import, highest-level API), (c) sentence-transformers native ONNX backend (~30-40s, still imports torch). Only (a) and (b) eliminate PyTorch.

### Quick Stats
- **Components**: 1 new adapter file, 1 new config model, factory updates, ~7 files total
- **Dependencies**: `onnxruntime` (new), `transformers` (for tokenizer, already transitive)
- **Test Coverage**: Existing test patterns are comprehensive — follow same patterns
- **Complexity**: Medium — well-understood adapter pattern, new ML runtime integration
- **Prior Learnings**: 15 relevant discoveries from plans 009, 032, 046
- **Domains**: No formal domain system; fits cleanly in `embedding-adapters` boundary

---

## How It Currently Works

### Entry Points

| Entry Point | Type | Location | Purpose |
|-------------|------|----------|---------|
| `create_embedding_adapter_from_config()` | Factory | `embedding_adapter.py:120-192` | Selects adapter by `EmbeddingConfig.mode` |
| `EmbeddingService.create()` | Factory | `embedding_service.py:131-183` | Second factory site — must also add ONNX |
| `_preload_embedding_adapter()` | MCP startup | `cli/mcp.py:68-103` | Creates + warms adapter at MCP boot |

### Current Adapter Selection Flow

```
EmbeddingConfig.mode = "azure" | "openai_compatible" | "local" | "fake"
                                                         ↓
                                              SentenceTransformerEmbeddingAdapter
                                                         ↓
                                              import sentence_transformers  ← 93 SECONDS
                                                         ↓
                                              SentenceTransformer(model, device)
                                                         ↓
                                              model.encode(texts, normalize=True)
                                                         ↓
                                              list[list[float]]
```

### What ONNX Would Replace

```
EmbeddingConfig.mode = "onnx"  ← NEW
                    ↓
          OnnxEmbeddingAdapter
                    ↓
          import onnxruntime  ← ~1 SECOND
                    ↓
          AutoTokenizer.from_pretrained(model)
          InferenceSession(model_onnx_path)
                    ↓
          tokenize → session.run() → mean_pool → L2_normalize
                    ↓
          list[list[float]]  (numerically equivalent)
```

### Exact Numeric Contract

The ONNX adapter must produce embeddings that are numerically equivalent to the sentence-transformers adapter:
- **Model**: `BAAI/bge-small-en-v1.5` (or any model with ONNX export)
- **Dimensions**: 384
- **Normalization**: L2 normalized (`normalize_embeddings=True`)
- **Max sequence length**: 512 tokens
- **Pooling**: Mean pooling (weighted by attention mask)
- **Return type**: `list[float]` / `list[list[float]]` (not numpy)
- **Tolerance**: L2 distance < 1e-5 per dimension between torch and ONNX outputs

---

## Architecture & Design

### Component Map — Where ONNX Fits

```
src/fs2/core/adapters/
├── embedding_adapter.py          ← ABC + factory (add "onnx" branch)
├── embedding_adapter_azure.py    ← Azure OpenAI
├── embedding_adapter_openai.py   ← OpenAI-compatible
├── embedding_adapter_local.py    ← SentenceTransformer (PyTorch)
├── embedding_adapter_onnx.py     ← NEW: ONNX Runtime
├── embedding_adapter_fake.py     ← Test double
└── exceptions.py                 ← Shared error hierarchy

src/fs2/config/objects.py
├── EmbeddingConfig.mode           ← Add "onnx" to Literal
├── OnnxEmbeddingConfig            ← NEW: model, max_seq_length, provider
└── EmbeddingConfig.onnx           ← NEW: Optional[OnnxEmbeddingConfig]
```

### Design Patterns to Follow (from PS findings)

| Pattern | How ONNX Adapter Should Follow It |
|---------|-----------------------------------|
| ABC contract (PS-01) | Implement `provider_name`, `embed_text()`, `embed_batch()`, override `warmup()` |
| ConfigurationService DI (PS-02) | Constructor takes `ConfigurationService`, calls `config.require(EmbeddingConfig)` |
| Error hierarchy (PS-03) | Raise `EmbeddingAdapterError` for ONNX failures |
| Lazy loading (PS-04) | Lazy-load ONNX session in `_get_session()` with `threading.Lock` |
| sync→async wrapping (PS-05) | Wrap `session.run()` in `run_in_executor()` |
| Return type (PS-06) | Convert numpy to `list[float]` / `list[list[float]]` |
| Dep probing (PS-07) | Use `importlib.util.find_spec("onnxruntime")` in factory |
| File naming (PS-08) | `embedding_adapter_onnx.py` |

---

## Dependencies & Integration

### New Dependencies

| Library | Purpose | Size | Import Time |
|---------|---------|------|-------------|
| `onnxruntime` | ONNX model inference | ~50-100MB | ~1s |
| `transformers` | `AutoTokenizer` for tokenization | Already transitive | Already loaded |

### Dependencies NOT Needed

| Library | Why Not Needed |
|---------|---------------|
| `torch` | ONNX Runtime replaces PyTorch for inference |
| `sentence-transformers` | Manual tokenize + pool + normalize replaces ST wrapper |

### Optional Dependency Group

```toml
# pyproject.toml
[project.optional-dependencies]
onnx-embeddings = ["onnxruntime>=1.17"]
```

### Two Factory Sites to Update

1. `embedding_adapter.py:create_embedding_adapter_from_config()` — add `elif mode == "onnx"` branch
2. `embedding_service.py:EmbeddingService.create()` — add `elif mode == "onnx"` branch

Both currently branch on `azure/openai_compatible/local/fake`. Missing one creates inconsistent behavior (IA-08).

---

## Config Model Design

### New Config Objects

```python
class OnnxEmbeddingConfig(BaseModel):
    """Configuration for ONNX Runtime embedding adapter."""
    model: str = "BAAI/bge-small-en-v1.5"
    max_seq_length: int = 512
    # ONNX Runtime execution provider: CPUExecutionProvider, CUDAExecutionProvider, etc.
    provider: str = "CPUExecutionProvider"
```

### Updated EmbeddingConfig

```python
class EmbeddingConfig(BaseModel):
    mode: Literal["azure", "openai_compatible", "local", "fake", "onnx"] = "local"
    # ... existing fields ...
    onnx: OnnxEmbeddingConfig | None = None
```

### Auto-Dimensions

Like local mode, ONNX with `bge-small-en-v1.5` should auto-set `dimensions=384`.

---

## Quality & Testing

### Test Strategy for ONNX Adapter

| Test Category | What to Test | Pattern to Follow |
|---------------|-------------|-------------------|
| Constructor | Config validation, fail-fast on missing config | QT-02: `test_embedding_adapter_local.py:55-100` |
| Return types | `list[float]`, not numpy | QT-01: adapter unit tests |
| Dimensions | Output dim == config dim | QT-03: dimension validation tests |
| Concurrency | Thread-safe session loading | QT-04: warmup tests |
| Batch semantics | One embedding per input, in order | QT-05: service integration tests |
| Graceful degradation | `None` when onnxruntime missing | PS-07: `find_spec` pattern |
| MCP injection | Works as injected adapter for semantic search | QT-08: MCP search tests |

### Testing Without Real Model

Follow the existing pattern: use mocked/fake ONNX session in unit tests (documented exception to fakes-only convention, same as local adapter). Integration tests can use FakeEmbeddingAdapter.

---

## Prior Learnings (From Previous Implementations)

### Most Critical for ONNX

| ID | Type | Key Insight | Action |
|----|------|-------------|--------|
| PL-01 | gotcha | Keep model loading lazy, not in `__init__` | Lazy-load ONNX session in `_get_session()` |
| PL-02 | insight | Wrap sync inference in executor | ONNX `session.run()` is sync — needs `run_in_executor()` |
| PL-03 | insight | Singleton cache + lock around session | Use `threading.Lock` with double-checked locking |
| PL-05 | warning | Keep provider imports out of contract layer | Don't import `onnxruntime` at module level in factory |
| PL-06 | critical | Normalize outputs, return plain Python lists | Must L2-normalize and convert numpy → list[float] |
| PL-07 | gotcha | Dimensions are model-fixed, error on mismatch | Auto-detect dim from ONNX model output shape |
| PL-08 | gotcha | Don't rely on auto pooling for incompatible models | Implement mean pooling explicitly for ONNX |
| PL-09 | decision | Keep heavyweight runtimes optional | New `onnx-embeddings` optional dep group |
| PL-10 | insight | Device auto-detection matters | ONNX uses "execution providers" not devices — different pattern |
| PL-12 | decision | Cache load failures, don't retry forever | Store `_session_error` like local adapter's `_model_error` |
| PL-15 | gotcha | Clear stale vectors on model change | Add ONNX backend info to graph metadata |

---

## Critical Discoveries

### 🚨 Critical Finding 01: Two Factory Sites
**Impact**: Critical
**Source**: IA-08, DC-04
**What**: Both `create_embedding_adapter_from_config()` and `EmbeddingService.create()` must be updated. Missing one means ONNX works for search but not for `fs2 scan --embed`, or vice versa.

### 🚨 Critical Finding 02: Graph Metadata Doesn't Track Backend
**Impact**: Critical
**Source**: DB-07, DB-08
**What**: Current metadata stores `embedding_model` and `embedding_dimensions` but not the backend (torch vs ONNX). Switching backends silently would mix embedding spaces in the same graph. Must add backend metadata and require `--force` re-embed on backend change.

### 🚨 Critical Finding 03: Mean Pooling Must Be Manual
**Impact**: Critical
**Source**: PL-08, DE-01
**What**: Without sentence-transformers, ONNX adapter must implement mean pooling + L2 normalization manually. The formula: `sum(last_hidden_state * attention_mask) / sum(attention_mask)`, then `embedding / norm(embedding)`. Getting this wrong produces incompatible embeddings.

### ⚠️ Finding 04: ONNX Model Must Be Exported/Available
**Impact**: High
**Source**: DE-08, DE-09
**What**: `BAAI/bge-small-en-v1.5` needs an ONNX export. Options: (a) use HuggingFace Optimum to export on first use, (b) download pre-exported ONNX from HuggingFace Hub, (c) use sentence-transformers' export capability. Option (b) is simplest — many popular models already have ONNX exports on the Hub.

---

## Modification Considerations

### ✅ Safe to Modify
1. **`embedding_adapter.py` factory** — Adding a new `elif` branch is well-established
2. **`config/objects.py`** — Adding new config model follows existing pattern
3. **`pyproject.toml`** — Adding optional dep group is standard

### ⚠️ Modify with Caution
1. **Graph metadata** — Adding backend tracking needs migration consideration
2. **`EmbeddingService.create()`** — Second factory site, easy to miss

### 🚫 Danger Zones
1. **Changing default mode from `local` to `onnx`** — Would silently change behavior for existing users
2. **Mixing embeddings from different backends** — Produces garbage search results

---

## Recommended Approach: Pure ONNX Runtime

Based on research, the recommended approach is **Pure ONNX Runtime** (not FastEmbed, not ST ONNX backend):

| Criterion | Pure ONNX | FastEmbed | ST ONNX Backend |
|-----------|-----------|-----------|-----------------|
| Import time | ~1-2s | ~0.5-1.5s | ~30-40s |
| Eliminates torch | ✅ | ✅ | ❌ |
| API control | Full | Limited | Full (ST API) |
| Dependency size | ~50-100MB | ~50-100MB | Same as local |
| Pooling control | Manual | Automatic | Automatic |
| Model compatibility | Any ONNX | FastEmbed catalog | Any ST model |

**Why not FastEmbed**: Less control over pooling/normalization details, catalog-limited model support, adds a third-party abstraction layer.

**Why not ST ONNX backend**: Still imports torch (30-40s), defeats the purpose.

**Why pure ONNX**: Full control, minimal deps, maximum import speed reduction, follows the existing adapter pattern exactly.

### ONNX Adapter Implementation Sketch

```python
class OnnxEmbeddingAdapter(EmbeddingAdapter):
    def __init__(self, config: ConfigurationService):
        # Load config, validate
        # Lazy-load session + tokenizer in _get_session()
    
    @property
    def provider_name(self) -> str:
        return "onnx"
    
    def _get_session(self):
        # Double-checked locking (like local adapter)
        # Import onnxruntime lazily
        # Load tokenizer from transformers
        # Create InferenceSession
    
    def _encode_sync(self, texts: list[str]) -> list[list[float]]:
        session, tokenizer = self._get_session()
        encoded = tokenizer(texts, max_length=512, padding=True, truncation=True, return_tensors="np")
        outputs = session.run(None, {k: v for k, v in encoded.items()})
        # Mean pooling + L2 normalization
        # Convert to list[list[float]]
    
    async def embed_text(self, text: str) -> list[float]:
        result = await self.embed_batch([text])
        return result[0]
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._encode_sync, texts)
    
    def warmup(self) -> None:
        try:
            self._get_session()
        except EmbeddingAdapterError as e:
            logger.warning(f"ONNX warmup failed: {e}")
```

---

## External Research Opportunities

### Research Opportunity 1: ONNX Model Availability on HuggingFace Hub

**Why Needed**: We need to confirm that `BAAI/bge-small-en-v1.5` has a pre-exported ONNX model available on HuggingFace Hub, or whether we need to export it ourselves using Optimum.
**Impact on Plan**: If no pre-exported model exists, we need an export step (adds complexity).
**Source Findings**: DE-08, Critical Finding 04

**Ready-to-use prompt:**
```
/deepresearch "Does BAAI/bge-small-en-v1.5 have a pre-exported ONNX model available on HuggingFace Hub? If so, what is the exact path/filename to download? If not, what is the simplest way to export it using HuggingFace Optimum or sentence-transformers' export_model_to_onnx? Also: does onnxruntime's InferenceSession automatically download ONNX models from HuggingFace Hub, or do we need to use huggingface_hub.hf_hub_download() first? Context: Python 3.14, onnxruntime 1.17+, targeting CPU inference on Windows/macOS/Linux."
```

### Research Opportunity 2: Tokenizer Import Time Without torch

**Why Needed**: The ONNX adapter uses `transformers.AutoTokenizer` which may transitively import torch. Need to confirm tokenizer-only import is lightweight.
**Impact on Plan**: If `AutoTokenizer` imports torch, we'd need to use `tokenizers` library directly instead.
**Source Findings**: DC-02, DE-10

**Ready-to-use prompt:**
```
/deepresearch "When using transformers.AutoTokenizer.from_pretrained() in Python, does it import torch? Can AutoTokenizer be used without torch installed? If torch is not installed, does the tokenizer still work for encoding text to input_ids and attention_mask as numpy arrays (return_tensors='np')? What is the import time for 'from transformers import AutoTokenizer' on Windows without torch installed? Alternative: can we use the tokenizers library directly (PreTrainedTokenizerFast) to avoid all torch dependencies?"
```

---

## Next Steps

1. **Optional**: Run `/deepresearch` prompts above for ONNX model availability and tokenizer behavior
2. **Proceed**: Run `/plan-1b-specify` to create the feature specification
3. **Then**: `/plan-3-architect` for implementation plan

---

**Research Complete**: 2026-04-08T00:30:00Z
**Report Location**: `docs/plans/047-onnx-embedding-adapter/research-dossier.md`
