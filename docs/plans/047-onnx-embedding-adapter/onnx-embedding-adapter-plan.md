# ONNX Embedding Adapter — Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-04-08
**Spec**: `docs/plans/047-onnx-embedding-adapter/onnx-embedding-adapter-spec.md`
**Status**: COMPLETE

## Summary

Importing sentence-transformers/PyTorch on Windows takes 93 seconds, making MCP semantic search and `fs2 scan --embed` painfully slow to start. This plan adds an `OnnxEmbeddingAdapter` using ONNX Runtime (0.68s import) that produces numerically identical embeddings (L2 < 1e-6, verified by workshop). The adapter follows the exact same ABC pattern, factory wiring, and DI conventions as the existing 4 adapters. A new `mode: "onnx"` config value activates it across both MCP search and scan embedding paths.

## Target Domains

| Domain | Status | Relationship | Role |
|--------|--------|-------------|------|
| embedding-adapters | no registry | **modify** | New `OnnxEmbeddingAdapter` + factory branch |
| config | no registry | **modify** | New `OnnxEmbeddingConfig` + `"onnx"` mode literal |
| embedding-service | no registry | **modify** | Update `EmbeddingService.create()` factory |
| mcp-server | no registry | **consume** | No changes — works via adapter ABC |
| cli | no registry | **consume** | No changes — works via EmbeddingService |

## Domain Manifest

| File | Domain | Classification | Rationale |
|------|--------|---------------|-----------|
| `src/fs2/core/adapters/embedding_adapter_onnx.py` | embedding-adapters | internal | **NEW**: ONNX Runtime adapter implementation |
| `src/fs2/core/adapters/embedding_adapter.py` | embedding-adapters | contract | Add `"onnx"` branch to `create_embedding_adapter_from_config()` |
| `src/fs2/config/objects.py` | config | internal | Add `OnnxEmbeddingConfig`, `"onnx"` to mode Literal, auto-default dims |
| `src/fs2/core/services/embedding/embedding_service.py` | embedding-service | internal | Add `"onnx"` branch to `EmbeddingService.create()` |
| `pyproject.toml` | project | internal | Add `onnx-embeddings` optional dependency group |
| `src/fs2/docs/local-embeddings.md` | docs | internal | Add ONNX section alongside local mode docs |
| `src/fs2/docs/configuration-guide.md` | docs | internal | Add ONNX config examples |
| `tests/unit/adapters/test_embedding_adapter_onnx.py` | tests | new | ONNX adapter unit tests |
| `tests/unit/config/test_onnx_embedding_config.py` | tests | new | ONNX config validation tests |

## Key Findings

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | `EmbeddingConfig.mode` is `Literal["azure","openai_compatible","local","fake"]` — Pydantic rejects `"onnx"` before adapter creation | Add `"onnx"` to the Literal in T001 |
| 02 | Critical | Two factory sites: `create_embedding_adapter_from_config()` AND `EmbeddingService.create()` — missing either means ONNX works for search but not scan, or vice versa | Update both in T004 and T005 |
| 03 | Critical | BGE models use CLS pooling, not mean pooling — workshop caught this, must read `1_Pooling/config.json` | Implement pooling detection in T002 |
| 04 | High | `auto_default_dimensions_for_local()` only fires for `mode=="local"` — ONNX would keep 1024 default (wrong, should be 384) | Extend auto-default to cover `"onnx"` in T001 |
| 05 | High | Metadata mismatch on backend switch: `embedding_model` stores `mode` value, so `local→onnx` triggers re-embed even with same underlying model | Store actual model name (e.g., `BAAI/bge-small-en-v1.5`) instead of mode for ONNX; accept mismatch as expected behavior for v1 |
| 06 | High | `transformers.AutoTokenizer` imports torch (38s) — must use `tokenizers.Tokenizer` directly | Workshop validated this approach; enforced in T002 |
| 07 | High | Must use offline-first download pattern (`local_files_only=True` then fallback) matching local adapter | Implement in T002 |

## Implementation

**Objective**: Add ONNX Runtime embedding adapter with identical output to sentence-transformers, eliminating the 93-second PyTorch import on Windows.
**Testing Approach**: Hybrid — TDD for pooling/encoding logic, lightweight for config/wiring. Targeted mocks for ONNX session (documented exception like local adapter).

### Tasks

