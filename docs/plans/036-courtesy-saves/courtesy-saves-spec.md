# Courtesy Saves in the Scan Pipeline

**Mode**: Simple
📚 This specification incorporates findings from `workshops/001-courtesy-saves-design.md`.

## Summary

Add periodic "courtesy saves" throughout the scan pipeline so that long-running scans survive crashes, process kills, and laptop sleeps. Currently the graph is saved **once** at the very end — if anything goes wrong, all work is lost. With courtesy saves, the pipeline writes the graph to disk after each stage and periodically within long-running stages (SmartContent, Embedding). On restart, hash-based skip automatically resumes from where it left off.

**WHY**: A first-time scan with local LLM takes 30-60 minutes (files only) or hours (all nodes). Users lose all progress on crash/kill/sleep. This is the #1 pain point for local LLM adoption — you can't trust the tool with long-running work.

## Goals

- **G1**: Graph is saved after each pipeline stage completes (Parsing, CrossFileRels, SmartContent, Embedding)
- **G2**: During SmartContent and Embedding, graph is saved every N processed nodes (N configurable, default ~10 for local, ~500 for cloud)
- **G3**: Graph saves are atomic (temp file + rename) — no corruption risk if killed mid-write
- **G4**: On restart after crash, prior scan's progress is automatically recovered via hash-based skip — no user intervention needed
- **G5**: Courtesy save overhead is <10% of total scan time

## Non-Goals

- **NG1**: Real-time streaming save (WAL, journal) — periodic batch saves are sufficient
- **NG2**: Multi-process locking — scan is single-pipeline, no concurrent writers
- **NG3**: Backup/versioning of prior graph states — just keep latest
- **NG4**: UI for "resume from checkpoint" — it's automatic via hash-based skip

## Target Domains

| Domain | Status | Relationship | Role in This Feature |
|--------|--------|-------------|---------------------|
| repos | existing | **modify** | Make GraphStore.save() atomic (temp+rename) |
| services | existing | **modify** | Add inter-stage saves in ScanPipeline.run(), extract save helper |
| stages | existing | **modify** | Add courtesy_save callback calls in SmartContent + Embedding stages |
| config | existing | **modify** | Add courtesy_save_interval to PipelineContext or SmartContentConfig |

ℹ️ No domain registry exists.

## Complexity

- **Score**: CS-2 (small)
- **Breakdown**: S=1, I=0, D=0, N=0, F=1, T=1 → Total P=3
  - **S=1** (Surface Area): Multiple files but focused changes — pipeline, stages, graph store
  - **I=0** (Integration): Pure internal, no external dependencies
  - **D=0** (Data/State): No schema changes — same graph.pickle format
  - **N=0** (Novelty): Well-specified from workshop, clear implementation path
  - **F=1** (Non-Functional): Performance consideration — save overhead must be <10%
  - **T=1** (Testing): Need to test atomic save, inter-stage save, intra-stage callback
- **Confidence**: 0.90
- **Assumptions**:
  - pickle.dump of ~6K node graph takes <1s (verified: ~0.5s in practice)
  - os.rename is atomic on same filesystem (POSIX guarantee)
  - Hash-based skip in SmartContent/Embedding works correctly with partial prior graphs
- **Dependencies**: None
- **Risks**: Save overhead on large graphs; mitigated by infrequent saves
- **Phases**: Single implementation phase (3 sub-phases in workshop)

## Acceptance Criteria

1. **AC01**: Given a scan in progress, when the process is killed after SmartContent processes 50/900 nodes, then restarting `fs2 scan` recovers ~40-50 nodes via hash-based skip and resumes from where it left off
2. **AC02**: Given `fs2 scan` running, when GraphStore.save() is called, then it writes to a temp file first and atomically renames — a concurrent kill cannot produce a corrupt graph.pickle
3. **AC03**: Given the scan pipeline completes the Parsing stage, then the graph is saved to disk before CrossFileRels begins
4. **AC04**: Given SmartContent is processing 900 nodes with courtesy_save_interval=10, then the graph is saved approximately every 10 completed nodes (~18-20 saves total)
5. **AC05**: Given Embedding is processing 6000 nodes with courtesy_save_interval=50, then the graph is saved approximately every 50 completed nodes
6. **AC06**: Given courtesy saves are enabled, then total scan time increases by less than 10% compared to saves disabled
7. **AC07**: Given a partial graph from a courtesy save, then `fs2 tree`, `fs2 search`, and MCP tools work correctly on the partial data (nodes present, some without smart_content/embeddings)

## Risks & Assumptions

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Save overhead >10% | Low | Medium | Benchmark: pickle.dump ~0.5s for 6K nodes; at 10-node interval that's ~45 saves = ~22s on a ~30min scan (~1%) |
| Partial graph confuses downstream tools | Low | Low | Graph is always structurally valid — just incomplete. Tools already handle null smart_content/embeddings |
| Atomic rename fails on network filesystem | Very Low | Medium | Document: courtesy saves require local filesystem |

**Assumptions**:
- Single pipeline execution (no concurrent scans on same graph)
- os.rename is atomic on local filesystems (POSIX, NTFS, APFS)
- Hash-based skip works correctly with partially-enriched prior graphs (confirmed by workshop research)

## Open Questions

*None — workshop + clarify resolved all questions.*

## Testing Strategy

- **Approach**: Lightweight
- **Focus**: Atomic save (temp+rename works), inter-stage saves fire after each stage, courtesy save callback fires at correct intervals
- **Excluded**: Performance benchmarking (manual), end-to-end crash recovery (manual)

## Clarifications

### Session 2026-03-15

| # | Question | Answer | Spec Impact |
|---|----------|--------|-------------|
| Q1 | Workflow Mode | **Simple** | Header updated |
| Q2 | Testing Strategy | **Lightweight** — atomic save + inter-stage + callback tests | Added Testing Strategy section |
| Q3 | Domain Review | **Confirmed** — repos, services, stages, config all existing | No changes needed |
| Q4 | Courtesy save interval | **10 for local, 50 for cloud** — save every ~20s local | Updated Design Decision 4 in workshop; spec updated |
