# Workshop: Courtesy Saves in the Scan Pipeline

> **Plan**: 036-courtesy-saves
> **Topic**: Periodic graph persistence during long-running scan stages
> **Date**: 2026-03-15

---

## Problem Statement

The scan pipeline currently saves the graph **once** — at the very end in StorageStage. A codebase with 900 files produces ~6,000 nodes. With local LLM smart content (~2s/node) that's ~30 minutes for files-only, ~3.5 hours for all nodes. If the process crashes, gets killed, or the laptop sleeps — **everything is lost**.

The existing hash-based skip only works if a **prior complete scan** exists. A user's first scan gets zero recovery.

### Current Architecture
```
Discovery → Parsing → CrossFileRels → SmartContent → Embedding → StorageStage(SAVE)
                                                                       ↑
                                                               ONLY save point
```

### Desired Architecture
```
Discovery → Parsing → SAVE → CrossFileRels → SAVE → SmartContent(save every N) → SAVE → Embedding(save every N) → SAVE
```

---

## Current State (Research Findings)

| Component | Saves? | Crash Impact |
|-----------|--------|-------------|
| **ScanPipeline.run()** | No inter-stage saves | All work lost |
| **StorageStage** | Single save at end | Only save point |
| **SmartContentStage** | In-memory only | 500 enrichments lost |
| **EmbeddingStage** | In-memory only | 500 embeddings lost |
| **CrossFileRelsStage** | In-memory only | All edges lost |
| **GraphStore.save()** | Direct write (not atomic) | Corruption risk |

**Key insight**: Graph is cleared at pipeline start (`graph_store.clear()`), prior nodes loaded into dict, then stages run in memory. If crash occurs, the cleared graph is gone and in-memory work is lost.

---

## Design: Courtesy Save Strategy

### Principle: Save Often, Resume Automatically

A "courtesy save" writes the current graph state to disk periodically during long-running stages. On resume, prior_nodes loads from the last courtesy save, and hash-based skip picks up where we left off.

### Design Decision 1: Where to Save

| Save Point | Trigger | Frequency |
|------------|---------|-----------|
| **After Parsing** | Stage completion | Always (1x) |
| **During SmartContent** | Every N nodes processed | N=10 (local), N=500 (cloud) |
| **After SmartContent** | Stage completion | Always (1x) |
| **During Embedding** | Every N nodes processed | N=50 (local), N=500 (cloud) |
| **After Embedding** | Stage completion | Always (1x) |
| **During CrossFileRels** | Every N edges resolved | N=100 |

**Why not after Discovery?** Discovery just lists files — no expensive work to protect.

### Design Decision 2: How to Save (Atomic Writes)

Current `GraphStore.save()` does direct `pickle.dump()` — if killed mid-write, graph.pickle is corrupt.

**Fix**: Write to temp file, then atomic rename:
```python
def save(self, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".pickle.tmp")
    with open(tmp_path, "wb") as f:
        pickle.dump((metadata, self._graph), f, protocol=pickle.HIGHEST_PROTOCOL)
    tmp_path.rename(path)  # Atomic on same filesystem
```

**Effort**: ~5 lines. **Impact**: Eliminates corruption risk entirely.

### Design Decision 3: How Stages Trigger Saves

Two approaches:

**Option A: Callback in PipelineContext** (recommended)
```python
# PipelineContext gains a save callback
@dataclass
class PipelineContext:
    courtesy_save: Callable[[], None] | None = None
    courtesy_save_interval: int = 10  # N items between saves
```

Stages call `context.courtesy_save()` periodically:
```python
# In SmartContentStage, after overlaying batch results:
if context.courtesy_save and processed_count % context.courtesy_save_interval == 0:
    context.courtesy_save()
```

**Option B: Inter-stage saves in ScanPipeline.run()**
```python
for stage in self._stages:
    context = stage.process(context)
    # Courtesy save after each stage
    if context.graph_store and stage.name != "storage":
        self._courtesy_save(context)
```

**Recommendation**: Both — Option B for inter-stage saves (easy, always works), Option A for intra-stage saves (SmartContent/Embedding during batch processing).

### Design Decision 4: Save Frequency by Provider

| Provider | SmartContent Interval | Embedding Interval | Rationale |
|----------|----------------------|-------------------|-----------|
| **local** (Ollama) | Every 10 nodes | Every 50 nodes | ~2s/node, save every ~20s |
| **cloud** (Azure/OpenAI) | Every 500 nodes | Every 500 nodes | Fast API, save every ~30s |

Could auto-detect from LLM config provider, or just use a `courtesy_save_interval` config field.

### Design Decision 5: What Gets Saved

The courtesy save must write the **current graph state** including:
- All nodes parsed so far (from ParsingStage)
- All smart_content generated so far (partially enriched)
- All embeddings generated so far (partially enriched)
- All cross-file edges resolved so far
- Graph metadata (scan timestamp, embedding model, etc.)

On resume, `_load_prior_nodes()` loads this partial graph. Hash-based skip in SmartContent/Embedding skips nodes already enriched. CrossFileRels reuses prior edges for unchanged files.

**Key constraint**: StorageStage currently calls `graph_store.clear()` then re-adds all nodes. For courtesy saves, we need to **update** the graph incrementally, not clear+rebuild.

Actually — looking at the code more carefully, `ScanPipeline.run()` clears the graph at line 226-227 BEFORE stages run. The courtesy save would need to re-add all current `context.nodes` and edges to the graph store before saving. This is what StorageStage already does (lines 63-98). We can extract that logic into a shared helper.

---

## Implementation Plan

### Phase 1: Atomic Saves + Inter-Stage Saves (~30 lines)

1. **Atomic save** in GraphStore.save() — temp file + rename
2. **Inter-stage save** in ScanPipeline.run() — save after Parsing, CrossFileRels, SmartContent, Embedding
3. Extract StorageStage's "add nodes + edges to graph" logic into reusable helper

### Phase 2: Intra-Stage Courtesy Saves (~50 lines)

4. **PipelineContext.courtesy_save** callback
5. **SmartContentStage** — call courtesy_save every N nodes during batch
6. **EmbeddingStage** — call courtesy_save every N nodes during batch
7. **Config** — `courtesy_save_interval` in SmartContentConfig (default 10)

### Phase 3: Auto-Detect Provider for Interval (~10 lines)

8. If LLM provider is "local", use interval=10; if cloud, use interval=500
9. Same for embeddings

---

## Estimated Impact

| Scenario | Before | After |
|----------|--------|-------|
| Crash at SmartContent node 500/900 | All 500 lost, full re-scan | ~490 saved, resume from ~node 490 |
| Crash at Embedding node 3000/6000 | All 3000 lost, full re-scan | ~2950 saved, resume from ~2950 |
| Crash during CrossFileRels | All edges lost | Edges from prior stages saved |
| Kill during pickle.dump | Corrupt graph.pickle | Clean graph (atomic write) |
| Laptop sleep during scan | Lost when process killed | Resume from last courtesy save |

---

## Complexity

**CS-2 (small)** — no architectural changes, just adding save calls at known points. Atomic save is 5 lines. Inter-stage save is ~10 lines. Intra-stage is ~30 lines across SmartContent + Embedding stages.

## Risks

| Risk | Mitigation |
|------|-----------|
| Frequent saves slow down scan | Pickle.dump of 6K-node graph takes <1s; every 10 items adds ~10% overhead for local LLM (2s/item) |
| Partial graph on disk confuses tools | Graph is always valid — just incomplete. Search/tree work on partial data |
| Concurrent access during save | Single-threaded pipeline, no concurrent readers during scan |
