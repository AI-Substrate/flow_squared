# ONNX Embedding Adapter

**Mode**: Simple

📚 This specification incorporates findings from `research-dossier.md`
📐 Workshop `001-onnx-runtime-embedding-inference.md` provides validated experimental results

## Research Context

The research dossier (73 findings, 8 subagents) and workshop experiment validated that:

1. **Import time**: ONNX Runtime imports in 0.68s vs PyTorch's 93s on Windows (137x faster)
2. **Numeric equivalence**: ONNX produces identical embeddings to sentence-transformers (L2 < 1e-6, cosine = 1.0)
3. **Critical gotcha**: BGE models use CLS token pooling, not mean pooling — using mean pooling produces L2 ~0.36 (wrong)
4. **Tokenizer trap**: `transformers.AutoTokenizer` imports torch (38s) — must use `tokenizers` library directly (0.02s)
5. **Model availability**: `BAAI/bge-small-en-v1.5` has `onnx/model.onnx` on HuggingFace Hub — no self-export needed

## Summary

Importing `sentence-transformers` on Windows takes **93 seconds** because it loads PyTorch, which requires loading 150+ MB of DLLs through Windows Defender scanning. This makes both MCP semantic search and `fs2 scan --embed` painfully slow to start on Windows.

This feature adds a new `OnnxEmbeddingAdapter` that uses ONNX Runtime instead of PyTorch for embedding inference. It implements the same `EmbeddingAdapter` ABC and produces numerically identical embeddings, but imports in under 1 second. It works for **all embedding use cases** — MCP search queries, `fs2 scan --embed` batch embedding, and any future consumer of the adapter ABC — because it plugs into the same factory and DI system as all other adapters.

## Goals

- **Eliminate PyTorch dependency for embedding inference**: ONNX Runtime replaces sentence-transformers + torch, reducing import time from 93s to ~0.68s on Windows
- **Produce numerically identical embeddings**: ONNX adapter must match sentence-transformers output within floating-point precision (L2 < 1e-5) for the same model, so existing graph embeddings remain compatible
- **Work everywhere the adapter ABC is consumed**: MCP search (query embedding via `embed_text()`), `fs2 scan --embed` (batch embedding via `embed_batch()`), and any future consumer — not just MCP
- **Auto-detect pooling strategy**: Read the model's `1_Pooling/config.json` to determine CLS vs mean pooling, rather than hardcoding one strategy
- **Keep ONNX Runtime optional**: Users who don't want ONNX should not be forced to install it — graceful fallback to `local` mode or text search
- **Follow existing adapter patterns**: Same file naming, DI, lazy loading, thread safety, and error handling conventions as the other 4 adapters

## Non-Goals

- **Replacing the `local` mode**: ONNX is a new mode (`mode: "onnx"`), not a silent replacement for `local`. Users who want torch/sentence-transformers can keep using `local` mode.
- **GPU support via ONNX**: CPU-only for v1. ONNX supports CUDA/DirectML execution providers, but this is a future enhancement.
- **Auto-exporting models to ONNX**: If a model doesn't have an ONNX export on HuggingFace Hub, the adapter should fail with an actionable error, not try to export using `optimum` (which requires torch).
- **Changing the default mode**: Default remains `local` for backward compatibility. ONNX can be recommended for Windows in documentation.
- **Training or fine-tuning**: ONNX Runtime is inference-only. Training stays on PyTorch.
- **Supporting non-HuggingFace models**: v1 only supports models hosted on HuggingFace Hub with ONNX exports.

## Target Domains

| Domain | Status | Relationship | Role in This Feature |
|--------|--------|-------------|---------------------|
| embedding-adapters | no registry | **modify** | Add new `OnnxEmbeddingAdapter` implementation and update adapter factory |
| config | no registry | **modify** | Add `OnnxEmbeddingConfig` model and `"onnx"` mode to `EmbeddingConfig` |
| embedding-service | no registry | **modify** | Update `EmbeddingService.create()` factory to support ONNX mode |
| mcp-server | no registry | **consume** | MCP preload and search handler already work via adapter ABC — no changes needed |
| cli | no registry | **consume** | `fs2 scan --embed` uses `EmbeddingService` which picks up ONNX via config — no changes needed |

