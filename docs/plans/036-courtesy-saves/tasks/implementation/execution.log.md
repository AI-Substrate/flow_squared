# Execution Log: Courtesy Saves — Implementation

## Stage 1: Foundation (T01, T06)

### T01: Atomic Save — GraphStore.save()
**Status**: ✅ Complete

Changed `save()` to write to `.pickle.tmp` then `os.rename()`. On failure, temp file is cleaned up via `unlink(missing_ok=True)`. Prior graph.pickle is never corrupted during write.

**Files**: `src/fs2/core/repos/graph_store_impl.py`

### T06: PipelineContext callback
**Status**: ✅ Complete

Added `courtesy_save: Callable[[], None] | None = None` field to PipelineContext dataclass.

**Files**: `src/fs2/core/services/pipeline_context.py`

## Stage 2: Pipeline saves (T02, T03)

### T02: Save Helper
**Status**: ✅ Complete

Created `_courtesy_save_graph(context, graph_store)` module-level function in scan_pipeline.py. Clears graph_store, adds all nodes + containment edges + cross-file edges, sets embedding metadata, then calls atomic save. Uses `contextlib.suppress(GraphStoreError)` for edge-add failures.

**Files**: `src/fs2/core/services/scan_pipeline.py`

### T03: Inter-stage Saves
**Status**: ✅ Complete

In `ScanPipeline.run()`: wires `context.courtesy_save` to a closure calling `_courtesy_save_graph`. After each stage's `process()`, calls `context.courtesy_save()` unless stage name is "storage".

**Files**: `src/fs2/core/services/scan_pipeline.py`

## Stage 3: Intra-stage saves (T04, T05)

### T04: SmartContent Intra-stage
**Status**: ✅ Complete

- SmartContentStage creates a wrapper callback that merges partial results (`stats["results"]`) into `context.nodes` then calls `context.courtesy_save()`.
- SmartContentService.process_batch() and _worker_loop() accept `courtesy_save: Callable | None`.
- Worker loop calls courtesy_save every 10 processed nodes (outside the stats lock).

**Files**: `src/fs2/core/services/stages/smart_content_stage.py`, `src/fs2/core/services/smart_content/smart_content_service.py`

### T05: Embedding Intra-stage
**Status**: ✅ Complete

- EmbeddingStage creates same wrapper callback pattern as SmartContent.
- EmbeddingService.process_batch() accepts `courtesy_save: Callable | None`.
- During node reassembly loop (after chunk batches complete), calls courtesy_save every 50 reassembled nodes.

**Files**: `src/fs2/core/services/stages/embedding_stage.py`, `src/fs2/core/services/embedding/embedding_service.py`

## Stage 4: Tests (T07)

### T07: Tests
**Status**: ✅ Complete

**4 atomic save tests** (TestAtomicSave):
- test_save_uses_temp_file_then_rename — verifies .tmp absent after save
- test_save_cleans_up_tmp_on_failure — mock rename failure, verify .tmp cleaned
- test_prior_graph_survives_if_new_save_interrupted — partial .tmp doesn't corrupt .pickle
- test_save_roundtrip_with_atomic_write — full save/load cycle works

**4 courtesy save tests** (TestCourtesySaves):
- test_courtesy_save_wired_in_context — pipeline sets callback
- test_inter_stage_save_called_after_each_non_storage_stage — 2 non-storage stages = 2 saves
- test_courtesy_save_rebuilds_graph_from_context — verify loadable graph with correct nodes
- test_courtesy_save_not_set_when_no_graph_store — None graph_store = None callback

**Results**: 1751 passed, 25 skipped, 0 failed (up from 1743)

## Summary

All 7 tasks complete. 8 new tests. Zero ruff violations. Full suite green.
