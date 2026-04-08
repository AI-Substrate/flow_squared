# Execution Log: 047 ONNX Embedding Adapter

**Plan**: `onnx-embedding-adapter-plan.md`
**Mode**: Simple
**Started**: 2026-04-08

---

## Baseline

| Check | Status | Details |
|-------|--------|---------|
| Tests | ⚠️ | 1927 passed, 18 failed (pre-existing), 31 skipped, 357 deselected |
| Lint | ✅ | All changed files pass ruff |

---

## Task Log

### T001: OnnxEmbeddingConfig + mode literal ✅
- Added `OnnxEmbeddingConfig(model, max_seq_length, provider)` to `config/objects.py`
- Added `"onnx"` to `EmbeddingConfig.mode` Literal
- Added `onnx: OnnxEmbeddingConfig | None = None` field
- Extended `auto_default_dimensions_for_local()` to cover both `"local"` and `"onnx"` modes (384 dims)

### T002: OnnxEmbeddingAdapter implementation ✅
- Created `src/fs2/core/adapters/embedding_adapter_onnx.py`
- Full adapter: lazy session + tokenizer loading with `threading.Lock` + double-checked locking
- Uses `tokenizers.Tokenizer` (not `transformers.AutoTokenizer` which imports torch)
- Pooling detection from `1_Pooling/config.json` (CLS vs mean, defaults to CLS)
- L2 normalization + numpy → list[float] conversion
- `warmup()` override for MCP preload compatibility
- Offline-first download via `hf_hub_download(local_files_only=True)` with fallback
- Error storage pattern matching local adapter (`_session_error`)

### T003: ONNX adapter tests ✅
- Created `tests/unit/adapters/test_embedding_adapter_onnx.py` — 22 tests
- Covers: init, CLS pooling, mean pooling, L2 normalization, return types, batch ordering, errors (missing onnxruntime, stored errors), thread safety, warmup, config validation, factory graceful degradation
- Uses mock `InferenceSession` and `Tokenizer` (documented exception like local adapter)

### T004: Adapter factory branch ✅
- Added `elif embedding_config.mode == "onnx"` branch to `create_embedding_adapter_from_config()`
- Probes `onnxruntime` via `find_spec` — returns `None` if missing
- Auto-creates `OnnxEmbeddingConfig()` if not provided

### T005: EmbeddingService factory branch ✅
- Added `elif embedding_config.mode == "onnx"` branch to `EmbeddingService.create()`
- Mirrors T004 logic exactly

### T006: pyproject optional deps ✅
- Added `onnx-embeddings = ["onnxruntime>=1.17"]` to `[project.optional-dependencies]`

### T007: Documentation updates ✅
- Updated `src/fs2/docs/local-embeddings.md` with ONNX quick start section
- Updated `src/fs2/docs/configuration-guide.md` with ONNX config examples

### T008: Config validation tests ✅
- Combined into T003 test file (TestOnnxConfigValidation class)
- Tests: mode acceptance, defaults, auto-dimensions, explicit override, validation

## Final Results

| Check | Status | Details |
|-------|--------|---------|
| New tests | ✅ | 22/22 pass |
| Full suite | ✅ | 1949 passed (+22), 18 failed (pre-existing), 0 new failures |
| Lint | ✅ | All changed files pass ruff |

## Discoveries & Learnings

| ID | Type | Discovery | Action Taken |
|----|------|-----------|--------------|
| D01 | gotcha | ruff SIM103 flags `if x: return True; if y: return False; return True` pattern — wants `return not y` | Refactored pooling detection to use `return not pooling_config.get(...)` |
| D02 | gotcha | ruff F541 flags f-strings without placeholders | Changed to plain strings for static error messages |
| D03 | insight | T003 and T008 naturally combined into one test file since config tests are adapter-adjacent | Merged all 22 tests into `test_embedding_adapter_onnx.py` |