> ℹ️ No formal domain registry exists. The MCP server and CLI are **consume** relationships — they don't need changes because they work through the adapter ABC and factory pattern. Setting `mode: "onnx"` in config is all that's needed.

## Complexity

- **Score**: CS-3 (medium)
- **Breakdown**: S=1, I=1, D=0, N=0, F=1, T=1 (Total P=4)
- **Confidence**: 0.90 (high — workshop validated the approach experimentally)

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Surface Area (S) | 1 | 1 new adapter file, factory updates, config model — ~6 files |
| Integration (I) | 1 | New external dep (`onnxruntime`), but well-understood and tested |
| Data/State (D) | 0 | No schema changes; graph metadata compatibility validated |
| Novelty (N) | 0 | Workshop proved the approach works — zero ambiguity |
| Non-Functional (F) | 1 | Performance is the motivation; must verify import time and embedding accuracy |
| Testing/Rollout (T) | 1 | Needs adapter unit tests + integration test; existing patterns to follow |

- **Assumptions**:
  - HuggingFace Hub models with ONNX exports include `onnx/model.onnx`, `tokenizer.json`, and `1_Pooling/config.json`
  - The `tokenizers` library (Rust-based) does not import torch
  - ONNX Runtime CPU provider works identically across Windows, macOS, and Linux

- **Dependencies**:
  - `onnxruntime` (new optional dependency)
  - `tokenizers` (already a transitive dependency of `transformers`)
  - `huggingface_hub` (already a dependency)
  - `numpy` (already a dependency)

- **Risks**:
  - Some models may not have ONNX exports on HuggingFace Hub — fail with actionable error
  - Pooling config detection relies on `1_Pooling/config.json` existing — need fallback
  - `tokenizers` library API may differ subtly from `transformers.AutoTokenizer` for edge-case texts

- **Phases**: Single phase — the adapter is self-contained

## Testing Strategy

- **Approach**: Hybrid — TDD for pooling/encoding logic (CLS vs mean detection, L2 normalization, tokenizer output), lightweight for config/factory wiring
- **Mock Policy**: Follow project convention of fakes (`FakeEmbeddingAdapter`). Targeted mocks for ONNX `InferenceSession` in unit tests — same documented exception as local adapter (loading 127MB model in tests is impractical).
- **Focus Areas**:
  - Pooling strategy detection: CLS vs mean from config.json (TDD)
  - Encode pipeline: tokenize → inference → pool → normalize → list[float] (TDD)
  - Numeric equivalence: compare against known ST output vectors (TDD)
  - Config/factory wiring: mode selection, graceful degradation (lightweight)
  - Thread-safe session loading: double-checked locking (lightweight — follows 046 pattern)
- **Excluded**: No real model downloads in CI; no GPU provider tests

## Documentation Strategy

- **Location**: Hybrid — update existing `src/fs2/docs/local-embeddings.md` and `src/fs2/docs/configuration-guide.md` with ONNX sections
- **Rationale**: Users looking for embedding docs already know these files. Adding ONNX alongside local mode is natural — no new file needed.

## Acceptance Criteria

1. **Import time under 2 seconds**: On Windows, the ONNX adapter imports all its dependencies (`onnxruntime`, `tokenizers`, `huggingface_hub`, `numpy`) in under 2 seconds total — no torch import.

2. **Numeric equivalence**: For `BAAI/bge-small-en-v1.5`, the ONNX adapter produces embeddings with L2 distance < 1e-5 from sentence-transformers output across a test suite of at least 5 diverse texts.

3. **MCP search works**: Setting `mode: "onnx"` in config, the MCP server's semantic search produces correct ranked results using ONNX-generated query embeddings against existing graph embeddings.

