# Cross-File Relationships for fs2

**Mode**: Full

📚 This specification incorporates findings from exploration.md and four authoritative workshops:
- [001-edge-storage.md](workshops/001-edge-storage.md) — Storage design decisions
- [002-serena-benchmarks.md](workshops/002-serena-benchmarks.md) — Serena benchmark data & config
- [003-cli-changes.md](workshops/003-cli-changes.md) — CLI/MCP surface changes
- [004-multi-project.md](workshops/004-multi-project.md) — Multi-language & multi-project design (empirically validated)

## Research Context

The fs2 graph currently stores **containment edges only** (file → class → method). AI agents using `get_node` can see a node's code and its children, but cannot discover **who calls it**, **what it calls**, **what imports it**, or **what it inherits from**. This makes call tree walking, impact analysis, and dependency tracing impossible without text-based guesswork.

**Key research findings**:
- FastCode has a mature cross-file system using tree-sitter extraction + custom symbol resolution (Python only). It finds ~699 refs for the fs2 codebase.
- Serena provides LSP-powered resolution via Pyright. It finds ~9926 refs for the same codebase — **14x more** — because it uses real type analysis. Zero errors.
- Serena's LSP is single-threaded (~110ms per node), but running **20 parallel instances** achieves **14.3x speedup** (29s for 3634 nodes). 20 is the sweet spot; 30 shows CPU contention.
- The existing networkx DiGraph can store typed edges (`edge_type="references"`) alongside containment edges without switching to MultiDiGraph.

## Summary

Add cross-file relationship edges to the fs2 graph so that when an agent calls `get_node`, the response includes which other nodes reference it and which nodes it references. This enables call tree walking, dependency tracing, and impact analysis — capabilities that agents currently lack entirely.

Cross-file resolution is powered by **Serena** (LSP/Pyright), running as a pool of parallel MCP server instances during scan. The feature is **enabled by default** when `serena-mcp-server` is on PATH (installed via `uv tool install serena-agent`) and degrades gracefully when unavailable.

## Goals

- **Call tree walking**: An agent can start at any function/method and discover all callers (incoming) and all callees (outgoing), then follow those references recursively
- **Impact analysis**: Before changing a function, an agent can see every file/function that depends on it
- **Dependency awareness**: Understand which files import which, and which classes inherit from which
- **Zero-config by default**: Works automatically if Serena is installed; no manual setup needed
- **Acceptable scan cost**: Cross-file resolution adds ~30s to scan time (parallelised across 20 Serena instances)
- **Graceful degradation**: If Serena is not installed, scan completes normally without cross-file edges — no errors, just an info message

## Non-Goals

