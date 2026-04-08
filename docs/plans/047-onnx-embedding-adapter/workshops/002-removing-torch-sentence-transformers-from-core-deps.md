# Workshop: Removing torch/sentence-transformers from Core Dependencies

**Type**: Integration Pattern
**Plan**: 047-onnx-embedding-adapter
**Spec**: `../onnx-embedding-adapter-spec.md`
**Created**: 2026-04-08
**Status**: Draft

**Related Documents**:
- `001-onnx-runtime-embedding-inference.md` (validates ONNX as replacement)
- `src/fs2/core/adapters/embedding_adapter_local.py` (only consumer of torch/ST)
- `src/fs2/core/adapters/embedding_adapter_onnx.py` (replacement adapter)

**Domain Context**:
- **Primary Domain**: embedding-adapters
- **Related Domains**: config, cli (install surface)

---

## Purpose

Define the safe removal of `sentence-transformers` and `torch` from fs2's core `[project.dependencies]`, making `onnxruntime` the core embedding backend. This eliminates a 93s import penalty on Windows and removes ~2GB of transitive dependencies from the default install.

## Key Questions Addressed

- What breaks if we remove `sentence-transformers`/`torch` from core deps?
- What transitive deps do we lose and need to re-declare?
- What code changes are needed beyond `pyproject.toml`?
- How do users who *want* sentence-transformers still get it?
- Does `__init__.py` re-export of `SentenceTransformerEmbeddingAdapter` blow up at import time?

---

## Current State

### pyproject.toml (before)

```toml
dependencies = [
    # ... 15 other deps ...
    "sentence-transformers>=3.0",   # ← pulls in torch, transformers, tokenizers, huggingface_hub, scipy, scikit-learn
    "torch>=2.0",                    # ← ~150MB CPU wheel, 93s import on Windows
]

[project.optional-dependencies]
local-embeddings = [
    "sentence-transformers>=3.0",
    "torch>=2.0",
]
onnx-embeddings = [
    "onnxruntime>=1.17",
]
```

### Transitive Dependency Chain

```
sentence-transformers
├── torch (150MB+, 93s import on Windows)
├── transformers
│   ├── tokenizers        ← ONNX adapter needs this
│   └── huggingface_hub   ← ONNX adapter needs this
├── scipy
├── scikit-learn
├── numpy                 ← already a direct dep
└── Pillow (optional)
```

**Problem**: Removing `sentence-transformers` also removes `tokenizers` and `huggingface_hub`, which the ONNX adapter imports directly.

---

## Change Inventory

### 1. pyproject.toml — Dependency Swap

```toml
# REMOVE from core dependencies:
#   "sentence-transformers>=3.0",
#   "torch>=2.0",

# ADD to core dependencies:
#   "onnxruntime>=1.17",
#   "tokenizers>=0.21",
#   "huggingface-hub>=0.20",

# KEEP optional extra unchanged:
# [project.optional-dependencies]
# local-embeddings = [
#     "sentence-transformers>=3.0",
#     "torch>=2.0",
# ]
```

**Install size impact** (approximate):

| Package | Size | Import Time (Windows) |
|---------|------|-----------------------|
| ~~torch~~ | ~150MB | ~~93s~~ |
| ~~sentence-transformers~~ | ~5MB | ~~(via torch)~~ |
| ~~transformers~~ | ~30MB | ~~(via torch)~~ |
| ~~scipy~~ | ~40MB | — |
| ~~scikit-learn~~ | ~30MB | — |
| **onnxruntime** | ~15MB | 0.13s |
| **tokenizers** | ~7MB | 0.02s |
| **huggingface-hub** | ~1MB | 0.54s |
| **Net savings** | **~225MB** | **~93s** |

### 2. src/fs2/core/adapters/__init__.py — Guard the Re-export

**Current** (line 55-57): Direct import at module level — **will crash** if sentence-transformers isn't installed.

```python
from fs2.core.adapters.embedding_adapter_local import (
    SentenceTransformerEmbeddingAdapter,
)
```

**Fix**: Make it conditional.

```python
# SentenceTransformerEmbeddingAdapter is optional — requires `pip install fs2[local-embeddings]`
try:
    from fs2.core.adapters.embedding_adapter_local import (
        SentenceTransformerEmbeddingAdapter,
    )
except ImportError:
    pass
```

Also update `__all__` (line 115) — remove `"SentenceTransformerEmbeddingAdapter"` from the list, or guard it:

```python
# Build __all__ dynamically for optional adapters
__all__ = [
    # ... all the non-optional exports ...
]
try:
    from fs2.core.adapters.embedding_adapter_local import SentenceTransformerEmbeddingAdapter  # noqa: F811
    __all__.append("SentenceTransformerEmbeddingAdapter")
except ImportError:
    pass
```

**Alternative (simpler)**: Just remove the re-export entirely. Consumers already import from the specific module:
- `embedding_adapter.py:196` → `from fs2.core.adapters.embedding_adapter_local import SentenceTransformerEmbeddingAdapter`
- `embedding_service.py:183` → same
- Tests → same

Nobody uses `from fs2.core.adapters import SentenceTransformerEmbeddingAdapter`. **Verify with grep.**

### 3. src/fs2/core/adapters/embedding_adapter.py — Already Safe ✅

The factory (line 169-206) already guards correctly:

```python
elif embedding_config.mode == "local":
    import importlib.util
    
    # Prefer ONNX when available
    if importlib.util.find_spec("onnxruntime") is not None:
        # ... returns OnnxEmbeddingAdapter
    
    # Probe sentence-transformers availability
    if importlib.util.find_spec("sentence_transformers") is None:
        return None  # ← graceful degradation
    
    # Lazy import only if available
    from fs2.core.adapters.embedding_adapter_local import ...
```

