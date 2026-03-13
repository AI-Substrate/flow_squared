# Cross-File Relationships Implementation Plan

**Plan Version**: 1.0.0
**Created**: 2026-03-12
**Spec**: [cross-file-rels-spec.md](cross-file-rels-spec.md)
**Status**: READY
**Mode**: Full
**Complexity**: CS-3 (medium)

## Summary

The fs2 graph currently stores only containment edges (file → class → method). This plan adds cross-file relationship edges using Serena (LSP/Pyright) as the resolution engine, running as a pool of parallel MCP server instances during scan. When complete, `get_node` will return a `relationships` field showing which other nodes reference a given node, enabling call tree walking, impact analysis, and dependency tracing. The approach was empirically validated: 20 parallel Serena instances resolve 3634 nodes in 29 seconds with 0 errors and 14.3x speedup over sequential.

## Target Domains

| Domain | Status | Relationship | Role |
|--------|--------|-------------|------|
| core/repos | existing | **modify** | GraphStore ABC gains `get_edges()` + `add_edge(**edge_data)` |
| core/services/stages | existing | **modify** | New CrossFileRelsStage |
| core/services | existing | **modify** | ScanPipeline gains new stage + PipelineContext gains `cross_file_edges` |
| core/models | existing | **consume** | CodeNode unchanged; PipelineContext extended |
| config | existing | **modify** | New CrossFileRelsConfig |
| cli | existing | **modify** | scan.py gains 2 flags |
| mcp | existing | **modify** | `get_node` gains `relationships` output; tree gains ref count |

## Domain Manifest

| File | Domain | Classification | Rationale |
|------|--------|---------------|-----------|
| `src/fs2/core/repos/graph_store.py` | core/repos | contract | ABC gains `get_edges()` method + `add_edge` accepts `**edge_data` |
| `src/fs2/core/repos/graph_store_impl.py` | core/repos | internal | NetworkXGraphStore implements `get_edges()` + edge attributes |
| `src/fs2/core/repos/graph_store_fake.py` | core/repos | internal | FakeGraphStore implements `get_edges()` + edge data tracking |
| `src/fs2/core/services/stages/cross_file_rels_stage.py` | core/services/stages | internal | **NEW** — Serena pool management, node sharding, edge collection |
| `src/fs2/core/services/pipeline_context.py` | core/services | internal | Gains `cross_file_edges` field |
| `src/fs2/core/services/stages/storage_stage.py` | core/services/stages | internal | Writes `cross_file_edges` after containment edges |
| `src/fs2/core/services/scan_pipeline.py` | core/services | internal | Adds CrossFileRelsStage to default stage order |
| `src/fs2/core/services/tree_service.py` | core/services | internal | Filter cross-file edges from `get_children` results; add ref count |
| `src/fs2/config/objects.py` | config | internal | New `CrossFileRelsConfig` class + register in `YAML_CONFIG_TYPES` |
| `src/fs2/cli/scan.py` | cli | internal | `--no-cross-refs`, `--cross-refs-instances` flags |
| `src/fs2/mcp/server.py` | mcp | internal | `_code_node_to_dict` gains `graph_store` param; `get_node` passes it |

## Key Findings

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | **Critical** | `get_children()` returns ALL successors via `self._graph.successors()`. Cross-file edges will make foreign nodes appear as "children" in tree output. | Phase 1: TreeService must filter children to same-file containment edges only. Add edge_type filtering or file-path check. |
| 02 | **High** | `add_edge()` signature is strict `(parent_id, child_id)` — no **kwargs. Cannot pass edge attributes to networkx. | Phase 1: Change to `add_edge(parent_id, child_id, **edge_data)`. Backward compatible — existing callers don't pass kwargs. |
| 03 | **High** | FakeGraphStore tracks edges as `dict[str, set[str]]` — cannot store edge metadata. | Phase 1: Extend to `dict[str, dict[str, dict]]` or add `_edge_data` dict. |
| 04 | **High** | No `get_edges()` method exists on GraphStore ABC. MCP `get_node` cannot query relationships. | Phase 1: Add `get_edges(node_id, direction, edge_type)` to ABC + impls. |
| 05 | **Medium** | RestrictedUnpickler whitelist allows only stdlib + CodeNode + networkx types. Edge attributes (plain dicts) are safe. | Document: edge attributes MUST be plain dicts/strings/ints only. No custom classes. |
| 06 | **Medium** | `FORMAT_VERSION = "1.0"` — load logs warning on mismatch but continues. Edge attributes don't change format. | Phase 1: Bump to "1.1". Old graphs load fine (edges have empty dicts). |
| 07 | **Medium** | MCP `_code_node_to_dict` doesn't receive graph_store. `get_node` tool already calls `get_graph_store()`. | Phase 3: Pass store to `_code_node_to_dict` for relationship output. |
| 08 | **Low** | Search service doesn't read edges — uses only `get_all_nodes()` + `get_parent()`. | No action needed. Search is unaffected. |