- **Real-time resolution**: Not a live LSP — edges are computed at scan time and persisted in the graph
- **Multi-language in v1**: Serena handles multiple languages natively (Python, TypeScript, Go, Rust, C#, Java — empirically validated in workshop 004). Each detected project root gets its own Serena pool. Cross-file refs are within-project only — no cross-project references
- **Call expression detail**: Edges store node_id references only, not the call expression text or argument types
- **Third-party library resolution**: Only project-internal references are stored (stdlib/pip imports are resolved by Serena but we only create edges to nodes that exist in the graph)
- **Incremental edge updates**: v1 re-resolves all nodes every scan. Incremental (only changed files) is a future optimisation

## Target Domains

| Domain | Status | Relationship | Role in This Feature |
|--------|--------|-------------|---------------------|
| core/repos | existing | **modify** | GraphStore ABC gains `get_edges()` method; impl + fake updated |
| core/services/stages | existing | **modify** | New CrossFileRelsStage added to pipeline |
| core/services | existing | **modify** | ScanPipeline updated with new stage in default order |
| core/models | existing | **consume** | CodeNode used as-is (no changes); PipelineContext gains `cross_file_edges` field |
| config | existing | **modify** | New CrossFileRelsConfig added to config objects |
| cli | existing | **modify** | scan.py gains `--no-cross-refs` and `--cross-refs-instances` flags |
| mcp | existing | **modify** | `get_node` tool output gains `relationships` field |

No new domains are created. This feature threads through existing domains.

## Complexity

- **Score**: CS-3 (medium)
- **Breakdown**: S=2, I=2, D=1, N=0, F=1, T=1 (Total P=7)
- **Confidence**: 0.85
- **Assumptions**:
  - Serena MCP server works reliably with streamable-http transport (validated by benchmarks)
  - DiGraph typed edges don't collide with containment edges (validated by analysis)
  - 20 parallel Serena instances fit in typical dev machine memory (~6GB)
- **Dependencies**:
  - `serena-agent` installed via `uv tool install` (external, optional)
  - `fastmcp` client for talking to Serena instances (already in deps)
- **Risks**:
  - Serena startup/shutdown adds overhead if the project is very small
  - Memory pressure on constrained machines with 20 Pyright instances
  - Serena API may change across versions (mitigated by version pinning)
- **Phases**: See below (4 natural phases)

## Acceptance Criteria

1. **AC1**: Running `fs2 scan` on a Python project with Serena installed produces a graph containing `edge_type="references"` edges between callable/type nodes, in addition to existing containment edges
2. **AC2**: Running `fs2 get-node <callable_node_id>` returns a `relationships` field containing `referenced_by` with a list of node_ids that reference this node
3. **AC3**: Running `fs2 scan --no-cross-refs` produces a graph with zero cross-file edges (containment only, same as today)
4. **AC4**: Running `fs2 scan` when Serena is NOT installed produces a graph identical to today's (no errors, info message logged)
5. **AC5**: The `get_edges()` method on GraphStore returns edges filtered by `edge_type` and `direction`
6. **AC6**: The MCP `get_node` tool includes `relationships` in its output when cross-file edges exist for that node
7. **AC7**: Cross-file resolution completes in under 60 seconds for codebases with ≤5000 callable/type nodes (with 20 Serena instances)
8. **AC8**: The `.fs2/config.yaml` `cross_file_rels` section allows configuring `enabled`, `parallel_instances`, and `languages`
9. **AC9**: Running `fs2 scan --cross-refs-instances 5` uses 5 Serena instances instead of the default 20
10. **AC10**: Graph format version is bumped to 1.1; old graphs (1.0) load without error but have no cross-file edges
11. **AC11**: `fs2 tree --detail max` shows a reference count next to each node that has cross-file edges (e.g., `[1-50] (3 refs)`)

## Risks & Assumptions

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Serena instance pool fails to start | Low | High | Timeout + graceful skip with warning; scan continues without cross-file edges |
| Memory exhaustion with 20 Pyright instances | Medium | Medium | Configurable `parallel_instances`; document resource requirements |
| Serena API changes break integration | Low | Medium | Pin to known-good version; abstract behind adapter boundary |
| DiGraph edge collision (same u,v pair for containment AND reference) | Very Low | Low | Containment is within-file, references are cross-file; log if detected |
| Slow scan on large codebases (>10k nodes) | Medium | Medium | Configurable instances; `--no-cross-refs` escape hatch |

**Assumptions**:
- Python is the first and primary language for cross-file resolution
- Users have enough RAM for N Pyright instances (each ~300MB)
- `serena-mcp-server` binary is stable and available via `uv tool install serena-agent`
- The `find_referencing_symbols` Serena tool returns comprehensive, accurate results

## Open Questions

1. **Incremental resolution**: Should we track which nodes changed and only re-resolve those? (Deferred to future optimisation)
2. ~~**Edge direction semantics**~~: **RESOLVED** — Use single `edge_type="references"`. Serena returns generic references; attempting to classify as calls/imports/inherits adds complexity without reliable accuracy.
3. ~~**Tree ref count**~~: **RESOLVED** — Yes, show ref count in `tree --detail max` output (e.g., `[1-50] (3 refs)`).

## Workshop Opportunities

All critical workshops have been completed:

| Topic | Type | Status | Document |
|-------|------|--------|----------|
| Edge Storage | Storage Design | ✅ Done | [001-edge-storage.md](workshops/001-edge-storage.md) |
| Serena Benchmarks | Integration Pattern | ✅ Done | [002-serena-benchmarks.md](workshops/002-serena-benchmarks.md) |
| CLI Changes | CLI Flow | ✅ Done | [003-cli-changes.md](workshops/003-cli-changes.md) |
| Multi-Project | Integration Pattern | ✅ Done | [004-multi-project.md](workshops/004-multi-project.md) |
| stdio vs HTTP | Integration Pattern | ✅ Done | [005-stdio-vs-http.md](workshops/005-stdio-vs-http.md) |
| SCIP Language Boot | Integration Pattern | ✅ Done | [007-scip-language-boot.md](workshops/007-scip-language-boot.md) |
| SCIP Cross-Language Standardisation | Integration Pattern | ✅ Done | [008-scip-cross-language-standardisation.md](workshops/008-scip-cross-language-standardisation.md) |

No further workshops are needed before architecture.

## Testing Strategy

- **Approach**: Hybrid
- **Rationale**: GraphStore ABC changes (`get_edges`, `add_edge` with `**edge_data`) and CrossFileRelsStage logic (Serena pool management, node sharding, edge collection) have real complexity — TDD for these. CLI flags, config object, and MCP output changes are mechanical — lightweight tests.
- **TDD Focus Areas**:
  - GraphStore `get_edges()` — direction filtering, edge_type filtering, empty results
  - GraphStore `add_edge()` with `**edge_data` — backward compatibility, edge data preservation
  - CrossFileRelsStage — Serena availability detection, graceful skip, edge collection
  - PipelineContext `cross_file_edges` — accumulation and pass-through to StorageStage
- **Lightweight Areas**:
  - CLI flag parsing (`--no-cross-refs`, `--cross-refs-instances`)
  - CrossFileRelsConfig validation
  - MCP `get_node` relationships output
- **Mock Policy**: Allow targeted mocks — mock Serena MCP calls and subprocess spawning; use real FakeGraphStore fixtures for graph operations
- **Excluded**: End-to-end benchmark tests (covered by `scripts/serena-explore/benchmark*.py`)

## Documentation Strategy

- **Location**: Hybrid (README section + `docs/how/` guide)
- **README.md**: Add a section on cross-file relationships — what they are, how to install Serena, basic config
- **docs/how/**: Detailed guide covering configuration options, troubleshooting, performance tuning (`parallel_instances`), interpreting `relationships` output

## Clarifications

### Session 2026-03-12

| # | Question | Answer |
|---|----------|--------|
| Q1 | Workflow Mode | **Full** — Multi-phase plan, required dossiers, all gates |
| Q2 | Testing Strategy | **Hybrid** — TDD for GraphStore ABC + stage logic, lightweight for CLI/config/MCP |
| Q3 | Mock Usage | **Targeted mocks** — Mock Serena MCP calls and subprocess spawning, real fixtures for GraphStore |
| Q4 | Documentation Strategy | **Hybrid** — README section + docs/how/ guide |
| Q5 | Domain Review | **Confirmed** — 7 existing domains, all changes respect contracts, no new domains |
| Q6 | Harness | **Continue without** — Unit tests + benchmark scripts sufficient |
| Q7 | Edge Type Semantics | **Single type: `references`** — Simpler, matches Serena's generic output |
| Q8 | Tree Ref Count | **Yes** — Show ref count in `tree --detail max` output |