**No changes needed.**

### 4. src/fs2/core/services/embedding/embedding_service.py — Already Safe ✅

Line 182-189 is guarded by `else` (only reached when onnxruntime is unavailable) and uses lazy import:

```python
else:
    from fs2.core.adapters.embedding_adapter_local import (
        SentenceTransformerEmbeddingAdapter,
    )
```

**No changes needed** — will only execute if user has `sentence-transformers` installed.

### 5. src/fs2/core/adapters/embedding_adapter_local.py — Already Safe ✅

All torch/sentence_transformers imports are lazy:
- Line 77: `import torch` inside `_detect_device()` method
- Line 129: `from sentence_transformers import SentenceTransformer` inside `_get_model()` with `try/except ImportError`

**No changes needed** — file is only imported when factory selects local mode.

### 6. Documentation Updates

| File | Change |
|------|--------|
| `src/fs2/docs/local-embeddings.md` | Update install instructions: default is ONNX now, ST is optional extra |
| `src/fs2/docs/configuration-guide.md` | Update mode descriptions: `local` prefers ONNX, falls back to ST |
| `docs/how/user/local-embeddings.md` | Same as above |
| `docs/how/user/configuration-guide.md` | Same as above |

### 7. Test Files — No Source Changes Needed

All test files already mock `sentence_transformers`/`torch` via `unittest.mock.patch` or fake modules. They don't do real imports. The mocking means they'll work regardless of whether the packages are installed.

| Test File | Pattern | Status |
|-----------|---------|--------|
| `test_embedding_adapter.py` | `patch("importlib.util.find_spec", ...)` | ✅ Safe |
| `test_embedding_adapter_local.py` | `patch.dict("sys.modules", {"torch": ...})` | ✅ Safe |
| `test_embedding_adapter_local_warmup.py` | Fake `sentence_transformers` module | ✅ Safe |
| `test_mcp_embedding_preload.py` | `patch("importlib.util.find_spec", ...)` | ✅ Safe |

---

## Decision: What About `__init__.py`?

### Option A: Guard with try/except (Safe, backward compatible)

```python
try:
    from fs2.core.adapters.embedding_adapter_local import SentenceTransformerEmbeddingAdapter
    __all__.append("SentenceTransformerEmbeddingAdapter")
except ImportError:
    pass
```

**Pro**: Anyone doing `from fs2.core.adapters import SentenceTransformerEmbeddingAdapter` still works if they have ST installed.  
**Con**: Adds complexity; silent failure on missing optional dep.

### Option B: Remove the re-export entirely (Clean, explicit) — RECOMMENDED

Remove lines 55-57 and line 115 from `__init__.py`. Add `OnnxEmbeddingAdapter` to the re-exports instead.

```python
from fs2.core.adapters.embedding_adapter_onnx import OnnxEmbeddingAdapter
```

**Pro**: Clean, no conditional imports, ONNX is the primary adapter now.  
**Con**: Breaking change if anyone imports `SentenceTransformerEmbeddingAdapter` from the barrel.

**Verdict**: Option B. The only consumers import from the specific module, not the barrel. Verify:

```bash
grep -r "from fs2.core.adapters import.*SentenceTransformer" src/ tests/
```

If zero hits → safe to remove.

---

## Execution Checklist

```
1. [ ] pyproject.toml: Remove sentence-transformers, torch from core deps
2. [ ] pyproject.toml: Add onnxruntime, tokenizers, huggingface-hub to core deps
3. [ ] pyproject.toml: Keep local-embeddings optional extra unchanged
4. [ ] __init__.py: Remove SentenceTransformerEmbeddingAdapter re-export
5. [ ] __init__.py: Add OnnxEmbeddingAdapter re-export
6. [ ] uv lock: Regenerate lockfile
7. [ ] Verify: `uv run python -c "import fs2"` succeeds without torch
8. [ ] Verify: `uv run python -c "from fs2.core.adapters import OnnxEmbeddingAdapter"` works
9. [ ] Verify: Factory returns OnnxEmbeddingAdapter for mode=local
10. [ ] Verify: All unit tests pass
11. [ ] Docs: Update install instructions in 4 doc files
12. [ ] Global install: `uv tool install --force --reinstall fs2 --from .`
13. [ ] E2E: `fs2 scan` with embeddings, `fs2 search` returns results
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `__init__.py` crashes on import | **HIGH** if not fixed | **HIGH** — all of fs2 breaks | Fix re-export (item 4 above) |
| `tokenizers` not declared, disappears | **HIGH** if not added | **HIGH** — ONNX adapter breaks | Add to core deps (item 2) |
| `huggingface_hub` not declared | **HIGH** if not added | **HIGH** — model download breaks | Add to core deps (item 2) |
| Tests fail without torch | **LOW** | **LOW** — all mocked | Already verified |
| User expects torch, doesn't have it | **LOW** | **LOW** | Docs + actionable error in adapter |

---

## Open Questions

### Q1: Should we keep the `local-embeddings` optional extra?

**RESOLVED**: Yes. Users who specifically want GPU inference via CUDA need torch. The extra is their escape hatch: `pip install fs2[local-embeddings]`.

### Q2: Should `mode: "local"` in config still work?

**RESOLVED**: Yes. The factory already prefers ONNX when `onnxruntime` is available (which it will be as a core dep), and falls back to sentence-transformers if installed. `mode: "local"` → ONNX adapter. No config migration needed.

### Q3: Do we need `onnx-embeddings` optional extra anymore?

**RESOLVED**: No — remove it. `onnxruntime` is now a core dep. Keeping the extra is confusing.