## Harness Strategy

Harness: Not applicable (user override — unit tests + benchmark scripts in `scripts/serena-explore/` are sufficient).

## Phases

### Phase Index

| Phase | Title | Primary Domain | Objective | Depends On | CS |
|-------|-------|---------------|-----------|------------|-----|
| 1 | GraphStore Edge Infrastructure | core/repos | Add typed edge storage + query API to graph layer | None | CS-2 |
| 2 | CrossFileRels Pipeline Stage | core/services | Serena pool management, node sharding, edge collection | Phase 1 | CS-3 |
| 3 | Config + CLI + MCP Surface | config, cli, mcp | Config object, scan flags, relationship output, tree ref count | Phase 1 | CS-2 |
| 4 | Integration + Documentation | all | Wire stage into pipeline, end-to-end validation, docs | Phase 2, 3 | CS-2 |

---

### Phase 1: GraphStore Edge Infrastructure

**Objective**: Enable the graph layer to store, persist, and query typed edges alongside existing containment edges.
**Domain**: core/repos
**Delivers**:
- `add_edge()` accepts `**edge_data` (backward compatible)
- New `get_edges()` method on GraphStore ABC + both impls
- TreeService filters cross-file edges from containment results
- FORMAT_VERSION bumped to 1.1
**Depends on**: None
**Key risks**: Finding 01 (tree breakage) — must verify tree ignores cross-file edges.

| # | Task | Domain | Success Criteria | Notes |
|---|------|--------|-----------------|-------|
| 1.1 | Modify `GraphStore.add_edge()` to accept `**edge_data: Any` | core/repos | Existing callers work unchanged; new callers can pass `edge_type="references"` | Per finding 02. TDD. |
| 1.2 | Add `GraphStore.get_edges(node_id, direction, edge_type)` abstract method | core/repos | Returns `list[tuple[str, dict]]` filtered by direction and edge_type | Per finding 04. TDD. |
| 1.3 | Implement `get_edges()` in NetworkXGraphStore | core/repos | Direction filtering (incoming/outgoing/both) works; edge_type filter works; empty results for no edges | TDD. |
| 1.4 | Update NetworkXGraphStore `add_edge()` to pass `**edge_data` to networkx | core/repos | `self._graph.edges[u, v]` contains edge_data dict after add | TDD. |
| 1.5 | Update FakeGraphStore — store edge data + implement `get_edges()` | core/repos | FakeGraphStore tracks edge attributes; `get_edges` returns correct results | Per finding 03. TDD. |
| 1.6 | Add save/load roundtrip test for edge attributes | core/repos | Edge attributes survive pickle save + RestrictedUnpickler load | Per finding 05. |
| 1.7 | Bump FORMAT_VERSION to "1.1" | core/repos | Old 1.0 graphs load with warning; new graphs save as 1.1 | Per finding 06. Lightweight. |
| 1.8 | Fix TreeService to filter cross-file edges from `get_children()` results | core/services | Tree output shows only same-file containment children, not cross-file refs | Per finding 01. Critical. TDD. |
| 1.9 | Fix `get_parent()` in both impls to filter cross-file edges | core/repos | `get_parent()` returns containment parent only — never a cross-file reference node | Per DYK-01. Critical. TDD. |

**Acceptance Criteria**:
- [AC5] `get_edges()` returns edges filtered by `edge_type` and `direction`
- [AC10] Graph format version is 1.1; old 1.0 graphs load without error

---

### Phase 2: CrossFileRels Pipeline Stage