| Status | ID | Task | Domain | Path(s) | Done When | Notes |
|--------|-----|------|--------|---------|-----------|-------|
| [x] | T001 | Add `OnnxEmbeddingConfig` and `"onnx"` mode to config | config | `src/fs2/config/objects.py` | Complete | Extended auto_default_dimensions to cover onnx |
| [x] | T002 | Create `OnnxEmbeddingAdapter` implementation | embedding-adapters | `src/fs2/core/adapters/embedding_adapter_onnx.py` | Complete | Full adapter with CLS/mean pooling, thread safety, warmup |
| [x] | T003 | TDD tests for ONNX adapter encode pipeline | tests | `tests/unit/adapters/test_embedding_adapter_onnx.py` | 22 tests, all pass | Covers pooling, normalization, types, errors, threading, config |
| [x] | T004 | Add `"onnx"` branch to adapter factory | embedding-adapters | `src/fs2/core/adapters/embedding_adapter.py` | Complete | find_spec probe + OnnxEmbeddingConfig auto-create |
| [x] | T005 | Add `"onnx"` branch to `EmbeddingService.create()` | embedding-service | `src/fs2/core/services/embedding/embedding_service.py` | Complete | Mirrors T004 logic |
| [x] | T006 | Add `onnx-embeddings` optional dep group | project | `pyproject.toml` | Complete | onnxruntime>=1.17 |
| [x] | T007 | Update user docs with ONNX section | docs | `src/fs2/docs/local-embeddings.md`, `src/fs2/docs/configuration-guide.md` | Complete | ONNX quick start + config examples |
| [x] | T008 | Config validation tests | tests | `tests/unit/adapters/test_embedding_adapter_onnx.py` | Included in T003 | Combined into single test file |

### Task Dependencies

```
T001 (config model) ── standalone, do first
T003 (TDD tests) ──→ write alongside T002
T002 (adapter impl) ──→ depends on T001
T004 (adapter factory) ──→ depends on T001, T002
T005 (service factory) ──→ depends on T001, T002
T006 (pyproject) ── standalone
T007 (docs) ── standalone, do last
T008 (config tests) ──→ depends on T001
```

### Recommended Execution Order

1. **T001** — Config model (everything depends on this)
2. **T008** — Config validation tests (lightweight, verify T001)
3. **T003** — TDD tests for adapter (write first)
4. **T002** — ONNX adapter implementation (make T003 pass)
5. **T004** — Adapter factory branch
6. **T005** — EmbeddingService factory branch
7. **T006** — pyproject optional deps
8. **T007** — Documentation updates

### Acceptance Criteria

- [x] AC-1: ONNX adapter imports (`onnxruntime`, `tokenizers`, `huggingface_hub`, `numpy`) complete in under 2 seconds — no torch import
- [x] AC-2: For `BAAI/bge-small-en-v1.5`, ONNX adapter produces embeddings with L2 distance < 1e-5 from sentence-transformers across 5+ diverse texts
- [x] AC-3: MCP search with `mode: "onnx"` produces correct ranked results
- [x] AC-4: `fs2 scan --embed` with `mode: "onnx"` generates and stores embeddings in graph
- [x] AC-5: Adapter reads `1_Pooling/config.json` — uses CLS for BGE, mean when configured
- [x] AC-6: Missing `onnxruntime` → factory returns `None`, search falls back to text mode
- [x] AC-7: Missing `onnx/model.onnx` → `EmbeddingAdapterError` with actionable message
- [x] AC-8: `mode: "onnx"` accepted by config. `OnnxEmbeddingConfig` has `model`, `max_seq_length`, `provider` with defaults
- [x] AC-9: Thread-safe session loading with double-checked locking
- [x] AC-10: `warmup()` pre-loads session, compatible with MCP preload (046)
- [x] AC-11: All existing modes (`azure`, `openai_compatible`, `local`, `fake`) unaffected
- [x] AC-12: `embed_text()` returns `list[float]`, `embed_batch()` returns `list[list[float]]`

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Model has no ONNX export on Hub | Medium | Medium | Fail with actionable error: "Use mode: 'local' or export with optimum-cli" |
| `1_Pooling/config.json` missing from Hub | Low | High | Fall back to CLS pooling (most common for popular models) |
| Metadata mismatch on local→onnx switch | High | Low | Expected behavior — user must re-embed or use `--force`. V1 accepts this. |
| `tokenizers` edge cases vs `transformers` | Low | Medium | Test with diverse code snippets in T003 |
| ONNX session slower than expected on some CPUs | Very Low | Low | Benchmark validated 0.03s for 5 texts — well within acceptable range |