4. **Scan embedding works**: `fs2 scan --embed` with `mode: "onnx"` generates and stores embeddings in the graph using the ONNX adapter via `EmbeddingService`, identical to how `local` mode works.

5. **CLS pooling for BGE models**: The adapter reads `1_Pooling/config.json` and uses CLS token pooling for BGE models. Mean pooling is used when `pooling_mode_mean_tokens: true`.

6. **Graceful degradation**: If `onnxruntime` is not installed and mode is `"onnx"`, the factory returns `None` and search falls back to text mode — same pattern as missing `sentence-transformers`.

7. **Actionable error on missing ONNX export**: If the model's HuggingFace repo doesn't have `onnx/model.onnx`, the adapter raises `EmbeddingAdapterError` with a message explaining how to export or switch to `local` mode.

8. **Config integration**: `mode: "onnx"` is a valid config value. `OnnxEmbeddingConfig` supports `model`, `max_seq_length`, and `provider` fields with sensible defaults.

9. **Thread-safe session loading**: The ONNX session is loaded lazily with double-checked locking (same pattern as local adapter), preventing concurrent duplicate loads.

10. **warmup() support**: The adapter's `warmup()` method pre-loads the ONNX session and tokenizer in a background thread, compatible with the MCP preload system from plan 046.

11. **No regression on existing modes**: All existing adapter modes (`azure`, `openai_compatible`, `local`, `fake`) continue to work exactly as before.

12. **Return type contract**: `embed_text()` returns `list[float]`, `embed_batch()` returns `list[list[float]]` — not numpy arrays.

## Risks & Assumptions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Model has no ONNX export on Hub | Medium | Medium | Fail with actionable error; document which models are supported |
| `1_Pooling/config.json` missing | Low | High | Fall back to CLS pooling (most common for popular models) |
| `tokenizers` API edge cases | Low | Medium | Test with diverse code snippets; compare token-by-token with transformers |
| ONNX model version drift from torch weights | Low | Medium | Workshop verified HF repo ONNX matches — monitor for model updates |
| `huggingface_hub` network required on first use | Medium | Low | Same as local adapter — offline-first with `local_files_only` pattern |

### Assumptions

- Users have run `fs2 scan --embed` at least once (to populate graph embeddings) before using ONNX for MCP search — the ONNX adapter only changes the embedding backend, not the graph format
- The `tokenizers` library produces identical tokenization to `transformers.AutoTokenizer` for the same `tokenizer.json`
- ONNX Runtime CPU provider is sufficient for the embedding workload (inference on small models is fast)
- Existing graph embeddings (from `local` mode) are fully compatible with ONNX-generated query embeddings because both produce numerically identical vectors

## Open Questions

*All resolved by workshop — see Workshop 001.*

## Workshop Opportunities

| Topic | Type | Why Workshop | Key Questions |
|-------|------|--------------|---------------|
| ~~ONNX Runtime embedding inference~~ | ~~Integration Pattern~~ | ~~COMPLETED~~ | See `workshops/001-onnx-runtime-embedding-inference.md` |

All workshop opportunities have been addressed. The specification is ready for architecture.

## Clarifications

### Session 2026-04-08

**Q1: Workflow Mode** → **Simple**. Single-phase plan, inline tasks. Workshop eliminated ambiguity; adapter is self-contained.

**Q2: Testing Strategy** → **Hybrid**. TDD for pooling/encoding/equivalence logic, lightweight for config/factory wiring.

**Q3: Mock Usage** → **Follow project convention**: fakes via `FakeEmbeddingAdapter` where possible, targeted mocks for ONNX `InferenceSession` in unit tests (same documented exception as local adapter — loading 127MB model in tests is impractical).

**Q4: Domain Review** → **Confirmed**. 3 modify (embedding-adapters, config, embedding-service), 2 consume (mcp-server, cli). No adjustments.

**Q5: Documentation Strategy** → **Hybrid**. Update existing `local-embeddings.md` and `configuration-guide.md` with ONNX sections alongside local mode docs.
