# Local Embedding Adapter for Offline Semantic Search

**Mode**: Simple

📚 This specification incorporates findings from [Workshop 001: Local SentenceTransformer Embeddings](workshops/001-local-sentence-transformer-embeddings.md)

## Research Context

The 009-embeddings plan established fs2's embedding architecture: an `EmbeddingAdapter` ABC with Azure and OpenAI-compatible implementations. These require API credentials and network access. Workshop 001 benchmarked local SentenceTransformer models on Apple Silicon (MPS), CUDA, and CPU, finding that `BAAI/bge-small-en-v1.5` delivers 947 items/s on MPS with strong retrieval quality (MTEB ~50-54), making it viable as a zero-cost, fully offline alternative.

Key workshop findings:
- **BGE-small-en-v1.5** is the recommended default (best retrieval quality per size)
- MPS gives ~3× speedup over CPU; CUDA expected to be even faster
- Parallel multi-process encoding **hurts** on GPU (contention)
- CodeBERT/UniXcoder are **not usable** via SentenceTransformer (wrong pooling)
- `torch` + `sentence-transformers` are ~2 GB — must be optional deps
- Darwin requires `pool=None` workaround for MPS stability

## Summary

**WHAT**: Add a new `local` embedding mode to fs2 that generates embeddings on-device using SentenceTransformer models, requiring no API keys, no network access, and no ongoing costs.

**WHY**: Currently, fs2's semantic search (`fs2 search --mode semantic`) only works if users have Azure or OpenAI API credentials configured. This excludes:
- Developers without cloud accounts
- Air-gapped / offline environments
- Users who want to avoid per-token API costs
- Open-source contributors who can't use proprietary APIs
- CI/CD pipelines without API credential access

Local embeddings make semantic search a **zero-configuration feature** — users install an optional dependency and set `mode: local` in config.

## Goals

- **G1**: Users can generate embeddings locally without any API keys or network access
- **G2**: Local embeddings are a drop-in replacement — existing `fs2 scan --embed` and `fs2 search` commands work without modification
- **G3**: Device auto-detection picks the fastest available hardware (CUDA > MPS > CPU)
- **G4**: The large `torch` dependency is optional — users who don't need local embeddings are unaffected
- **G5**: Configuration follows existing patterns (YAML, env vars) and is discoverable
- **G6**: The adapter works correctly on Linux (CPU/CUDA), macOS (CPU/MPS), and Windows (CPU/CUDA)

## Non-Goals

- **NG1**: Fine-tuning models for code-specific embeddings (use pre-trained models as-is)
- **NG2**: Supporting non-SentenceTransformer models (e.g., CodeBERT with [CLS] pooling)
- **NG3**: Automatic migration between embedding providers (changing mode requires re-embedding)
- **NG4**: GPU memory management or multi-GPU support
- **NG5**: Model download progress UI (SentenceTransformer handles this internally)
- **NG6**: Hybrid local+API embedding strategies

## Target Domains

