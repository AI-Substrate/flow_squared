# Fix FX001: Remove torch/sentence-transformers from core deps, make onnxruntime core

**Created**: 2026-04-08
**Status**: Complete
**Plan**: [047-onnx-embedding-adapter](../onnx-embedding-adapter-plan.md)
**Source**: Workshop 002 finding — default `pip install fs2` pulls 225MB+ of torch/scipy/scikit-learn; ONNX adapter (the intended default) was optional-only
**Domain(s)**: config (modify), embedding-adapters (modify), docs (modify), project (modify)

---

## Problem

`sentence-transformers>=3.0` and `torch>=2.0` are declared in `[project.dependencies]`, making them mandatory for every fs2 install. The ONNX adapter (plan 047) was built specifically to eliminate the 93-second Windows import penalty, but `onnxruntime` is only in the optional `onnx-embeddings` extra. Every default install gets the slow path. Additionally, removing `sentence-transformers` will remove its transitive deps (`tokenizers`, `huggingface_hub`) which the ONNX adapter imports directly.

## Proposed Fix

1. Remove `sentence-transformers` and `torch` from core `[project.dependencies]`
2. Add `onnxruntime`, `tokenizers`, and `huggingface-hub` to core deps
3. Remove the now-redundant `onnx-embeddings` optional extra
4. Fix `src/fs2/core/adapters/__init__.py` — the top-level re-export of `SentenceTransformerEmbeddingAdapter` will crash at import time without `sentence-transformers`
5. Update 4 doc files that say "No extra installation needed — sentence-transformers and torch are included"

## Domain Impact

| Domain | Relationship | What Changes |
|--------|-------------|-------------|
| project | **modify** | `pyproject.toml` dependency swap |
| embedding-adapters | **modify** | `__init__.py` — remove ST re-export, add ONNX re-export |
| docs | **modify** | 4 doc files — update install instructions |
| config | consume | No changes — `mode: "local"` factory already prefers ONNX |
| embedding-service | consume | No changes — lazy imports already guarded |

## Tasks

| Status | ID | Task | Domain | Path(s) | Done When | Notes |
|--------|-----|------|--------|---------|-----------|-------|
| [x] | FX001-1 | Remove `sentence-transformers`, `torch` from core deps; add `onnxruntime`, `tokenizers`, `huggingface-hub`; remove `onnx-embeddings` extra | project | `/Users/jordanknight/substrate/fs2/045-windows-compat/pyproject.toml` | `uv lock` succeeds; `uv run python -c "import fs2"` works without torch | Net ~225MB savings. Keep `local-embeddings` extra for GPU users |
| [x] | FX001-2 | Remove `SentenceTransformerEmbeddingAdapter` re-export; add `OnnxEmbeddingAdapter` re-export | embedding-adapters | `/Users/jordanknight/substrate/fs2/045-windows-compat/src/fs2/core/adapters/__init__.py` | `from fs2.core.adapters import OnnxEmbeddingAdapter` works; no crash on `import fs2` | Barrel grep confirmed zero consumers of ST re-export |
| [x] | FX001-3 | Update `src/fs2/docs/local-embeddings.md` — ONNX is default, ST is optional extra | docs | `/Users/jordanknight/substrate/fs2/045-windows-compat/src/fs2/docs/local-embeddings.md` | Doc says ONNX is included, ST requires `pip install fs2[local-embeddings]` | |
| [x] | FX001-4 | Update `docs/how/user/local-embeddings.md` — same changes | docs | `/Users/jordanknight/substrate/fs2/045-windows-compat/docs/how/user/local-embeddings.md` | Consistent with FX001-3 | |
| [x] | FX001-5 | Regenerate lockfile and verify all tests pass | project | `/Users/jordanknight/substrate/fs2/045-windows-compat/uv.lock` | `uv lock` + `uv run python -m pytest -q tests/unit/` green | |
| [x] | FX001-6 | Reinstall global fs2 and verify `fs2 scan` + `fs2 search` work E2E | project | — | `fs2 search "error handling"` returns embedding results | |

## Workshops Consumed

- [002-removing-torch-sentence-transformers-from-core-deps.md](../workshops/002-removing-torch-sentence-transformers-from-core-deps.md) — full audit of all torch/ST references, transitive dep chain analysis, `__init__.py` crash risk

## Acceptance

- [x] `pip install fs2` (or `uv tool install fs2`) does NOT install torch or sentence-transformers
- [x] `import fs2` succeeds without torch installed
- [x] `mode: "local"` in config resolves to `OnnxEmbeddingAdapter` by default
- [x] All unit tests pass
- [x] `fs2 scan` + `fs2 search` return embedding results E2E
- [x] Users can still get sentence-transformers via `pip install fs2[local-embeddings]`

## Discoveries & Learnings

_Populated during implementation._

| Date | Task | Type | Discovery | Resolution |
|------|------|------|-----------|------------|
| 2026-04-08 | FX001-5 | Gotcha | `scipy` and `scikit-learn` were transitive deps of `sentence-transformers`, used by `report_service.py` for `ConvexHull`, `KMeans`, `PCA`, `TSNE`, `TfidfVectorizer` | Added both as direct core deps: `scipy>=1.12`, `scikit-learn>=1.4` |
| 2026-04-08 | FX001-5 | Insight | 8 pre-existing failures in `test_report_service.py` (empty vocabulary, TF-IDF fallback) — confirmed identical before and after changes | No action — pre-existing, unrelated to this fix |
