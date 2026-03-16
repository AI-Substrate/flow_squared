# Courtesy Saves — Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-03-15
**Spec**: [courtesy-saves-spec.md](courtesy-saves-spec.md)
**Status**: COMPLETE

## Summary

Add periodic graph persistence throughout the scan pipeline. Currently saves once at the end — crash loses everything. With courtesy saves: atomic writes, save after each stage, save every N nodes during SmartContent/Embedding.

## Target Domains

| Domain | Status | Relationship | Tasks |
|--------|--------|-------------|-------|
| repos | existing | modify | T01 (atomic save) |
| services | existing | modify | T02, T03 (pipeline saves, save helper) |
| stages | existing | modify | T04, T05 (intra-stage courtesy saves) |
| config | existing | modify | T06 (PipelineContext callback field) |

## Key Findings

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | Graph is **cleared** before stages run (scan_pipeline.py L227) — courtesy saves must re-add nodes to graph_store | Save helper must populate graph_store from context.nodes before saving |
| 02 | High | GraphStore.save() does direct pickle.dump, not atomic temp+rename | Fix: write to .tmp then rename |
| 03 | Medium | SmartContent/Embedding overlay results AFTER batch completes (L167/L150) — intra-stage saves need to happen during batch processing via callback | Use progress callback or courtesy_save callback in PipelineContext |

## Implementation

**Objective**: Make scans crash-resilient with periodic graph saves
**Testing Approach**: Lightweight — atomic save test, inter-stage save test

### Tasks

| Status | ID | Task | Domain | Path(s) | Done When | Notes |
|--------|-----|------|--------|---------|-----------|-------|
| [ ] | T01 | Atomic save: GraphStore.save() writes to temp file then renames | repos | `src/fs2/core/repos/graph_store_impl.py` | Save writes to .pickle.tmp then renames; kill during write leaves prior graph intact | AC02 |
| [ ] | T02 | Extract save helper: reusable function that populates graph_store from context.nodes + edges then saves | services | `src/fs2/core/services/scan_pipeline.py` | Helper takes context, adds nodes + containment edges + cross-file edges to graph_store, then calls save() | AC03, needed by T03-T05 |
| [ ] | T03 | Inter-stage saves: call save helper after each stage in ScanPipeline.run() | services | `src/fs2/core/services/scan_pipeline.py` | Graph saved after Parsing, CrossFileRels, SmartContent, Embedding (before StorageStage) | AC03 |
| [ ] | T04 | SmartContent intra-stage save: add courtesy_save callback, fire every N nodes during batch | stages | `src/fs2/core/services/stages/smart_content_stage.py`, `src/fs2/core/services/smart_content/smart_content_service.py` | During batch processing, courtesy save fires every 10 nodes (local) / 50 nodes (cloud) | AC01, AC04 |
| [ ] | T05 | Embedding intra-stage save: same pattern as T04 for embedding batch | stages | `src/fs2/core/services/stages/embedding_stage.py` | During batch processing, courtesy save fires every 50 nodes | AC05 |
| [ ] | T06 | PipelineContext: add courtesy_save callback field + wire in ScanPipeline | config | `src/fs2/core/services/pipeline_context.py`, `src/fs2/core/services/scan_pipeline.py` | PipelineContext has courtesy_save callback; ScanPipeline wires it to save helper | AC01 |
| [ ] | T07 | Tests: atomic save + inter-stage save verification | repos, services | `tests/unit/repos/test_graph_store_impl.py`, `tests/unit/services/test_scan_pipeline.py` | Atomic save verified (temp+rename); inter-stage save count verified | AC02, AC03 |

### Architecture

```
ScanPipeline.run():
  context = PipelineContext(...)
  context.prior_nodes = load_prior()
  graph_store.clear()
  
  for stage in stages:
      context = stage.process(context)
      if stage.name != "storage":
          _courtesy_save(context)          ← NEW: inter-stage save
  
  return summary

_courtesy_save(context):                   ← NEW: save helper
  graph_store.clear()                      (rebuild from context)
  for node in context.nodes:
      graph_store.add_node(node)
  for node in context.nodes:
      if node.parent_node_id:
          graph_store.add_edge(...)
  for src, tgt, data in context.cross_file_edges:
      graph_store.add_edge(...)
  graph_store.save(context.graph_path)     (atomic: .tmp + rename)

SmartContentStage.process():
  ...
  batch_result = asyncio.run(
      service.process_batch(
          needs_generation,
          courtesy_save=context.courtesy_save,  ← NEW: passed to batch
      )
  )

SmartContentService._worker():
  ... after every 10 nodes processed ...
  if courtesy_save and processed % interval == 0:
      courtesy_save()                      ← NEW: intra-stage save
```

### Acceptance Criteria

- [ ] AC01: Crash at node 50/900 → restart recovers ~40-50 nodes
- [ ] AC02: GraphStore.save() is atomic (temp+rename)
- [ ] AC03: Graph saved after Parsing, CrossFileRels, SmartContent, Embedding
- [ ] AC04: SmartContent saves every ~10 nodes (local)
- [ ] AC05: Embedding saves every ~50 nodes
- [ ] AC06: Overhead <10% of scan time
- [ ] AC07: Partial graph works with tree/search/MCP

## Progress

- Tasks: 7/7 complete
- ACs verified: 5/7 (AC06 overhead, AC07 partial graph usability — need integration test)