| Domain | Status | Relationship | Role in This Feature |
|--------|--------|-------------|---------------------|
| adapters | existing | **modify** | Add new `SentenceTransformerEmbeddingAdapter` implementation |
| config | existing | **modify** | Add `LocalEmbeddingConfig` model and extend `EmbeddingConfig` with `mode: local` |
| dependencies | existing | **modify** | Wire new adapter into factory function and DI |
| services | existing | **modify** | Embedding stage: error-and-block on dimension mismatch (per AC #13) |
| cli | existing | **modify** | Update `fs2 init` template for local default, add `--force` flag to scan |

*No new domains required — this feature extends existing adapter and config patterns.*

## Complexity

- **Score**: CS-3 (medium)
- **Breakdown**: S=1, I=1, D=0, N=0, F=1, T=1 → Total P=4 → CS-2 base, +1 for optional dependency complexity
  - **S=1** (Surface Area): Multiple files touched (adapter, config, factory, __init__, pyproject.toml, tests) but follows established patterns
  - **I=1** (Integration): One external dep (`sentence-transformers` + `torch`) — well-understood, stable
  - **D=0** (Data/State): No schema changes; embeddings stored in same format
  - **N=0** (Novelty): Well-specified by workshop; clear patterns from existing adapters
  - **F=1** (Non-Functional): Cross-platform device detection, optional dep handling
  - **T=1** (Testing): Integration tests need mock model; unit tests follow existing patterns
- **Confidence**: 0.90
- **Assumptions**:
  - SentenceTransformer's `model.encode()` API remains stable
  - `BAAI/bge-small-en-v1.5` produces 384-dim embeddings (verified by benchmark)
  - `run_in_executor` is sufficient for async wrapping (no need for subprocess)
- **Dependencies**:
  - `sentence-transformers >= 3.0`
  - `torch >= 2.0`
  - No changes needed to FAISS/cosine index (just uses different dimension)
- **Risks**: See Risks & Assumptions section
- **Phases**:
  1. Config model + validation
  2. Adapter implementation + factory wiring
  3. Tests + optional dependency guard
  4. Documentation + pyproject.toml

## Acceptance Criteria

1. **Given** a user with `mode: local` in `.fs2/config.yaml` and `sentence-transformers` installed, **when** they run `fs2 scan --embed`, **then** embeddings are generated locally without any network API calls.

2. **Given** a user with local embeddings indexed, **when** they run `fs2 search "error handling" --mode semantic`, **then** results are returned using locally-generated embeddings.

3. **Given** a machine with an NVIDIA GPU and CUDA installed, **when** the adapter initializes with `device: auto`, **then** it selects CUDA and logs the GPU name.

4. **Given** a Mac with Apple Silicon, **when** the adapter initializes with `device: auto`, **then** it selects MPS and logs "MPS detected (Apple Silicon)".

5. **Given** a machine with no GPU, **when** the adapter initializes with `device: auto`, **then** it selects CPU.

6. **Given** a user requests `device: cuda` but no CUDA is available, **when** the adapter initializes, **then** it falls back to CPU and logs a warning.

7. **Given** `sentence-transformers` is NOT installed, **when** `mode: local` is used, **then** an `EmbeddingAdapterError` is raised with message: "Install it with: pip install fs2[local-embeddings]".

8. **Given** `mode: local` with no `local:` section in config, **when** the adapter is created, **then** it uses defaults (model: `BAAI/bge-small-en-v1.5`, device: `auto`, max_seq_length: `512`) and `dimensions` auto-defaults to `384`.

9. **Given** the configured `dimensions` (e.g., 1024) differs from the model's actual dimension (384), **when** the model loads, **then** a warning is logged identifying the mismatch.

10. **Given** `embed_batch` is called with a list of texts, **when** encoding completes, **then** the return type is `list[list[float]]` (not numpy arrays).

11. **Given** the adapter is running on macOS, **when** `embed_batch` calls `model.encode()`, **then** `pool=None` is set in encode kwargs to avoid MPS multiprocessing crash.

12. **Given** `mode: local` in config, **when** `create_embedding_adapter_from_config` is called, **then** it returns a `SentenceTransformerEmbeddingAdapter` instance.

13. **Given** a graph with stored embeddings at dimension 1024, **when** the user changes config to `mode: local` (384-dim) and runs `fs2 scan --embed`, **then** the scan errors with a clear message explaining the dimension mismatch and instructs the user to run `fs2 scan --embed --force`.

## Risks & Assumptions

| Risk | Impact | Mitigation |
|------|--------|------------|
| `torch` adds ~2 GB to install | Users surprised by large download | Optional dep group `[local-embeddings]`; clear error message on missing import |
| Dimension mismatch when switching modes | Search index breaks (384 vs 1024) | Warning on mismatch; docs say "re-embed after mode change" |
| First model load downloads ~130 MB | Slow first run, fails offline | Model cached after first download; document offline prep |
| MPS warmup latency on first batch | First batch 2-3× slower | Acceptable; subsequent batches are fast |
| SentenceTransformer API changes | Adapter breaks on upgrade | Pin minimum version; encode() API has been stable |

**Assumptions**:
- Users accept that local and API embeddings are NOT interchangeable (different dimensions, different quality)
- Model download from HuggingFace Hub is acceptable for first-time setup
- Single-process encoding is sufficient (parallel encoding proven slower on GPU)

## Open Questions

~~1. **Should `dimensions` auto-update when using local mode?**~~ → **Resolved**: Yes — auto-default dimensions to 384 when `mode: local`. See Clarifications.

~~2. **Should `fs2 scan --embed` detect dimension changes and prompt for re-embed?**~~ → **Resolved**: Error and block — refuse to scan if stored embedding dimensions don't match config. User must run `fs2 scan --embed --force`. See Clarifications.

## Testing Strategy

- **Approach**: Full TDD — tests first for adapter, config, and factory
- **Rationale**: The adapter has clear contracts (ABC methods, device detection, error handling, type conversion) that suit test-first development. Config validation and factory wiring also have well-defined expected behavior.
- **Focus Areas**:
  - ABC compliance (all abstract methods implemented)
  - Device detection chain (CUDA > MPS > CPU, fallbacks)
  - Import guard (actionable error when `sentence-transformers` missing)
  - Return type enforcement (`list[list[float]]`, not numpy)
  - Darwin `pool=None` workaround
  - Config validation (`LocalEmbeddingConfig` fields)
  - Factory integration (`create_embedding_adapter_from_config` returns correct adapter)
  - Dimension auto-default for `mode: local`
- **Mock Usage**: Allow targeted mocks — mock `SentenceTransformer` model only (loading a real 130MB model in unit tests is impractical). This is a documented exception to the project's "fakes over mocks" convention.
- **Excluded**: Real model download/inference (too slow for CI). Integration tests with real models should use `@pytest.mark.slow`.

## Documentation Strategy

- **Location**: Hybrid (README + docs/how/)
  - README.md: Quick-start section for local embeddings (install, config, run)
  - docs/how/user/local-embeddings.md: Detailed guide (model selection, device config, migration from API, troubleshooting)
- **Rationale**: Users need a fast path (README) plus depth for model comparison and cross-platform device setup

## Clarifications

### Session 2026-03-15

**Q1 — Workflow Mode**: Simple — single-phase plan, quick path. Workshop already completed the heavy design work.

**Q2 — Testing Strategy**: Full TDD — write tests first for adapter, config, and factory.

**Q3 — Mock Usage**: Allow targeted mocks — mock SentenceTransformer model only. Loading a real 130MB model in unit tests is impractical. Documented exception to "fakes over mocks" convention.

**Q4 — Documentation Strategy**: Hybrid (README + docs/how/) — quick-start in README, detailed guide in docs/how/user/local-embeddings.md.

**Q5 — Dimension auto-default**: Yes — auto-default `dimensions` to 384 when `mode: local` is set. Simplest UX, avoids users needing to know model dimension. Updated AC #8 and config design.

**Q6 — Dimension mismatch on re-scan**: Error and block — if stored embeddings have different dimensions than config, refuse to scan and require `fs2 scan --embed --force`. This prevents mixed-dimension graphs (which silently break search). User experience: clear error message explaining the mismatch and how to fix it.
- **Note**: This is a change to the existing embedding stage mismatch behavior (currently warns but continues). The change only applies when dimensions actually differ, not when model name changes within the same dimension space.

**Q7 — Default mode for new projects**: Local embeddings should be the **default mode** when running `fs2 init` on a new machine. This means changing `EmbeddingConfig.mode` default from `"azure"` to `"local"` and ensuring the generated config template uses `mode: local`.

## Workshop Opportunities

| Topic | Type | Why Workshop | Key Questions |
|-------|------|--------------|---------------|
| Local SentenceTransformer Embeddings | Integration Pattern | ✅ **COMPLETED** | Model selection, async wrapping, device detection, config design |

> Workshop 001 has been completed — see `workshops/001-local-sentence-transformer-embeddings.md` for full design including benchmark data, adapter code sketch, and configuration examples.
