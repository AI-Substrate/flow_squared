# Execution Log: Fix FX001 — Remove torch/sentence-transformers from core deps

## FX001-1: Swap deps in pyproject.toml ✅

Removed `sentence-transformers>=3.0` and `torch>=2.0` from `[project.dependencies]`.
Added `onnxruntime>=1.17`, `tokenizers>=0.21`, `huggingface-hub>=0.20` as direct core deps.
Removed the redundant `onnx-embeddings` optional extra (onnxruntime is now core).
Kept `local-embeddings` extra for GPU users who want PyTorch.

## FX001-2: Fix `__init__.py` re-exports ✅

Replaced `SentenceTransformerEmbeddingAdapter` re-export with `OnnxEmbeddingAdapter` in barrel.
Updated `__all__` list accordingly. Updated module docstring.

## FX001-3: Update `src/fs2/docs/local-embeddings.md` ✅

Rewrote intro: ONNX is now included by default, ST is optional via `pip install fs2[local-embeddings]`.
Removed "ONNX Mode (Recommended for Windows)" section (now redundant — it's the default).
Updated offline pre-download command from `SentenceTransformer(...)` to `snapshot_download(...)`.

## FX001-4: Update `docs/how/user/local-embeddings.md` ✅

Same changes as FX001-3. Updated title description, install message, and pre-download command.

## FX001-5: Regenerate lockfile and verify tests ✅

**Discovery**: `scipy` and `scikit-learn` were transitive deps of `sentence-transformers` used by `report_service.py`.
Added both as direct core deps (`scipy>=1.12`, `scikit-learn>=1.4`).

Results: 1702 passed, 13 skipped, 292 deselected (excluding 8 pre-existing report_service failures unrelated to this fix).

**Evidence**: `mode=local → OnnxEmbeddingAdapter (provider: onnx)`
**Evidence**: `torch available: False`, `onnxruntime available: True`, `import fs2: OK`

## FX001-6: Global reinstall + E2E verify ✅

`uv tool install --force --reinstall fs2 --from .` — no torch/sentence-transformers in install.
`fs2 search "error handling" --limit 3` returned 3 results with `match_field: "embedding"` — semantic search works.
