# Local Embedding Adapter Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-03-15
**Spec**: [local-embeddings-spec.md](local-embeddings-spec.md)
**Workshop**: [001-local-sentence-transformer-embeddings.md](workshops/001-local-sentence-transformer-embeddings.md)
**Status**: COMPLETE

## Summary

Add a `SentenceTransformerEmbeddingAdapter` that enables fully local, zero-API-cost embedding generation using HuggingFace SentenceTransformer models. This extends the existing `EmbeddingAdapter` ABC with a new `mode: local` config option, auto-detecting CUDA/MPS/CPU devices. Local mode becomes the **default** for new projects via `fs2 init`, making semantic search work out-of-the-box without API credentials. The large `torch` dependency is managed as an optional install group `[local-embeddings]`.

## Target Domains

| Domain | Status | Relationship | Role |
|--------|--------|-------------|------|
| adapters | existing | **modify** | New `SentenceTransformerEmbeddingAdapter` implementation |
| config | existing | **modify** | `LocalEmbeddingConfig` model, `mode: local` in `EmbeddingConfig`, dimension auto-default |
| dependencies | existing | **modify** | Factory function wiring (via adapters/embedding_adapter.py) |
| cli | existing | **modify** | Update `fs2 init` template, add `--force` to scan |
| services | existing | **modify** | Embedding stage: error-and-block on dimension mismatch (per AC #13) |

## Domain Manifest

| File | Domain | Classification | Rationale |
|------|--------|---------------|-----------|
| `src/fs2/config/objects.py` | config | internal | Add `LocalEmbeddingConfig`, extend `EmbeddingConfig` mode Literal + defaults |
| `src/fs2/core/adapters/embedding_adapter_local.py` | adapters | internal | **NEW** — SentenceTransformer adapter implementation |
| `src/fs2/core/adapters/embedding_adapter.py` | adapters | contract | Add `mode: local` branch to factory function |
| `src/fs2/core/adapters/__init__.py` | adapters | internal | Export new adapter class |
| `src/fs2/core/services/stages/embedding_stage.py` | services | internal | Dimension mismatch → error-and-block |
| `src/fs2/cli/init.py` | cli | internal | Update DEFAULT_CONFIG template for local mode |
| `src/fs2/cli/scan.py` | cli | internal | Add `--force` flag for dimension override |
| `pyproject.toml` | config | internal | Add `[local-embeddings]` optional dep group |
| `tests/unit/config/test_embedding_config.py` | config | internal | Tests for LocalEmbeddingConfig + mode="local" |
| `tests/unit/adapters/test_embedding_adapter_local.py` | adapters | internal | **NEW** — Full adapter test suite |
| `tests/unit/adapters/test_embedding_adapter.py` | adapters | internal | Extend factory tests for local mode |
| `tests/unit/services/stages/test_embedding_stage.py` | services | internal | Test dimension mismatch error-and-block |
| `docs/how/user/local-embeddings.md` | — | documentation | **NEW** — User guide |
| `README.md` | — | documentation | Quick-start section |

## Key Findings

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | `EmbeddingConfig.mode` Literal at `objects.py:632` is `["azure", "openai_compatible", "fake"]` with default `"azure"`. Must add `"local"` and change default. Pydantic handles validation automatically — no existing tests break. | T002 |
| 02 | Critical | `fs2 init` exists at `src/fs2/cli/init.py` with `DEFAULT_CONFIG` template (lines 18-106). Embedding section is fully commented out. Must add uncommented local mode as default. | T009 |
| 03 | High | No `--force` flag exists on `fs2 scan`. Current dimension mismatch in `embedding_stage.py:80-84` only warns. Must add `--force` flag and change to error-and-block. | T008 |
| 04 | High | Import boundary tests at `test_import_boundaries.py` verify ABC files contain no SDK imports. `sentence_transformers` must be lazy-imported only in the implementation file, never in ABC. | T004 |
| 05 | High | Existing adapter tests mock `ConfigurationService` + `_get_client()` via `patch.object`. Follow OpenAI adapter test pattern (`test_embedding_adapter_openai.py`). For local adapter, mock `SentenceTransformer` class at module level. | T005, T006 |
| 06 | Medium | `pyproject.toml` has `[project.optional-dependencies]` with `dev` group. No provider-specific groups exist yet. Add `local-embeddings` group here. | T010 |
| 07 | Medium | Factory returns `None` for unknown modes (no error). Adding `"local"` branch follows existing pattern — lazy import of implementation, check for `None` config. | T007 |

## Implementation

**Objective**: Deliver a fully tested local embedding adapter with config, factory wiring, init template default, dimension mismatch protection, and documentation.
**Testing Approach**: Full TDD — tests first for config, adapter, factory. Targeted mocks for SentenceTransformer model (documented exception to fakes-over-mocks).

### Tasks

| Status | ID | Task | Domain | Path(s) | Done When | Notes |
|--------|-----|------|--------|---------|-----------|-------|
| [x] | T001 | **Write config tests (TDD)** — Test `LocalEmbeddingConfig` defaults/validation, `mode="local"` Literal, dimension auto-default, nested local section. Follow pattern from `TestEmbeddingConfigAzureNested`. | config | `tests/unit/config/test_embedding_config.py` | All new tests fail (red); existing tests unchanged | TDD: tests first |
| [x] | T002 | **Add `LocalEmbeddingConfig` model** — Pydantic model with `model: str`, `device: Literal[...]`, `max_seq_length: int`. Add field validators. | config | `src/fs2/config/objects.py` | Config instantiates with defaults; validates device values; `model` defaults to `BAAI/bge-small-en-v1.5` | Per workshop D4 |
| [x] | T003 | **Extend `EmbeddingConfig`** — Add `"local"` to mode Literal. Change default from `"azure"` to `"local"`. Add `local: LocalEmbeddingConfig \| None = None` field. Add model validator: when `mode="local"` and `dimensions` not explicitly set, auto-default to `384`. | config | `src/fs2/config/objects.py` | T001 config tests pass (green); `EmbeddingConfig(mode="local")` works; `dimensions` auto-defaults to 384 for local mode; existing azure/openai modes still work | Per finding 01, spec Q5 |
| [x] | T004 | **Write adapter unit tests (TDD)** — ABC compliance, provider_name, device detection chain, import guard error, Darwin workaround, return type enforcement, dimension mismatch warning, lazy model loading. Mock `SentenceTransformer` at module level. Follow `test_embedding_adapter_openai.py` pattern. | adapters | `tests/unit/adapters/test_embedding_adapter_local.py` | All new tests fail (red); no real model download in CI | TDD: tests first; per finding 05, spec Q3 |
| [x] | T005 | **Create `SentenceTransformerEmbeddingAdapter`** — Implement ABC: `provider_name → "local"`, `embed_text`, `embed_batch`. Lazy-import `sentence_transformers`. Device detection (CUDA>MPS>CPU). `run_in_executor` for async. Darwin `pool=None`. Convert numpy→`list[float]`. | adapters | `src/fs2/core/adapters/embedding_adapter_local.py` | T004 adapter tests pass (green); adapter passes ABC compliance; returns `list[list[float]]`; lazy import raises actionable error | Per workshop design, finding 04 |
| [x] | T006 | **Write adapter factory tests (TDD)** — Test `create_embedding_adapter_from_config` returns `SentenceTransformerEmbeddingAdapter` for `mode="local"`. Test returns adapter with default config when `local:` section missing. | adapters | `tests/unit/adapters/test_embedding_adapter.py` | All new tests fail (red) | TDD: tests first; per finding 07 |
| [x] | T007 | **Wire factory function** — Add `elif embedding_config.mode == "local":` branch to `create_embedding_adapter_from_config`. Lazy-import adapter. Create default `LocalEmbeddingConfig()` if section missing. | adapters | `src/fs2/core/adapters/embedding_adapter.py` | T006 factory tests pass (green); factory returns `SentenceTransformerEmbeddingAdapter` for `mode="local"` | Per finding 07 |
| [x] | T008 | **Dimension mismatch error-and-block** — Change `embedding_stage.py` mismatch handling: when `embedding_dimensions` differs, raise error (not warning). Add `--force` flag to `scan.py` CLI that bypasses the check. Pass force flag through pipeline context. | services, cli | `src/fs2/core/services/stages/embedding_stage.py`, `src/fs2/cli/scan.py` | Dimension mismatch blocks scan with clear error; `--force` overrides | Per finding 03, spec AC #13 |
| [x] | T009 | **Update `fs2 init` template** — Change `DEFAULT_CONFIG` in `init.py` to include uncommented local embedding section as default. Keep azure/openai examples commented. | cli | `src/fs2/cli/init.py` | `fs2 init` creates config with `mode: local` and `dimensions: 384` | Per finding 02, user req |
| [x] | T010 | **Add optional dependency group** — Add `local-embeddings = ["sentence-transformers>=3.0", "torch>=2.0"]` to `[project.optional-dependencies]` in `pyproject.toml`. | config | `pyproject.toml` | `pip install fs2[local-embeddings]` installs torch + sentence-transformers | Per finding 06 |
| [x] | T011 | **Update adapter exports** — Add `SentenceTransformerEmbeddingAdapter` to `__init__.py` imports and `__all__`. | adapters | `src/fs2/core/adapters/__init__.py` | Import works: `from fs2.core.adapters import SentenceTransformerEmbeddingAdapter` | Mechanical |
| [x] | T012 | **Write user documentation** — Create `docs/how/user/local-embeddings.md`: install, config, model selection, device setup, migration from API, troubleshooting. Add quick-start to README. | — | `docs/how/user/local-embeddings.md`, `README.md` | Docs cover install→config→run path | Per spec doc strategy |

### Acceptance Criteria

- [x] AC1: `mode: local` in config + `sentence-transformers` installed → `fs2 scan --embed` generates embeddings locally (no API calls) ✅ verified: 5704 nodes on fs2, 826 on home-improvement
- [x] AC2: `fs2 search "error handling" --mode semantic` returns results using local embeddings ✅ verified
- [x] AC3: CUDA auto-detected when available; MPS on Apple Silicon; CPU fallback ✅ verified: MPS on Apple Silicon
- [x] AC4: Device fallback with warning when requested device unavailable ✅ unit tests
- [x] AC5: Missing `sentence-transformers` → `EmbeddingAdapterError` with install instructions ✅ verified: integration + unit
- [x] AC6: Default config (no `local:` section) → uses `BAAI/bge-small-en-v1.5`, `device: auto`, `max_seq_length: 512` ✅ unit tests
- [x] AC7: `dimensions` auto-defaults to 384 when `mode: local` ✅ unit tests (DYK-3 model_fields_set)
- [x] AC8: Dimension mismatch warning when config `dimensions` differs from model output ✅ unit tests
- [x] AC9: Return type is `list[list[float]]` (not numpy) ✅ unit tests
- [x] AC10: macOS sets `pool=None` in encode kwargs ✅ unit tests
- [x] AC11: `create_embedding_adapter_from_config` returns `SentenceTransformerEmbeddingAdapter` for `mode: local` ✅ unit tests
- [x] AC12: Dimension mismatch between stored graph and config → error blocks scan; `--force` overrides ✅ verified: home-improvement
- [x] AC13: `fs2 init` creates config with `mode: local` as default embedding mode ✅ verified: init.py template

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Changing `EmbeddingConfig.mode` default from `azure` to `local` breaks existing users | Low | Medium | Only affects new configs from `fs2 init`; existing `.fs2/config.yaml` files with `mode: azure` are preserved. Default change is safe because EmbeddingConfig returns `None` from factory when `sentence-transformers` isn't installed (graceful degradation). |
| `torch` not installable on all platforms (e.g., some ARM Linux) | Low | Medium | Optional dep; adapter raises clear error on import failure |
| `--force` flag added to scan may interact with other scan behaviors | Low | Low | Flag only affects dimension mismatch check; passes through context cleanly |
| Model dimension (384) differs from current default (1024) | N/A | N/A | Auto-default resolved in spec Q5; adapter warns on mismatch |