**Objective**: Build the stage that spawns Serena instances, shards nodes, resolves references, and collects edges.
**Domain**: core/services/stages
**Delivers**:
- `CrossFileRelsStage` class implementing `PipelineStage`
- Serena instance pool management (start/wait/stop)
- Project detection (marker files) for multi-project repos
- Node sharding (round-robin across instances)
- Edge collection into `context.cross_file_edges`
- Graceful skip when Serena unavailable
**Depends on**: Phase 1 (needs `add_edge(**edge_data)` in StorageStage)
**Key risks**: Serena startup reliability; subprocess management; port conflicts.

| # | Task | Domain | Success Criteria | Notes |
|---|------|--------|-----------------|-------|
| 2.1 | Add `cross_file_edges` field to PipelineContext | core/services | `list[tuple[str, str, dict]]` field with `default_factory=list` | Lightweight. |
| 2.2 | Update StorageStage to write `cross_file_edges` | core/services/stages | After containment edges, writes cross-file edges with edge_data; records metrics | Lightweight. DYK-05: `add_edge()` raises GraphStoreError if either node doesn't exist. Must pre-filter edges to only those where both source_id and target_id exist in the graph — Serena returns refs to stdlib/external symbols that aren't graph nodes. |
| 2.3 | Implement Serena availability detection (`shutil.which`) | core/services/stages | Returns True when `serena-mcp-server` on PATH, False otherwise | TDD. |
| 2.4 | Implement project detection (marker file walk) | core/services/stages | Finds project roots by marker files; returns `list[ProjectRoot]` | Per workshop 004. TDD. |
| 2.5 | Implement Serena project auto-creation (`serena project create`) | core/services/stages | Creates `.serena/project.yml` if not exists; indexes project | TDD with FakeSubprocessRunner (fake over mock per doctrine). |
| 2.6 | Implement Serena instance pool (start N instances, wait for ready, stop) | core/services/stages | Pool starts on consecutive ports; all instances respond; clean shutdown | TDD with FakeSerenaPool (fake implementing pool interface). |
| 2.7 | Implement node sharding (group by project, round-robin across instances) | core/services/stages | Nodes distributed proportionally; unmatched files skipped | Per workshop 004. TDD. |
| 2.8 | Implement reference resolution (FastMCP client → `find_referencing_symbols`) | core/services/stages | For each node, queries Serena and maps response to `(source_id, target_id, edge_data)` | TDD with FakeSerenaClient (fake implementing resolution interface). DYK-03: Skip reference edges where source already contains target (containment wins over reference on same (u,v) pair — DiGraph would overwrite). |
| 2.9 | Implement CrossFileRelsStage.process() orchestration | core/services/stages | Full flow: detect → create project → start pool → shard → resolve → collect → stop | Integration test. |
| 2.10 | Implement graceful skip (no Serena, config disabled, `--no-cross-refs`) | core/services/stages | Stage logs info message, sets metrics, returns context unchanged | TDD. |

**Acceptance Criteria**:
- [AC1] Scan with Serena produces graph with `edge_type="references"` edges
- [AC4] Scan without Serena produces identical graph to today (no errors)
- [AC7] Resolution completes in under 60 seconds for ≤5000 nodes

---

### Phase 3: Config + CLI + MCP Surface

**Objective**: Wire the feature into user-facing surfaces: config file, CLI flags, MCP output, tree ref count.
**Domain**: config, cli, mcp
**Delivers**:
- `CrossFileRelsConfig` in config/objects.py
- `--no-cross-refs` and `--cross-refs-instances` in scan.py
- `relationships` field in MCP `get_node` output
- Ref count in `tree --detail max`
**Depends on**: Phase 1 (needs `get_edges()` for MCP output)
**Key risks**: None — all mechanical changes following established patterns.

| # | Task | Domain | Success Criteria | Notes |
|---|------|--------|-----------------|-------|
| 3.1 | Create `CrossFileRelsConfig` pydantic model with `__config_path__ = "cross_file_rels"` | config | Fields: `enabled`, `parallel_instances`, `serena_base_port`, `timeout_per_node`, `languages`; `__config_path__` ClassVar set; registered in `YAML_CONFIG_TYPES` | Per workshop 002. Lightweight. |
| 3.2 | Add `--no-cross-refs` flag to scan.py | cli | Flag parsed; passed through to pipeline; scan output reflects status | Per workshop 003. Lightweight. |
| 3.3 | Add `--cross-refs-instances` flag to scan.py | cli | Overrides `parallel_instances` from config; validated ≥1 | Per workshop 003. Lightweight. |
| 3.4 | Update MCP `_code_node_to_dict` — accept `graph_store` param | mcp | When graph_store provided, calls `get_edges()` and includes `relationships` dict | Per finding 07. Lightweight. |
| 3.5 | Update MCP `get_node` tool — pass store to `_code_node_to_dict` | mcp | `get_node` output includes `relationships.referenced_by` when edges exist | Per finding 07. Lightweight. |
| 3.6 | Add ref count to tree `--detail max` output | mcp + cli | Nodes with cross-file edges show `(N refs)` suffix | Per AC11. Lightweight. |
| 3.7 | Add `.serena/` to default `.gitignore` template | config | `fs2 init` creates `.gitignore` with `.serena/` entry | Lightweight. |

**Acceptance Criteria**:
- [AC2] `get-node` returns `relationships.referenced_by` list
- [AC3] `--no-cross-refs` produces zero cross-file edges
- [AC6] MCP `get_node` includes `relationships` in output
- [AC8] Config section parsed from `.fs2/config.yaml`
- [AC9] `--cross-refs-instances 5` uses 5 instances
- [AC11] `tree --detail max` shows ref count

---

### Phase 4: Integration + Documentation

**Objective**: Wire CrossFileRelsStage into ScanPipeline default stages, validate end-to-end, write documentation.
**Domain**: all
**Delivers**:
- CrossFileRelsStage in ScanPipeline default stage list
- ScanPipeline constructor accepts cross-file-rels config
- End-to-end validation (scan → get-node with relationships)
- README section + docs/how/ guide
**Depends on**: Phase 2 (stage), Phase 3 (config/CLI)
**Key risks**: Integration timing — stage must run after Parsing, before SmartContent.

| # | Task | Domain | Success Criteria | Notes |
|---|------|--------|-----------------|-------|
| 4.1 | Add CrossFileRelsStage to ScanPipeline default stage list | core/services | Stage order: Discovery → Parsing → **CrossFileRels** → SmartContent → Embedding → Storage | Per workshop 001. |
| 4.2 | Wire config through ScanPipeline constructor → PipelineContext | core/services | `CrossFileRelsConfig` available in context for stage to read | Follow existing smart_content_service pattern. |
| 4.3 | Wire CLI flags through scan.py → ScanPipeline | cli | `--no-cross-refs` and `--cross-refs-instances` reach the stage | Follow `--no-smart-content` pattern. |
| 4.4 | End-to-end integration test | all | Scan a test project with FakeSerenaPool → graph has reference edges → `get_node` shows relationships | Integration test. |
| 4.5 | Add README section on cross-file relationships | docs | Installation, config, usage, interpreting output | Per documentation strategy. |
| 4.6 | Add `docs/how/cross-file-relationships.md` guide | docs | Detailed config, performance tuning, troubleshooting | Per documentation strategy. |

**Acceptance Criteria**:
- [AC1] Full scan produces reference edges (end-to-end)
- [AC2] `get-node` shows relationships (end-to-end)
- Documentation exists and is accurate

---

## Acceptance Criteria (Full List)

- [ ] [AC1] `fs2 scan` with Serena produces `edge_type="references"` edges
- [ ] [AC2] `fs2 get-node` returns `relationships.referenced_by` list
- [ ] [AC3] `--no-cross-refs` produces zero cross-file edges
- [ ] [AC4] Scan without Serena installed: no errors, info message
- [ ] [AC5] `get_edges()` returns filtered edges by type and direction
- [ ] [AC6] MCP `get_node` includes `relationships` in output
- [ ] [AC7] Resolution < 60s for ≤5000 nodes (20 instances)
- [ ] [AC8] Config section `cross_file_rels` parsed from YAML
- [ ] [AC9] `--cross-refs-instances 5` uses 5 instances
- [ ] [AC10] Format version 1.1; old 1.0 graphs load without error
- [ ] [AC11] `tree --detail max` shows ref count per node

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Serena pool fails to start | Low | High | Timeout + graceful skip; scan continues without edges |
| Memory exhaustion (20 Pyright instances) | Medium | Medium | Configurable `parallel_instances`; document ~300MB/instance |
| `get_children()` returns cross-file nodes in tree | Very Low | High | Phase 1.8: file-path filter in TreeService |
| Serena API changes | Low | Medium | Version pin; abstract behind stage boundary |
| Port conflicts on `8330-8349` | Low | Low | Configurable `serena_base_port` |
